import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objs as go
import openai
import ta
import requests
import os
import bcrypt
import json
from fpdf import FPDF
from datetime import datetime

st.set_page_config(page_title="SmartInvestor", layout="wide")

# 사용자 인증 관련 로직
def load_users():
    if os.path.exists("users.csv"):
        return pd.read_csv("users.csv")
    else:
        return pd.DataFrame(columns=["user_id", "email", "password_hash", "is_admin", "show_heatmap"])

def save_users(df):
    df.to_csv("users.csv", index=False)

def authenticate(email, password):
    users = load_users()
    user = users[users["email"] == email]
    if not user.empty:
        stored_hash = user.iloc[0]["password_hash"]
        if bcrypt.checkpw(password.encode(), stored_hash.encode()):
            return user.iloc[0]
    return None

def register_user(email, password, is_admin=False):
    users = load_users()
    if email in users["email"].values:
        return False, "이미 존재하는 이메일입니다."
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user_id = len(users) + 1
    new_user = pd.DataFrame([[user_id, email, hashed, is_admin, True]], columns=users.columns)
    users = pd.concat([users, new_user], ignore_index=True)
    save_users(users)
    return True, "회원가입 성공"

def load_portfolio(user_id):
    path = f"portfolio_{user_id}.csv"
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame(columns=["ticker", "avg_price", "qty"])

def save_portfolio(user_id, df):
    df.to_csv(f"portfolio_{user_id}.csv", index=False)

# 로그인 UI
if "user" not in st.session_state:
    st.title("🔐 SmartInvestor 로그인")
    mode = st.radio("작업 선택", ["로그인", "회원가입"])
    email = st.text_input("이메일")
    password = st.text_input("비밀번호", type="password")
    if st.button("확인"):
        if mode == "로그인":
            user = authenticate(email, password)
            if user:
                st.session_state.user = dict(user)
                st.experimental_rerun()
            else:
                st.error("로그인 실패: 이메일 또는 비밀번호가 잘못되었습니다.")
        else:
            success, msg = register_user(email, password)
            if success:
                st.success(msg)
            else:
                st.error(msg)
    st.stop()

# 로그인 후 진입
user = st.session_state.user
st.sidebar.markdown(f"👤 {user['email']}님 환영합니다.")
menu = st.sidebar.selectbox("메뉴", ["🏠 홈", "📊 분석", "🧾 리포트", "🛡 관리자"] if user["is_admin"] else ["🏠 홈", "📊 분석", "🧾 리포트"])

# Finviz 히트맵 + 추천 + 뉴스
if menu == "🏠 홈":
    st.title("🏠 대시보드")
    if user["show_heatmap"] and st.session_state.get("is_mobile") != True:
        st.markdown("### 🌐 히트맵 (Finviz)")
        st.markdown('<iframe src="https://finviz.com/map.ashx?t=sec" width="100%" height="600"></iframe>', unsafe_allow_html=True)
    else:
        st.markdown("[🌐 히트맵 바로가기](https://finviz.com/map.ashx?t=sec)")

    st.markdown("### 💼 내 포트폴리오")
    portfolio_df = load_portfolio(user["user_id"])
    file = st.file_uploader("CSV 업로드", type="csv")
    if file:
        uploaded_df = pd.read_csv(file)
        save_portfolio(user["user_id"], uploaded_df)
        portfolio_df = uploaded_df
    if not portfolio_df.empty:
        st.dataframe(portfolio_df)

    st.markdown("### 🔍 추천 ETF")
    etfs = ["SPY", "QQQ", "VTI", "ARKK", "TQQQ", "SOXL"]
    selected = []
    for ticker in etfs:
        try:
            df = yf.download(ticker, period="6mo")
            rsi = ta.momentum.RSIIndicator(df["Close"]).rsi().iloc[-1]
            macd = ta.trend.MACD(df["Close"]).macd_diff().iloc[-1]
            if rsi < 30 and macd > 0:
                selected.append(ticker)
        except:
            pass
    st.write("추천 종목:", selected)

    st.markdown("### 📰 투자 뉴스 (Investing.com 요약)")
    def fetch_news():
        try:
            url = "https://www.investing.com/rss/news_285.rss"
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")
            news = []
            for item in items[:5]:
                title = item.find("title").text
                link = item.find("link").text
                summary = title
                if "OPENAI_API_KEY" in st.secrets:
                    openai.api_key = st.secrets["OPENAI_API_KEY"]
                    prompt = f"뉴스 제목을 한국어로 요약해줘: {title}"
                    gpt_resp = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}])
                    summary = gpt_resp.choices[0].message.content.strip()
                news.append(f"- [{summary}]({link})")
            return news
        except:
            return ["❌ 뉴스 로딩 실패"]

    for n in fetch_news():
        st.markdown(n)

# PDF 생성
elif menu == "🧾 리포트":
    st.title("📄 추천 리포트 다운로드")
    def generate_pdf(tickers):
        class PDF(FPDF):
            def header(self):
                self.set_font("Arial", "B", 14)
                self.cell(0, 10, "추천 ETF 리포트", ln=True, align="C")
                self.ln(10)
            def footer(self):
                self.set_y(-15)
                self.set_font("Arial", "I", 8)
                self.cell(0, 10, datetime.now().strftime("%Y-%m-%d %H:%M"), align="C")
            def add_body(self, tickers):
                self.set_font("Arial", "", 12)
                for i, t in enumerate(tickers, 1):
                    self.cell(0, 10, f"{i}. {t}", ln=True)

        pdf = PDF()
        pdf.add_page()
        pdf.add_body(tickers)
        path = "/mnt/data/recommendation.pdf"
        pdf.output(path)
        return path

    recs = ["TQQQ", "SOXL", "ARKK"]
    pdf_path = generate_pdf(recs)
    with open(pdf_path, "rb") as f:
        st.download_button("📥 PDF 다운로드", f, file_name="ETF_추천.pdf")

# 관리자
elif menu == "🛡 관리자" and user["is_admin"]:
    st.title("🛡 사용자 관리")
    users = load_users()
    st.dataframe(users)
    target_email = st.text_input("비밀번호 초기화할 이메일")
    if st.button("초기화"):
        idx = users[users["email"] == target_email].index
        if not idx.empty:
            new_hash = bcrypt.hashpw("temp1234".encode(), bcrypt.gensalt()).decode()
            users.at[idx[0], "password_hash"] = new_hash
            save_users(users)
            st.success("비밀번호가 'temp1234'로 초기화되었습니다.")
        else:
            st.warning("해당 이메일 없음")
