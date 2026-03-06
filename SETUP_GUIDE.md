# WINGS Auto-Fetch 설정 가이드 (다른 PC용)

이 가이드는 **다른 직원의 PC**에서 WINGS 데이터를 자동으로 다운로드하고
GitHub에 push하여 Streamlit Cloud 대시보드에 반영하는 방법을 설명합니다.

---

## 1단계: 필수 프로그램 설치

### Python 설치
1. https://www.python.org/downloads/ 에서 Python 3.11+ 다운로드
2. 설치 시 **"Add Python to PATH"** 반드시 체크
3. 설치 완료 후 터미널(cmd)에서 확인:
   ```
   python --version
   ```

### Git 설치
1. https://git-scm.com/download/win 에서 Git 다운로드 및 설치
2. 설치 완료 후 터미널에서 확인:
   ```
   git --version
   ```

### Google Chrome
- 이미 설치되어 있어야 합니다 (WINGS 자동화에 사용)

---

## 2단계: 프로젝트 다운로드

터미널(cmd 또는 PowerShell)을 열고:

```bash
# 원하는 폴더로 이동 (예: 바탕화면)
cd %USERPROFILE%\Desktop

# GitHub에서 프로젝트 클론
git clone https://github.com/YongbinChung/PMM-Systemization.git

# 프로젝트 폴더로 이동
cd PMM-Systemization
```

---

## 3단계: Python 라이브러리 설치

```bash
pip install -r requirements.txt
pip install playwright pyotp
python -m playwright install chromium
```

---

## 4단계: Git 사용자 설정

```bash
git config user.name "사용자이름"
git config user.email "사용자이메일@example.com"
```

> GitHub 계정이 필요합니다. 레포지토리에 push 권한이 있어야 합니다.
> 권한이 없다면 YongbinChung에게 collaborator 초대를 요청하세요.

---

## 5단계: TOTP 비밀키 설정 (완전 자동화)

이 단계를 완료하면 Authenticator 코드를 수동으로 입력할 필요 없이
**완전 자동**으로 WINGS 로그인이 가능합니다.

### 5-1. Microsoft 보안 정보 페이지 접속
브라우저에서 접속: https://mysignins.microsoft.com/security-info

### 5-2. 새 인증 앱 추가
1. **"Add sign-in method"** (로그인 방법 추가) 클릭
2. **"Authenticator app"** 선택 → **"Add"** 클릭
3. **"I want to use a different authenticator app"** 클릭
4. **"Next"** 클릭하면 QR 코드가 나타남

### 5-3. 비밀키 확인
1. QR 코드 화면에서 **"Can't scan image?"** 클릭
2. **"Secret key"** (비밀키) 가 텍스트로 표시됨
3. 이 키를 복사해 두세요!

> **중요**: 기존 Microsoft Authenticator 앱은 그대로 유지하세요.
> 이것은 추가 등록이며, 기존 앱과 동시에 사용 가능합니다.

### 5-4. 비밀키 저장
```bash
python setup_totp.py
```
1. 복사한 비밀키를 붙여넣기
2. 생성된 6자리 코드가 Authenticator 앱의 코드와 일치하는지 확인
3. "y" 입력하면 저장 완료

> **주의**: `.totp_secret` 파일은 이 PC에만 저장되며, GitHub에 올라가지 않습니다.

---

## 6단계: WINGS 데이터 다운로드 실행

```bash
python wings_scheduler.py
```

### TOTP 설정 완료 시 (완전 자동):
1. Chrome 브라우저가 자동으로 열림
2. WINGS 로그인 페이지 → 브라우저에서 아이디/비밀번호 입력
3. **인증 코드 자동 생성 및 입력** (터미널에 코드가 표시됨)
4. 자동으로 다운로드 + GitHub push 완료

### TOTP 미설정 시 (수동 입력):
1. Chrome 브라우저가 자동으로 열림
2. WINGS 로그인 페이지 → 브라우저에서 아이디/비밀번호 입력
3. 터미널에 Authenticator 코드 입력 프롬프트가 나타남
4. 핸드폰에서 코드 확인 후 입력
5. 자동으로 다운로드 + GitHub push 완료

### 옵션:
```bash
# push 없이 다운로드만
python wings_scheduler.py --no-push

# 3개월만 다운로드
python wings_scheduler.py --months-ahead 3
```

---

## 7단계 (선택): 매일 자동 실행 등록

TOTP 설정을 완료했다면 완전 자동 실행이 가능합니다.

```bash
# 관리자 권한으로 실행해야 합니다
python wings_scheduler.py --setup-task
```

매일 오전 7시에 자동으로 실행됩니다.

> **참고**: 아이디/비밀번호는 Chrome 프로필에 저장되므로,
> 처음 1회만 수동 로그인하면 이후에는 자동 입력됩니다.

---

## 문제 해결

### "git push 실패" 오류
- GitHub 로그인 필요: `git push` 시 GitHub 인증 팝업이 나타나면 로그인
- 또는 GitHub Personal Access Token 설정:
  ```bash
  git remote set-url origin https://TOKEN@github.com/YongbinChung/PMM-Systemization.git
  ```

### "playwright 오류"
```bash
python -m playwright install chromium
```

### "pyotp 오류"
```bash
pip install pyotp
```

### Chrome 프로필 충돌 오류
- Chrome을 모두 닫은 후 다시 실행

### TOTP 코드가 틀린 경우
- 비밀키 재설정: `python setup_totp.py`
- PC 시계가 정확한지 확인 (TOTP는 시간 기반)

### 로그인이 안 될 때
- WINGS 접근 권한이 있는 계정인지 확인
- 회사 VPN에 연결되어 있는지 확인
