"""
WINGS Auto-Fetch Scheduler
===========================
Automatically downloads WINGS data for next month onwards,
saves to wings_data/ folder, and pushes to GitHub.

Usage:
  - Manual run:   python wings_scheduler.py
  - With Windows Task Scheduler: run daily/weekly automatically

The script fetches production months from next month up to 12 months ahead,
saves the CSV in wings_data/, then commits & pushes to GitHub.
"""

import os
import sys
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path

# Project root
PROJECT_DIR = Path(__file__).parent.resolve()
WINGS_DATA_DIR = PROJECT_DIR / 'wings_data'
WINGS_DATA_DIR.mkdir(exist_ok=True)

# Add project to path for imports
sys.path.insert(0, str(PROJECT_DIR))


def get_future_months(months_ahead: int = 6) -> list:
    """Generate YYYY-MM strings from next month up to months_ahead months."""
    today = date.today()
    # Start from next month
    first_of_next = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    months = []
    for i in range(months_ahead):
        m = (first_of_next.replace(day=1) + timedelta(days=32 * i)).replace(day=1)
        months.append(f'{m.year}-{m.month:02d}')
    return months


def _get_auth_code() -> str:
    """TOTP 비밀키가 있으면 자동 생성, 없으면 터미널에서 입력받는다."""
    secret_file = PROJECT_DIR / '.totp_secret'

    # 1) 비밀키 파일이 있으면 자동 생성
    if secret_file.exists():
        try:
            import pyotp
            secret = secret_file.read_text().strip()
            totp = pyotp.TOTP(secret)
            code = totp.now()
            print(f'  [TOTP 자동 생성: {code}]')
            return code
        except ImportError:
            print('  pyotp가 설치되지 않았습니다. pip install pyotp')
        except Exception as e:
            print(f'  TOTP 자동 생성 실패: {e}')

    # 2) 수동 입력 fallback
    print('\n' + '=' * 50)
    print('  Microsoft Authenticator 코드를 입력하세요')
    print('=' * 50)
    code = input('  코드 (6자리): ').strip()
    print()
    return code


def fetch_and_save(months: list) -> str | None:
    """Fetch WINGS data for given months and save to wings_data/."""
    from wings_scraper import download_wings_excel

    months_label = '_'.join(m.replace('-', '') for m in months)
    today_str = date.today().strftime('%Y%m%d')
    filename = f'WINGS_{months_label}_{today_str}.csv'
    dest_path = WINGS_DATA_DIR / filename

    def on_status(msg):
        print(f'  [{msg}]')

    try:
        print(f'Fetching WINGS data for months: {months}')
        dl_path = download_wings_excel(
            months=months,
            download_dir=str(WINGS_DATA_DIR),
            on_status=on_status,
            auth_code_callback=_get_auth_code,
        )
        # Rename to standardized filename
        dl = Path(dl_path)
        if dl.exists() and dl != dest_path:
            shutil.move(str(dl), str(dest_path))
        print(f'Saved: {dest_path}')
        return str(dest_path)
    except Exception as e:
        print(f'ERROR: {type(e).__name__}: {e}')
        return None


def git_push(files: list):
    """Stage, commit, and push files to GitHub."""
    os.chdir(str(PROJECT_DIR))

    # Stage files
    for f in files:
        rel = os.path.relpath(f, str(PROJECT_DIR))
        subprocess.run(['git', 'add', rel], check=True)

    # Check if there are staged changes
    result = subprocess.run(
        ['git', 'diff', '--cached', '--quiet'],
        capture_output=True,
    )
    if result.returncode == 0:
        print('No changes to commit.')
        return

    # Commit and push
    today_str = date.today().strftime('%Y-%m-%d')
    msg = f'Auto-fetch WINGS data ({today_str})'
    subprocess.run(['git', 'commit', '-m', msg], check=True)
    subprocess.run(['git', 'push'], check=True)
    print('Pushed to GitHub.')


def setup_windows_task():
    """Register a daily Windows Task Scheduler task."""
    python_exe = sys.executable
    script_path = str(Path(__file__).resolve())
    task_name = 'WINGS_AutoFetch'

    # Create task to run daily at 7:00 AM
    cmd = (
        f'schtasks /Create /F /SC DAILY /TN "{task_name}" '
        f'/TR "\"{python_exe}\" \"{script_path}\"" '
        f'/ST 07:00'
    )
    print(f'Creating scheduled task: {task_name}')
    print(f'Command: {cmd}')
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f'Task "{task_name}" created successfully. Runs daily at 07:00.')
    else:
        print(f'Failed to create task: {result.stderr}')
        print('You may need to run as Administrator.')


def main():
    import argparse
    parser = argparse.ArgumentParser(description='WINGS Auto-Fetch Scheduler')
    parser.add_argument('--setup-task', action='store_true',
                        help='Register Windows Task Scheduler (daily 7AM)')
    parser.add_argument('--months-ahead', type=int, default=6,
                        help='How many months ahead to fetch (default: 6)')
    parser.add_argument('--no-push', action='store_true',
                        help='Download only, do not git push')
    args = parser.parse_args()

    if args.setup_task:
        setup_windows_task()
        return

    months = get_future_months(args.months_ahead)
    print(f'Target months: {months}')

    # Clean old files in wings_data/
    for old_file in WINGS_DATA_DIR.glob('WINGS_*.csv'):
        old_file.unlink()
        print(f'Removed old: {old_file.name}')

    saved_path = fetch_and_save(months)

    if saved_path and not args.no_push:
        # Also add .gitkeep to ensure folder is tracked
        gitkeep = WINGS_DATA_DIR / '.gitkeep'
        gitkeep.touch()
        git_push([saved_path, str(gitkeep)])
    elif not saved_path:
        print('Fetch failed. Nothing to push.')


if __name__ == '__main__':
    main()
