# -*- coding: utf-8 -*-
"""
화학물질 관리시스템 - Chemical Substance Management System
Star Truck Korea — All 47K CAS + 16K HS fully matched
"""

import streamlit as st
import pandas as pd
import re
import io
from pathlib import Path
from rapidfuzz import fuzz, process

st.set_page_config(page_title="화학물질 관리시스템", page_icon="⚗️", layout="wide", initial_sidebar_state="collapsed")

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0&display=swap');
* { font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif !important; }
.material-symbols-rounded { font-family: 'Material Symbols Rounded' !important; font-size: 20px !important; }
.block-container { padding-top: 0rem !important; }
header[data-testid="stHeader"] { background: transparent !important; height: 2rem !important; }
.stApp { background-color: #f4f6f9; }
button[data-testid="stSidebarCollapseButton"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #001845 0%, #002060 40%, #003080 100%);
    min-width: 230px !important; max-width: 230px !important;
}
section[data-testid="stSidebar"] * { color: #fff !important; }
section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.15) !important; }
.top-header {
    background: linear-gradient(135deg, #001845 0%, #002060 60%, #003894 100%);
    padding: 1rem 2rem; border-radius: 0 0 12px 12px;
    margin: -1rem -1rem 1.2rem -1rem;
    display: flex; align-items: center; gap: 1rem;
    box-shadow: 0 2px 12px rgba(0,32,96,0.25);
}
.top-header h1 { color: #fff; font-size: 1.4rem; font-weight: 700; margin: 0; }
.top-header .sub { color: #8cb4ff; font-size: 0.8rem; margin: 0; }
.stats-row { display: flex; gap: 1rem; margin-bottom: 1rem; }
.stat-box { flex:1; background:#fff; border-radius:10px; padding:0.8rem 1rem; text-align:center; border:1px solid #dde3ea; }
.stat-box .num { font-size:1.5rem; font-weight:800; color:#002060; margin:0; }
.stat-box .lbl { font-size:0.75rem; color:#5a6a7a; margin:0; }
.page-title { color:#002060; font-size:1.15rem; font-weight:700; padding-bottom:0.5rem; border-bottom:2px solid #002060; margin-bottom:1rem; }
.detail-section-title { color:#002060; font-size:0.9rem; font-weight:700; padding:0.4rem 0; border-bottom:1.5px solid #002060; margin-bottom:0.6rem; }
.detail-row { display:flex; border-bottom:1px solid #f0f2f5; padding:0.35rem 0; font-size:0.85rem; }
.detail-label { width:160px; min-width:160px; color:#002060; font-weight:600; }
.detail-value { color:#333; flex:1; }
.law-badge { display:inline-block; background:#002060; color:#fff; padding:0.2rem 0.6rem; border-radius:5px; font-size:0.78rem; font-weight:600; margin:0.1rem; }
.reg-tag { display:inline-block; padding:0.15rem 0.5rem; border-radius:4px; font-size:0.75rem; font-weight:600; margin:0.1rem; }
.reg-tag-red { background:#fde8e8; color:#c0392b; border:1px solid #e74c3c; }
.reg-tag-orange { background:#fef3e2; color:#d35400; border:1px solid #f0ad4e; }
.reg-tag-yellow { background:#fef9e7; color:#b7950b; border:1px solid #f1c40f; }
.reg-tag-green { background:#eafaf1; color:#1e8449; border:1px solid #27ae60; }
.reg-tag-blue { background:#eaf2f8; color:#1a5276; border:1px solid #3498db; }
.reg-tag-purple { background:#f4ecf7; color:#6c3483; border:1px solid #9b59b6; }
.import-req-box { background:#f8f9fb; border:1px solid #dde3ea; border-radius:8px; padding:0.8rem; font-size:0.82rem; line-height:1.7; white-space:pre-wrap; max-height:250px; overflow-y:auto; }
[data-testid="stDataFrame"] div[role="columnheader"],
[data-testid="stDataFrame"] div[role="columnheader"] *,
[data-testid="stDataFrame"] th { background:#002060 !important; color:#fff !important; font-weight:700 !important; font-size:0.8rem !important; }
[data-testid="stTextInput"] > div > div > input { font-size:0.95rem !important; padding:0.6rem 1rem !important; border-radius:8px !important; border:2px solid #002060 !important; }
[data-testid="stTextInput"] > div > div > input:focus { border-color:#0066cc !important; }
.stButton > button { background:#002060 !important; color:#fff !important; border:none !important; border-radius:6px !important; font-weight:600 !important; }
.stDownloadButton > button { background:#1a8754 !important; color:#fff !important; border:none !important; border-radius:6px !important; font-weight:600 !important; }
.stTabs [data-baseweb="tab"] { background:#e8ecf1; border-radius:8px 8px 0 0; padding:0.5rem 1.5rem; font-weight:600; color:#002060; }
.stTabs [aria-selected="true"] { background:#002060 !important; color:#fff !important; }
/* Hide arrow_right material icon in expanders */
[data-testid="stExpander"] summary span.material-symbols-rounded,
[data-testid="stExpander"] summary span[data-testid="stExpanderToggleIcon"],
[data-testid="stExpander"] details summary svg,
[data-testid="stExpander"] details summary svg + span,
[data-testid="stExpander"] details summary > div:first-child,
.streamlit-expanderHeader .material-symbols-rounded,
details[data-testid="stExpander"] summary > span:first-child {
    display: none !important;
    font-size: 0 !important;
    width: 0 !important;
    overflow: hidden !important;
}
/* Force hide sidebar collapse button */
[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"] { display: none !important; visibility: hidden !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent
CAS_FILE = "cas_data.xlsx"
HS_FILE = "(수정) [별표2] 수입요령.xlsx"
KREACH_FILE = "K-REACH list in DTK.xlsx"


@st.cache_data(show_spinner="CAS 데이터 (47,463건) 로딩 중...")
def load_cas():
    df = pd.read_excel(DATA_DIR / CAS_FILE, dtype=str).fillna("")
    df.columns = [
        "NO", "CAS번호", "영문명", "국문명", "기존",
        "급성/만성/생태", "사고대비", "제한/금지/허가",
        "중점", "잔류", "유해특성분류",
        "등록대상기존화학물질", "기존물질여부",
    ]
    for c in df.columns:
        df[c] = df[c].str.strip()
    return df


@st.cache_data(show_spinner="수입요령 (16,328건) 로딩 중...")
def load_hs():
    df = pd.read_excel(DATA_DIR / HS_FILE, dtype=str).fillna("")
    df.columns = ["구분", "류", "호", "소호1", "소호2", "세번", "품명", "수입요령", "관련법령"]
    for c in df.columns:
        df[c] = df[c].str.strip()
    return df


@st.cache_data(show_spinner="K-REACH 데이터 로딩 중...")
def load_kreach():
    fp = DATA_DIR / KREACH_FILE
    comp = pd.read_excel(fp, sheet_name="Component", dtype=str).fillna("")
    comp.columns = [
        "No", "Part number", "Description", "CAS No", "Check DTK CAS",
        "min", "max", "%", "Weight (kg)", "HS Code", "Demand", "_blank",
        "Inside weight", "New material", "PM", "Subjected PM",
        "Toxic", "Restriction", "Prohibition", "Accident",
        "관리대상", "중점관리대상", "기존 살생물질", "col21", "암 돌연변이성",
        "Exemption", "Delivery prohibition", "LoC", "SDS",
        "Application date / No.", "check", "Confirm", "Report",
        "Registration", "Declaration", "Safety&Label", "Pre-registration",
        "remarks", "O or X", "Remark", "Contact point",
    ]
    comp["Part number"] = comp["Part number"].replace("", pd.NA).ffill().fillna("")
    comp["Description"] = comp["Description"].replace("", pd.NA).ffill().fillna("")
    hs = pd.read_excel(fp, sheet_name="HS", dtype=str).fillna("")
    hs.columns = ["HS Code", "관련법령", "관련항목"]
    return comp, hs


@st.cache_data(show_spinner="전체 데이터 매칭 중 (47K CAS × 16K HS)...")
def build_master():
    cas_df = load_cas()
    hs_df = load_hs()
    kreach_comp, kreach_hs = load_kreach()

    # ── 1. Extract CAS numbers from HS 수입요령 text ──
    bracket_re = re.compile(r"\[([^\]]+)\]")
    cas_re = re.compile(r"\b(\d{2,7}-\d{2}-\d)\b")

    # HS세번 -> list of (관련법령, 품명, 수입요령)
    hs_by_code = {}
    for _, r in hs_df.iterrows():
        code = r["세번"]
        if code:
            if code not in hs_by_code:
                hs_by_code[code] = []
            hs_by_code[code].append(r)

    # Extract CAS from all HS rows
    hs_cas_map = {}  # CAS -> list of hs rows
    hs_eng_map = {}  # eng_name_lower -> list of hs rows
    for _, r in hs_df.iterrows():
        text = r["수입요령"]
        if not text:
            continue
        for btext in bracket_re.findall(text):
            cas_matches = cas_re.findall(btext)
            if cas_matches:
                parts = re.split(r";\s*", btext)
                eng = ""
                for p in parts:
                    p = p.strip()
                    if not cas_re.match(p) and not eng:
                        eng = p
                for cn in cas_matches:
                    if cn not in hs_cas_map:
                        hs_cas_map[cn] = []
                    hs_cas_map[cn].append(r)
                if eng:
                    el = eng.lower()
                    if el not in hs_eng_map:
                        hs_eng_map[el] = []
                    hs_eng_map[el].append(r)

    hs_eng_keys = list(hs_eng_map.keys())

    # K-REACH HS law lookup
    kr_law = {}
    kr_item = {}
    for _, r in kreach_hs.iterrows():
        c = r["HS Code"].strip()
        if c:
            kr_law[c] = r["관련법령"]
            kr_item[c] = r["관련항목"]

    # K-REACH Component CAS lookup
    kr_cas = {}
    for _, r in kreach_comp.iterrows():
        c = r["CAS No"].strip()
        if c:
            kr_cas[c] = r

    # ── 2. Build master: one row per CAS substance ──
    records = []
    for _, cas_row in cas_df.iterrows():
        cas = cas_row["CAS번호"]
        eng = cas_row["영문명"]
        kor = cas_row["국문명"]

        # Find HS matches
        hs_matches = []

        # a) Direct CAS match in HS text
        if cas and cas in hs_cas_map:
            hs_matches = hs_cas_map[cas]

        # b) English name match
        if not hs_matches and eng:
            eng_lower = eng.lower()
            if eng_lower in hs_eng_map:
                hs_matches = hs_eng_map[eng_lower]
            else:
                # Fuzzy
                m = process.extractOne(eng_lower, hs_eng_keys, scorer=fuzz.token_sort_ratio, score_cutoff=88)
                if m:
                    hs_matches = hs_eng_map[m[0]]

        # Get K-REACH info if available
        kr = kr_cas.get(cas, None)

        if hs_matches:
            # Use first match for primary info, combine laws
            hs_row = hs_matches[0]
            all_laws = set()
            for hr in hs_matches:
                law = hr["관련법령"]
                if law:
                    for l in re.split(r"[/,\n]", law):
                        l = l.strip()
                        if l:
                            all_laws.add(l)
            hs_code = hs_row["세번"]
            hs4 = hs_code[:4] if len(hs_code) >= 4 else hs_code
            # Also add K-REACH laws
            kr_l = kr_law.get(hs4, "")
            if kr_l:
                for l in re.split(r"[/,]", kr_l):
                    l = l.strip()
                    if l:
                        all_laws.add(l)

            records.append({
                "CAS No": cas,
                "영문명": eng,
                "국문명": kor,
                "HS Code": hs_code,
                "품명": hs_row["품명"],
                "관련항목": kr_item.get(hs4, ""),
                "관련법령": " / ".join(sorted(all_laws)),
                "수입요령": hs_row["수입요령"],
                "급성/만성/생태": cas_row["급성/만성/생태"],
                "사고대비": cas_row["사고대비"],
                "제한/금지/허가": cas_row["제한/금지/허가"],
                "중점": cas_row["중점"],
                "잔류": cas_row["잔류"],
                "유해특성분류": cas_row["유해특성분류"],
                "기존물질여부": cas_row["기존물질여부"],
                "기존코드": cas_row["기존"],
                # K-REACH fields
                "Part number": kr["Part number"] if kr is not None else "",
                "Description": kr["Description"] if kr is not None else "",
                "Toxic": kr["Toxic"] if kr is not None else "",
                "Restriction": kr["Restriction"] if kr is not None else "",
                "Prohibition": kr["Prohibition"] if kr is not None else "",
                "Accident": kr["Accident"] if kr is not None else "",
                "관리대상": kr["관리대상"] if kr is not None else "",
                "중점관리대상": kr["중점관리대상"] if kr is not None else "",
                "Exemption": kr["Exemption"] if kr is not None else "",
                "PM": kr["PM"] if kr is not None else "",
                "SDS": kr["SDS"] if kr is not None else "",
                "Registration": kr["Registration"] if kr is not None else "",
            })
        else:
            # No HS match
            records.append({
                "CAS No": cas,
                "영문명": eng,
                "국문명": kor,
                "HS Code": "",
                "품명": "",
                "관련항목": "",
                "관련법령": "",
                "수입요령": "",
                "급성/만성/생태": cas_row["급성/만성/생태"],
                "사고대비": cas_row["사고대비"],
                "제한/금지/허가": cas_row["제한/금지/허가"],
                "중점": cas_row["중점"],
                "잔류": cas_row["잔류"],
                "유해특성분류": cas_row["유해특성분류"],
                "기존물질여부": cas_row["기존물질여부"],
                "기존코드": cas_row["기존"],
                "Part number": kr["Part number"] if kr is not None else "",
                "Description": kr["Description"] if kr is not None else "",
                "Toxic": kr["Toxic"] if kr is not None else "",
                "Restriction": kr["Restriction"] if kr is not None else "",
                "Prohibition": kr["Prohibition"] if kr is not None else "",
                "Accident": kr["Accident"] if kr is not None else "",
                "관리대상": kr["관리대상"] if kr is not None else "",
                "중점관리대상": kr["중점관리대상"] if kr is not None else "",
                "Exemption": kr["Exemption"] if kr is not None else "",
                "PM": kr["PM"] if kr is not None else "",
                "SDS": kr["SDS"] if kr is not None else "",
                "Registration": kr["Registration"] if kr is not None else "",
            })

    # ── 3. Add HS-only entries (ALL unmatched HS rows, not deduplicated) ──
    matched_hs_codes = set(r["HS Code"] for r in records if r["HS Code"])
    for _, r in hs_df.iterrows():
        code = r["세번"]
        if code and code not in matched_hs_codes:
            law = r["관련법령"]
            all_laws = set()
            if law:
                for l in re.split(r"[/,\n]", law):
                    l = l.strip()
                    if l:
                        all_laws.add(l)
            records.append({
                "CAS No": "", "영문명": "", "국문명": "",
                "HS Code": code, "품명": r["품명"],
                "관련항목": "",
                "관련법령": " / ".join(sorted(all_laws)),
                "수입요령": r["수입요령"],
                "급성/만성/생태": "", "사고대비": "", "제한/금지/허가": "",
                "중점": "", "잔류": "", "유해특성분류": "", "기존물질여부": "", "기존코드": "",
                "Part number": "", "Description": "",
                "Toxic": "", "Restriction": "", "Prohibition": "", "Accident": "",
                "관리대상": "", "중점관리대상": "", "Exemption": "",
                "PM": "", "SDS": "", "Registration": "",
            })

    master = pd.DataFrame(records).fillna("")
    # Add HS 4-digit column for search
    master["HS 4자리"] = master["HS Code"].apply(lambda x: x[:4] if len(str(x)) >= 4 else str(x))
    return master


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def search_df(df, query, columns):
    if not query or not query.strip():
        return df
    q = query.strip().lower()
    combined = df[columns].apply(lambda row: " ".join(str(v).lower() for v in row), axis=1)
    mask = pd.Series(True, index=df.index)
    for t in q.split():
        mask &= combined.str.contains(re.escape(t), case=False, na=False)
    return df[mask]


def to_excel(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Data")
    return buf.getvalue()


DL_COLS = [
    "CAS No", "영문명", "국문명", "기존코드", "HS Code", "품명", "관련항목", "관련법령",
    "급성/만성/생태", "사고대비", "제한/금지/허가", "중점", "잔류", "유해특성분류", "기존물질여부",
    "Part number", "Description", "Toxic", "Restriction", "Prohibition", "Accident",
    "관리대상", "중점관리대상", "Exemption", "PM", "SDS", "Registration",
]

TABLE_COLS = ["CAS No", "영문명", "국문명", "HS 4자리", "HS Code", "품명", "관련법령"]


def _v(row, key):
    """Get value from row, return '-' if empty."""
    val = str(row.get(key, "")).strip()
    return val if val else "-"


def render_detail(row):
    cas = str(row.get("CAS No", "")).strip()
    eng = str(row.get("영문명", "")).strip()
    kor = str(row.get("국문명", "")).strip()
    hs = str(row.get("HS Code", "")).strip()
    product = str(row.get("품명", "")).strip()
    law = str(row.get("관련법령", "")).strip()
    req = str(row.get("수입요령", "")).strip()

    # Build clean title — avoid [] which Streamlit renders as material icons
    title_parts = []
    if cas:
        title_parts.append(cas)
    if eng:
        title_parts.append(f"- {eng}")
    if kor:
        title_parts.append(f"({kor})")
    if not title_parts:
        title_parts.append(product or hs or "항목")
    title = " ".join(title_parts)

    with st.expander(title, expanded=False):
        # -- 기본정보 --
        st.markdown('<div class="detail-section-title">기본정보</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""
            <div class="detail-row"><div class="detail-label">CAS No.</div><div class="detail-value">{cas or '-'}</div></div>
            <div class="detail-row"><div class="detail-label">영문명</div><div class="detail-value">{eng or '-'}</div></div>
            <div class="detail-row"><div class="detail-label">국문명</div><div class="detail-value">{kor or '-'}</div></div>
            <div class="detail-row"><div class="detail-label">기존코드</div><div class="detail-value">{_v(row,'기존코드')}</div></div>
            <div class="detail-row"><div class="detail-label">기존물질여부</div><div class="detail-value">{_v(row,'기존물질여부')}</div></div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="detail-row"><div class="detail-label">HS Code</div><div class="detail-value">{hs or '-'}</div></div>
            <div class="detail-row"><div class="detail-label">HS 4자리</div><div class="detail-value">{hs[:4] if len(hs)>=4 else hs or '-'}</div></div>
            <div class="detail-row"><div class="detail-label">품명</div><div class="detail-value">{product or '-'}</div></div>
            <div class="detail-row"><div class="detail-label">관련항목</div><div class="detail-value">{_v(row,'관련항목')}</div></div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="detail-row"><div class="detail-label">Part Number</div><div class="detail-value">{_v(row,'Part number')}</div></div>
            <div class="detail-row"><div class="detail-label">Description</div><div class="detail-value">{_v(row,'Description')}</div></div>
            <div class="detail-row"><div class="detail-label">PM</div><div class="detail-value">{_v(row,'PM')}</div></div>
            <div class="detail-row"><div class="detail-label">SDS</div><div class="detail-value">{_v(row,'SDS')}</div></div>
            """, unsafe_allow_html=True)

        # -- 관련법령 --
        if law:
            st.markdown('<div class="detail-section-title">관련법령</div>', unsafe_allow_html=True)
            badges = " ".join(f'<span class="law-badge">{l.strip()}</span>' for l in re.split(r"[/]", law) if l.strip())
            st.markdown(badges, unsafe_allow_html=True)

        # -- 규제물질 정보 --
        reg_items = [
            ("급성/만성/생태", "reg-tag-red"), ("사고대비", "reg-tag-orange"),
            ("제한/금지/허가", "reg-tag-red"), ("중점", "reg-tag-purple"),
            ("잔류", "reg-tag-yellow"), ("Toxic", "reg-tag-red"),
            ("Restriction", "reg-tag-red"), ("Prohibition", "reg-tag-red"),
            ("Accident", "reg-tag-orange"), ("관리대상", "reg-tag-purple"),
            ("중점관리대상", "reg-tag-purple"), ("Exemption", "reg-tag-green"),
        ]
        tags = [f'<span class="reg-tag {cls}">{f}: {str(row.get(f,"")).strip()}</span>'
                for f, cls in reg_items if str(row.get(f, "")).strip()]
        if tags:
            st.markdown('<div class="detail-section-title">규제물질 정보</div>', unsafe_allow_html=True)
            st.markdown(" ".join(tags), unsafe_allow_html=True)

        # -- 유해특성분류 --
        hazard = str(row.get("유해특성분류", "")).strip()
        if hazard:
            st.markdown('<div class="detail-section-title">유해특성분류 및 혼합물 함량기준</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="import-req-box">{hazard}</div>', unsafe_allow_html=True)

        # -- 신고/등록 현황 --
        status_items = [("Registration", "등록"), ("SDS", "SDS")]
        status_vals = [(label, str(row.get(k, "")).strip()) for k, label in status_items if str(row.get(k, "")).strip()]
        if status_vals:
            st.markdown('<div class="detail-section-title">신고/등록 현황</div>', unsafe_allow_html=True)
            st.markdown(" ".join(f'<span class="reg-tag reg-tag-green">{label}: {val}</span>' for label, val in status_vals), unsafe_allow_html=True)

        # -- 수입요령 --
        if req:
            st.markdown('<div class="detail-section-title">수입요령</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="import-req-box">{req}</div>', unsafe_allow_html=True)


def show_results(results, key):
    if results.empty:
        st.warning("검색 결과가 없습니다.")
        return

    st.markdown(f'총 **{len(results):,}** 건')

    c1, c2 = st.columns([4, 1])
    with c2:
        avail = [c for c in DL_COLS if c in results.columns]
        st.download_button(
            "엑셀 다운로드", data=to_excel(results[avail]),
            file_name=f"chemical_{key}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"dl_{key}", use_container_width=True,
        )

    MAX = 500
    show = results.head(MAX)
    if len(results) > MAX:
        st.info(f"상위 {MAX}건만 표시합니다.")

    avail_t = [c for c in TABLE_COLS if c in show.columns]
    st.dataframe(show[avail_t].reset_index(drop=True), use_container_width=True,
                 height=min(450, 35 * len(show) + 38))

    st.markdown("---")
    st.markdown('<div class="page-title">상세 정보</div>', unsafe_allow_html=True)
    PER = 15
    pages = max(1, (len(show) + PER - 1) // PER)
    pg = 1
    if pages > 1:
        pg = st.number_input("페이지", 1, pages, 1, key=f"pg_{key}")
        st.caption(f"페이지 {pg}/{pages}")
    s, e = (pg - 1) * PER, min(pg * PER, len(show))
    for _, row in show.iloc[s:e].iterrows():
        render_detail(row)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding:1rem 0 0.5rem 0;">
        <div style="font-size:1.8rem;">⚗️</div>
        <div style="font-size:1rem; font-weight:700;">화학물질 관리시스템</div>
        <div style="font-size:0.65rem; color:#8cb4ff; margin-top:0.2rem;">Chemical Substance Management</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    st.caption("Star Truck Korea")

# ---------------------------------------------------------------------------
# Header + Load
# ---------------------------------------------------------------------------
st.markdown("""
<div class="top-header">
    <span style="font-size:1.8rem;">&#9883;</span>
    <div><h1>화학물질 관리시스템</h1><p class="sub">Chemical Substance Management System — Star Truck Korea</p></div>
</div>
""", unsafe_allow_html=True)

try:
    master = build_master()
except Exception as e:
    st.error(f"데이터 로딩 오류: {e}")
    st.stop()

cas_total = load_cas()
hs_total = load_hs()
has_hs = master[master["HS Code"] != ""]
has_law = master[master["관련법령"] != ""]
has_both = master[(master["CAS No"] != "") & (master["HS Code"] != "")]
cas_hs_match_count = len(has_both)

st.markdown(f"""
<div class="stats-row">
    <div class="stat-box"><p class="num">{len(cas_total):,}</p><p class="lbl">CAS 물질 (전체)</p></div>
    <div class="stat-box"><p class="num">{len(has_hs):,}</p><p class="lbl">HS 코드</p></div>
    <div class="stat-box"><p class="num">{cas_hs_match_count:,}</p><p class="lbl">CAS-HS 매칭</p></div>
    <div class="stat-box"><p class="num">{len(has_law):,}</p><p class="lbl">법령 매칭</p></div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 4 Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["📋 HS Code 검색", "🔬 CAS Number 검색", "⚖️ 법률 검색", "🔍 품목명 검색"])

with tab1:
    st.markdown('<div class="page-title">HS Code 검색 (앞 4자리 입력)</div>', unsafe_allow_html=True)
    q1 = st.text_input("HS Code 입력 (앞 4자리)", placeholder="예: 2710, 3208, 2909", key="q_hs")
    if q1:
        show_results(search_df(master, q1, ["HS Code", "HS 4자리"]), "hs")
    else:
        st.info("HS Code 앞 4자리를 입력하면 해당 코드의 모든 화학물질 · 법령 · 수입요령이 표시됩니다.")

with tab2:
    st.markdown('<div class="page-title">CAS Number 검색</div>', unsafe_allow_html=True)
    q2 = st.text_input("CAS Number 입력", placeholder="예: 64-19-7, 67124-09-8", key="q_cas")
    if q2:
        show_results(search_df(master, q2, ["CAS No"]), "cas")
    else:
        st.info("CAS Number를 입력하면 해당 물질의 모든 정보가 표시됩니다.")

with tab3:
    st.markdown('<div class="page-title">법률 검색</div>', unsafe_allow_html=True)
    all_laws = set()
    for s in master["관련법령"].unique():
        if s:
            for l in re.split(r"[/]", s):
                l = l.strip()
                if l:
                    all_laws.add(l)
    c1, c2 = st.columns([2, 3])
    with c1:
        sel = st.selectbox("법령 선택", ["전체"] + sorted(all_laws), key="sel_law")
    with c2:
        q3 = st.text_input("또는 직접 입력", placeholder="예: 화평법, 산업안전", key="q_law")
    if q3:
        show_results(search_df(master, q3, ["관련법령"]), "law")
    elif sel != "전체":
        r = master[master["관련법령"].str.contains(re.escape(sel), case=False, na=False)]
        show_results(r, "law")
    else:
        lc = [{"법령명": l, "관련 물질 수": master["관련법령"].str.contains(re.escape(l), case=False, na=False).sum()} for l in sorted(all_laws)]
        st.dataframe(pd.DataFrame(lc).sort_values("관련 물질 수", ascending=False).reset_index(drop=True),
                     use_container_width=True, height=400)

with tab4:
    st.markdown('<div class="page-title">품목명 검색 (영문/한글)</div>', unsafe_allow_html=True)
    q4 = st.text_input("품목명 입력", placeholder="예: GEAR OIL, Acetic acid, 염소, 페인트", key="q_name")
    if q4:
        show_results(search_df(master, q4, ["영문명", "국문명", "품명", "Description", "관련항목"]), "name")
    else:
        st.info("영문 또는 한글 품목명을 입력하면 관련 화학물질 정보가 표시됩니다.")
