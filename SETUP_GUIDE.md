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
pip install playwright
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

## 5단계: WINGS 데이터 다운로드 실행

```bash
python wings_scheduler.py
```

### 실행 흐름:
1. Chrome 브라우저가 자동으로 열림
2. WINGS 로그인 페이지가 나타남
3. **브라우저에서 아이디/비밀번호 입력**
4. **터미널에 Authenticator 코드 입력 프롬프트가 나타남:**
   ```
   ==================================================
     Microsoft Authenticator 코드를 입력하세요
   ==================================================
     코드 (6자리): ______
   ```
5. 핸드폰의 Microsoft Authenticator 앱에서 코드 확인 후 입력
6. 자동으로 다운로드 + GitHub push 완료

### 옵션:
```bash
# push 없이 다운로드만
python wings_scheduler.py --no-push

# 3개월만 다운로드
python wings_scheduler.py --months-ahead 3
```

---

## 6단계 (선택): 매일 자동 실행 등록

> 주의: 자동 실행 시에도 Authenticator 코드를 입력해야 하므로,
> PC 앞에 있을 때 실행되도록 설정하세요.

```bash
# 관리자 권한으로 실행해야 합니다
python wings_scheduler.py --setup-task
```

이렇게 하면 매일 오전 7시에 자동으로 터미널이 열리고 코드 입력을 기다립니다.

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

### Chrome 프로필 충돌 오류
- Chrome을 모두 닫은 후 다시 실행

### 로그인이 안 될 때
- WINGS 접근 권한이 있는 계정인지 확인
- 회사 VPN에 연결되어 있는지 확인
