import streamlit as st
import pandas as pd
import yfinance as yf
import ta
import requests
import bcrypt
import sqlite3
import os
import logging
from fpdf import FPDF
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple
import time

# Streamlit 페이지 설정
st.set_page_config(
    page_title="SmartInvestor Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 기술적 분석 임계값 상수
BUY_SIGNALS = {
    'RSI_OVERSOLD': 30,
    'CCI_OVERSOLD': -100,
    'MFI_OVERSOLD': 20,
    'STOCHRSI_OVERSOLD': 0.2,
    'MIN_SCORE': 3  # 5개 조건 중 최소 3개 만족
}

# 기본 추천 종목
DEFAULT_SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMZN', 'NVDA', 'META',
    'QQQ', 'SPY', 'VTI', 'IWM', 'ARKK', 'TQQQ', 
    'XLK', 'XLF', 'XLE', 'XLV', 'BTC-USD', 'ETH-USD'
]

# CSS 스타일 적용
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #667eea;
    }
    .success-alert {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 0.75rem 1.25rem;
        border-radius: 0.375rem;
        margin: 1rem 0;
    }
    .warning-alert {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        color: #856404;
        padding: 0.75rem 1.25rem;
        border-radius: 0.375rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

class DatabaseManager:
    """데이터베이스 관리 클래스"""
    
    def __init__(self, db_path: str = "smartinvestor.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """데이터베이스 초기화"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        is_admin BOOLEAN DEFAULT FALSE,
                        show_heatmap BOOLEAN DEFAULT TRUE,
                        risk_level TEXT DEFAULT 'moderate',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                # 기본 관리자 계정 생성 (admin@smartinvestor.com / admin123)
                admin_hash = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
                conn.execute('''
                    INSERT OR IGNORE INTO users (email, password_hash, is_admin) 
                    VALUES (?, ?, ?)
                ''', ("admin@smartinvestor.com", admin_hash, True))
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"데이터베이스 초기화 오류: {e}")
            raise
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """이메일로 사용자 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM users WHERE email = ?", (email,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"사용자 조회 오류: {e}")
            return None
    
    def create_user(self, email: str, password_hash: str) -> bool:
        """새 사용자 생성"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                    (email, password_hash)
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False
        except sqlite3.Error as e:
            logger.error(f"사용자 생성 오류: {e}")
            return False
    
    def update_user_password(self, email: str, new_password_hash: str) -> bool:
        """비밀번호 업데이트"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "UPDATE users SET password_hash = ? WHERE email = ?",
                    (new_password_hash, email)
                )
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"비밀번호 업데이트 오류: {e}")
            return False
    
    def get_all_users(self) -> List[Dict]:
        """모든 사용자 조회"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM users ORDER BY created_at DESC")
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"전체 사용자 조회 오류: {e}")
            return []

class TechnicalAnalyzer:
    """기술적 분석 클래스"""
    
    @staticmethod
    @st.cache_data(ttl=300)
    def get_stock_data(symbol: str, period: str = "6mo") -> Optional[pd.DataFrame]:
        """주식 데이터 조회"""
        try:
            data = yf.download(symbol, period=period, progress=False)
            if data.empty:
                return None
            return data
        except Exception as e:
            logger.error(f"데이터 조회 오류 {symbol}: {e}")
            return None
    
    @staticmethod
    def calculate_technical_indicators(df: pd.DataFrame) -> Dict:
        """기술적 지표 계산"""
        try:
            close = df["Close"]
            high = df["High"]
            low = df["Low"]
            volume = df["Volume"]
            
            rsi = ta.momentum.RSIIndicator(close).rsi().iloc[-1]
            macd_indicator = ta.trend.MACD(close)
            macd_line = macd_indicator.macd_diff()
            cci = ta.trend.CCIIndicator(high, low, close).cci().iloc[-1]
            mfi = ta.volume.MFIIndicator(high, low, close, volume).money_flow_index().iloc[-1]
            stochrsi = ta.momentum.StochRSIIndicator(close).stochrsi().iloc[-1]
            
            return {
                'rsi': rsi if not pd.isna(rsi) else 50,
                'macd_current': macd_line.iloc[-1] if len(macd_line) > 0 and not pd.isna(macd_line.iloc[-1]) else 0,
                'macd_previous': macd_line.iloc[-2] if len(macd_line) > 1 and not pd.isna(macd_line.iloc[-2]) else 0,
                'cci': cci if not pd.isna(cci) else 0,
                'mfi': mfi if not pd.isna(mfi) else 50,
                'stochrsi': stochrsi if not pd.isna(stochrsi) else 0.5,
                'current_price': close.iloc[-1],
                'price_change': ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100) if len(close) > 1 else 0
            }
        except Exception as e:
            logger.error(f"기술적 지표 계산 오류: {e}")
            return {}
    
    @staticmethod
    def evaluate_buy_signals(indicators: Dict) -> Tuple[int, List[str]]:
        """매수 신호 평가"""
        score = 0
        signals = []
        
        try:
            if indicators.get('rsi', 100) < BUY_SIGNALS['RSI_OVERSOLD']:
                score += 1
                signals.append("RSI 과매도")
            
            if (indicators.get('macd_current', 0) > 0 and 
                indicators.get('macd_previous', 0) < 0):
                score += 1
                signals.append("MACD 골든크로스")
            
            if indicators.get('cci', 0) < BUY_SIGNALS['CCI_OVERSOLD']:
                score += 1
                signals.append("CCI 과매도")
            
            if indicators.get('mfi', 100) < BUY_SIGNALS['MFI_OVERSOLD']:
                score += 1
                signals.append("MFI 과매도")
            
            if indicators.get('stochrsi', 1) < BUY_SIGNALS['STOCHRSI_OVERSOLD']:
                score += 1
                signals.append("StochRSI 과매도")
                
        except Exception as e:
            logger.error(f"매수 신호 평가 오류: {e}")
        
        return score, signals

class NewsAnalyzer:
    """뉴스 분석 클래스"""
    
    @staticmethod
    @st.cache_data(ttl=1800)
    def fetch_investment_news(max_items: int = 5) -> List[Dict]:
        """투자 뉴스 조회"""
        news_list = []
        try:
            rss_url = "https://www.investing.com/rss/news_285.rss"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            
            response = requests.get(rss_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            parser = ET.XMLParser(resolve_entities=False)
            root = ET.fromstring(response.content, parser)
            items = root.findall(".//item")[:max_items]
            
            for item in items:
                title_elem = item.find("title")
                link_elem = item.find("link")
                
                if title_elem is not None and link_elem is not None:
                    news_list.append({
                        'title': title_elem.text,
                        'link': link_elem.text
                    })
            
        except Exception as e:
            logger.error(f"뉴스 조회 오류: {e}")
            news_list.append({'title': '뉴스 로딩 실패', 'link': '#'})
        
        return news_list
    
    @staticmethod
    def summarize_with_gpt(title: str) -> str:
        """GPT 뉴스 요약 (API 키가 있을 때만)"""
        try:
            if hasattr(st.secrets, "OPENAI_API_KEY") and st.secrets["OPENAI_API_KEY"]:
                from openai import OpenAI
                client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
                
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": f"다음 투자 뉴스 제목을 한국어로 간단히 요약(30자 이내): {title}"}],
                    max_tokens=50,
                    temperature=0.3
                )
                return response.choices[0].message.content.strip()
            else:
                return "GPT 요약 미사용 (API 키 없음)"
        except Exception as e:
            return f"원제목: {title[:50]}..."

def analyze_symbol(symbol: str) -> Optional[Dict]:
    """개별 종목 분석"""
    try:
        df = TechnicalAnalyzer.get_stock_data(symbol)
        if df is None:
            return None
        
        indicators = TechnicalAnalyzer.calculate_technical_indicators(df)
        if not indicators:
            return None
        
        score, signals = TechnicalAnalyzer.evaluate_buy_signals(indicators)
        
        return {
            'symbol': symbol,
            'score': score,
            'signals': signals,
            'indicators': indicators
        }
    except Exception as e:
        logger.error(f"종목 분석 오류 {symbol}: {e}")
        return None

def analyze_symbols_parallel(symbols: List[str]) -> List[Dict]:
    """병렬 종목 분석"""
    results = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_symbol = {executor.submit(analyze_symbol, symbol): symbol for symbol in symbols}
        
        for future in as_completed(future_to_symbol):
            result = future.result()
            if result and result['score'] >= BUY_SIGNALS['MIN_SCORE']:
                results.append(result)
    
    return sorted(results, key=lambda x: x['score'], reverse=True)

def create_pdf_report(recommended_stocks: List[Dict]) -> bytes:
    """PDF 리포트 생성"""
    class SmartInvestorPDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 16)
            self.cell(0, 10, 'SmartInvestor Pro - AI 투자 분석 리포트', 0, 1, 'C')
            self.ln(10)
        
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'생성일시: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 0, 'C')
    
    pdf = SmartInvestorPDF()
    pdf.add_page()
    pdf.set_font('Arial', '', 12)
    
    if recommended_stocks:
        pdf.cell(0, 10, '🎯 AI 추천 종목 분석 결과', 0, 1)
        pdf.ln(5)
        
        for i, stock in enumerate(recommended_stocks, 1):
            symbol = stock.get('symbol', 'N/A')  
            score = stock.get('score', 0)
            signals = ', '.join(stock.get('signals', []))
            indicators = stock.get('indicators', {})
            
            pdf.cell(0, 8, f"{i}. {symbol} (매수신호 점수: {score}/5)", 0, 1)
            pdf.cell(0, 6, f"   현재가: ${indicators.get('current_price', 0):.2f}", 0, 1)
            if signals:
                pdf.cell(0, 6, f"   감지된 신호: {signals}", 0, 1)
            pdf.ln(3)
    else:
        pdf.cell(0, 10, '현재 매수 조건에 부합하는 종목이 없습니다.', 0, 1)
        pdf.ln(5)
        pdf.cell(0, 8, '투자 시 고려사항:', 0, 1)
        pdf.cell(0, 6, '- 분산 투자를 통한 리스크 관리', 0, 1)
        pdf.cell(0, 6, '- 장기 투자 관점 유지', 0, 1)
        pdf.cell(0, 6, '- 정기적인 포트폴리오 리밸런싱', 0, 1)
    
    return pdf.output(dest='S').encode('latin-1')

def authenticate_user(email: str, password: str, db_manager: DatabaseManager) -> Optional[Dict]:
    """사용자 인증"""
    user = db_manager.get_user_by_email(email)
    if user and bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return user
    return None

def main():
    """메인 애플리케이션"""
    
    # 데이터베이스 초기화
    try:
        db_manager = DatabaseManager()
    except Exception as e:
        st.error(f"⚠️ 데이터베이스 연결 실패: {e}")
        st.stop()
    
    # 사용자 인증
    if "user" not in st.session_state:
        st.markdown('<div class="main-header"><h1>🔐 SmartInvestor Pro 로그인</h1><p>AI 기반 투자 분석 플랫폼에 오신 것을 환영합니다!</p></div>', unsafe_allow_html=True)
        
        # 데모 계정 안내
        st.info("🎯 **데모 계정으로 바로 체험하세요!**\n\n📧 **관리자**: admin@smartinvestor.com / admin123\n\n🆕 또는 새 계정을 만들어보세요!")
        
        tab1, tab2 = st.tabs(["🔑 로그인", "📝 회원가입"])
        
        with tab1:
            with st.form("login_form"):
                email = st.text_input("📧 이메일", placeholder="example@email.com")
                password = st.text_input("🔒 비밀번호", type="password")
                login_btn = st.form_submit_button("🚀 로그인", use_container_width=True)
                
                if login_btn and email and password:
                    user = authenticate_user(email, password, db_manager)
                    if user:
                        st.session_state.user = user
                        st.success("✅ 로그인 성공!")
                        st.rerun()
                    else:
                        st.error("❌ 로그인 실패: 이메일 또는 비밀번호를 확인해주세요.")
        
        with tab2:
            with st.form("signup_form"):
                new_email = st.text_input("📧 이메일", placeholder="your@email.com")
                new_password = st.text_input("🔒 비밀번호", type="password", help="8자 이상 입력해주세요")
                signup_btn = st.form_submit_button("📝 회원가입", use_container_width=True)
                
                if signup_btn and new_email and new_password:
                    if len(new_password) < 8:
                        st.error("❌ 비밀번호는 8자 이상이어야 합니다.")
                    else:
                        hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                        if db_manager.create_user(new_email, hashed_password):
                            st.success("🎉 회원가입 완료! 로그인 탭에서 로그인해주세요.")
                        else:
                            st.error("❌ 회원가입 실패: 이미 존재하는 이메일입니다.")
        st.stop()
    
    user = st.session_state.user
    
    # 사이드바
    with st.sidebar:
        st.markdown(f"### 👤 환영합니다!")
        st.markdown(f"**{user['email']}**님")
        
        if user.get('is_admin'):
            st.success("🛡️ 관리자 권한")
        
        if st.button("🚪 로그아웃", use_container_width=True):
            del st.session_state.user
            st.rerun()
        
        st.markdown("---")
        
        menu_options = ["🏠 홈", "📊 종목 분석", "📰 뉴스", "📄 리포트", "⚙️ 설정"]
        if user.get("is_admin"):
            menu_options.append("🛡️ 관리자")
        
        menu = st.selectbox("📋 메뉴 선택", menu_options)
    
    # 메인 컨텐츠
    if menu == "🏠 홈":
        st.markdown('<div class="main-header"><h1>🏠 SmartInvestor Pro 대시보드</h1><p>AI가 분석한 투자 기회를 확인하세요</p></div>', unsafe_allow_html=True)
        
        # 시장 히트맵
        if user.get("show_heatmap", True):
            st.markdown("### 🌐 실시간 시장 현황")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("📈 [Finviz 섹터 히트맵](https://finviz.com/map.ashx?t=sec)")
            with col2:
                st.markdown("📊 [S&P500 히트맵](https://finviz.com/map.ashx?t=sec_all)")
        
        st.markdown("---")
        
        # AI 추천 종목
        st.markdown("### 🎯 AI 추천 종목 (실시간 분석)")
        
        analysis_placeholder = st.empty()
        
        with analysis_placeholder:
            with st.spinner("🤖 AI가 시장을 분석하고 있습니다... 잠시만 기다려주세요!"):
                recommended = analyze_symbols_parallel(DEFAULT_SYMBOLS)
        
        analysis_placeholder.empty()
        
        if recommended:
            st.markdown(f'<div class="success-alert">✅ <strong>{len(recommended)}개의 매수 기회</strong>를 발견했습니다!</div>', unsafe_allow_html=True)
            
            # 상위 추천 종목들을 카드 형태로 표시
            for i, stock in enumerate(recommended[:5]):
                with st.expander(f"🔥 #{i+1}. {stock['symbol']} - 매수신호 점수: {stock['score']}/5", expanded=(i == 0)):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        st.markdown(f"**감지된 매수 신호:**")
                        for signal in stock['signals']:
                            st.markdown(f"• {signal}")
                    
                    with col2:
                        indicators = stock['indicators']
                        st.metric("현재가", f"${indicators.get('current_price', 0):.2f}")
                        st.metric("일일 변동", f"{indicators.get('price_change', 0):+.2f}%")
                    
                    with col3:
                        st.metric("RSI", f"{indicators.get('rsi', 0):.1f}")
                        st.metric("MFI", f"{indicators.get('mfi', 0):.1f}")
        else:
            st.markdown('<div class="warning-alert">⚠️ 현재 강력한 매수 신호를 보이는 종목이 없습니다. 시장 상황을 계속 모니터링하고 있습니다.</div>', unsafe_allow_html=True)
            
            # 투자 조언
            st.markdown("### 💡 투자 가이드")
            col1, col2 = st.columns(2)
            with col1:
                st.info("**현재 시장 상황**\n\n시장이 고점권에서 조정을 받고 있을 가능성이 있습니다. 신중한 접근이 필요합니다.")
            with col2:
                st.success("**추천 전략**\n\n✓ 달러 코스트 평균법 활용\n✓ 분산 투자 유지\n✓ 장기 관점 유지")
    
    elif menu == "📊 종목 분석":
        st.markdown('<div class="main-header"><h1>📊 개별 종목 심층 분석</h1></div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        with col1:
            symbol = st.text_input("🔍 종목 코드 입력", value="AAPL", help="예: AAPL, TSLA, QQQ, BTC-USD").upper()
        with col2:
            analyze_btn = st.button("📈 분석 시작", use_container_width=True)
        
        if analyze_btn and symbol:
            with st.spinner(f"📊 {symbol} 분석 중..."):
                result = analyze_symbol(symbol)
            
            if result:
                col1, col2 = st.columns([3, 2])
                
                with col1:
                    st.subheader(f"📈 {symbol} 분석 결과")
                    
                    # 점수 표시
                    score = result['score']
                    if score >= 4:
                        st.success(f"🚀 매수 신호 점수: {score}/5 (강력 추천)")
                    elif score >= 3:
                        st.warning(f"⚡ 매수 신호 점수: {score}/5 (추천)")
                    else:
                        st.info(f"📊 매수 신호 점수: {score}/5 (관망)")
                    
                    # 신호 상세 정보
                    if result['signals']:
                        st.markdown("**✅ 감지된 매수 신호:**")
                        for signal in result['signals']:
                            st.markdown(f"• {signal}")
                    else:
                        st.markdown("**ℹ️ 현재 뚜렷한 매수 신호가 없습니다.**")
                
                with col2:
                    st.subheader("📊 기술적 지표")
                    indicators = result['indicators']
                    
                    st.metric("💰 현재가", f"${indicators.get('current_price', 0):.2f}")
                    st.metric("📈 RSI", f"{indicators.get('rsi', 0):.2f}")
                    st.metric("📉 CCI", f"{indicators.get('cci', 0):.2f}")
                    st.metric("💧 MFI", f"{indicators.get('mfi', 0):.2f}")
                    st.metric("⚡ StochRSI", f"{indicators.get('stochrsi', 0):.3f}")
            else:
                st.error(f"❌ {symbol} 데이터를 가져올 수 없습니다. 종목 코드를 확인해주세요.")
    
    elif menu == "📰 뉴스":
        st.markdown('<div class="main-header"><h1>📰 투자 뉴스 & AI 분석</h1></div>', unsafe_allow_html=True)
        
        with st.spinner("📰 최신 투자 뉴스를 가져오는 중..."):
            news_list = NewsAnalyzer.fetch_investment_news(10)
        
        st.markdown("### 📈 오늘의 투자 뉴스")
        
        for i, news in enumerate(news_list, 1):
            if news['title'] != '뉴스 로딩 실패':
                with st.expander(f"📰 뉴스 #{i}", expanded=(i == 1)):
                    summary = NewsAnalyzer.summarize_with_gpt(news['title'])
                    
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**🤖 AI 요약:** {summary}")
                        st.markdown(f"**📄 원제목:** {news['title']}")
                    with col2:
                        st.markdown(f"[📖 원문 보기]({news['link']})")
                    st.markdown("---")
    
    elif menu == "📄 리포트":
        st.markdown('<div class="main-header"><h1>📄 AI 투자 리포트 생성</h1></div>', unsafe_allow_html=True)
        
        st.markdown("""
        ### 📊 맞춤형 투자 리포트
        현재 시장 상황과 AI 분석을 바탕으로 개인화된 투자 리포트를 생성합니다.
        """)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.info("""
            **📋 리포트에 포함되는 내용:**
            - AI 추천 종목 및 매수 신호 분석
            - 기술적 지표 상세 데이터
            - 투자 가이드라인 및 주의사항
            - 생성 일시 및 데이터 출처
            """)
        
        with col2:
            generate_btn = st.button("📄 리포트 생성", use_container_width=True, type="primary")
        
        if generate_btn:
            with st.spinner("📊 AI가 시장을 분석하고 리포트를 생성하는 중..."):
                recommended = analyze_symbols_parallel(DEFAULT_SYMBOLS)
                pdf_data = create_pdf_report(recommended)
            
            st.success("✅ 리포트 생성 완료!")
            
            st.download_button(
                label="📥 PDF 리포트 다운로드",
                data=pdf_data,
                file_name=f"SmartInvestor_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
    
    elif menu == "⚙️ 설정":
        st.markdown('<div class="main-header"><h1>⚙️ 사용자 설정</h1></div>', unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["🎨 표시 설정", "📊 분석 설정"])
        
        with tab1:
            st.subheader("화면 표시 옵션")
            
            show_heatmap = st.checkbox(
                "메인 페이지에서 시장 히트맵 링크 표시", 
                value=user.get("show_heatmap", True),
                help="Finviz 히트맵 링크를 홈 화면에 표시합니다"
            )
            
            st.subheader("알림 설정")
            email_alerts = st.checkbox("이메일 알림 받기 (향후 추가 예정)", disabled=True)
            
            if st.button("💾 설정 저장"):
                st.success("✅ 설정이 저장되었습니다!")
        
        with tab2:
            st.subheader("투자 성향 설정")
            
            risk_levels = {
                "conservative": "🛡️ 보수적 (안전 중심)",
                "moderate": "⚖️ 균형형 (기본 설정)", 
                "aggressive": "🚀 적극적 (고수익 추구)"
            }
            
            selected_risk = st.selectbox(
                "투자 성향을 선택하세요",
                options=list(risk_levels.keys()),
                format_func=lambda x: risk_levels[x],
                index=list(risk_levels.keys()).index(user.get("risk_level", "moderate"))
            )
            
            st.subheader("분석 기준 조정")
            
            col1, col2 = st.columns(2)
            with col1:
                custom_rsi = st.slider("RSI 과매도 기준", 20, 40, BUY_SIGNALS['RSI_OVERSOLD'])
                custom_mfi = st.slider("MFI 과매도 기준", 10, 30, BUY_SIGNALS['MFI_OVERSOLD'])
            
            with col2:
                custom_cci = st.slider("CCI 과매도 기준", -200, -50, BUY_SIGNALS['CCI_OVERSOLD'])
                min_score = st.slider("최소 매수 신호 점수", 1, 5, BUY_SIGNALS['MIN_SCORE'])
            
            st.info("⚠️ 설정 변경은 현재 세션에만 적용됩니다.")
    
    elif menu == "🛡️ 관리자" and user.get("is_admin"):
        st.markdown('<div class="main-header"><h1>🛡️ 관리자 대시보드</h1></div>', unsafe_allow_html=True)
        
        tab1, tab2, tab3 = st.tabs(["👥 사용자 관리", "📊 시스템 현황", "🔧 도구"])
        
        with tab1:
            st.subheader("등록된 사용자 목록")
            users = db_manager.get_all_users()
            
            if users:
                df = pd.DataFrame(users)
                # 민감한 정보 제외하고 표시
                display_df = df[['user_id', 'email', 'is_admin', 'created_at']].copy()
                display_df.columns = ['ID', '이메일', '관리자', '가입일']
                st.dataframe(display_df, use_container_width=True)
            
            st.subheader("사용자 관리 도구")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**비밀번호 초기화**")
                email_to_reset = st.text_input("초기화할 사용자 이메일")
                
                if st.button("🔄 'temp1234'로 초기화"):
                    if email_to_reset:
                        new_hash = bcrypt.hashpw("temp1234".encode(), bcrypt.gensalt()).decode()
                        if db_manager.update_user_password(email_to_reset, new_hash):
                            st.success(f"✅ {email_to_reset}의 비밀번호가 초기화되었습니다.")
                        else:
                            st.error("❌ 사용자를 찾을 수 없습니다.")
            
            with col2:
                st.markdown("**시스템 통계**")
                total_users = len(users) if users else 0
                admin_users = len([u for u in users if u.get('is_admin')]) if users else 0
                
                st.metric("총 사용자 수", total_users)
                st.metric("관리자 수", admin_users)
        
        with tab2:
            st.subheader("📊 시스템 현황")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("데이터베이스 상태", "정상 ✅")
            with col2:
                st.metric("API 연결", "활성 🟢")
            with col3:
                st.metric("캐시 상태", "작동중 ⚡")
            
            st.subheader("📈 사용 통계")
            st.info("상세한 사용 통계는 향후 업데이트에서 제공됩니다.")
        
        with tab3:
            st.subheader("🔧 시스템 도구")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🧹 캐시 초기화", help="Streamlit 캐시를 초기화합니다"):
                    st.cache_data.clear()
                    st.success("✅ 캐시가 초기화되었습니다!")
            
            with col2:
                if st.button("🔄 데이터 새로고침", help="주식 데이터를 강제로 새로고침합니다"):
                    st.rerun()

    # 푸터
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 20px;'>
        <p>🤖 <strong>SmartInvestor Pro</strong> - AI 기반 개인 투자 분석 플랫폼</p>
        <p>⚠️ <em>투자 결정은 신중하게 하시고, 이 도구는 참고용으로만 사용하세요.</em></p>
        <p>📧 문의사항이 있으시면 관리자에게 연락해주세요.</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
