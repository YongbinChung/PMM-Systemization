"""
WINGS 자동 다운로드 모듈
로컬 Chrome (WingsAutomation 프로필)을 이용해 WINGS Extended Search에서
Requested delivery date 조건으로 Excel 파일을 자동 다운로드합니다.

사용법:
    from wings_scraper import download_wings_excel
    path = download_wings_excel(["2026-04"], on_status=print)
    path = download_wings_excel(["2026-04", "2026-05"], on_status=print)
"""

import os
import sys
import glob
import asyncio
import tempfile
import subprocess
import threading
import concurrent.futures
from playwright.async_api import async_playwright

WINGS_URL = "https://wings.tsac.daimlertruck.com/sites/main.jsp"

# 전용 Chrome 프로필 디렉터리 (사용자의 메인 Chrome과 충돌 방지)
WINGS_PROFILE_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "Google", "Chrome", "User Data", "WingsAutomation",
)


def _release_profile_lock():
    """WingsAutomation 프로필을 점유 중인 Chrome을 종료하고 락 파일을 제거한다."""
    # PowerShell로 WingsAutomation 프로필 사용 중인 Chrome 프로세스 종료
    try:
        subprocess.run(
            ['powershell', '-Command',
             'Get-CimInstance Win32_Process -Filter "Name=\'chrome.exe\'" | '
             'Where-Object {$_.CommandLine -like \'*WingsAutomation*\'} | '
             'ForEach-Object {Stop-Process -Id $_.ProcessId -Force}'],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass

    # Singleton 락 파일 제거 (Chrome이 비정상 종료 시 남기는 파일)
    for fname in ('SingletonLock', 'SingletonCookie', 'SingletonSocket'):
        fpath = os.path.join(WINGS_PROFILE_DIR, fname)
        try:
            if os.path.exists(fpath):
                os.remove(fpath)
        except Exception:
            pass


def _find_chrome_exe() -> str | None:
    """시스템에 설치된 Google Chrome 실행 파일 경로를 찾는다."""
    candidates = [
        os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                     r"Google\Chrome\Application\chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                     r"Google\Chrome\Application\chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""),
                     r"Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def _are_consecutive(months_sorted: list) -> bool:
    """정렬된 'YYYY-MM' 리스트가 월 단위로 연속인지 확인한다."""
    for i in range(len(months_sorted) - 1):
        y1, m1 = map(int, months_sorted[i].split('-'))
        y2, m2 = map(int, months_sorted[i + 1].split('-'))
        next_m, next_y = (m1 + 1, y1) if m1 < 12 else (1, y1 + 1)
        if not (y2 == next_y and m2 == next_m):
            return False
    return True


async def _copy_filter_row(page, row_idx: int):
    """FilterCriteriaWidget row_idx의 복사(📋) 버튼을 클릭해 새 행을 추가한다."""
    copy_bbox = await page.evaluate(
        """idx => {
            const rows = dijit.registry.toArray().filter(w =>
                w.declaredClass === 'com.daimler.wings.view.grid.filter.FilterCriteriaWidget'
            );
            if (!rows[idx]) return null;
            const buttons = dijit.registry.findWidgets(rows[idx].domNode)
                .filter(w => w.declaredClass.includes('Button'));
            let btn = null;
            for (const b of buttons) {
                const html  = (b.domNode.innerHTML || '').toLowerCase();
                const cls   = (b.domNode.className || '').toLowerCase();
                const title = (b.domNode.title || b.label || b.title || '').toLowerCase();
                if (html.includes('copy') || cls.includes('copy') ||
                    html.includes('clone') || html.includes('duplicate') ||
                    title.includes('copy') || title.includes('clone') ||
                    title.includes('duplicate')) {
                    btn = b; break;
                }
            }
            if (!btn && buttons.length >= 3) btn = buttons[2];
            if (!btn) return null;
            const r = btn.domNode.getBoundingClientRect();
            return {x: r.x + r.width / 2, y: r.y + r.height / 2,
                    scrollX: window.scrollX, scrollY: window.scrollY};
        }""",
        row_idx,
    )
    if copy_bbox:
        await page.mouse.click(
            copy_bbox["x"] + copy_bbox["scrollX"],
            copy_bbox["y"] + copy_bbox["scrollY"],
        )
    else:
        await page.click("text=New criteria")
    await page.wait_for_timeout(1000)


async def _set_all_row_connectors(page, connector: str = "or"):
    """필터 행 사이의 모든 and/or 커넥터를 지정한 값으로 변경한다.

    비연속 월 검색 시 'and' → 'or' 변경에 사용한다.
    커넥터 위젯은 현재 값이 'and' 또는 'or'인 dijit 위젯으로 탐지한다.
    """
    conn_bboxes = await page.evaluate(
        """() => {
            const result = [];
            for (const w of dijit.registry.toArray()) {
                try {
                    const val = w.get ? w.get('value') : null;
                    if (val !== 'and' && val !== 'or') continue;
                    if (!w.domNode) continue;
                    const r = w.domNode.getBoundingClientRect();
                    // ▼ 버튼: 오른쪽 끝에서 10px 안쪽
                    result.push({x: r.x + r.width - 10, y: r.y + r.height / 2,
                                  scrollX: window.scrollX, scrollY: window.scrollY,
                                  id: w.id, currentVal: val});
                } catch (e) {}
            }
            return result;
        }"""
    )
    for bbox in conn_bboxes:
        await page.mouse.click(
            bbox["x"] + bbox["scrollX"],
            bbox["y"] + bbox["scrollY"],
        )
        await page.wait_for_timeout(800)
        await _click_popup_item_by_text_playwright(page, connector)
        await page.wait_for_timeout(500)


async def _wings_download_async(months: list, download_dir: str, on_status=None) -> str:

    months_sorted = sorted(months)
    start_date = months_sorted[0] + "-01"
    end_date = months_sorted[-1] + "-01"
    single = len(months_sorted) == 1
    consecutive = _are_consecutive(months_sorted)

    os.makedirs(WINGS_PROFILE_DIR, exist_ok=True)
    os.makedirs(download_dir, exist_ok=True)

    def status(msg: str):
        if on_status:
            on_status(msg)

    # 이전 세션에서 잠긴 프로필 해제
    _release_profile_lock()

    chrome_exe = _find_chrome_exe()

    async with async_playwright() as p:
        launch_kwargs = dict(
            headless=False,
            accept_downloads=True,
            downloads_path=download_dir,
            args=["--start-maximized"],
            viewport=None,
        )
        if chrome_exe:
            launch_kwargs["executable_path"] = chrome_exe

        ctx = await p.chromium.launch_persistent_context(
            WINGS_PROFILE_DIR,
            **launch_kwargs,
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # ── 1. WINGS 접속 ──────────────────────────────────────────────────────
        status("WINGS에 접속 중...")
        await page.goto(WINGS_URL, wait_until="networkidle", timeout=30000)

        # 로그인이 필요한 경우 (WingsAutomation 프로필 첫 사용 시)
        if await page.locator("input[type='password']").count() > 0:
            status("로그인이 필요합니다. 브라우저에서 직접 로그인해 주세요...")
            await page.wait_for_selector("text=Extended search", timeout=180000)
            status("로그인 완료")

        # ── 2. Extended Search 진입 ────────────────────────────────────────────
        status("Extended Search 클릭 중...")
        await page.click("text=Extended search")
        await page.wait_for_load_state("networkidle", timeout=15000)

        # ── 3. 기존 필터 조건 제거 ────────────────────────────────────────────
        try:
            remove_btn = page.locator("text=Remove all filter criteria")
            if await remove_btn.is_visible(timeout=2000):
                await remove_btn.click()
                await page.wait_for_timeout(600)
        except Exception:
            pass

        # ── 4. 필터 조건 설정 ─────────────────────────────────────────────────
        status("필터 조건 설정 중...")
        if single:
            # 단일 월: equal = YYYY-MM-01
            await _set_filter_row(page, 0, "Requested delivery date", "equal", start_date)

        elif consecutive:
            # 연속 월 (예: 04,05,06): greater equal start AND less equal end
            await _set_filter_row(page, 0, "Requested delivery date", "greater equal", start_date)
            await _copy_filter_row(page, 0)
            await _set_filter_row(page, 1, "Requested delivery date", "less equal", end_date)

        else:
            # 비연속 월 (예: 04,06): 각 월마다 equal 행 추가
            for i, month in enumerate(months_sorted):
                date_str = month + "-01"
                if i > 0:
                    await _copy_filter_row(page, i - 1)
                await _set_filter_row(page, i, "Requested delivery date", "equal", date_str)
            # 행 사이 커넥터를 and → or 로 변경 (비연속 월은 OR 조건)
            await _set_all_row_connectors(page, "or")

        # ── 5. Execute 클릭 → 결과 페이지 대기 ───────────────────────────────
        status("검색 실행 중...")
        await page.click("text=Execute")

        # 3초 후 입력 오류 팝업 확인
        await asyncio.sleep(3)
        try:
            popup = page.locator("text=The requested action could not be completed")
            if await popup.is_visible(timeout=500):
                debug_info = ""
                try:
                    with open("wings_debug.log", encoding="utf-8") as _f:
                        debug_info = _f.read()
                except Exception:
                    pass
                raise RuntimeError(
                    "WINGS 입력 오류(U0033): 필터 조건이 올바르게 설정되지 않았습니다.\n\n"
                    f"디버그 로그:\n{debug_info}"
                )
        except RuntimeError:
            raise
        except Exception:
            pass

        # 결과 페이지의 Export 버튼이 나타날 때까지 대기 (최대 60초)
        status("결과 로드 대기 중...")
        try:
            await page.wait_for_selector("text=Export", timeout=60000)
        except Exception:
            raise RuntimeError("검색 결과 페이지가 로드되지 않았습니다 (60초 초과).")

        # Export 전 4초 추가 대기 (결과 완전 로드)
        await page.wait_for_timeout(4000)

        # ── 6. Export 클릭 → 다운로드 대기 ───────────────────────────────────
        status("Export 클릭 중... 파일 다운로드를 기다리는 중입니다.")

        download_holder = []
        download_event = asyncio.Event()

        def _on_download(dl):
            download_holder.append(dl)
            download_event.set()

        # 현재 페이지 + 팝업으로 열리는 새 페이지에도 download 리스너 등록
        page.on("download", _on_download)

        def _on_new_page(new_page):
            new_page.on("download", _on_download)

        ctx.on("page", _on_new_page)

        # 파일시스템 감시: Export 클릭 전 기존 파일 스냅샷
        user_dl_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        _snap_dirs = [download_dir, user_dl_dir]
        _before = set()
        for _d in _snap_dirs:
            _before.update(glob.glob(os.path.join(_d, "*.xlsx")))
            _before.update(glob.glob(os.path.join(_d, "*.xls")))

        await page.click("text=Export")

        # 방어선 1: Playwright download 이벤트 (30초 대기)
        fpath = None
        try:
            await asyncio.wait_for(download_event.wait(), timeout=30)
            dl = download_holder[0]
            fname = dl.suggested_filename or f"wings_{start_date}_to_{end_date}.xlsx"
            fpath = os.path.join(download_dir, fname)
            await dl.save_as(fpath)
            status(f"다운로드 완료: {fname}")
        except asyncio.TimeoutError:
            # 방어선 2: 파일시스템에서 새 파일 탐지 (최대 60초)
            status("다운로드 파일 감지 중...")
            for _ in range(60):
                _after = set()
                for _d in _snap_dirs:
                    _after.update(glob.glob(os.path.join(_d, "*.xlsx")))
                    _after.update(glob.glob(os.path.join(_d, "*.xls")))
                _new = {f for f in (_after - _before) if not f.endswith(".crdownload")}
                if _new:
                    fpath = max(_new, key=os.path.getmtime)
                    fname = os.path.basename(fpath)
                    status(f"다운로드 완료: {fname}")
                    break
                await asyncio.sleep(1)
            if not fpath:
                raise RuntimeError("다운로드 시간 초과 (90초). Export 후 파일이 생성되지 않았습니다.")

        await ctx.close()
        return fpath


async def _set_filter_row(page, row_idx: int, field: str, operator: str, value: str):
    """WINGS Extended Search 필터 행 설정.

    사용자 동작 그대로 재현:
    1) 필드 입력창에 키워드 타이핑 → 2초 대기 → 첫 번째 팝업 항목 클릭
    2) 오퍼레이터 입력창 클릭 → 첫 번째 팝업 항목 클릭
    3) 나타나는 날짜 입력창에 직접 타이핑
    """
    log = []

    # ── 0. FilterCriteriaWidget에서 위젯 ID 수집 ──────────────────────────────
    info = await page.evaluate(
        """idx => {
            const rows = dijit.registry.toArray().filter(w =>
                w.declaredClass === 'com.daimler.wings.view.grid.filter.FilterCriteriaWidget'
            );
            if (!rows[idx]) return null;
            const children = dijit.registry.findWidgets(rows[idx].domNode);
            const fieldW = children.find(c => c.declaredClass.includes('DatafieldDataFilteringSelect'));
            const opW    = children.find(c =>
                c.declaredClass.includes('FilteringSelect') && !c.declaredClass.includes('Datafield')
            );
            // 오퍼레이터의 ▼ 화살표 버튼 노드
            let opBtn = null;
            if (opW) {
                // 1) 위젯 프로퍼티로 찾기
                opBtn = opW._buttonNode || opW.downArrowNode || opW._arrowNode || null;
                // 2) 위젯 domNode 안에서 CSS 클래스로 찾기
                if (!opBtn && opW.domNode) {
                    opBtn = opW.domNode.querySelector(
                        '.dijitArrowButton, .dijitDownArrowButton, [class*="ArrowButton"], [class*="arrowButton"]'
                    );
                }
            }
            return {
                fieldId:    fieldW ? fieldW.id : null,
                fieldNode:  fieldW ? (fieldW.focusNode ? fieldW.focusNode.id : null) : null,
                opId:       opW    ? opW.id    : null,
                opNode:     opW    ? (opW.focusNode ? opW.focusNode.id : null) : null,
                opArrow:    opBtn  ? opBtn.id  : null,
                opArrowClass: opBtn ? (opBtn.className || '') : null,
            };
        }""",
        row_idx,
    )
    log.append(f"info={info}")
    if not info or not info.get("fieldId"):
        log.append("ERROR: widget not found")
        _write_debug(row_idx, log)
        return

    field_id   = info["fieldId"]
    field_node = info.get("fieldNode")  # focusNode ID (input element)
    op_id      = info.get("opId")
    op_node    = info.get("opNode")
    op_arrow   = info.get("opArrow")   # ▼ 화살표 버튼 ID

    # ── 1. 필드 입력창에 "Requested" 타이핑 → 팝업 대기 → 첫 번째 항목 클릭 ──
    keyword = field.split()[0]  # e.g. "Requested"

    if field_node:
        # Playwright 자체 클릭으로 포커스 확보 후 타이핑
        try:
            await page.locator(f"#{field_node}").click()
            await page.keyboard.press("Control+a")
            await page.keyboard.press("Delete")
            await page.wait_for_timeout(200)
            await page.keyboard.type(keyword, delay=80)
            log.append(f"field typed via locator: {keyword}")
        except Exception as e:
            log.append(f"field locator error: {e}")
            # fallback: JS focus + keyboard
            await page.evaluate(
                """id => {
                    const w = dijit.byId(id);
                    if (w && w.focusNode) { w.focusNode.focus(); w.focusNode.click(); }
                }""",
                field_id,
            )
            await page.keyboard.type(keyword, delay=80)
            log.append(f"field typed via JS fallback: {keyword}")
    else:
        # focusNode ID 없음 → JS로 위젯 직접 조작
        await page.evaluate(
            """id => {
                const w = dijit.byId(id);
                if (!w) return;
                if (w.focusNode) { w.focusNode.focus(); w.focusNode.click(); }
            }""",
            field_id,
        )
        await page.keyboard.type(keyword, delay=80)
        log.append(f"field typed via JS (no focusNode id): {keyword}")

    await page.wait_for_timeout(3000)  # 팝업이 나타날 때까지 3초 대기 (사용자 지시)

    # 팝업 첫 번째 항목 Playwright 실제 클릭
    first_item_result = await _click_first_popup_item_playwright(page)
    log.append(f"field popup: {first_item_result}")
    await page.wait_for_timeout(1000)  # 필드 선택 후 오퍼레이터 드롭다운 갱신 대기

    # ── 2. 오퍼레이터: ▼ 화살표 클릭 → 팝업 → 첫 번째 항목 클릭 ─────────────
    # 사용자 지시: 텍스트 입력창은 절대 클릭 안 함. ▼ 오른쪽 끝만 클릭.
    if op_id:
        # 오퍼레이터 위젯 전체 domNode의 bounding box를 구해서
        # 오른쪽 끝(▼ 버튼 위치)을 page.mouse.click으로 직접 클릭
        op_bbox = await page.evaluate(
            """id => {
                const w = dijit.byId(id);
                if (!w || !w.domNode) return null;
                const r = w.domNode.getBoundingClientRect();
                return {x: r.x, y: r.y, w: r.width, h: r.height,
                        scrollX: window.scrollX, scrollY: window.scrollY};
            }""",
            op_id,
        )
        log.append(f"op_bbox={op_bbox}")

        if op_bbox:
            # ▼ 는 위젯 오른쪽 끝에 있음 → 오른쪽에서 10px 안쪽, 수직 중앙
            click_x = op_bbox['x'] + op_bbox['scrollX'] + op_bbox['w'] - 10
            click_y = op_bbox['y'] + op_bbox['scrollY'] + op_bbox['h'] / 2
            await page.mouse.click(click_x, click_y)
            log.append(f"op arrow clicked via mouse ({click_x:.0f}, {click_y:.0f})")
        else:
            # bbox 실패 → JS _openDropDown 시도
            await page.evaluate(
                """id => {
                    const w = dijit.byId(id);
                    if (!w) return;
                    if (typeof w._openDropDown === 'function') w._openDropDown();
                }""",
                op_id,
            )
            log.append("op opened via JS _openDropDown (bbox fallback)")

        await page.wait_for_timeout(1200)

        op_result = await _click_popup_item_by_text_playwright(page, operator)
        log.append(f"op popup: {op_result}")
        await page.wait_for_timeout(1000)  # 날짜 입력창 나타날 때까지 대기

    # ── 3. 날짜 입력창 찾기 (FilterCriteriaWidget 자식 + 전역 검색) ──────────
    date_node_id = await page.evaluate(
        """idx => {
            // 방법 1: FilterCriteriaWidget 자식에서 검색
            const rows = dijit.registry.toArray().filter(w =>
                w.declaredClass === 'com.daimler.wings.view.grid.filter.FilterCriteriaWidget'
            );
            if (rows[idx]) {
                const children = dijit.registry.findWidgets(rows[idx].domNode);
                const dateW = children.find(c =>
                    (c.declaredClass.includes('TextBox') || c.declaredClass.includes('ValidationTextBox')) &&
                    !c.declaredClass.includes('FilteringSelect')
                );
                if (dateW && dateW.focusNode) return {id: dateW.id, nodeId: dateW.focusNode.id, src: 'widget_child'};
            }

            // 방법 2: dijit 레지스트리 전체에서 보이는 TextBox 검색
            const allWidgets = dijit.registry.toArray();
            const textBoxes = allWidgets.filter(w =>
                (w.declaredClass.includes('TextBox') || w.declaredClass.includes('ValidationTextBox')) &&
                !w.declaredClass.includes('FilteringSelect') &&
                w.domNode && w.domNode.offsetParent !== null
            );
            if (textBoxes.length > 0) {
                const w = textBoxes[0];
                return {id: w.id, nodeId: w.focusNode ? w.focusNode.id : null, src: 'global_registry', cls: w.declaredClass};
            }

            // 방법 3: DOM에서 보이는 text input 검색 (필터 영역 내)
            const filterArea = document.querySelector('.wings-filter, .filter-criteria, [class*="FilterCriteria"]');
            const target = filterArea || document.body;
            const inputs = Array.from(target.querySelectorAll('input[type="text"], input:not([type])'))
                .filter(el => el.offsetParent !== null && !el.readOnly && !el.disabled);
            // 마지막 input이 보통 새로 생긴 날짜 입력창
            if (inputs.length > 0) {
                const el = inputs[inputs.length - 1];
                return {id: null, nodeId: el.id || null, src: 'dom_input', cls: el.className};
            }

            return null;
        }""",
        row_idx,
    )
    log.append(f"date_node={date_node_id}")

    if date_node_id:
        widget_id = date_node_id.get("id")
        node_id   = date_node_id.get("nodeId")
        src       = date_node_id.get("src", "")

        if widget_id:
            # Dojo 위젯 API로 값 설정
            await page.evaluate(
                """([id, val]) => {
                    const w = dijit.byId(id);
                    if (!w) return;
                    w.set('value', val);
                    if (w.validate) w.validate(false);
                    // change 이벤트 발생시켜 WINGS가 값 인식하도록
                    if (w.focusNode) {
                        w.focusNode.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                }""",
                [widget_id, value],
            )
            log.append(f"date SET via widget ({src}): {value}")
        elif node_id:
            # DOM input에 직접 타이핑
            try:
                await page.locator(f"#{node_id}").click()
                await page.keyboard.press("Control+a")
                await page.keyboard.type(value, delay=80)
                log.append(f"date TYPED via locator ({src}): {value}")
            except Exception as e:
                log.append(f"date locator error: {e}")
        else:
            log.append("date: no usable id found")
    else:
        # 최후 수단: Tab으로 날짜 필드로 이동 후 타이핑
        await page.keyboard.press("Tab")
        await page.wait_for_timeout(300)
        await page.keyboard.type(value, delay=80)
        log.append(f"date TYPED via Tab fallback: {value}")

    _write_debug(row_idx, log)
    await page.wait_for_timeout(400)


async def _click_first_popup_item_playwright(page) -> str:
    """보이는 Dojo 팝업에서 첫 번째 항목을 Playwright 실제 클릭으로 선택한다.

    JS dispatchEvent 대신 Playwright locator().click()을 사용하여
    실제 마우스 이벤트를 발생시킨다.
    """
    # 시도 1: [item] 속성을 가진 요소 (DataGrid 스타일 팝업)
    for sel in ('[item]', '.dijitComboBoxItem', '.dijitMenuItem'):
        try:
            loc = page.locator(sel).first()
            if await loc.count() > 0:
                txt = (await loc.inner_text()).strip()[:50]
                await loc.click(timeout=3000)
                return f"playwright:{sel} '{txt}'"
        except Exception as e:
            # 이 셀렉터는 실패 → 다음 시도
            continue

    # 시도 2: ArrowDown + Enter 키보드 방식
    await page.keyboard.press("ArrowDown")
    await page.wait_for_timeout(300)
    await page.keyboard.press("Enter")
    return "keyboard:ArrowDown+Enter"


async def _click_popup_item_by_text_playwright(page, target_text: str) -> str:
    """팝업에서 target_text와 일치하는 항목을 선택한다.

    방법 1) JS getBoundingClientRect → page.mouse.click (단일 JS 호출, 빠름)
    방법 2) Playwright locator 텍스트 필터 클릭 (fallback)
    방법 3) 첫 번째 항목 fallback
    """
    target_lower = target_text.lower().strip()

    # ── 방법 1: JS 단일 호출로 위치 탐색 → page.mouse.click ─────────────────
    # 루프 없이 JS 한 번으로 처리 → 빠름
    bbox = await page.evaluate(
        """text => {
            const lower = text.toLowerCase().trim();
            const popupSels = [
                '.dijitComboBoxPopup', '.dijitPopup', '.dijitSelectMenu',
                '[role="listbox"]', '[role="list"]'
            ];
            const popups = popupSels.flatMap(s => Array.from(document.querySelectorAll(s)))
                .filter(el => {
                    const cs = window.getComputedStyle(el);
                    return cs.display !== 'none' && cs.visibility !== 'hidden'
                        && el.offsetParent !== null;
                });
            const containers = popups.length > 0 ? popups : [document.body];
            const itemSels = [
                '[item]', '[role="option"]', '.dijitComboBoxItem',
                '.dijitMenuItem', '.dijitSelectItem'
            ];
            for (const exact of [true, false]) {
                for (const container of containers) {
                    for (const isel of itemSels) {
                        for (const el of container.querySelectorAll(isel)) {
                            if (el.offsetParent === null) continue;
                            const t = el.textContent.trim().toLowerCase();
                            if (exact ? t === lower : t.includes(lower)) {
                                const r = el.getBoundingClientRect();
                                return {x: r.x + r.width/2, y: r.y + r.height/2,
                                        partial: !exact, tag: el.tagName};
                            }
                        }
                    }
                    for (const el of container.querySelectorAll('div, li, span')) {
                        if (el.offsetParent === null || el.children.length > 0) continue;
                        const t = el.textContent.trim().toLowerCase();
                        if (exact ? t === lower : t.includes(lower)) {
                            const r = el.getBoundingClientRect();
                            return {x: r.x + r.width/2, y: r.y + r.height/2,
                                    partial: !exact, tag: el.tagName, leaf: true};
                        }
                    }
                }
            }
            return null;
        }""",
        target_lower,
    )

    if bbox:
        await page.mouse.click(bbox["x"], bbox["y"])
        match_type = "partial" if bbox.get("partial") else "exact"
        return f"js+mouse:{match_type}:{target_text}({bbox.get('tag','')})"

    # ── 방법 2: Playwright 텍스트 필터 locator ──────────────────────────────
    for sel in ('[item]', '[role="option"]', '.dijitComboBoxItem',
                '.dijitMenuItem', '.dijitSelectItem'):
        try:
            loc = page.locator(sel).filter(has_text=target_text)
            if await loc.count() > 0:
                await loc.first().click(timeout=3000)
                return f"pw_filter:{sel} '{target_text}'"
        except Exception:
            continue

    # ── 방법 3: 첫 번째 항목 fallback ───────────────────────────────────────
    result = await _click_first_popup_item_playwright(page)
    return f"fallback→{result}"


async def _click_popup_item(page, text: str) -> bool:
    """열려 있는 Dojo 드롭다운 팝업에서 텍스트가 정확히 일치하는 항목을 클릭한다.
    JavaScript DOM 직접 조작 방식으로 정확한 매칭을 보장한다.
    """
    result = await page.evaluate(
        """text => {
            const lower = text.toLowerCase();
            // 모든 Dojo 팝업 순회
            const popups = document.querySelectorAll(
                '.dijitComboBoxPopup, .dijitPopup, .dijitSelectMenu'
            );
            for (const popup of popups) {
                // 숨겨진 팝업 제외
                const style = window.getComputedStyle(popup);
                if (style.display === 'none' || style.visibility === 'hidden') continue;

                // 후보 항목 탐색: 텍스트 노드를 직접 가진 요소 우선
                const candidates = popup.querySelectorAll(
                    '.dijitComboBoxItem, .dijitMenuItem, [item]'
                );
                for (const el of candidates) {
                    if (el.textContent.trim().toLowerCase() === lower) {
                        el.click();
                        return 'clicked: ' + text;
                    }
                }
                // fallback: leaf 텍스트 노드를 가진 아무 요소
                const leaves = popup.querySelectorAll('div, span, li, td');
                for (const el of leaves) {
                    if (el.children.length === 0 &&
                        el.textContent.trim().toLowerCase() === lower) {
                        el.click();
                        return 'clicked (leaf): ' + text;
                    }
                }
            }
            // 디버그: 보이는 팝업 목록
            const visible = Array.from(document.querySelectorAll(
                '.dijitComboBoxPopup, .dijitPopup'
            )).filter(p => window.getComputedStyle(p).display !== 'none')
              .map(p => p.className + ':' + p.children.length);
            return 'not found; popups=' + visible.join('|');
        }""",
        text,
    )
    # 디버그 로그에 결과 기록
    try:
        with open("wings_debug.log", "a", encoding="utf-8") as _f:
            _f.write(f"  _click_popup_item('{text}'): {result}\n")
    except Exception:
        pass
    return result.startswith("clicked")


def _write_debug(row_idx: int, log: list):
    try:
        mode = "a" if row_idx > 0 else "w"
        with open("wings_debug.log", mode, encoding="utf-8") as _f:
            _f.write(f"[filter_row={row_idx}] {log}\n")
    except Exception:
        pass


def download_wings_excel(months: list, download_dir: str = None, on_status=None) -> str:
    """
    WINGS에서 Excel 파일을 동기적으로 다운로드한다.

    Parameters
    ----------
    months : list of str
        'YYYY-MM' 형식의 생산월 리스트. 예: ['2026-04'] 또는 ['2026-04', '2026-05']
    download_dir : str, optional
        저장 디렉터리. None이면 임시 폴더 자동 생성.
    on_status : callable, optional
        진행 상황 콜백. on_status(str) 형태로 호출된다.

    Returns
    -------
    str
        다운로드된 파일의 절대 경로.
    """
    if not download_dir:
        download_dir = tempfile.mkdtemp(prefix="wings_dl_")

    # Streamlit의 asyncio 루프와 충돌을 막기 위해 별도 스레드에서 실행.
    # Windows에서 subprocess 지원을 위해 ProactorEventLoop을 명시 생성.
    # Streamlit UI 업데이트(on_status)를 위해 세션 컨텍스트를 스레드에 전달.
    _st_ctx = None
    if on_status is not None:
        try:
            from streamlit.runtime.scriptrunner import get_script_run_ctx
            _st_ctx = get_script_run_ctx()
        except Exception:
            pass

    def _run():
        if _st_ctx is not None:
            try:
                from streamlit.runtime.scriptrunner import add_script_run_ctx
                add_script_run_ctx(threading.current_thread(), _st_ctx)
            except Exception:
                pass
        loop = asyncio.ProactorEventLoop()
        try:
            return loop.run_until_complete(
                _wings_download_async(months, download_dir, on_status)
            )
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        return future.result(timeout=300)  # 5분 타임아웃
