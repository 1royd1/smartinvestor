# 🚀 SmartInvestor Pro - AI 투자 분석 플랫폼

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-url.streamlit.app)

**SmartInvestor Pro**는 AI와 기술적 분석을 활용한 스마트 투자 분석 도구입니다. 실시간 시장 데이터를 분석하여 매수 기회를 발견하고, 개인화된 투자 리포트를 제공합니다.

## ✨ 주요 기능

### 🤖 AI 기반 분석
- **5가지 기술적 지표** 동시 분석 (RSI, MACD, CCI, MFI, StochRSI)
- **점수 기반 매수 신호** (5점 만점 시스템)
- **실시간 시장 데이터** 분석

### 📊 스마트 대시보드
- **직관적인 UI/UX** - 모던하고 사용하기 쉬운 인터페이스
- **실시간 추천 종목** - AI가 선별한 투자 기회
- **시장 히트맵** 연동 (Finviz)

### 📰 뉴스 & 인사이트
- **투자 뉴스 자동 수집** (Investing.com RSS)
- **AI 뉴스 요약** (OpenAI GPT 연동)
- **개별 종목 심층 분석**

### 📄 리포트 생성
- **PDF 투자 리포트** 자동 생성
- **개인화된 분석 결과** 포함
- **투자 가이드라인** 제공

### 🔐 사용자 관리
- **안전한 인증 시스템** (bcrypt 해싱)
- **관리자 기능** 포함
- **사용자별 설정** 저장

## 🎯 데모 계정

바로 체험해보세요!

```
관리자 계정:
이메일: admin@smartinvestor.com
비밀번호: admin123
```

## 🚀 Streamlit Cloud 배포 가이드

### 1. GitHub 리포지토리 준비

```bash
# 1. 새 리포지토리 생성
git init
git add .
git commit -m "Initial commit: SmartInvestor Pro"
git remote add origin https://github.com/yourusername/smartinvestor-pro.git
git push -u origin main
```

### 2. Streamlit Cloud 연결

1. [share.streamlit.io](https://share.streamlit.io) 접속
2. **"Connect to GitHub"** 클릭
3. 리포지토리 선택: `yourusername/smartinvestor-pro`
4. 메인 파일 경로: `streamlit_app.py`
5. **"Deploy!"** 클릭

### 3. 환경 변수 설정 (선택사항)

OpenAI GPT 뉴스 요약 기능을 사용하려면:

1. Streamlit Cloud 앱 설정에서 **"Secrets"** 클릭
2. 다음 내용 추가:

```toml
# .streamlit/secrets.toml 형식
OPENAI_API_KEY = "your-openai-api-key-here"
```

> 💡 **참고**: OpenAI API 키가 없어도 기본 기능은 모두 사용 가능합니다!

## 💻 로컬 개발 환경 설정

### 사전 요구사항
- Python 3.8 이상
- pip 패키지 관리자

### 설치 및 실행

```bash
# 1. 리포지토리 클론
git clone https://github.com/yourusername/smartinvestor-pro.git
cd smartinvestor-pro

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 애플리케이션 실행
streamlit run streamlit_app.py
```

브라우저에서 `http://localhost:8501` 접속

## 📊 분석 기준

### 매수 신호 조건 (5점 만점)

| 지표 | 조건 | 의미 |
|------|------|------|
| **RSI** | < 30 | 과매도 구간 (반등 가능성) |
| **MACD** | 골든크로스 | 상승 모멘텀 시작 |
| **CCI** | < -100 | 과매도 신호 |
| **MFI** | < 20 | 자금 유입 부족 (반등 대기) |
| **StochRSI** | < 0.2 | 극도의 과매도 |

**추천 기준**: 5개 조건 중 **3개 이상 만족**시 추천

### 지원 종목
- **미국 주식**: AAPL, MSFT, GOOGL, TSLA, AMZN 등
- **ETF**: QQQ, SPY, VTI, ARKK 등
- **암호화폐**: BTC-USD, ETH-USD 등

## 🔧 커스터마이징

### 1. 분석 종목 변경

`streamlit_app.py`에서 `DEFAULT_SYMBOLS` 수정:

```python
DEFAULT_SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL',  # 원하는 종목 추가
    'QQQ', 'SPY', 'VTI',      # ETF
    'BTC-USD', 'ETH-USD'      # 암호화폐
]
```

### 2. 매수 신호 임계값 조정

```python
BUY_SIGNALS = {
    'RSI_OVERSOLD': 25,      # 더 엄격한 기준
    'MIN_SCORE': 4           # 더 높은 점수 요구
}
```

## ⚠️ 중요 안내사항

### 투자 관련 주의사항
- 🚨 **이 도구는 투자 참고용이며, 실제 투자 결정은 본인 책임입니다**
- 📈 과거 데이터 기반 분석이므로 미래 수익을 보장하지 않습니다
- 💰 분산 투자와 리스크 관리를 권장합니다
- 📚 투자 전 충분한 학습과 조사를 하시기 바랍니다

### 기술적 제한사항
- 실시간 데이터가 아닌 지연 데이터 사용 (15-20분 지연)
- 무료 API 사용시 요청 제한 있음
- 네트워크 상태에 따른 성능 차이 발생 가능

## 🛠 기술 스택

- **Frontend**: Streamlit
- **Backend**: Python
- **Database**: SQLite
- **Data Source**: Yahoo Finance (yfinance)
- **Technical Analysis**: TA-Lib
- **News**: Investing.com RSS
- **AI**: OpenAI GPT (선택사항)
- **Security**: bcrypt
- **Report**: FPDF

## 📈 로드맵

### v1.1 (개발 중)
- [ ] 포트폴리오 추적 기능
- [ ] 이메일 알림 시스템
- [ ] 백테스팅 모듈
- [ ] 모바일 반응형 개선

### v1.2 (계획)
- [ ] 한국 주식 지원 (KRX)
- [ ] 실시간 알림 시스템
- [ ] 소셜 트레이딩 기능
- [ ] 고급 차트 시각화

## 🤝 기여하기

1. Fork 프로젝트
2. Feature 브랜치 생성 (`git checkout -b feature/AmazingFeature`)
3. 변경사항 커밋 (`git commit -m 'Add some AmazingFeature'`)
4. 브랜치에 Push (`git push origin feature/AmazingFeature`)
5. Pull Request 생성

## 📞 지원

- 🐛 **버그 리포트**: [GitHub Issues](https://github.com/yourusername/smartinvestor-pro/issues)
- 💡 **기능 제안**: [GitHub Discussions](https://github.com/yourusername/smartinvestor-pro/discussions)
- 📧 **기타 문의**: 관리자에게 직접 연락

## 📄 라이선스

MIT License - 자세한 내용은 [LICENSE](LICENSE) 파일 참조

## ⭐ 스타 히스토리

[![Star History Chart](https://api.star-history.com/svg?repos=yourusername/smartinvestor-pro&type=Date)](https://star-history.com/#yourusername/smartinvestor-pro&Date)

---

<div align="center">

**🚀 SmartInvestor Pro로 더 스마트한 투자를 시작하세요!**

[![Made with Streamlit](https://img.shields.io/badge/Made%20with-Streamlit-red.svg)](https://streamlit.io)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[🌟 Star this repo](https://github.com/yourusername/smartinvestor-pro) | [🚀 Live Demo](https://your-app-url.streamlit.app) | [📖 Documentation](https://github.com/yourusername/smartinvestor-pro/wiki)

</div>