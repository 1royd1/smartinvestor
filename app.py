import streamlit as st
import pandas as pd
import yfinance as yf
import ta
import openai
import requests
import bcrypt
import os
from fpdf import FPDF
from datetime import datetime
import xml.etree.ElementTree as ET

st.set_page_config(page_title="SmartInvestor", layout="wide")

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
            return user.iloc[0].to_dict()
    return None

if "user" not in st.session_state:
    st.title("🔐 SmartInvestor 로그인")
    mode = st.radio("작업 선택", ["로그인", "회원가입"])
    email = st.text_input("이메일")
    password = st.text_input("비밀번호", type="password")
    if st.button("확인"):
        if mode == "로그인":
            user = authenticate(email, password)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("로그인 실패: 이메일 또는 비밀번호 오류")
        else:
            users = load_users()
            if email in users["email"].values:
                st.error("이미 존재하는 이메일입니다.")
            else:
                hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                user_id = len(users) + 1
                new_user = pd.DataFrame([[user_id, email, hashed, False, True]], columns=users.columns)
                users = pd.concat([users, new_user], ignore_index=True)
                save_users(users)
                st.success("회원가입 완료. 다시 로그인 해주세요.")
    st.stop()

user = st.session_state.user
st.sidebar.markdown(f"👤 {user['email']}님")
menu = st.sidebar.selectbox("메뉴", ["🏠 홈", "🧾 리포트", "🛡 관리자"])

if menu == "🏠 홈":
    st.title("🏠 대시보드")
    if user["show_heatmap"]:
        st.markdown("### 🌐 히트맵 (Finviz)")
        st.markdown("[🌐 히트맵 바로가기 (Finviz)](https://finviz.com/map.ashx?t=sec)")
    else:
        st.markdown("[🌐 히트맵 바로가기](https://finviz.com/map.ashx?t=sec)")

    st.markdown("### 🔍 추천 ETF (다중 기술지표)")
    etfs = ["SPY", "QQQ", "ARKK", "SOXL", "TQQQ", "VTI", "VOO", "XLF", "XLE", "XLK"]
    selected = []
    for sym in etfs:
        try:
            df = yf.download(sym, period="6mo")
            close = df["Close"]
            rsi = ta.momentum.RSIIndicator(close).rsi().iloc[-1]
            macd = ta.trend.MACD(close).macd_diff()
            cci = ta.trend.CCIIndicator(df["High"], df["Low"], close).cci().iloc[-1]
            mfi = ta.volume.MFIIndicator(df["High"], df["Low"], close, df["Volume"]).money_flow_index().iloc[-1]
            stochrsi = ta.momentum.StochRSIIndicator(close).stochrsi().iloc[-1]
            if rsi < 30 and macd.iloc[-1] > 0 and macd.iloc[-2] < 0 and cci < -100 and mfi < 20 and stochrsi < 0.2:
                selected.append(sym)
        except:
            continue
    if selected:
        st.success("추천 ETF: " + ", ".join(selected))
    else:
        st.warning("조건에 부합하는 ETF 없음.")

    st.markdown("### 📰 투자 뉴스 요약 (GPT)")
    def fetch_news():
        url = "https://www.investing.com/rss/news_285.rss"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")
        news = []
        for item in items[:5]:
            title = item.find("title").text
            link = item.find("link").text
            gpt_summary = title
            if "OPENAI_API_KEY" in st.secrets:
                from openai import OpenAI
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
                prompt = f"뉴스 제목을 한국어로 간단 요약해줘: {title}"
                gpt_resp = client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}])
                gpt_summary = response.choices[0].message.content.strip()
            summary_combined = f"**🧠 GPT 요약:** {gpt_summary}\\n[원문 보기]({link})"
            news.append(summary_combined)
        return news
    for n in fetch_news():
        st.markdown(n)

if menu == "🧾 리포트":
    st.title("📄 추천 리포트 다운로드")
    class PDF(FPDF):
        def header(self): self.cell(0, 10, "Recommendation Report", ln=True, align="C")
        def footer(self): self.set_y(-15); self.cell(0, 10, datetime.now().strftime("%Y-%m-%d %H:%M"), 0, 0, "C")
        def body(self, tickers):
            for i, t in enumerate(tickers, 1): self.cell(0, 10, f"{i}. {t}", ln=True)
    pdf = PDF()
    pdf.add_page()
    pdf.body(["TQQQ", "ARKK"])
    path = "/mnt/data/recommend_final.pdf"
    pdf.output(path)
    with open(path, "rb") as f:
        st.download_button("PDF 다운로드", f, file_name="report.pdf")

if menu == "🛡 관리자" and user["is_admin"]:
    st.title("🛡 관리자 기능")
    users = load_users()
    st.dataframe(users)
    email = st.text_input("초기화할 이메일")
    if st.button("비밀번호 초기화"):
        idx = users[users["email"] == email].index
        if not idx.empty:
            users.at[idx[0], "password_hash"] = bcrypt.hashpw("temp1234".encode(), bcrypt.gensalt()).decode()
            save_users(users)
            st.success("비밀번호가 temp1234로 초기화됨.")
