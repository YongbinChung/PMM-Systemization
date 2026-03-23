"""매일 오전 7시 Windows 작업 스케줄러로 실행되는 WINGS 자동 다운로드 스크립트.

사용법:
  python _wings_daily.py

이 스크립트는 직접 실행하지 않고, Windows 작업 스케줄러가 _wings_daily.bat을 통해 실행합니다.
"""
import sys, os, json
from datetime import date, timedelta

# 프로젝트 경로 설정
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from wings_scraper import _download_in_process

def main():
    # 이번 달 + 향후 6개월
    months = []
    today = date.today()
    for i in range(7):
        d = date(today.year, today.month, 1) + timedelta(days=32 * i)
        ms = f"{d.year}-{d.month:02d}"
        if ms not in months:
            months.append(ms)

    download_dir = os.path.join(PROJECT_DIR, "_wings_dl")
    os.makedirs(download_dir, exist_ok=True)

    status_file = os.path.join(download_dir, "_status.txt")
    result_file = os.path.join(download_dir, "_result.json")

    # 이전 결과 정리
    for f in [status_file, result_file]:
        try:
            os.remove(f)
        except OSError:
            pass

    def on_status(msg):
        print(msg)
        with open(status_file, "w", encoding="utf-8") as f:
            f.write(msg)

    print(f"WINGS Daily Auto-Fetch: months={months}")
    try:
        path = _download_in_process(months, download_dir, on_status, None)
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump({"ok": True, "path": path}, f)
        print(f"SUCCESS: {path}")
    except Exception as e:
        import traceback
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump({"ok": False, "error": traceback.format_exc()}, f)
        print(f"ERROR: {e}")
        input("Press Enter to close...")

if __name__ == "__main__":
    main()
