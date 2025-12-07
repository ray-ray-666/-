import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit.components.v1 as components

# --- 1. 全局配置與 CSS 暴力放大 (視覺優化) ---
st.set_page_config(page_title="TitanTrade V5 - 全火力指揮官", layout="wide", page_icon="🦁")

st.markdown("""
    <style>
    /* 引入科技字體 */
    @import url('https://fonts.googleapis.com/css2?family=Exo+2:wght@500;700&family=Noto+Sans+TC:wght@500;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Exo 2', 'Noto Sans TC', sans-serif;
        font-size: 18px !important; /* 基礎字體加大 */
    }

    /* 背景深色化 */
    .stApp { background-color: #000000; }
    
    /* 側邊欄優化 */
    [data-testid="stSidebar"] {
        background-color: #0f111a;
        border-right: 2px solid #222;
    }
    [data-testid="stSidebar"] h1 {
        font-size: 36px !important;
        color: #FFD700 !important;
        text-align: center;
        text-shadow: 0 0 10px #FFD700;
    }
    .stRadio label {
        font-size: 22px !important; /* 選單字體加大 */
        color: #ffffff !important;
        margin-top: 10px;
    }
    
    /* 數據卡片放大 */
    div[data-testid="stMetricValue"] {
        font-size: 32px !important;
        color: #00f2ff !important;
        text-shadow: 0 0 5px rgba(0, 242, 255, 0.5);
    }
    div[data-testid="stMetricLabel"] {
        font-size: 18px !important;
        color: #aaaaaa !important;
    }
    
    /* 分析報告區塊 */
    .analysis-box {
        background-color: #111;
        border: 1px solid #333;
        padding: 25px;
        border-radius: 15px;
        margin-bottom: 20px;
    }
    h3, h4 { font-size: 26px !important; }
    p, li { font-size: 20px !important; line-height: 1.6 !important; }
    
    </style>
    """, unsafe_allow_html=True)

# --- 2. 側邊欄 ---
with st.sidebar:
    st.title("🦁 TITAN V5")
    market_type = st.radio(
        "資產市場", 
        ["🇺🇸 美股", "🇹🇼 台股", "₿ 加密貨幣", "📈 ETF"],
        index=0
    )
    
    if "美股" in market_type:
        default_ticker, tv_exch = "NVDA", "NASDAQ"
    elif "台股" in market_type:
        default_ticker, tv_exch = "2330", "TWSE"
    elif "加密" in market_type:
        default_ticker, tv_exch = "BTC-USD", "BINANCE"
    else:
        default_ticker, tv_exch = "QQQ", "AMEX"

    user_input = st.text_input("輸入代號", default_ticker)
    
    interval_map = {"15分鐘": "15m", "30分鐘": "30m", "1小時": "1h", "4小時": "4h", "日線": "1d", "周線": "1wk"}
    selected_label = st.selectbox("週期", list(interval_map.keys()), index=2)
    interval_code = interval_map[selected_label]

    # 代號處理
    if "台股" in market_type or (market_type == "📈 ETF" and user_input.isdigit()):
        yf_ticker = f"{user_input}.TW" if not user_input.endswith(".TW") else user_input
        tv_symbol = user_input
    else:
        yf_ticker = user_input
        tv_symbol = user_input.replace("-USD", "USDT")
        
    if st.button("🚀 強制刷新數據", type="primary"):
        st.cache_data.clear()

# --- 3. 數據與指標運算 (核心引擎) ---
def get_data_with_indicators(ticker, interval):
    try:
        # 抓取數據
        if interval == "4h":
            df = yf.Ticker(ticker).history(period="730d", interval="1h", prepost=True)
            if df.empty: return None
            agg = {'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}
            df = df.resample('4h').agg(agg).dropna()
        else:
            p_map = {"15m":"60d", "30m":"60d", "1h":"730d", "1d":"5y", "1wk":"10y"}
            df = yf.Ticker(ticker).history(period=p_map.get(interval,"2y"), interval=interval, prepost=True)
            
        if df.empty: return None
        
        # === 指標計算全家桶 ===
        close = df['Close']
        high = df['High']
        low = df['Low']
        
        # 1. MACD
        exp12 = close.ewm(span=12, adjust=False).mean()
        exp26 = close.ewm(span=26, adjust=False).mean()
        df['MACD'] = exp12 - exp26
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['Hist'] = df['MACD'] - df['Signal']
        
        # 2. RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + gain/loss))
        
        # 3. KD (Stochastic)
        low_min = low.rolling(9).min()
        high_max = high.rolling(9).max()
        df['RSV'] = (close - low_min) / (high_max - low_min) * 100
        df['K'] = df['RSV'].ewm(alpha=1/3, adjust=False).mean()
        df['D'] = df['K'].ewm(alpha=1/3, adjust=False).mean()
        
        # 4. 布林通道 & 寬度 (Bandwidth)
        df['MA20'] = close.rolling(20).mean()
        df['STD20'] = close.rolling(20).std()
        df['Upper'] = df['MA20'] + (df['STD20'] * 2)
        df['Lower'] = df['MA20'] - (df['STD20'] * 2)
        df['Bandwidth'] = (df['Upper'] - df['Lower']) / df['MA20'] # 通道寬度 (看壓縮/發散)
        
        # 5. ATR (真實波幅 - 用於計算風險)
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        df['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR'] = df['TR'].rolling(14).mean()
        
        # 6. OBV (能量潮)
        df['OBV'] = (np.sign(close.diff()) * df['Volume']).fillna(0).cumsum()
        
        # 7. MA
        df['MA60'] = close.rolling(60).mean()
        df['EMA200'] = close.ewm(span=200, adjust=False).mean()

        return df
    except Exception as e:
        return None

# 獲取情緒 (模擬)
def get_sentiment():
    try:
        # 簡單模擬，真實環境建議接 API
        vix = yf.Ticker("^VIX").history(period="2d")['Close'].iloc[-1]
        score = max(min(100 - (vix - 10) * 2.5, 100), 0)
        return score, vix
    except:
        return 50, 20

df = get_data_with_indicators(yf_ticker, interval_code)
fg_score, vix_val = get_sentiment()

# --- 4. 頂部儀表板 ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("TITAN 代號", user_input)
c2.metric("Fear & Greed", f"{fg_score:.0f}", "貪婪" if fg_score>60 else "恐慌" if fg_score<40 else "中性")
c3.metric("VIX 恐慌指數", f"{vix_val:.2f}", "高風險" if vix_val>25 else "低風險", delta_color="inverse")
if df is not None:
    c4.metric("最新價格", f"{df['Close'].iloc[-1]:.2f}", f"{df['Close'].iloc[-1]-df['Close'].iloc[-2]:.2f}")

# --- 5. 主內容 ---
tab1, tab2, tab3 = st.tabs(["⚡ AI 戰術分析與圖表", "📊 TradingView 模式", "🧮 獲利試算"])

with tab1:
    if df is not None and len(df) > 60:
        last = df.iloc[-1]
        
        # === A. 互動式技術圖表 (Plotly Subplots) ===
        # 建立 3 行圖表 (主圖, MACD, KD)
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2],
                            subplot_titles=(f"{yf_ticker} 價格走勢", "MACD 動能", "KD 隨機指標"))

        # 1. 主圖 (K線 + MA + BB)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                                     name='K線', increasing_line_color='#00ff00', decreasing_line_color='#ff0000'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=1.5), name='MA20'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Upper'], line=dict(color='gray', width=1, dash='dot'), name='BB上'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Lower'], line=dict(color='gray', width=1, dash='dot'), name='BB下'), row=1, col=1)

        # 2. MACD (Bar + Lines)
        colors = ['#00ff00' if v >= 0 else '#ff0000' for v in df['Hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['Hist'], marker_color=colors, name='MACD柱'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='#00d4ff', width=1), name='快線'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='#ff9900', width=1), name='慢線'), row=2, col=1)

        # 3. KD
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='#ff00ff', width=1), name='K值'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='white', width=1), name='D值'), row=3, col=1)
        
        # 設定預設顯示範圍 (解決 K 棒黏在一起的問題)
        # 預設只顯示最後 100 根，但保留前面數據可滑動
        start_idx = max(0, len(df) - 100)
        start_date = df.index[start_idx]
        end_date = df.index[-1]

        fig.update_layout(
            height=800, # 圖表拉高
            xaxis_rangeslider_visible=False,
            paper_bgcolor='black',
            plot_bgcolor='#0e0e0e',
            font=dict(color='white', size=14),
            dragmode='pan', # 預設拖曳
            xaxis=dict(range=[start_date, end_date]), # 關鍵：鎖定初始範圍
            showlegend=True
        )
        st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True}) # 開啟滾輪縮放

        # === B. AI 戰略分析報告 (邏輯判斷) ===
        st.markdown("### 🦁 AI 戰略指揮中心")
        
        # 1. 綜合評分邏輯
        score = 0
        signals = []
        
        # 趨勢
        if last['Close'] > last['MA20']: score += 20; signals.append("✅ 站上月線 (短多)")
        if last['Close'] > last['EMA200']: score += 20; signals.append("✅ 站上年線 (長多)")
        
        # 指標
        if last['RSI'] < 30: score += 15; signals.append("✅ RSI 超賣 (反彈機會)")
        elif last['RSI'] > 70: score -= 15; signals.append("⚠️ RSI 超買 (過熱)")
        
        if last['MACD'] > last['Signal']: score += 10; signals.append("✅ MACD 黃金交叉")
        else: score -= 10; signals.append("🔻 MACD 死亡交叉")
        
        if last['K'] > last['D'] and last['K'] < 20: score += 10; signals.append("✅ KD 低檔金叉")
        if last['Bandwidth'] < 0.05: signals.append("⚡ 布林通道極度壓縮 (變盤前兆)")
        
        # OBV 趨勢
        obv_trend = "資金流入" if df['OBV'].iloc[-1] > df['OBV'].iloc[-5] else "資金流出"
        
        # 2. 生成建議
        atr_sl = last['ATR'] * 2
        rec_color = "#00ff00" if score > 20 else "#ff0000" if score < -20 else "#ffff00"
        rec_text = "積極做多" if score > 20 else "偏空調節" if score < -20 else "區間震盪"
        
        st.markdown(f"""
        <div class="analysis-box" style="border-left: 5px solid {rec_color};">
            <h2 style="color:{rec_color}">🛡️ 總指揮建議：{rec_text} (信心分: {score})</h2>
            <hr style="border-color: #333;">
            <div style="display: flex; flex-wrap: wrap; gap: 20px;">
                <div style="flex: 1;">
                    <h4>📊 關鍵數據透視</h4>
                    <ul>
                        <li><b>RSI (14):</b> {last['RSI']:.1f}</li>
                        <li><b>KD (9,3,3):</b> K={last['K']:.1f}, D={last['D']:.1f}</li>
                        <li><b>OBV 能量:</b> {obv_trend}</li>
                        <li><b>ATR 波動:</b> {last['ATR']:.2f} (高風險)</li>
                        <li><b>布林寬度:</b> {last['Bandwidth']:.3f}</li>
                    </ul>
                </div>
                <div style="flex: 1;">
                    <h4>🎯 進出場策略 (參考 ATR)</h4>
                    <ul>
                        <li><b>若是做多：</b> 建議止損設在 <span style="color:#ff4444">${(last['Close'] - atr_sl):.2f}</span></li>
                        <li><b>若是做空：</b> 建議止損設在 <span style="color:#ff4444">${(last['Close'] + atr_sl):.2f}</span></li>
                        <li><b>訊號解讀：</b> {', '.join(signals)}</li>
                    </ul>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    else:
        st.warning("數據讀取中... 請稍候")

with tab2:
    tv_int = {"15m":"15", "1h":"60", "4h":"240", "1d":"D", "1wk":"W"}.get(interval_code, "D")
    components.html(f"""
    <div class="tradingview-widget-container">
      <div id="tradingview_chart"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "width": "100%", "height": 800, "symbol": "{tv_exch}:{tv_symbol}",
        "interval": "{tv_int}", "timezone": "Asia/Taipei", "theme": "dark",
        "style": "1", "locale": "zh_TW", "toolbar_bg": "#f1f3f6",
        "enable_publishing": false, "allow_symbol_change": true,
        "container_id": "tradingview_chart"
      }});
      </script>
    </div>
    """, height=810)

with tab3:
    st.markdown("### 🧮 交易計算機")
    cols = st.columns(3)
    capital = cols[0].number_input("本金 (U)", value=1000.0)
    leverage = cols[1].slider("槓桿", 1, 100, 10)
    direction = cols[2].radio("方向", ["多", "空"])
    
    entry = st.number_input("進場價", value=last['Close'] if df is not None else 0.0)
    exit_p = st.number_input("出場價", value=last['Close']*1.05 if df is not None else 0.0)
    
    if st.button("計算損益"):
        size = capital * leverage
        if direction == "多":
            pnl = size * ((exit_p - entry)/entry)
        else:
            pnl = size * ((entry - exit_p)/entry)
            
        st.markdown(f"### 預估損益: :{'green' if pnl>0 else 'red'}[${pnl:.2f}] (ROE: {pnl/capital*100:.2f}%)")