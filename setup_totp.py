"""
TOTP 비밀키 설정 스크립트
========================
Microsoft Authenticator의 TOTP 비밀키를 저장하여
WINGS 자동 로그인을 완전 자동화합니다.

사용법:
  python setup_totp.py
"""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.resolve()
SECRET_FILE = PROJECT_DIR / '.totp_secret'


def main():
    print()
    print('=' * 60)
    print('  WINGS Auto-Fetch: TOTP 비밀키 설정')
    print('=' * 60)
    print()
    print('이 스크립트는 Microsoft Authenticator의 TOTP 비밀키를')
    print('저장하여 로그인을 완전 자동화합니다.')
    print()
    print('--- 비밀키 확인 방법 ---')
    print()
    print('1. 브라우저에서 접속:')
    print('   https://mysignins.microsoft.com/security-info')
    print()
    print('2. "Add sign-in method" (로그인 방법 추가) 클릭')
    print()
    print('3. "Authenticator app" 선택 → "Add"')
    print()
    print('4. "I want to use a different authenticator app" 클릭')
    print()
    print('5. QR 코드 화면에서 "Can\'t scan image?" 클릭')
    print('   → "Secret key" (비밀키) 가 텍스트로 표시됨')
    print('   → 이 키를 복사하세요!')
    print()
    print('6. 동시에 Microsoft Authenticator 앱에도 등록하세요')
    print('   (기존 앱은 그대로, 새 항목을 추가)')
    print()
    print('-' * 60)

    if SECRET_FILE.exists():
        current = SECRET_FILE.read_text().strip()
        masked = current[:4] + '****' + current[-4:] if len(current) > 8 else '****'
        print(f'현재 저장된 비밀키: {masked}')
        print()

    secret = input('TOTP 비밀키를 입력하세요 (빈칸: 취소): ').strip()

    if not secret:
        print('취소되었습니다.')
        return

    # 공백/하이픈 제거
    secret = secret.replace(' ', '').replace('-', '').upper()

    # 검증: pyotp로 코드 생성 테스트
    try:
        import pyotp
    except ImportError:
        print('\npyotp 설치 중...')
        import subprocess
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyotp'], check=True)
        import pyotp

    try:
        totp = pyotp.TOTP(secret)
        code = totp.now()
        print(f'\n테스트 생성된 코드: {code}')
        print('Microsoft Authenticator 앱의 코드와 비교해 보세요.')
        print()

        confirm = input('코드가 일치하나요? (y/n): ').strip().lower()
        if confirm != 'y':
            print('비밀키가 올바르지 않습니다. 다시 시도하세요.')
            return

    except Exception as e:
        print(f'\n오류: {e}')
        print('비밀키 형식이 올바르지 않습니다.')
        return

    # 저장
    SECRET_FILE.write_text(secret)
    print(f'\n비밀키가 저장되었습니다: {SECRET_FILE}')
    print('이제 wings_scheduler.py 실행 시 자동으로 인증 코드가 생성됩니다!')
    print()
    print('주의: .totp_secret 파일은 절대 GitHub에 올리지 마세요!')


if __name__ == '__main__':
    main()
