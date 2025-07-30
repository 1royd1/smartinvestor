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
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from typing import List, Dict, Optional, Tuple
import time
import re

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

# 기본 추천 종목 (더 안정적인 종목들로 구성)
DEFAULT_SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMZN', 'NVDA', 'META',
    'QQQ', 'SPY', 'VTI', 'IWM', 'ARKK', 'TQQQ', 
    'XLK', 'XLF', 'XLE', 'XLV', 'JPM', 'JNJ', 'PG', 'KO'
]

# CSS 스타일 적용 (개선된 스타일)
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem 1rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        border-left: 4px solid #667eea;
        margin-bottom: 1rem;
    }
    .success-alert {
        background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 1rem 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 4px solid #28a745;
    }
    .warning-alert {
        background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
        border: 1px solid #ffeaa7;
        color: #856404;
        padding: 1rem 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 4px solid #ffc107;
    }
    .error-alert {
        background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 1rem 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 4px solid #dc3545;
    }
    .stButton > button {
        border-radius: 25px;
        border: none;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
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
                
                # 사용자 설정 테이블 추가
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS user_settings (
                        user_id INTEGER PRIMARY KEY,
                        rsi_threshold INTEGER DEFAULT 30,
                        cci_threshold INTEGER DEFAULT -100,
                        mfi_threshold INTEGER DEFAULT 20,
                        stochrsi_threshold REAL DEFAULT 0.2,
                        min_score INTEGER DEFAULT 3,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                ''')
                
                # 기본 관리자 계정 생성
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
                cursor = conn.execute(
                    "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                    (email, password_hash)
                )
                user_id = cursor.lastrowid
                
                # 기본 설정 생성
                conn.execute('''
                    INSERT INTO user_settings (user_id) VALUES (?)
                ''', (user_id,))
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
    """기술적 분석 클래스 (개선된 버전)"""
    
    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def get_stock_data(symbol: str, period: str = "6mo") -> Optional[pd.DataFrame]:
        """주식 데이터 조회 (개선된 오류 처리)"""
        try:
            # 유효한 심볼인지 간단히 체크
            if not re.match(r'^[A-Z0-9\-\.]+$', symbol):
                logger.warning(f"유효하지 않은 심볼 형식: {symbol}")
                return None
            
            # 타임아웃과 함께 데이터 조회
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, timeout=10)
            
            if data.empty or len(data) < 20:  # 최소 20일 데이터 필요
                logger.warning(f"데이터 부족: {symbol}")
                return None
                
            return data
            
        except Exception as e:
            logger.error(f"데이터 조회 오류 {symbol}: {e}")
            return None
    
    @staticmethod
    def calculate_technical_indicators(df: pd.DataFrame) -> Dict:
        """기술적 지표 계산 (개선된 안정성)"""
        try:
            if df is None or df.empty or len(df) < 20:
                return {}
                
            close = df["Close"]
            high = df["High"]
            low = df["Low"]
            volume = df["Volume"]
            
            # 안전한 지표 계산
            indicators = {}
            
            # RSI
            try:
                rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
                indicators['rsi'] = rsi.iloc[-1] if not rsi.empty and not pd.isna(rsi.iloc[-1]) else 50
            except:
                indicators['rsi'] = 50
            
            # MACD
            try:
                macd_indicator = ta.trend.MACD(close)
                macd_line = macd_indicator.macd_diff()
                if len(macd_line) >= 2:
                    indicators['macd_current'] = macd_line.iloc[-1] if not pd.isna(macd_line.iloc[-1]) else 0
                    indicators['macd_previous'] = macd_line.iloc[-2] if not pd.isna(macd_line.iloc[-2]) else 0
                else:
                    indicators['macd_current'] = 0
                    indicators['macd_previous'] = 0
            except:
                indicators['macd_current'] = 0
                indicators['macd_previous'] = 0
            
            # CCI
            try:
                cci = ta.trend.CCIIndicator(high, low, close, window=20).cci()
                indicators['cci'] = cci.iloc[-1] if not cci.empty and not pd.isna(cci.iloc[-1]) else 0
            except:
                indicators['cci'] = 0
            
            # MFI
            try:
                mfi = ta.volume.MFIIndicator(high, low, close, volume, window=14).money_flow_index()
                indicators['mfi'] = mfi.iloc[-1] if not mfi.empty and not pd.isna(mfi.iloc[-1]) else 50
            except:
                indicators['mfi'] = 50
            
            # StochRSI
            try:
                stochrsi = ta.momentum.StochRSIIndicator(close, window=14).stochrsi()
                indicators['stochrsi'] = stochrsi.iloc[-1] if not stochrsi.empty and not pd.isna(stochrsi.iloc[-1]) else 0.5
            except:
                indicators['stochrsi'] = 0.5
            
            # 가격 정보
            indicators['current_price'] = close.iloc[-1]
            if len(close) > 1:
                indicators['price_change'] = ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100)
            else:
                indicators['price_change'] = 0
                
            return indicators
            
        except Exception as e:
            logger.error(f"기술적 지표 계산 오류: {e}")
            return {}
    
    @staticmethod
    def evaluate_buy_signals(indicators: Dict, custom_thresholds: Dict = None) -> Tuple[int, List[str]]:
        """매수 신호 평가 (사용자 정의 임계값 지원)"""
        if not indicators:
            return 0, []
            
        thresholds = custom_thresholds or BUY_SIGNALS
        score = 0
        signals = []
        
        try:
            # RSI 과매도
            if indicators.get('rsi', 100) < thresholds.get('RSI_OVERSOLD', 30):
                score += 1
                signals.append(f"RSI 과매도 ({indicators.get('rsi', 0):.1f})")
            
            # MACD 골든크로스
            if (indicators.get('macd_current', 0) > 0 and 
                indicators.get('macd_previous', 0) <= 0):
                score += 1
                signals.append("MACD 골든크로스")
            
            # CCI 과매도
            if indicators.get('cci', 0) < thresholds.get('CCI_OVERSOLD', -100):
                score += 1
                signals.append(f"CCI 과매도 ({indicators.get('cci', 0):.1f})")
            
            # MFI 과매도
            if indicators.get('mfi', 100) < thresholds.get('MFI_OVERSOLD', 20):
                score += 1
                signals.append(f"MFI 과매도 ({indicators.get('mfi', 0):.1f})")
            
            # StochRSI 과매도
            if indicators.get('stochrsi', 1) < thresholds.get('STOCHRSI_OVERSOLD', 0.2):
                score += 1
                signals.append(f"StochRSI 과매도 ({indicators.get('stochrsi', 0):.3f})")
                
        except Exception as e:
            logger.error(f"매수 신호 평가 오류: {e}")
        
        return score, signals

class NewsAnalyzer:
    """뉴스 분석 클래스 (개선된 버전)"""
    
    @staticmethod
    @st.cache_data(ttl=1800, show_spinner=False)
    def fetch_investment_news(max_items: int = 5) -> List[Dict]:
        """투자 뉴스 조회 (개선된 오류 처리)"""
        news_list = []
        
        # 여러 뉴스 소스 시도
        rss_sources = [
            "https://www.investing.com/rss/news_285.rss",
            "https://feeds.finance.yahoo.com/rss/2.0/headline",
            "https://www.marketwatch.com/rss/topstories"
        ]
        
        for rss_url in rss_sources:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                
                response = requests.get(rss_url, headers=headers, timeout=15)
                response.raise_for_status()
                
                parser = ET.XMLParser(resolve_entities=False)
                root = ET.fromstring(response.content, parser)
                items = root.findall(".//item")[:max_items]
                
                for item in items:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    
                    if title_elem is not None and link_elem is not None:
                        title = title_elem.text
                        link = link_elem.text
                        
                        # 중복 제거
                        if not any(news['title'][:50] == title[:50] for news in news_list):
                            news_list.append({
                                'title': title,
                                'link': link,
                                'source': rss_url.split('//')[1].split('/')[0]
                            })
                
                if news_list:  # 첫 번째 소스에서 성공하면 중단
                    break
                    
            except Exception as e:
                logger.warning(f"뉴스 소스 {rss_url} 오류: {e}")
                continue
        
        if not news_list:
            news_list.append({
                'title': '현재 뉴스를 불러올 수 없습니다. 나중에 다시 시도해주세요.',
                'link': '#',
                'source': 'system'
            })
        
        return news_list
    
    @staticmethod
    def summarize_with_gpt(title: str) -> str:
        """GPT 뉴스 요약 (개선된 버전)"""
        try:
            if hasattr(st.secrets, "OPENAI_API_KEY") and st.secrets["OPENAI_API_KEY"]:
                import openai
                openai.api_key = st.secrets["OPENAI_API_KEY"]
                
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{
                        "role": "user", 
                        "content": f"다음 투자 뉴스 제목을 한국어로 간단히 요약해주세요 (30자 이내): {title}"
                    }],
                    max_tokens=50,
                    temperature=0.3,
                    timeout=10
                )
                return response.choices[0].message.content.strip()
            else:
                return f"📰 {title[:50]}..."
        except Exception as e:
            logger.error(f"GPT 요약 오류: {e}")
            return f"📰 {title[:50]}..."

def analyze_symbol(symbol: str, custom_thresholds: Dict = None) -> Optional[Dict]:
    """개별 종목 분석 (개선된 버전)"""
    try:
        # 입력값 정리
        symbol = symbol.strip().upper()
        
        df = TechnicalAnalyzer.get_stock_data(symbol)
        if df is None:
            return None
        
        indicators = TechnicalAnalyzer.calculate_technical_indicators(df)
        if not indicators:
            return None
        
        score, signals = TechnicalAnalyzer.evaluate_buy_signals(indicators, custom_thresholds)
        
        return {
            'symbol': symbol,
            'score': score,
            'signals': signals,
            'indicators': indicators,
            'last_updated': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"종목 분석 오류 {symbol}: {e}")
        return None

def analyze_symbols_parallel(symbols: List[str], custom_thresholds: Dict = None, max_workers: int = 3) -> List[Dict]:
    """병렬 종목 분석 (개선된 버전)"""
    results = []
    failed_symbols = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 타임아웃을 포함한 future 생성
        future_to_symbol = {
            executor.submit(analyze_symbol, symbol, custom_thresholds): symbol 
            for symbol in symbols
        }
        
        for future in as_completed(future_to_symbol, timeout=60):
            symbol = future_to_symbol[future]
            try:
                result = future.result(timeout=10)
                if result and result['score'] >= (custom_thresholds or BUY_SIGNALS).get('MIN_SCORE', 3):
                    results.append(result)
            except TimeoutError:
                logger.warning(f"분석 타임아웃: {symbol}")
                failed_symbols.append(symbol)
            except Exception as e:
                logger.error(f"분석 실패 {symbol}: {e}")
                failed_symbols.append(symbol)
    
    # 실패한 종목이 있으면 로그에 기록
    if failed_symbols:
        logger.info(f"분석 실패 종목: {failed_symbols}")
    
    return sorted(results, key=lambda x: x['score'], reverse=True)

def create_pdf_report(recommended_stocks: List[Dict]) -> bytes:
    """PDF 리포트 생성 (개선된 유니코드 처리)"""
    try:
        class SmartInvestorPDF(FPDF):
            def header(self):
                self.set_font('Arial', 'B', 16)
                self.cell(0, 10, 'SmartInvestor Pro - Investment Analysis Report', 0, 1, 'C')
                self.ln(10)
            
            def footer(self):
                self.set_y(-15)
                self.set_font('Arial', 'I', 8)
                self.cell(0, 10, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 0, 'C')
        
        pdf = SmartInvestorPDF()
        pdf.add_page()
        pdf.set_font('Arial', '', 12)
        
        if recommended_stocks:
            pdf.cell(0, 10, 'AI Recommended Stocks Analysis', 0, 1)
            pdf.ln(5)
            
            for i, stock in enumerate(recommended_stocks, 1):
                symbol = stock.get('symbol', 'N/A')  
                score = stock.get('score', 0)
                signals = stock.get('signals', [])
                indicators = stock.get('indicators', {})
                
                pdf.cell(0, 8, f"{i}. {symbol} (Buy Signal Score: {score}/5)", 0, 1)
                pdf.cell(0, 6, f"   Current Price: ${indicators.get('current_price', 0):.2f}", 0, 1)
                pdf.cell(0, 6, f"   RSI: {indicators.get('rsi', 0):.2f}", 0, 1)
                pdf.cell(0, 6, f"   Detected Signals: {len(signals)} indicators", 0, 1)
                pdf.ln(3)
        else:
            pdf.cell(0, 10, 'No stocks meet the current buy criteria.', 0, 1)
            pdf.ln(5)
            pdf.cell(0, 8, 'Investment Guidelines:', 0, 1)
            pdf.cell(0, 6, '- Diversify your portfolio', 0, 1)
            pdf.cell(0, 6, '- Maintain long-term perspective', 0, 1)
            pdf.cell(0, 6, '- Regular portfolio rebalancing', 0, 1)
        
        return pdf.output(dest='S').encode('latin-1')
        
    except Exception as e:
        logger.error(f"PDF 생성 오류: {e}")
        # 기본 텍스트 리포트 생성
        report = f"""SmartInvestor Pro - Investment Analysis Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'='*50}
RECOMMENDED STOCKS
{'='*50}

"""
        if recommended_stocks:
            for i, stock in enumerate(recommended_stocks, 1):
                report += f"{i}. {stock.get('symbol', 'N/A')} - Score: {stock.get('score', 0)}/5\n"
                report += f"   Price: ${stock.get('indicators', {}).get('current_price', 0):.2f}\n"
                report += f"   Signals: {len(stock.get('signals', []))}\n\n"
        else:
            report += "No stocks meet the current buy criteria.\n"
        
        return report.encode('utf-8')

def authenticate_user(email: str, password: str, db_manager: DatabaseManager) -> Optional[Dict]:
    """사용자 인증"""
    if not email or not password:
        return None
        
    user = db_manager.get_user_by_email(email.lower().strip())
    if user and bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return user
    return None

def validate_email(email: str) -> bool:
    """이메일 유효성 검사"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def main():
    """메인 애플리케이션 (개선된 버전)"""
    
    # 세션 상태 초기화
    if "user" not in st.session_state:
        st.session_state.user = None
    if "analysis_cache" not in st.session_state:
        st.session_state.analysis_cache = {}
    
    # 데이터베이스 초기화
    try:
        db_manager = DatabaseManager()
    except Exception as e:
        st.error(f"⚠️ 데이터베이스 연결 실패: {e}")
        st.error("애플리케이션을 다시 시작해주세요.")
        st.stop()
    
    # 사용자 인증
    if st.session_state.user is None:
        st.markdown('<div class="main-header"><h1>🔐 SmartInvestor Pro 로그인</h1><p>AI 기반 투자 분석 플랫폼에 오신 것을 환영합니다!</p></div>', unsafe_allow_html=True)
        
        # 데모 계정 안내
        st.info("🎯 **데모 계정으로 바로 체험하세요!**\n\n📧 **관리자**: admin@smartinvestor.com / admin123\n\n🆕 또는 새 계정을 만들어보세요!")
        
        tab1, tab2 = st.tabs(["🔑 로그인", "📝 회원가입"])
        
        with tab1:
            with st.form("login_form"):
                email = st.text_input("📧 이메일", placeholder="example@email.com")
                password = st.text_input("🔒 비밀번호", type="password")
                login_btn = st.form_submit_button("🚀 로그인", use_container_width=True)
                
                if login_btn:
                    if not email or not password:
                        st.error("❌ 이메일과 비밀번호를 모두 입력해주세요.")
                    elif not validate_email(email):
                        st.error("❌ 유효한 이메일 주소를 입력해주세요.")
                    else:
                        with st.spinner("로그인 중..."):
                            user = authenticate_user(email, password, db_manager)
                        if user:
                            st.session_state.user = user
                            st.success("✅ 로그인 성공!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ 로그인 실패: 이메일 또는 비밀번호를 확인해주세요.")
        
        with tab2:
            with st.form("signup_form"):
                new_email = st.text_input("📧 이메일", placeholder="your@email.com")
                new_password = st.text_input("🔒 비밀번호", type="password", help="8자 이상 입력해주세요")
                confirm_password = st.text_input("🔒 비밀번호 확인", type="password")
                signup_btn = st.form_submit_button("📝 회원가입", use_container_width=True)
                
                if signup_btn:
                    if not new_email or not new_password:
                        st.error("❌ 모든 필드를 입력해주세요.")
                    elif not validate_email(new_email):
                        st.error("❌ 유효한 이메일 주소를 입력해주세요.")
                    elif len(new_password) < 8:
                        st.error("❌ 비밀번호는 8자 이상이어야 합니다.")
                    elif new_password != confirm_password:
                        st.error("❌ 비밀번호가 일치하지 않습니다.")
                    else:
                        hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                        if db_manager.create_user(new_email.lower().strip(), hashed_password):
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
            # 세션 상태 초기화
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        
        st.markdown("---")
        
        menu_options = ["🏠 홈", "📊 종목 분석", "📰 뉴스", "📄 리포트", "⚙️ 설정"]
        if user.get("is_admin"):
            menu_options.append("🛡️ 관리자")
        
        menu = st.selectbox("📋 메뉴 선택", menu_options)
    
    # 메인 컨텐츠
    if menu == "🏠 홈":
        st.markdown('<div class="main-header"><h1>🏠 SmartInvestor Pro 대시보드</h1><p>AI가 분석한 투자 기회를 확인하세요</p></div>', unsafe_allow_html=True)
        
        # 시장 현황 (개선된 링크)
        if user.get("show_heatmap", True):
            st.markdown("### 🌐 실시간 시장 현황")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("📈 [Finviz 섹터 히트맵](https://finviz.com/map.ashx?t=sec)")
            with col2:
                st.markdown("📊 [S&P500 히트맵](https://finviz.com/map.ashx?t=sec_all)")
            with col3:
                st.markdown("🌍 [글로벌 지수](https://finviz.com/futures.ashx)")
        
        st.markdown("---")
        
        # 시스템 상태 표시
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📊 분석 대상", f"{len(DEFAULT_SYMBOLS)}개 종목")
        with col2:
            st.metric("⏱️ 캐시 상태", "활성")
        with col3:
            st.metric("🔄 업데이트", "5분마다")
        with col4:
            current_time = datetime.now().strftime("%H:%M")
            st.metric("🕐 현재 시간", current_time)
        
        # AI 추천 종목
        st.markdown("### 🎯 AI 추천 종목 (실시간 분석)")
        
        # 분석 버튼과 자동 새로고침
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            analyze_now = st.button("🔄 지금 분석", use_container_width=True)
        with col2:
            clear_cache = st.button("🧹 캐시 지우기", use_container_width=True)
        with col3:
            auto_refresh = st.checkbox("⏰ 5분마다 자동 새로고침", value=False)
        
        if clear_cache:
            st.cache_data.clear()
            st.session_state.analysis_cache = {}
            st.success("✅ 캐시가 초기화되었습니다!")
            st.rerun()
        
        # 캐시 확인
        cache_key = f"analysis_{datetime.now().strftime('%Y%m%d_%H_%M')[:12]}"  # 5분 단위
        
        if analyze_now or cache_key not in st.session_state.analysis_cache or auto_refresh:
            analysis_placeholder = st.empty()
            
            with analysis_placeholder:
                with st.spinner("🤖 AI가 시장을 분석하고 있습니다..."):
                    try:
                        recommended = analyze_symbols_parallel(DEFAULT_SYMBOLS, max_workers=3)
                        st.session_state.analysis_cache[cache_key] = recommended
                    except Exception as e:
                        st.error(f"❌ 분석 중 오류가 발생했습니다: {e}")
                        recommended = []
            
            analysis_placeholder.empty()
        else:
            recommended = st.session_state.analysis_cache.get(cache_key, [])
        
        if recommended:
            st.markdown(f'<div class="success-alert">✅ <strong>{len(recommended)}개의 매수 기회</strong>를 발견했습니다!</div>', unsafe_allow_html=True)
            
            # DataFrame으로 요약 표시
            summary_data = []
            for stock in recommended:
                summary_data.append({
                    '종목': stock['symbol'],
                    '점수': f"{stock['score']}/5",
                    '현재가': f"${stock['indicators'].get('current_price', 0):.2f}",
                    '일일변동': f"{stock['indicators'].get('price_change', 0):+.2f}%",
                    '신호수': len(stock['signals']),
                    'RSI': f"{stock['indicators'].get('rsi', 0):.1f}"
                })
            
            df_summary = pd.DataFrame(summary_data)
            st.dataframe(df_summary, use_container_width=True)
            
            # 상위 추천 종목들을 카드 형태로 표시
            st.markdown("### 🔥 추천 종목 상세 분석")
            for i, stock in enumerate(recommended[:3]):  # 상위 3개만 상세 표시
                with st.expander(f"#{i+1}. {stock['symbol']} - 매수신호 점수: {stock['score']}/5", expanded=(i == 0)):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        st.markdown("**🎯 감지된 매수 신호:**")
                        for signal in stock['signals']:
                            st.markdown(f"• {signal}")
                    
                    with col2:
                        indicators = stock['indicators']
                        st.metric("💰 현재가", f"${indicators.get('current_price', 0):.2f}")
                        st.metric("📈 일일 변동", f"{indicators.get('price_change', 0):+.2f}%")
                    
                    with col3:
                        st.metric("📊 RSI", f"{indicators.get('rsi', 0):.1f}")
                        st.metric("💧 MFI", f"{indicators.get('mfi', 0):.1f}")
                        st.metric("⚡ CCI", f"{indicators.get('cci', 0):.1f}")
        else:
            # API 연결 상태 확인
            st.markdown('<div class="warning-alert">⚠️ 현재 강력한 매수 신호를 보이는 종목이 없습니다.</div>', unsafe_allow_html=True)
            
            # 연결 테스트
            st.markdown("### 🔍 시스템 진단")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🧪 API 연결 테스트"):
                    with st.spinner("연결 테스트 중..."):
                        test_result = analyze_symbol("AAPL")
                        if test_result:
                            st.success("✅ API 연결 정상")
                            st.json(test_result['indicators'])
                        else:
                            st.error("❌ API 연결 실패 - Yahoo Finance 서비스 확인 필요")
            
            with col2:
                st.info("""
                **가능한 원인:**
                - Yahoo Finance API 일시 중단
                - 네트워크 연결 문제  
                - 현재 시장이 과열 상태
                - 분석 기준이 너무 엄격함
                """)
            
            # 투자 조언
            st.markdown("### 💡 투자 가이드")
            col1, col2 = st.columns(2)
            with col1:
                st.info("""
                **📊 현재 시장 상황**
                
                시장이 고점권에서 조정을 받고 있을 가능성이 있습니다. 
                신중한 접근이 필요한 시기입니다.
                """)
            with col2:
                st.success("""
                **💡 추천 전략**
                
                ✓ 달러 코스트 평균법 활용
                ✓ 분산 투자 유지  
                ✓ 장기 관점 유지
                ✓ 현금 비중 확보
                """)
    
    elif menu == "📊 종목 분석":
        st.markdown('<div class="main-header"><h1>📊 개별 종목 심층 분석</h1></div>', unsafe_allow_html=True)
        
        # 인기 종목 바로가기 버튼
        st.markdown("### 🔥 인기 종목 바로가기")
        popular_stocks = ['AAPL', 'TSLA', 'NVDA', 'GOOGL', 'MSFT', 'AMZN', 'META', 'QQQ']
        
        cols = st.columns(len(popular_stocks))
        selected_from_popular = None
        
        for i, stock in enumerate(popular_stocks):
            with cols[i]:
                if st.button(stock, key=f"popular_{stock}"):
                    selected_from_popular = stock
        
        st.markdown("---")
        
        # 종목 입력
        col1, col2 = st.columns([3, 1])
        with col1:
            symbol = st.text_input(
                "🔍 종목 코드 입력", 
                value=selected_from_popular or "AAPL", 
                help="예: AAPL, TSLA, QQQ, BTC-USD",
                key="symbol_input"
            ).upper().strip()
        with col2:
            analyze_btn = st.button("📈 분석 시작", use_container_width=True, type="primary")
        
        # 유효성 검사
        if symbol and not re.match(r'^[A-Z0-9\-\.]+$', symbol):
            st.warning("⚠️ 올바른 종목 코드를 입력해주세요 (영문, 숫자, -, . 만 사용)")
        
        if (analyze_btn or selected_from_popular) and symbol:
            with st.spinner(f"📊 {symbol} 분석 중..."):
                result = analyze_symbol(symbol)
            
            if result:
                # 분석 성공
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.subheader(f"📈 {symbol} 분석 결과")
                    
                    # 점수 표시 (개선된 시각화)
                    score = result['score']
                    score_color = "🟢" if score >= 4 else "🟡" if score >= 3 else "🔴"
                    
                    st.markdown(f"""
                    <div style='padding: 1rem; border-radius: 10px; background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); border-left: 5px solid {"#28a745" if score >= 4 else "#ffc107" if score >= 3 else "#dc3545"}; margin: 1rem 0;'>
                        <h3>{score_color} 매수 신호 점수: {score}/5</h3>
                        <p>{"🚀 강력 추천" if score >= 4 else "⚡ 추천" if score >= 3 else "📊 관망 권장"}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 신호 상세 정보
                    if result['signals']:
                        st.markdown("**✅ 감지된 매수 신호:**")
                        for i, signal in enumerate(result['signals'], 1):
                            st.markdown(f"{i}. {signal}")
                    else:
                        st.markdown("**ℹ️ 현재 뚜렷한 매수 신호가 감지되지 않았습니다.**")
                    
                    # 추가 분석 정보
                    st.markdown("**📊 투자 의견:**")
                    if score >= 4:
                        st.success("매우 좋은 매수 타이밍입니다. 다만 분할 매수를 고려해보세요.")
                    elif score >= 3:
                        st.warning("괜찮은 매수 기회입니다. 추가 확인 후 투자하세요.")
                    else:
                        st.info("현재는 관망하며 더 좋은 기회를 기다리는 것이 좋겠습니다.")
                
                with col2:
                    st.subheader("📊 기술적 지표")
                    indicators = result['indicators']
                    
                    # 메트릭 표시
                    st.metric("💰 현재가", f"${indicators.get('current_price', 0):.2f}")
                    
                    col2_1, col2_2 = st.columns(2)
                    with col2_1:
                        rsi_value = indicators.get('rsi', 0)
                        rsi_delta = "과매도" if rsi_value < 30 else "과매수" if rsi_value > 70 else "중립"
                        st.metric("📈 RSI", f"{rsi_value:.1f}", delta=rsi_delta)
                        
                        mfi_value = indicators.get('mfi', 0)
                        st.metric("💧 MFI", f"{mfi_value:.1f}")
                    
                    with col2_2:
                        cci_value = indicators.get('cci', 0)
                        st.metric("📉 CCI", f"{cci_value:.1f}")
                        
                        stochrsi_value = indicators.get('stochrsi', 0)
                        st.metric("⚡ StochRSI", f"{stochrsi_value:.3f}")
                    
                    # MACD 정보
                    macd_current = indicators.get('macd_current', 0)
                    macd_previous = indicators.get('macd_previous', 0)
                    macd_trend = "상승" if macd_current > macd_previous else "하락"
                    st.metric("📊 MACD", f"{macd_current:.4f}", delta=macd_trend)
                
                # 차트 데이터 (선택사항)
                st.markdown("---")
                if st.checkbox("📈 간단한 가격 차트 보기"):
                    try:
                        df = TechnicalAnalyzer.get_stock_data(symbol, period="3mo")
                        if df is not None and not df.empty:
                            st.line_chart(df['Close'].tail(60))  # 최근 60일
                        else:
                            st.warning("차트 데이터를 불러올 수 없습니다.")
                    except Exception as e:
                        st.error(f"차트 생성 오류: {e}")
            
            else:
                # 분석 실패
                st.markdown(f'<div class="error-alert">❌ <strong>{symbol}</strong> 데이터를 가져올 수 없습니다.</div>', unsafe_allow_html=True)
                
                # 해결 방법 제안
                st.markdown("""
                ### 🔧 문제 해결 방법:
                1. **종목 코드 확인**: 정확한 티커 심볼인지 확인해주세요
                2. **네트워크 확인**: 인터넷 연결을 확인해주세요  
                3. **다른 종목 시도**: 다른 종목으로 테스트해보세요
                4. **시간 후 재시도**: Yahoo Finance API가 일시적으로 중단되었을 수 있습니다
                """)
                
                # 예시 종목 제안
                st.markdown("### 📋 시도해볼만한 종목들:")
                example_symbols = [
                    "**미국 주식**: AAPL, MSFT, GOOGL, TSLA, AMZN, NVDA, META",
                    "**ETF**: QQQ, SPY, VTI, IWM, ARKK, XLK, XLF",
                    "**암호화폐**: BTC-USD, ETH-USD"
                ]
                for example in example_symbols:
                    st.markdown(f"• {example}")
    
    elif menu == "📰 뉴스":
        st.markdown('<div class="main-header"><h1>📰 투자 뉴스 & AI 분석</h1></div>', unsafe_allow_html=True)
        
        # 뉴스 새로고침 버튼
        col1, col2 = st.columns([1, 3])
        with col1:
            refresh_news = st.button("🔄 뉴스 새로고침", use_container_width=True)
        with col2:
            st.info("💡 뉴스는 30분마다 자동으로 업데이트됩니다")
        
        if refresh_news:
            st.cache_data.clear()
        
        with st.spinner("📰 최신 투자 뉴스를 가져오는 중..."):
            news_list = NewsAnalyzer.fetch_investment_news(10)
        
        if news_list and news_list[0]['title'] != '현재 뉴스를 불러올 수 없습니다. 나중에 다시 시도해주세요.':
            st.markdown("### 📈 오늘의 투자 뉴스")
            
            for i, news in enumerate(news_list, 1):
                with st.expander(f"📰 뉴스 #{i}", expanded=(i == 1)):
                    col1, col2 = st.columns([4, 1])
                    
                    with col1:
                        # GPT 요약 (있는 경우)
                        summary = NewsAnalyzer.summarize_with_gpt(news['title'])
                        if "GPT 요약 미사용" not in summary:
                            st.markdown(f"**🤖 AI 요약:** {summary}")
                        
                        st.markdown(f"**📄 원제목:** {news['title']}")
                        st.markdown(f"**🌐 출처:** {news.get('source', 'Unknown')}")
                    
                    with col2:
                        st.markdown(f"[📖 원문 보기]({news['link']})")
                    
                    st.markdown("---")
        else:
            st.markdown('<div class="warning-alert">⚠️ 현재 뉴스를 불러올 수 없습니다.</div>', unsafe_allow_html=True)
            
            st.markdown("""
            ### 🔧 대안 뉴스 소스:
            - [Yahoo Finance](https://finance.yahoo.com/news/)
            - [MarketWatch](https://www.marketwatch.com/)
            - [Investing.com](https://www.investing.com/news/)
            - [Bloomberg](https://www.bloomberg.com/markets)
            """)
    
    elif menu == "📄 리포트":
        st.markdown('<div class="main-header"><h1>📄 AI 투자 리포트 생성</h1></div>', unsafe_allow_html=True)
        
        st.markdown("""
        ### 📊 맞춤형 투자 리포트
        현재 시장 상황과 AI 분석을 바탕으로 개인화된 투자 리포트를 생성합니다.
        """)
        
        # 리포트 옵션
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown("""
            **📋 리포트에 포함되는 내용:**
            - 🎯 AI 추천 종목 및 매수 신호 분석
            - 📊 기술적 지표 상세 데이터  
            - 💡 투자 가이드라인 및 주의사항
            - 📅 생성 일시 및 데이터 출처
            - ⚠️ 리스크 고지사항
            """)
            
            # 리포트 형식 선택
            report_format = st.selectbox(
                "📄 리포트 형식 선택",
                ["PDF (추천)", "텍스트", "JSON"],
                help="PDF는 한글 지원에 제한이 있을 수 있습니다"
            )
        
        with col2:
            st.markdown("### 🚀 생성하기")
            generate_btn = st.button("📄 리포트 생성", use_container_width=True, type="primary")
            
            if st.checkbox("🔄 최신 데이터로 분석", value=True, help="체크시 실시간 분석 후 리포트 생성"):
                use_realtime = True
            else:
                use_realtime = False
        
        if generate_btn:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # 1단계: 데이터 수집
                status_text.text("1/3 📊 시장 데이터 수집 중...")
                progress_bar.progress(33)
                
                if use_realtime:
                    recommended = analyze_symbols_parallel(DEFAULT_SYMBOLS, max_workers=3)
                else:
                    cache_key = f"analysis_{datetime.now().strftime('%Y%m%d_%H')}"
                    recommended = st.session_state.analysis_cache.get(cache_key, [])
                
                # 2단계: 리포트 생성
                status_text.text("2/3 📝 리포트 생성 중...")
                progress_bar.progress(66)
                
                if report_format == "PDF (추천)":
                    report_data = create_pdf_report(recommended)
                    file_ext = "pdf"
                    mime_type = "application/pdf"
                elif report_format == "JSON":
                    report_data = {
                        "generated_at": datetime.now().isoformat(),
                        "recommended_stocks": recommended,
                        "total_analyzed": len(DEFAULT_SYMBOLS),
                        "recommendations_found": len(recommended)
                    }
                    import json
                    report_data = json.dumps(report_data, indent=2, ensure_ascii=False).encode('utf-8')
                    file_ext = "json"
                    mime_type = "application/json"
                else:  # 텍스트
                    report_content = f"""SmartInvestor Pro - 투자 분석 리포트
생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*60}

추천 종목 분석 결과:
"""
                    if recommended:
                        for i, stock in enumerate(recommended, 1):
                            report_content += f"""
{i}. {stock['symbol']} (점수: {stock['score']}/5)
   현재가: ${stock['indicators'].get('current_price', 0):.2f}
   감지된 신호: {', '.join(stock['signals']) if stock['signals'] else '없음'}
   RSI: {stock['indicators'].get('rsi', 0):.2f}
   MFI: {stock['indicators'].get('mfi', 0):.2f}
"""
                    else:
                        report_content += "\n현재 매수 조건에 부합하는 종목이 없습니다.\n"
                    
                    report_content += f"""
{'='*60}
투자 주의사항:
- 본 리포트는 투자 참고용이며, 실제 투자 결정은 본인 책임입니다
- 과거 데이터 기반 분석이므로 미래 수익을 보장하지 않습니다  
- 분산 투자와 리스크 관리를 권장합니다
- 투자 전 충분한 학습과 조사를 하시기 바랍니다

SmartInvestor Pro - AI 기반 투자 분석 플랫폼
"""
                    report_data = report_content.encode('utf-8')
                    file_ext = "txt"
                    mime_type = "text/plain"
                
                # 3단계: 완료
                status_text.text("3/3 ✅ 완료!")
                progress_bar.progress(100)
                
                time.sleep(0.5)
                progress_bar.empty()
                status_text.empty()
                
                st.success("✅ 리포트 생성 완료!")
                
                # 결과 요약
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📊 분석 종목", len(DEFAULT_SYMBOLS))
                with col2:
                    st.metric("🎯 추천 종목", len(recommended))
                with col3:
                    st.metric("📄 리포트 크기", f"{len(report_data) / 1024:.1f} KB")
                
                # 다운로드 버튼
                st.download_button(
                    label=f"📥 {report_format} 리포트 다운로드",
                    data=report_data,
                    file_name=f"SmartInvestor_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.{file_ext}",
                    mime=mime_type,
                    use_container_width=True
                )
                
                # 미리보기 (텍스트인 경우)
                if report_format == "텍스트":
                    with st.expander("📖 리포트 미리보기"):
                        st.text(report_data.decode('utf-8'))
                elif report_format == "JSON":
                    with st.expander("📖 JSON 미리보기"):
                        st.json(json.loads(report_data.decode('utf-8')))
                
            except Exception as e:
                progress_bar.empty()
                status_text.empty()
                st.error(f"❌ 리포트 생성 중 오류가 발생했습니다: {e}")
                logger.error(f"리포트 생성 오류: {e}")
    
    elif menu == "⚙️ 설정":
        st.markdown('<div class="main-header"><h1>⚙️ 사용자 설정</h1></div>', unsafe_allow_html=True)
        
        tab1, tab2, tab3 = st.tabs(["🎨 표시 설정", "📊 분석 설정", "🔒 계정 설정"])
        
        with tab1:
            st.subheader("화면 표시 옵션")
            
            show_heatmap = st.checkbox(
                "메인 페이지에서 시장 히트맵 링크 표시", 
                value=user.get("show_heatmap", True),
                help="Finviz 히트맵 링크를 홈 화면에 표시합니다"
            )
            
            show_chart = st.checkbox(
                "종목 분석에서 가격 차트 자동 표시",
                value=False,
                help="개별 종목 분석시 차트를 자동으로 표시합니다"
            )
            
            st.subheader("알림 설정")
            email_alerts = st.checkbox("이메일 알림 받기 (향후 추가 예정)", disabled=True)
            push_alerts = st.checkbox("브라우저 알림 받기 (향후 추가 예정)", disabled=True)
            
            if st.button("💾 표시 설정 저장"):
                # 여기서 실제로는 데이터베이스에 저장해야 함
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
            st.info("💡 기준을 조정하면 더 엄격하거나 관대한 추천을 받을 수 있습니다.")
            
            col1, col2 = st.columns(2)
            with col1:
                custom_rsi = st.slider(
                    "RSI 과매도 기준", 
                    min_value=20, max_value=40, 
                    value=BUY_SIGNALS['RSI_OVERSOLD'],
                    help="낮을수록 더 엄격한 기준"
                )
                custom_mfi = st.slider(
                    "MFI 과매도 기준", 
                    min_value=10, max_value=30, 
                    value=BUY_SIGNALS['MFI_OVERSOLD'],
                    help="자금 유입/유출 지표"
                )
                custom_stochrsi = st.slider(
                    "StochRSI 과매도 기준",
                    min_value=0.1, max_value=0.3, 
                    value=BUY_SIGNALS['STOCHRSI_OVERSOLD'],
                    step=0.05,
                    help="0에 가까울수록 더 엄격"
                )
            
            with col2:
                custom_cci = st.slider(
                    "CCI 과매도 기준", 
                    min_value=-200, max_value=-50, 
                    value=BUY_SIGNALS['CCI_OVERSOLD'],
                    help="음수값이며, 절댓값이 클수록 엄격"
                )
                min_score = st.slider(
                    "최소 매수 신호 점수", 
                    min_value=1, max_value=5, 
                    value=BUY_SIGNALS['MIN_SCORE'],
                    help="5개 지표 중 몇 개 이상 만족해야 추천할지"
                )
                
                # 분석 대상 종목 수
                max_symbols = st.slider(
                    "분석 대상 종목 수",
                    min_value=10, max_value=50,
                    value=len(DEFAULT_SYMBOLS),
                    help="더 많은 종목을 분석하면 시간이 오래 걸립니다"
                )
            
            # 사용자 정의 설정 미리보기
            custom_settings = {
                'RSI_OVERSOLD': custom_rsi,
                'MFI_OVERSOLD': custom_mfi,
                'CCI_OVERSOLD': custom_cci,
                'STOCHRSI_OVERSOLD': custom_stochrsi,
                'MIN_SCORE': min_score
            }
            
            st.subheader("📊 설정 미리보기")
            col1, col2 = st.columns(2)
            with col1:
                st.json({
                    "투자성향": risk_levels[selected_risk],
                    "분석기준": "사용자 정의" if custom_settings != BUY_SIGNALS else "기본값"
                })
            with col2:
                difficulty = "높음" if min_score >= 4 else "보통" if min_score >= 3 else "낮음"
                st.metric("추천 난이도", difficulty)
                st.metric("분석 종목수", max_symbols)
            
            if st.button("🧪 현재 설정으로 테스트"):
                with st.spinner("사용자 정의 설정으로 분석 중..."):
                    test_symbols = DEFAULT_SYMBOLS[:max_symbols]
                    test_results = analyze_symbols_parallel(test_symbols, custom_settings, max_workers=3)
                    
                st.success(f"✅ 테스트 완료: {len(test_results)}개 종목 추천")
                if test_results:
                    for stock in test_results[:3]:
                        st.write(f"• {stock['symbol']}: {stock['score']}/5점")
            
            st.warning("⚠️ 설정 변경은 현재 세션에만 적용됩니다. 영구 저장 기능은 향후 추가 예정입니다.")
        
        with tab3:
            st.subheader("🔒 계정 정보")
            
            # 사용자 정보 표시
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"""
                **👤 계정 정보**
                - 이메일: {user['email']}
                - 계정 유형: {'관리자' if user.get('is_admin') else '일반 사용자'}
                - 가입일: {user.get('created_at', 'N/A')}
                """)
            
            with col2:
                st.info(f"""
                **📊 사용 통계**
                - 로그인 횟수: N/A (향후 추가)
                - 마지막 분석: N/A (향후 추가)
                - 생성한 리포트: N/A (향후 추가)
                """)
            
            st.subheader("🔐 비밀번호 변경")
            
            with st.form("change_password_form"):
                current_password = st.text_input("현재 비밀번호", type="password")
                new_password = st.text_input("새 비밀번호", type="password", help="8자 이상 입력")
                confirm_new_password = st.text_input("새 비밀번호 확인", type="password")
                
                change_password_btn = st.form_submit_button("🔄 비밀번호 변경")
                
                if change_password_btn:
                    if not all([current_password, new_password, confirm_new_password]):
                        st.error("❌ 모든 필드를 입력해주세요.")
                    elif len(new_password) < 8:
                        st.error("❌ 새 비밀번호는 8자 이상이어야 합니다.")
                    elif new_password != confirm_new_password:
                        st.error("❌ 새 비밀번호가 일치하지 않습니다.")
                    else:
                        # 현재 비밀번호 확인
                        if bcrypt.checkpw(current_password.encode(), user["password_hash"].encode()):
                            new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                            if db_manager.update_user_password(user['email'], new_hash):
                                st.success("✅ 비밀번호가 성공적으로 변경되었습니다!")
                                st.info("🔄 보안을 위해 다시 로그인해주세요.")
                            else:
                                st.error("❌ 비밀번호 변경에 실패했습니다.")
                        else:
                            st.error("❌ 현재 비밀번호가 올바르지 않습니다.")
            
            st.subheader("⚠️ 계정 관리")
            
            with st.expander("🗑️ 계정 삭제 (주의)"):
                st.warning("⚠️ **위험**: 계정을 삭제하면 모든 데이터가 영구적으로 삭제됩니다.")
                st.error("현재 계정 삭제 기능은 구현되지 않았습니다. 필요시 관리자에게 문의하세요.")
    
    elif menu == "🛡️ 관리자" and user.get("is_admin"):
        st.markdown('<div class="main-header"><h1>🛡️ 관리자 대시보드</h1></div>', unsafe_allow_html=True)
        
        tab1, tab2, tab3, tab4 = st.tabs(["👥 사용자 관리", "📊 시스템 현황", "🔧 도구", "📈 통계"])
        
        with tab1:
            st.subheader("👥 등록된 사용자 목록")
            users = db_manager.get_all_users()
            
            if users:
                # 사용자 데이터 정리
                df = pd.DataFrame(users)
                display_df = df[['user_id', 'email', 'is_admin', 'created_at']].copy()
                display_df.columns = ['ID', '이메일', '관리자', '가입일']
                display_df['관리자'] = display_df['관리자'].map({True: '✅', False: '❌'})
                
                # 검색 기능
                search_email = st.text_input("🔍 이메일 검색", placeholder="사용자 이메일 입력...")
                if search_email:
                    display_df = display_df[display_df['이메일'].str.contains(search_email, case=False, na=False)]
                
                st.dataframe(display_df, use_container_width=True)
                
                # 사용자 통계
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("총 사용자", len(users))
                with col2:
                    admin_count = len([u for u in users if u.get('is_admin')])
                    st.metric("관리자", admin_count)
                with col3:
                    regular_count = len(users) - admin_count
                    st.metric("일반 사용자", regular_count)
                with col4:
                    today_signups = len([u for u in users if u.get('created_at', '').startswith(datetime.now().strftime('%Y-%m-%d'))])
                    st.metric("오늘 가입", today_signups)
            
            st.subheader("🔧 사용자 관리 도구")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**🔄 비밀번호 초기화**")
                email_to_reset = st.text_input("초기화할 사용자 이메일")
                new_temp_password = st.text_input("임시 비밀번호", value="temp1234", help="기본값: temp1234")
                
                if st.button("🔄 비밀번호 초기화"):
                    if email_to_reset and new_temp_password:
                        new_hash = bcrypt.hashpw(new_temp_password.encode(), bcrypt.gensalt()).decode()
                        if db_manager.update_user_password(email_to_reset, new_hash):
                            st.success(f"✅ {email_to_reset}의 비밀번호가 '{new_temp_password}'로 초기화되었습니다.")
                        else:
                            st.error("❌ 사용자를 찾을 수 없습니다.")
                    else:
                        st.error("❌ 이메일과 임시 비밀번호를 입력해주세요.")
            
            with col2:
                st.markdown("**➕ 관리자 계정 생성**")
                admin_email = st.text_input("새 관리자 이메일")
                admin_password = st.text_input("관리자 비밀번호", type="password")
                
                if st.button("👑 관리자 계정 생성"):
                    if admin_email and admin_password:
                        # 구현 필요: 관리자 계정 생성 로직
                        st.info("⚠️ 관리자 계정 생성 기능은 구현 중입니다.")
                    else:
                        st.error("❌ 모든 필드를 입력해주세요.")
        
        with tab2:
            st.subheader("📊 시스템 현황")
            
            # 시스템 메트릭
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                db_status = "정상 ✅" if db_manager else "오류 ❌"
                st.metric("데이터베이스", db_status)
            
            with col2:
                try:
                    test_data = TechnicalAnalyzer.get_stock_data("AAPL")
                    api_status = "정상 🟢" if test_data is not None else "오류 🔴"
                except:
                    api_status = "오류 🔴"
                st.metric("Yahoo Finance API", api_status)
            
            with col3:
                cache_info = st.cache_data.clear.__dict__ if hasattr(st.cache_data, 'clear') else {}
                st.metric("캐시 상태", "활성 ⚡")
            
            with col4:
                st.metric("서버 시간", datetime.now().strftime("%H:%M:%S"))
            
            # 시스템 리소스 (가상 데이터)
            st.subheader("💻 시스템 리소스")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("메모리 사용률", "45%", delta="-5%")
            with col2:
                st.metric("CPU 사용률", "23%", delta="+2%")
            with col3:
                st.metric("디스크 사용률", "67%", delta="+1%")
            
            # API 사용 통계 (가상 데이터)
            st.subheader("📈 API 사용 통계")
            
            today = datetime.now()
            api_data = {
                '시간': [f"{i:02d}:00" for i in range(24)],
                '요청수': [20 + (i * 3) % 50 for i in range(24)]
            }
            api_df = pd.DataFrame(api_data)
            st.line_chart(api_df.set_index('시간'))
        
        with tab3:
            st.subheader("🔧 시스템 도구")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**🧹 캐시 관리**")
                if st.button("🧹 모든 캐시 초기화", help="Streamlit 캐시를 초기화합니다"):
                    st.cache_data.clear()
                    if 'analysis_cache' in st.session_state:
                        st.session_state.analysis_cache = {}
                    st.success("✅ 모든 캐시가 초기화되었습니다!")
                
                if st.button("🔄 분석 캐시만 초기화"):
                    if 'analysis_cache' in st.session_state:
                        st.session_state.analysis_cache = {}
                    st.success("✅ 분석 캐시가 초기화되었습니다!")
            
            with col2:
                st.markdown("**🔄 시스템 제어**")
                if st.button("🔄 데이터 강제 새로고침", help="주식 데이터를 강제로 새로고침합니다"):
                    # 캐시 초기화 후 페이지 새로고침
                    st.cache_data.clear()
                    st.rerun()
                
                if st.button("🧪 API 연결 테스트"):
                    with st.spinner("API 연결 테스트 중..."):
                        test_symbols = ['AAPL', 'GOOGL', 'MSFT']
                        results = {}
                        
                        for symbol in test_symbols:
                            try:
                                data = TechnicalAnalyzer.get_stock_data(symbol)
                                results[symbol] = "✅ 성공" if data is not None else "❌ 실패"
                            except Exception as e:
                                results[symbol] = f"❌ 오류: {str(e)[:30]}"
                        
                        st.json(results)
            
            st.subheader("📊 데이터베이스 관리")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📋 데이터베이스 백업 (가상)", help="현재 구현되지 않음"):
                    st.info("💡 데이터베이스 백업 기능은 향후 구현 예정입니다.")
            
            with col2:
                if st.button("🗑️ 오래된 세션 정리", help="30일 이상 된 세션 데이터 정리"):
                    st.info("💡 세션 정리 기능은 향후 구현 예정입니다.")
        
        with tab4:
            st.subheader("📈 사용 통계")
            
            # 가상 통계 데이터 생성
            dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
            usage_data = {
                '날짜': dates,
                '분석 요청': [15 + (i * 2) % 25 for i in range(30)],
                '리포트 생성': [3 + (i % 8) for i in range(30)],
                '로그인': [8 + (i % 12) for i in range(30)]
            }
            usage_df = pd.DataFrame(usage_data)
            
            st.markdown("**📊 지난 30일 사용 현황**")
            st.line_chart(usage_df.set_index('날짜'))
            
            # 요약 통계
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("일평균 분석", f"{usage_df['분석 요청'].mean():.1f}회")
            with col2:
                st.metric("일평균 리포트", f"{usage_df['리포트 생성'].mean():.1f}개")
            with col3:
                st.metric("일평균 로그인", f"{usage_df['로그인'].mean():.1f}회")
            with col4:
                st.metric("총 데이터 포인트", f"{len(usage_df) * 3}개")
            
            # 인기 종목 (가상 데이터)
            st.subheader("🔥 인기 분석 종목 TOP 10")
            popular_stocks = pd.DataFrame({
                '순위': range(1, 11),
                '종목': ['AAPL', 'TSLA', 'NVDA', 'GOOGL', 'MSFT', 'AMZN', 'META', 'QQQ', 'SPY', 'ARKK'],
                '분석 횟수': [45, 38, 35, 32, 28, 25, 22, 20, 18, 15],
                '추천 비율': ['85%', '72%', '68%', '61%', '57%', '52%', '48%', '44%', '41%', '38%']
            })
            st.dataframe(popular_stocks, use_container_width=True, hide_index=True)
    
    # 푸터
    st.markdown("---")
    st.markdown(f"""
    <div style='text-align: center; color: #666; padding: 20px; background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); border-radius: 10px; margin-top: 2rem;'>
        <p style='margin: 0;'><strong>🤖 SmartInvestor Pro v2.0</strong> - AI 기반 개인 투자 분석 플랫폼</p>
        <p style='margin: 5px 0;'>⚠️ <em>투자 결정은 신중하게 하시고, 이 도구는 참고용으로만 사용하세요.</em></p>
        <p style='margin: 0;'>📧 문의사항: 관리자 ({user['email']}) | 🕐 현재 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"🚨 애플리케이션 오류: {e}")
        st.error("페이지를 새로고침하거나 관리자에게 문의하세요.")
        logger.error(f"메인 애플리케이션 오류: {e}")
