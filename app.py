import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit.components.v1 as components

# --- 1. 頁面設定 (加入 CSS 優化) ---
st.set_page_config(page_title="AlphaTrader - 智能交易中控台", layout="wide", page_icon="⚡")

# 自定義 CSS 讓介面更帥氣
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .stMetric {
        background-color: #262730;
        border: 1px solid #464b5f;
        padding: 10px;
        border-radius: 5px;
    }
    h1, h2, h3 {
        color: #00d4ff !important; 
        font-family: 'Roboto', sans-serif;
    }
    .report-card {
        background-color: #1c1f26;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #00d4ff;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("⚡ AlphaTrader 智能交易中控台")

# --- 2. 側邊欄：超級選單 ---
st.sidebar.header("🛸 戰情室設定")

market_type = st.sidebar.radio("資產類別", ["🇺🇸 美股個股", "🇹🇼 台股個股", "💰 加密貨幣", "📊 ETF (美/台)"], index=0)

# 預設代號邏輯
if market_type == "🇺🇸 美股個股":
    default_ticker = "NVDA"
    tv_exchange = "NASDAQ"
    input_help = "輸入代號 (如 AAPL, TSLA)"
elif market_type == "🇹🇼 台股個股":
    default_ticker = "2330"
    tv_exchange = "TWSE"
    input_help = "輸入代號 (如 2330, 2603)"
elif market_type == "💰 加密貨幣":
    default_ticker = "BTC-USD"
    tv_exchange = "BINANCE"
    input_help = "輸入代號 (如 ETH-USD)"
else: # ETF
    default_ticker = "0050"
    tv_exchange = "TWSE" # 預設給台股，美股需自動切換
    input_help = "輸入代號 (如 0050, 00878, VOO, QQQ)"

user_input = st.sidebar.text_input("輸入資產代號", default_ticker, help=input_help)

# 處理代號後綴
if (market_type == "🇹🇼 台股個股" or (market_type == "📊 ETF (美/台)" and user_input.isdigit())):
    # 如果是純數字 (像 0050 或 2330)，認定為台股
    yf_ticker = f"{user_input}.TW" if not user_input.endswith(".TW") else user_input
    tv_symbol = user_input
    tv_exchange = "TWSE"
else:
    # 美股或加密貨幣
    yf_ticker = user_input
    tv_symbol = user_input.replace("-USD", "USDT")
    if market_type == "📊 ETF (美/台)" and not user_input.isdigit():
        tv_exchange = "AMEX" # 美股 ETF 常見交易所

# 週期設定
interval_map = {
    "⚡ 15分鐘 (短沖)": "15m", 
    "⚡ 30分鐘 (當沖)": "30m", 
    "🕐 1小時 (短波)": "1h",
    "🕓 4小時 (波段)": "4h",
    "📅 日線 (趨勢)": "1d", 
    "📆 周線 (長線)": "1wk"
}
selected_label = st.sidebar.selectbox("K線週期", list(interval_map.keys()), index=3)
interval_code = interval_map[selected_label]

# --- 3. 核心運算引擎 (含 4H 合成 & 進階指標) ---
def get_data(ticker, interval_label):
    try:
        # === 週期處理邏輯 ===
        if interval_label in ["15m", "30m"]:
            df = yf.Ticker(ticker).history(period="60d", interval=interval_label)
        elif interval_label == "1h":
            df = yf.Ticker(ticker).history(period="730d", interval="1h")
        elif interval_label == "1d":
            df = yf.Ticker(ticker).history(period="5y", interval="1d")
        elif interval_label == "1wk":
            df = yf.Ticker(ticker).history(period="10y", interval="1wk")
        elif interval_label == "4h":
            # 4小時合成魔法
            df_1h = yf.Ticker(ticker).history(period="730d", interval="1h")
            if df_1h.empty: return None
            agg_dict = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
            df = df_1h.resample('4h').agg(agg_dict).dropna()
        else:
            return None

        if df.empty: return None
        return df
    except:
        return None

def calculate_advanced_indicators(df):
    df = df.copy()
    close = df['Close']
    high = df['High']
    low = df['Low']

    # 1. RSI (14)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # 2. MACD (12, 26, 9)
    exp12 = close.ewm(span=12, adjust=False).mean()
    exp26 = close.ewm(span=26, adjust=False).mean()
    df['MACD'] = exp12 - exp26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Hist'] = df['MACD'] - df['Signal']

    # 3. KD 隨機指標 (9, 3, 3)
    low_min = low.rolling(9).min()
    high_max = high.rolling(9).max()
    df['RSV'] = (close - low_min) / (high_max - low_min) * 100
    df['K'] = df['RSV'].ewm(alpha=1/3, adjust=False).mean()
    df['D'] = df['K'].ewm(alpha=1/3, adjust=False).mean()

    # 4. 布林通道 & 寬度 (20, 2)
    df['MA20'] = close.rolling(20).mean()
    std = close.rolling(20).std()
    df['Upper'] = df['MA20'] + (std * 2)
    df['Lower'] = df['MA20'] - (std * 2)
    df['BandWidth'] = (df['Upper'] - df['Lower']) / df['MA20'] # 通道寬度，看變盤

    # 5. ATR 真實波幅 (14) - 用於計算波動率與停損
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    df['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(14).mean()

    # 6. MA 均線系統
    df['MA60'] = close.rolling(60).mean() # 季線/生命線
    df['MA200'] = close.rolling(200).mean() # 牛熊線

    return df

# --- 執行數據獲取 ---
df = get_data(yf_ticker, interval_code)

# --- 4. 介面呈現 ---
tab1, tab2 = st.tabs(["🧠 AI 深度戰略分析", "📈 TradingView 專業圖表"])

with tab1:
    if df is not None and len(df) > 60:
        df = calculate_advanced_indicators(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # === A. 頂部資訊列 ===
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        price_change = last['Close'] - prev['Close']
        pct_change = (price_change / prev['Close']) * 100
        
        col_m1.metric("當前價格", f"{last['Close']:.2f}", f"{price_change:.2f} ({pct_change:.2f}%)")
        col_m2.metric("RSI 強弱", f"{last['RSI']:.1f}", "過熱" if last['RSI']>70 else "過冷" if last['RSI']<30 else "正常", delta_color="off")
        col_m3.metric("MACD 動能", f"{last['Hist']:.2f}", "增強" if last['Hist'] > prev['Hist'] else "減弱")
        col_m4.metric("ATR 波動 (風險)", f"{last['ATR']:.2f}", "高波動" if last['ATR'] > df['ATR'].mean() else "低波動", delta_color="inverse")

        # === B. AI 綜合評分系統 (邏輯運算) ===
        score = 0
        signals_bull = []
        signals_bear = []
        
        # 1. 趨勢面
        if last['Close'] > last['MA20']: score += 10; signals_bull.append("站上月線 (短多)")
        else: score -= 10; signals_bear.append("跌破月線 (短空)")
        
        if last['Close'] > last['MA60']: score += 15; signals_bull.append("站上季線 (中多)")
        else: score -= 15; signals_bear.append("跌破季線 (中空)")
        
        # 2. 動能面
        if last['MACD'] > last['Signal']: score += 10; signals_bull.append("MACD 黃金交叉")
        else: score -= 10; signals_bear.append("MACD 死亡交叉")
        
        if last['K'] > last['D']: score += 5; signals_bull.append("KD 黃金交叉")
        else: score -= 5; signals_bear.append("KD 死亡交叉")
        
        # 3. 極端值
        if last['RSI'] < 30: score += 15; signals_bull.append("RSI 超賣 (反彈機會)")
        elif last['RSI'] > 75: score -= 15; signals_bear.append("RSI 超買 (回調風險)")

        # 4. 布林通道
        if last['Close'] > last['Upper']: score += 5; signals_bull.append("突破布林上軌 (強勢)")
        elif last['Close'] < last['Lower']: score -= 5; signals_bear.append("跌破布林下軌 (弱勢)")

        # 正規化分數 (-100 到 100)
        final_score = max(min(score, 100), -100)
        
        # === C. 多空儀表板 (Gauge Chart) ===
        st.write("---")
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.subheader("🚀 多空力道儀表")
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = final_score,
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "AI 趨勢評分", 'font': {'size': 24}},
                gauge = {
                    'axis': {'range': [-100, 100], 'tickwidth': 1, 'tickcolor': "white"},
                    'bar': {'color': "#00d4ff"},
                    'bgcolor': "black",
                    'borderwidth': 2,
                    'bordercolor': "gray",
                    'steps': [
                        {'range': [-100, -40], 'color': '#ff4b4b'}, # 紅色 (空)
                        {'range': [-40, 40], 'color': '#262730'},  # 灰色 (盤整)
                        {'range': [40, 100], 'color': '#00c853'}],  # 綠色 (多)
                }))
            fig_gauge.update_layout(height=300, margin=dict(l=10,r=10,t=0,b=0), paper_bgcolor="#0e1117")
            st.plotly_chart(fig_gauge, use_container_width=True)

        with c2:
            st.subheader("📋 AI 戰略分析報告")
            
            # 狀態定義
            trend_status = "強勢看漲 🐂" if final_score > 40 else "強勢看跌 🐻" if final_score < -40 else "震盪整理 ⚖️"
            action_suggestion = "拉回找買點" if final_score > 20 else "反彈找空點" if final_score < -20 else "觀望 / 區間操作"
            
            st.markdown(f"""
            <div class="report-card">
                <h3>📊 當前趨勢：{trend_status}</h3>
                <p><b>🎯 操作建議：</b> {action_suggestion}</p>
                <p><b>🛡️ 建議停損參考 (ATR法)：</b> ${(last['Close'] - 2*last['ATR']):.2f} (多單) / ${(last['Close'] + 2*last['ATR']):.2f} (空單)</p>
                <hr>
                <p><b>✅ 多方訊號：</b> {', '.join(signals_bull) if signals_bull else '無明顯訊號'}</p>
                <p><b>❌ 空方訊號：</b> {', '.join(signals_bear) if signals_bear else '無明顯訊號'}</p>
            </div>
            """, unsafe_allow_html=True)

        # === D. 進階技術圖表 ===
        st.subheader("📉 深度技術圖表")
        
        # 主圖 (K線 + 均線 + 布林)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'))
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='orange', width=1), name='月線 (20MA)'))
        fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='blue', width=1), name='季線 (60MA)'))
        fig.add_trace(go.Scatter(x=df.index, y=df['Upper'], line=dict(color='rgba(255,255,255,0.3)', width=1, dash='dot'), name='布林上軌'))
        fig.add_trace(go.Scatter(x=df.index, y=df['Lower'], line=dict(color='rgba(255,255,255,0.3)', width=1, dash='dot'), name='布林下軌'))
        
        fig.update_layout(height=500, xaxis_rangeslider_visible=False, template="plotly_dark", 
                          title=f"{yf_ticker} 主圖表", margin=dict(l=0,r=0,t=30,b=0))
        st.plotly_chart(fig, use_container_width=True)
        
        # 副圖 (KD + MACD)
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            fig_kd = go.Figure()
            fig_kd.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='yellow', width=1.5), name='K值'))
            fig_kd.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='purple', width=1.5), name='D值'))
            fig_kd.add_hline(y=80, line_dash="dot", line_color="red")
            fig_kd.add_hline(y=20, line_dash="dot", line_color="green")
            fig_kd.update_layout(height=250, template="plotly_dark", title="KD 隨機指標", margin=dict(l=0,r=0,t=30,b=0))
            st.plotly_chart(fig_kd, use_container_width=True)
            
        with col_f2:
            colors = ['green' if val >= 0 else 'red' for val in df['Hist']]
            fig_macd = go.Figure()
            fig_macd.add_trace(go.Bar(x=df.index, y=df['Hist'], marker_color=colors, name='MACD柱狀'))
            fig_macd.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='cyan', width=1), name='快線'))
            fig_macd.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='orange', width=1), name='慢線'))
            fig_macd.update_layout(height=250, template="plotly_dark", title="MACD 動能指標", margin=dict(l=0,r=0,t=30,b=0))
            st.plotly_chart(fig_macd, use_container_width=True)

    else:
        st.info("💡 請在側邊欄輸入正確代號並選擇週期，系統將自動開始分析。")
        st.warning("若選擇短週期 (如 15m)，請留意是否為休市時間。")

with tab2:
    st.write("### 🌍 TradingView 國際市場即時圖表")
    
    # TV 代碼轉換
    tv_symbol_full = f"{tv_exchange}:{tv_symbol}"
    
    # 週期代碼轉換
    tv_interval_map = {"15m":"15", "30m":"30", "1h":"60", "4h":"240", "1d":"D", "1wk":"W"}
    tv_interval = tv_interval_map.get(interval_code, "D")
    
    html_code = f"""
    <div class="tradingview-widget-container">
      <div id="tradingview_chart"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {{
        "width": "100%",
        "height": 700,
        "symbol": "{tv_symbol_full}",
        "interval": "{tv_interval}",
        "timezone": "Asia/Taipei",
        "theme": "dark",
        "style": "1",
        "locale": "zh_TW",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "save_image": false,
        "container_id": "tradingview_chart"
      }}
      );
      </script>
    </div>
    """
    components.html(html_code, height=750)