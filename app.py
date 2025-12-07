import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit.components.v1 as components

# --- 1. 全局配置與 CSS 魔法 (視覺大整容) ---
st.set_page_config(page_title="TitanTrade - 頂級操盤中控", layout="wide", page_icon="🦁")

# 引入 Google Fonts 並強制覆寫 CSS
st.markdown("""
    <style>
    /* 引入科技感字體 */
    @import url('https://fonts.googleapis.com/css2?family=Exo+2:wght@400;700&family=Noto+Sans+TC:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Exo 2', 'Noto Sans TC', sans-serif;
    }

    /* 背景與主色調重塑 */
    .stApp {
        background-color: #050511; /* 極深藍 */
    }
    
    /* 側邊欄優化 */
    [data-testid="stSidebar"] {
        background-color: #0b0c1b;
        border-right: 1px solid #333;
    }
    [data-testid="stSidebar"] h1 {
        font-size: 30px !important;
        color: #FFD700 !important; /* 金色 */
        text-align: center;
    }
    .stRadio label {
        font-size: 20px !important; /* 資產類別字體放大 */
        font-weight: bold !important;
        color: #e0e0e0 !important;
        padding: 10px 0;
    }
    
    /* 指標卡片設計 */
    div[data-testid="stMetricValue"] {
        font-size: 28px !important;
        font-weight: 700 !important;
        color: #00f2ff !important; /* 霓虹青 */
    }
    div[data-testid="stMetricLabel"] {
        font-size: 16px !important;
        color: #8b9bb4 !important;
    }
    
    /* 自定義卡片容器 */
    .dashboard-card {
        background: linear-gradient(145deg, #161b2e, #0f1220);
        border: 1px solid #2a2f45;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        margin-bottom: 15px;
    }
    
    /* 標題美化 */
    h1, h2, h3 {
        color: #ffffff !important;
        text-shadow: 0 0 10px rgba(0, 242, 255, 0.3);
    }
    
    /* 按鈕美化 */
    .stButton>button {
        background: linear-gradient(90deg, #00d4ff, #0051ff);
        color: white;
        border: none;
        border-radius: 8px;
        font-size: 18px;
        font-weight: bold;
        width: 100%;
        transition: 0.3s;
    }
    .stButton>button:hover {
        transform: scale(1.02);
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.6);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 側邊欄：巨型選單 ---
with st.sidebar:
    st.title("🦁 TITAN TRADE")
    st.markdown("---")
    
    # 加大字體的單選按鈕
    market_type = st.radio(
        "選擇資產市場", 
        ["🇺🇸 美股 (US Stocks)", "🇹🇼 台股 (TW Stocks)", "₿ 加密貨幣 (Crypto)", "📈 ETF (Global)"],
        index=0
    )
    
    st.markdown("---")
    
    # 智慧輸入框
    if "美股" in market_type:
        default_ticker = "NVDA"
        tv_exch = "NASDAQ"
        hint = "輸入代號 (如: TSLA, AAPL, COIN)"
    elif "台股" in market_type:
        default_ticker = "2330"
        tv_exch = "TWSE"
        hint = "輸入代號 (如: 2330, 2603)"
    elif "加密" in market_type:
        default_ticker = "BTC-USD"
        tv_exch = "BINANCE"
        hint = "輸入代號 (如: ETH-USD, SOL-USD)"
    else:
        default_ticker = "QQQ"
        tv_exch = "AMEX"
        hint = "輸入代號 (如: VOO, 0050)"

    user_input = st.text_input("輸入資產代號", default_ticker, help=hint)
    
    # 週期選擇
    st.write("")
    st.markdown("**📊 K線週期**")
    interval_map = {"15分鐘 (當沖)": "15m", "1小時 (短波)": "1h", "4小時 (波段)": "4h", "日線 (趨勢)": "1d", "周線 (長線)": "1wk"}
    selected_label = st.selectbox("週期", list(interval_map.keys()), index=2, label_visibility="collapsed")
    interval_code = interval_map[selected_label]

    # 代號處理
    if "台股" in market_type or (market_type == "📈 ETF (Global)" and user_input.isdigit()):
        yf_ticker = f"{user_input}.TW" if not user_input.endswith(".TW") else user_input
        tv_symbol = user_input
    else:
        yf_ticker = user_input
        tv_symbol = user_input.replace("-USD", "USDT")
        
    st.markdown("---")
    if st.button("🔄 刷新即時數據"):
        st.cache_data.clear()

# --- 3. 頂部宏觀數據列 (Macro Bar) ---
# 這裡用 VIX 和 SPY 計算即時情緒，不依賴容易掛掉的爬蟲
def get_market_sentiment():
    try:
        # 抓取 VIX (恐慌指數) 和 SPY (大盤)
        tickers = yf.Tickers("^VIX ^GSPC DX-Y.NYB")
        data = tickers.history(period="5d")
        
        # 取得最新值
        vix_now = data['Close']['^VIX'].iloc[-1]
        vix_prev = data['Close']['^VIX'].iloc[-2]
        dxy_now = data['Close']['DX-Y.NYB'].iloc[-1]
        sp500_change = ((data['Close']['^GSPC'].iloc[-1] / data['Close']['^GSPC'].iloc[-5]) - 1) * 100
        
        # 簡單的情緒演算法 (0=極度恐慌, 100=極度貪婪)
        # VIX 低且大盤漲 = 貪婪; VIX 高且大盤跌 = 恐慌
        base_score = 50
        if vix_now < 15: base_score += 20
        elif vix_now > 30: base_score -= 30
        
        if sp500_change > 2: base_score += 10
        elif sp500_change < -2: base_score -= 10
        
        # 限制範圍 0-100
        fear_greed_score = max(min(base_score, 100), 0)
        
        return fear_greed_score, vix_now, dxy_now
    except:
        return 50, 20, 100 # 預設值防止報錯

fg_score, vix_val, dxy_val = get_market_sentiment()

# 顯示頂部數據
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🦁 Titan 代號", user_input)
with col2:
    fg_state = "極度貪婪 🤑" if fg_score > 75 else "貪婪 😃" if fg_score > 55 else "極度恐慌 😱" if fg_score < 25 else "恐慌 😨" if fg_score < 45 else "中性 😐"
    st.metric("市場情緒 (Fear & Greed)", f"{fg_score:.0f}", fg_state)
with col3:
    st.metric("VIX 恐慌指數", f"{vix_val:.2f}", "避險情緒高" if vix_val > 20 else "市場平穩", delta_color="inverse")
with col4:
    st.metric("DXY 美元指數", f"{dxy_val:.2f}", "資金回流美國" if dxy_val > 105 else "資金釋出")

# --- 4. 數據核心 ---
def get_main_data(ticker, interval):
    try:
        # 參數設置：prepost=True 抓盤前盤後，確保即時性
        if interval == "4h":
            df = yf.Ticker(ticker).history(period="730d", interval="1h", prepost=True)
            if df.empty: return None
            agg = {'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}
            df = df.resample('4h').agg(agg).dropna()
        elif interval in ["15m", "30m"]:
            df = yf.Ticker(ticker).history(period="60d", interval=interval, prepost=True)
        else:
            period_map = {"1h":"730d", "1d":"5y", "1wk":"10y"}
            df = yf.Ticker(ticker).history(period=period_map.get(interval,"2y"), interval=interval, prepost=True)
            
        return df if not df.empty else None
    except:
        return None

df = get_main_data(yf_ticker, interval_code)

# --- 5. 功能分頁 ---
tab1, tab2, tab3 = st.tabs(["⚡ AI 戰術分析", "📊 TradingView 專業圖表", "🧮 交易試算機 (槓桿/獲利)"])

# === Tab 1: AI 分析 ===
with tab1:
    if df is not None and len(df) > 50:
        # 技術指標計算
        close = df['Close']
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + gain/loss))
        # MA
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()
        # Bollinger
        std = close.rolling(20).std()
        upper = ma20 + (std * 2)
        lower = ma20 - (std * 2)
        
        curr_price = close.iloc[-1]
        curr_rsi = rsi.iloc[-1]
        
        # 綜合評分
        score = 0
        if curr_price > ma20.iloc[-1]: score += 20
        if curr_price > ma60.iloc[-1]: score += 20
        if curr_rsi < 30: score += 30 # 超賣反彈
        elif curr_rsi > 70: score -= 30 # 超買回調
        if (ma20.iloc[-1] > ma60.iloc[-1]): score += 10 # 多頭排列

        # 介面佈局
        c1, c2 = st.columns([2, 1])
        
        with c1:
            st.markdown("### 📉 趨勢圖表")
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'))
            fig.add_trace(go.Scatter(x=df.index, y=ma20, line=dict(color='#FFD700', width=1.5), name='MA20 (月線)'))
            fig.add_trace(go.Scatter(x=df.index, y=upper, line=dict(color='rgba(0, 212, 255, 0.3)', width=1), name='B Band上'))
            fig.add_trace(go.Scatter(x=df.index, y=lower, line=dict(color='rgba(0, 212, 255, 0.3)', width=1), name='B Band下'))
            
            fig.update_layout(
                height=500, 
                paper_bgcolor='rgba(0,0,0,0)', 
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                xaxis_rangeslider_visible=False,
                margin=dict(l=0,r=0,t=0,b=0)
            )
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            st.markdown("### 🤖 AI 戰略官建議")
            
            final_score = max(min(score, 100), -100)
            
            # 儀表板
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = final_score,
                domain = {'x': [0, 1], 'y': [0, 1]},
                gauge = {
                    'axis': {'range': [-100, 100], 'tickcolor': "white"},
                    'bar': {'color': "#00d4ff"},
                    'bgcolor': "#161b2e",
                    'steps': [
                        {'range': [-100, -30], 'color': '#ff2b2b'},
                        {'range': [-30, 30], 'color': '#444'},
                        {'range': [30, 100], 'color': '#00ff88'}],
                }
            ))
            fig_gauge.update_layout(height=250, margin=dict(l=20,r=20,t=30,b=20), paper_bgcolor='rgba(0,0,0,0)', font={'color': "white"})
            st.plotly_chart(fig_gauge, use_container_width=True)
            
            # 文字建議
            if final_score > 30:
                rec_title = "🚀 強力做多訊號"
                rec_color = "green"
                rec_text = "價格強勢且技術面支撐良好，適合進場或加碼。"
            elif final_score < -30:
                rec_title = "🛑 建議做空/減碼"
                rec_color = "red"
                rec_text = "技術面轉弱，上方壓力大，建議獲利了結或反向操作。"
            else:
                rec_title = "⚖️ 震盪觀望"
                rec_color = "gray"
                rec_text = "多空力道不明，建議縮手觀望或區間低買高賣。"
                
            st.markdown(f"""
            <div style="background-color: #1e2336; padding: 15px; border-radius: 10px; border-left: 5px solid {rec_color};">
                <h4 style="margin:0; color: white;">{rec_title}</h4>
                <p style="color: #bbb; margin-top: 10px;">{rec_text}</p>
                <p style="color: #00d4ff;">關鍵支撐: {lower.iloc[-1]:.2f} <br> 關鍵壓力: {upper.iloc[-1]:.2f}</p>
            </div>
            """, unsafe_allow_html=True)
            
    else:
        st.error("⚠️ 無法取得數據，請檢查代號是否正確，或市場目前是否休市。")

# === Tab 2: TradingView ===
with tab2:
    tv_interval_map = {"15m":"15", "1h":"60", "4h":"240", "1d":"D", "1wk":"W"}
    tv_int = tv_interval_map.get(interval_code, "D")
    
    components.html(f"""
    <div class="tradingview-widget-container">
      <div id="tradingview_chart"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {{
        "width": "100%", "height": 700, "symbol": "{tv_exch}:{tv_symbol}",
        "interval": "{tv_int}", "timezone": "Asia/Taipei", "theme": "dark",
        "style": "1", "locale": "zh_TW", "toolbar_bg": "#f1f3f6",
        "enable_publishing": false, "hide_side_toolbar": false, "allow_symbol_change": true,
        "container_id": "tradingview_chart"
      }}
      );
      </script>
    </div>
    """, height=710)

# === Tab 3: 交易計算機 (新增功能) ===
with tab3:
    st.markdown("### 🧮 智能交易試算機 (Position Calculator)")
    
    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        capital = st.number_input("💰 投入本金 (USDT/TWD)", value=1000.0, step=100.0)
        leverage = st.slider("⚡ 使用槓桿 (倍數)", 1, 125, 10)
    with cc2:
        entry_price = st.number_input("🔵 進場價格", value=float(df['Close'].iloc[-1]) if df is not None else 0.0, format="%.2f")
        exit_price = st.number_input("🔴 預期出場價格", value=float(df['Close'].iloc[-1]*1.05) if df is not None else 0.0, format="%.2f")
    with cc3:
        direction = st.radio("操作方向", ["做多 (Long)", "做空 (Short)"])
        fee_rate = st.number_input("手續費率 (%)", value=0.05, step=0.01) / 100

    # 計算邏輯
    if st.button("🚀 開始試算"):
        position_size = capital * leverage # 總倉位價值
        
        # 手續費 (開倉+平倉) 概算
        total_fee = position_size * fee_rate * 2 
        
        if direction == "做多 (Long)":
            price_diff_pct = (exit_price - entry_price) / entry_price
            gross_profit = position_size * price_diff_pct
        else:
            price_diff_pct = (entry_price - exit_price) / entry_price
            gross_profit = position_size * price_diff_pct
            
        net_profit = gross_profit - total_fee
        roe = (net_profit / capital) * 100
        
        # 顯示結果
        st.markdown("---")
        res_col1, res_col2, res_col3 = st.columns(3)
        
        res_col1.metric("總倉位價值", f"${position_size:,.2f}")
        res_col2.metric("預估淨利 (P&L)", f"${net_profit:,.2f}", delta_color="normal" if net_profit > 0 else "inverse")
        res_col3.metric("投資報酬率 (ROE)", f"{roe:.2f}%", f"{'🔥 暴賺' if roe > 50 else '👍 獲利' if roe > 0 else '💸 虧損'}")
        
        if net_profit > 0:
            st.balloons()
        else:
            st.warning("⚠️ 此交易預期會虧損，請重新評估風險！")