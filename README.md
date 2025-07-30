# 🚀 SmartInvestor Pro

AI와 기술적 분석을 활용한 스마트 투자 분석 도구입니다. 실시간 시장 데이터를 분석하여 매수 기회를 발견하고, 개인화된 투자 리포트를 제공합니다.

## 📋 주요 기능

### 📊 기술적 분석
- 5가지 기술적 지표 동시 분석 (RSI, MACD, CCI, MFI, StochRSI)
- 점수 기반 매수 신호 (5점 만점 시스템)
- 실시간 시장 데이터 분석

### 🎯 특별 기능
- 직관적인 UI/UX - 모던하고 사용하기 쉬운 인터페이스
- 실시간 추천 종목 - AI가 선별한 투자 기회
- 시장 히트맵 연동 (Finviz)

### 📰 뉴스 & AI
- 투자 뉴스 자동 수집 (Investing.com RSS)
- AI 뉴스 요약 (OpenAI GPT 연동)
- 개별 종목 심층 분석

### 📄 리포트
- PDF 투자 리포트 자동 생성
- 개인화된 분석 결과 포함
- 투자 가이드라인 제공

### 🔐 사용자 관리
- 안전한 인증 시스템 (bcrypt 해싱)
- 관리자 기능 포함
- 사용자별 설정 저장

## 🚀 빠른 시작

### 데모 계정
```
이메일: admin@smartinvestor.com
비밀번호: admin123
```

### 로컬 설치

1. **리포지토리 클론**
```bash
git clone https://github.com/1royd1/smartinvestor.git
cd smartinvestor
```

2. **가상환경 생성 (권장)**
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. **의존성 설치**
```bash
pip install -r requirements.txt
```

4. **애플리케이션 실행**
```bash
streamlit run app.py
```

5. **브라우저에서 접속**
```
http://localhost:8501
```

## 🌐 Streamlit Cloud 배포

### 1. GitHub에 코드 업로드
```bash
git add .
git commit -m "Initial commit: SmartInvestor Pro"
git push origin main
```

### 2. Streamlit Cloud 설정
1. [share.streamlit.io](https://share.streamlit.io) 접속
2. GitHub 리포지토리 연결
3. 메인 파일 경로: `app.py`
4. Deploy 클릭

### 3. 환경 변수 설정 (선택사항)
OpenAI API 키 설정을 위해 Streamlit Cloud의 Secrets에 추가:
```toml
OPENAI_API_KEY = "your-openai-api-key-here"
```

## 📊 매수 신호 기준

| 지표 | 조건 | 의미 |
|------|------|------|
| RSI | < 30 | 과매도 구간 (반등 가능성) |
| MACD | 골든크로스 | 상승 모멘텀 시작 |
| CCI | < -100 | 과매도 신호 |
| MFI | < 20 | 자금 유입 부족 (반등 대기) |
| StochRSI | < 0.2 | 극도의 과매도 |

**추천 기준**: 5개 조건 중 3개 이상 만족시 매수 추천

## 🛠️ 기술 스택

- **Frontend**: Streamlit
- **Backend**: Python
- **Database**: SQLite
- **Data Source**: Yahoo Finance (yfinance)
- **Technical Analysis**: TA-Lib
- **News**: Investing.com RSS
- **AI**: OpenAI GPT (선택사항)
- **Security**: bcrypt
- **Report**: FPDF

## 📁 프로젝트 구조

```
smartinvestor/
├── app.py                 # 메인 애플리케이션
├── requirements.txt       # 의존성 목록
├── README.md             # 프로젝트 설명서
├── .gitignore            # Git 제외 파일
└── smartinvestor.db      # SQLite 데이터베이스 (자동 생성)
```

## ⚙️ 커스터마이징

### 분석 종목 변경
`app.py`의 `DEFAULT_SYMBOLS` 수정:
```python
DEFAULT_SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL',  # 원하는 종목 추가
    'QQQ', 'SPY', 'VTI',      # ETF
    'BTC-USD', 'ETH-USD'      # 암호화폐
]
```

### 매수 신호 기준 조정
더 엄격한 기준을 원한다면:
```python
# RSI 과매도 기준을 25로 낮춤
if latest['RSI'] < 25:
    score += 1
    signals.append("RSI 과매도 신호")

# 최소 점수를 4점으로 상향
if score >= 4:  # 기존 3점에서 4점으로
    recommendations.append(...)
```

## 🚨 중요 사항

- 이 도구는 투자 참고용이며, 실제 투자 결정은 본인 책임입니다
- 과거 데이터 기반 분석이므로 미래 수익을 보장하지 않습니다
- 분산 투자와 리스크 관리를 권장합니다
- 투자 전 충분한 학습과 조사를 하시기 바랍니다

## 📈 제한사항

- 실시간 데이터가 아닌 지연 데이터 사용 (15-20분 지연)
- 무료 API 사용시 요청 제한 있음
- 네트워크 상태에 따른 성능 차이 발생 가능

## 🤝 기여하기

1. Fork 프로젝트
2. Feature 브랜치 생성 (`git checkout -b feature/AmazingFeature`)
3. 변경사항 커밋 (`git commit -m 'Add some AmazingFeature'`)
4. 브랜치에 Push (`git push origin feature/AmazingFeature`)
5. Pull Request 생성

## 📞 문의

- 🐛 버그 리포트: [GitHub Issues](https://github.com/1royd1/smartinvestor/issues)
- 💡 기능 제안: [GitHub Discussions](https://github.com/1royd1/smartinvestor/discussions)
- 📧 이메일: admin@smartinvestor.com

## 📄 라이선스

MIT License - 자세한 내용은 [LICENSE](LICENSE) 파일 참조

---

**🚀 SmartInvestor Pro로 더 스마트한 투자를 시작하세요!**
