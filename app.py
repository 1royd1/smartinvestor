
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
import openai
import datetime
import ta
import requests
import io
import platform

# ------------------------
# 설정
# ------------------------
st.set_page_config(page_title="SmartInvestor 대시보드", layout="wide")
st.title("📈 SmartInvestor: 종합 투자 대시보드")

# ------------------------
# 플랫폼 감지 (모바일 여부)
# ------------------------
def is_mobile():
    ua = st.session_state.get("_user_agent", "").lower()
    return "mobile" in ua or "android" in ua or "iphone" in ua

# ------------------------
# 메뉴
# ------------------------
menu = st.sidebar.selectbox("메뉴 선택", [
    "🏠 종합 대시보드",
    "📊 개별 종목 분석",
    "⭐ 추천 종목 스캐너",
    "📂 포트폴리오 보기",
    "🎯 성향 기반 ETF 추천",
    "📈 수익률 추적 그래프",
    "🔔 리스크 경고 알림",
    "🗓️ 리밸런싱 리마인더"
])

# ------------------------
# Investing.com 뉴스 RSS 연동
# ------------------------
def fetch_investing_news():
    try:
        rss_url = "https://www.investing.com/rss/news_285.rss"
        response = requests.get(rss_url, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            items = root.findall(".//item")
            news = []
            for item in items[:5]:
                title = item.find("title").text
                link = item.find("link").text
                # 번역 요약 추가 (OpenAI 필요)
                summary_prompt = f"다음 뉴스 제목을 한국어로 요약해줘:

{title}"
                try:
                    if "OPENAI_API_KEY" in st.secrets:
                        openai.api_key = st.secrets["OPENAI_API_KEY"]
                        response = openai.ChatCompletion.create(
                            model="gpt-3.5-turbo",
                            messages=[{"role": "user", "content": summary_prompt}]
                        )
                        translated = response.choices[0].message.content.strip()
                    else:
                        translated = "(GPT API 키 필요) " + title
                except:
                    translated = title
                news.append(f"- [{translated}]({link})")
            return news
        else:
            return ["❌ Investing.com RSS 데이터를 가져오지 못했습니다."]
    except:
        return ["❌ 뉴스 로딩 중 오류 발생"]

# ------------------------
# GPT 기반 자산 요약 리포트
# ------------------------
def summarize_portfolio_with_gpt(results):
    try:
        if not results:
            return "요약할 포트폴리오 정보가 없습니다."
        text_lines = [f"{ticker}: 수익률 {rate:.2f}%" for ticker, _, _, rate in results]
        prompt = f"""
        다음은 사용자의 주식 수익률 요약입니다. 각 종목별 수익률을 고려해 투자 포트폴리오 상태를 한국어로 분석하고 요약해주세요.

{chr(10).join(text_lines)}
        """
        if "OPENAI_API_KEY" in st.secrets:
            openai.api_key = st.secrets["OPENAI_API_KEY"]
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content.strip()
        else:
            return "GPT API 키가 설정되지 않았습니다."
    except Exception as e:
        return f"GPT 분석 실패: {e}"

# ------------------------
# 종합 대시보드
# ------------------------
if menu == "🏠 종합 대시보드":
    st.subheader("🏠 종합 투자 요약")

    if not is_mobile():
        st.markdown("### 🌐 시장 섹터 히트맵 (Finviz)")
        st.markdown("""
        <iframe src="https://finviz.com/map.ashx?t=sec" width="100%" height="550"></iframe>
        """, unsafe_allow_html=True)
    else:
        st.markdown("[🌐 Finviz 히트맵 바로가기](https://finviz.com/map.ashx?t=sec)")

    st.markdown("---")
    st.markdown("### 💼 내 자산 트래커 요약")
    uploaded = st.file_uploader("보유 종목 CSV (ticker, avg_price, qty)", type="csv", key="home_tracker")
    if uploaded:
        df = pd.read_csv(uploaded)
        results = []
        for _, row in df.iterrows():
            try:
                data = yf.download(row['ticker'], period='5d')
                price = data['Close'].iloc[-1]
                pnl = (price - row['avg_price']) * row['qty']
                rate = ((price - row['avg_price']) / row['avg_price']) * 100
                results.append((row['ticker'], price, pnl, rate))
            except:
                continue
        if results:
            st.write("### 📊 현재 보유 종목 수익률:")
            summary = summarize_portfolio_with_gpt(results)
            st.markdown("### 🤖 GPT 포트폴리오 요약 분석")
            st.info(summary)
            for ticker, price, pnl, rate in results:
                st.metric(f"{ticker}", f"${price:.2f}", f"{rate:.2f}%")

    st.markdown("---")
    st.markdown("### 🔍 오늘의 추천 종목 (조건 기반)")
    etf_list = [
        "SPY", "QQQ", "VTI", "VOO", "ARKK", "XLE", "XLF", "XLV", "XLK", "XLY", "XLC", "XLI",
        "XLB", "XLRE", "XLU", "XBI", "SOXL", "TQQQ", "FNGU", "DIA", "IWM", "SCHD", "HDV", "BND"
    ]
    selected = []
    with st.spinner("📡 실시간 스캔 중..."):
        for sym in etf_list:
            try:
                df = yf.download(sym, period="6mo")
                df['RSI'] = ta.momentum.RSIIndicator(close=df['Close']).rsi()
                macd_diff = ta.trend.MACD(close=df['Close']).macd_diff()
                if df['RSI'].iloc[-1] < 30 and macd_diff.iloc[-1] > 0 and macd_diff.iloc[-2] < 0:
                    selected.append(sym)
            except:
                continue
    if selected:
        st.success("✅ 조건에 부합하는 추천 ETF:")
        st.write(", ".join(selected))
    else:
        st.warning("조건에 맞는 추천 종목이 없습니다.")

    st.markdown("---")
    st.markdown("### 📰 글로벌 투자 뉴스 (Investing.com)")
    news_list = fetch_investing_news()
    for news in news_list:
        st.markdown(news)
