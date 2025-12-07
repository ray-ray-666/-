import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit.components.v1 as components

# --- 1. 全局配置與 CSS 暴力放大 (視覺優化) ---
st.set_page_config(page_title="TitanTrade V6 - 時光領主版", layout="wide", page_icon="🦁")

st.markdown("""
    <style>
    /* 引入科技字體 */
    @import url('https://fonts.googleapis.com/css2?family=Exo+2:wght@500;700&family=Noto+Sans+TC:wght@500;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Exo 2', 'Noto Sans TC', sans-serif;
        font-size: 18px !important;
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
        font-size: 22px !important;
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
    st.title("🦁 TITAN V6")
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
    
    # === 新增長週期選項 ===
    interval_map = {
        "⚡ 15分鐘": "15m", 
        "⚡ 30分鐘": "30m", 
        "🕐 1小時": "1h", 
        "🕓 4小時": "4h", 
        "📅 日線": "1d", 
        "📆 周線": "1wk",
        "🌙 月線 (1M)": "1mo",
        "🍂 季線 (3M)": "3mo",
        "🌗 半年線 (6M)": "6mo",
        "🌞 年線 (1Y)": "1y"
    }
    selected_label = st.selectbox("週期", list(interval_map.keys()), index=4) # 預設日線
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

# --- 3. 數據與指標運算 (核心引擎 - 含合成技術) ---
def get_data_with_indicators(ticker, interval):
    try:
        df = pd.DataFrame()
        
        # === A. 數據抓取策略 ===
        # 1. 短線 (分鐘/小時)
        if interval in ["15m", "30m"]:
            df = yf.Ticker(ticker).history(period="60d", interval=interval, prepost=True)
        
        # 2. 中線 (小時/日/周)
        elif interval == "1h":
            df = yf.Ticker(ticker).history(period="730d", interval="1h", prepost=True)
        elif interval == "4h":
            # 4小時合成
            df_1h = yf.Ticker(ticker).history(period="730d", interval="1h", prepost=True)
            if not df_1h.empty:
                agg = {'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}
                df = df_1h.resample('4h').agg(agg).dropna()
        
        # 3. 長線 (日/周/月/季) - 原生支援
        elif interval in ["1d", "1wk"]:
            p_map = {"1d":"10y", "1wk":"max"} # 抓長一點
            df = yf.Ticker(ticker).history(period=p_map[interval], interval=interval)
        elif interval in ["1mo", "3mo"]:
             df = yf.Ticker(ticker).history(period="max", interval=interval)

        # 4. 超長線 (半年/年) - 需合成
        elif interval == "6mo":
            # 用月線合成半年線
            df_mo = yf.Ticker(ticker).history(period="max", interval="1mo")
            if not df_mo.empty:
                agg = {'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}
                # 6M = 6個月
                df = df_mo.resample('6M').agg(agg).dropna()
        
        elif interval == "1y":
            # 用月線合成年線
            df_mo = yf.Ticker(ticker).history(period="max", interval="1mo")
            if not df_mo.empty:
                agg = {'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}
                # 12M = 12個月 (1年)
                df = df_mo.resample('12M').agg(agg).dropna()

        if df.empty: return None
        
        # === B. 指標計算全家桶 ===
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
        
        # 4. 布林通道 & 寬度
        df['MA20'] = close.rolling(20).mean()
        df['STD20'] = close.rolling(20).std()
        df['Upper'] = df['MA20'] + (df['STD20'] * 2)
        df['Lower'] = df['MA20'] - (df['STD20'] * 2)
        df['Bandwidth'] = (df['Upper'] - df['Lower']) / df['MA20']
        
        # 5. ATR
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        df['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR'] = df['TR'].rolling(14).mean()
        
        # 6. OBV
        df['OBV'] = (np.sign(close.diff()) * df['Volume']).fillna(0).cumsum()
        
        # 7. MA (長週期均線調整)
        # 如果是年線，MA20 代表 20年線，MA60 太長了，改用 EMA
        df['MA60'] = close.rolling(60).mean()
        df['EMA200'] = close.ewm(span=200, adjust=False).mean()

        return df
    except Exception as e:
        return None

# 獲取情緒 (模擬)
def get_sentiment():
    try:
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
tab1, tab2, tab3 = st.tabs(["⚡ AI 戰術分析與圖表", "📊 TradingView 模式", "🧮 獲利試算 (台幣/美金)"])

with tab1:
    if df is not None and len(df) > 20: # 門檻降低，因為年線數據少
        last = df.iloc[-1]
        
        # === A. 互動式技術圖表 ===
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2],
                            subplot_titles=(f"{yf_ticker} ({selected_label}) 趨勢", "MACD", "KD"))

        # 主圖
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                                     name='K線', increasing_line_color='#00ff00', decreasing_line_color='#ff0000'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=1.5), name='MA20'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Upper'], line=dict(color='gray', width=1, dash='dot'), name='BB上'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Lower'], line=dict(color='gray', width=1, dash='dot'), name='BB下'), row=1, col=1)

        # MACD
        colors = ['#00ff00' if v >= 0 else '#ff0000' for v in df['Hist']]
        fig.add_trace(go.Bar(x=df.index, y=df['Hist'], marker_color=colors, name='MACD柱'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='#00d4ff', width=1), name='快線'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='#ff9900', width=1), name='慢線'), row=2, col=1)

        # KD
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='#ff00ff', width=1), name='K值'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='white', width=1), name='D值'), row=3, col=1)
        
        # 顯示範圍設定
        show_bars = 50 if interval_code in ["6mo", "1y"] else 100
        start_idx = max(0, len(df) - show_bars)
        
        fig.update_layout(
            height=800, 
            xaxis_rangeslider_visible=False,
            paper_bgcolor='black',
            plot_bgcolor='#0e0e0e',
            font=dict(color='white', size=14),
            dragmode='pan',
            xaxis=dict(range=[df.index[start_idx], df.index[-1]]),
            showlegend=True
        )
        st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})

        # === B. AI 戰略分析 ===
        st.markdown("### 🦁 AI 戰略指揮中心")
        
        score = 0
        signals = []
        
        # 邏輯判斷 (若數據不足會略過)
        if not np.isnan(last['MA20']):
            if last['Close'] > last['MA20']: score += 20; signals.append("✅ 站上 MA20 (多頭)")
            else: score -= 20; signals.append("🔻 跌破 MA20 (空頭)")
        
        if not np.isnan(last['RSI']):
            if last['RSI'] < 30: score += 15; signals.append("✅ RSI 超賣")
            elif last['RSI'] > 70: score -= 15; signals.append("⚠️ RSI 超買")
            
        if not np.isnan(last['MACD']):
            if last['MACD'] > last['Signal']: score += 10; signals.append("✅ MACD 金叉")
            else: score -= 10; signals.append("🔻 MACD 死叉")
            
        # 生成建議
        atr_val = last['ATR'] if not np.isnan(last['ATR']) else last['Close']*0.02
        atr_sl = atr_val * 2
        rec_color = "#00ff00" if score > 20 else "#ff0000" if score < -20 else "#ffff00"
        rec_text = "積極做多" if score > 20 else "偏空調節" if score < -20 else "區間震盪"
        
        st.markdown(f"""
        <div class="analysis-box" style="border-left: 5px solid {rec_color};">
            <h2 style="color:{rec_color}">🛡️ 總指揮建議：{rec_text} (信心分: {score})</h2>
            <hr style="border-color: #333;">
            <div style="display: flex; flex-wrap: wrap; gap: 20px;">
                <div style="flex: 1;">
                    <h4>📊 關鍵數據 ({selected_label})</h4>
                    <ul>
                        <li><b>RSI:</b> {last['RSI']:.1f}</li>
                        <li><b>KD:</b> K={last['K']:.1f}, D={last['D']:.1f}</li>
                        <li><b>ATR:</b> {atr_val:.2f}</li>
                        <li><b>布林寬度:</b> {last['Bandwidth']:.3f}</li>
                    </ul>
                </div>
                <div style="flex: 1;">
                    <h4>🎯 策略建議</h4>
                    <ul>
                        <li><b>多單止損:</b> <span style="color:#ff4444">${(last['Close'] - atr_sl):.2f}</span></li>
                        <li><b>空單止損:</b> <span style="color:#ff4444">${(last['Close'] + atr_sl):.2f}</span></li>
                        <li><b>訊號:</b> {', '.join(signals)}</li>
                    </ul>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    else:
        st.warning(f"⚠️ 數據量不足，無法計算 {selected_label} 的技術指標 (或該資產上市時間不夠長)。")

with tab2:
    # TradingView 映射
    tv_map = {
        "15m":"15", "30m":"30", "1h":"60", "4h":"240", "1d":"D", "1wk":"W",
        "1mo":"M", "3mo":"3M", "6mo":"6M", "1y":"12M"
    }
    tv_int = tv_map.get(interval_code, "D")
    
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
    st.markdown("### 🧮 智能獲利試算 (含自動匯率轉換)")
    
    try:
        usdtwd = yf.Ticker("USDTWD=X").history(period="1d")['Close'].iloc[-1]
    except:
        usdtwd = 32.5 
    
    st.caption(f"💡 目前即時匯率: 1 USD ≈ {usdtwd:.2f} TWD")

    with st.container():
        c1, c2, c3 = st.columns(3)
        capital = c1.number_input("💰 投入本金 (U/USD)", value=1000.0, step=100.0)
        leverage = c1.slider("⚡ 槓桿倍數", 1, 125, 10)
        
        current_price = df['Close'].iloc[-1] if df is not None else 0.0
        entry = c2.number_input("🔵 進場價格", value=current_price, format="%.2f")
        exit_p = c2.number_input("🔴 預期出場", value=current_price * 1.05, format="%.2f")
        
        direction = c3.radio("操作方向", ["📈 做多 (Long)", "📉 做空 (Short)"])
        
    st.markdown("---")

    if st.button("🚀 開始計算損益", type="primary", use_container_width=True):
        position_size = capital * leverage 
        
        if direction == "📈 做多 (Long)":
            price_diff_pct = (exit_p - entry) / entry
        else:
            price_diff_pct = (entry - exit_p) / entry
            
        profit_usd = position_size * price_diff_pct
        profit_twd = profit_usd * usdtwd
        roe = (profit_usd / capital) * 100
        
        r1, r2, r3 = st.columns(3)
        color_str = "normal" if profit_usd > 0 else "inverse"
        
        with r1:
            st.metric("投資報酬率 (ROE)", f"{roe:.2f}%", "獲利" if roe > 0 else "虧損")
        with r2:
            st.metric("美金損益 (USD)", f"${profit_usd:,.2f}", delta_color=color_str)
        with r3:
            st.metric("台幣損益 (TWD)", f"NT$ {profit_twd:,.0f}", delta_color=color_str)

        if profit_usd > 0:
            st.success(f"恭喜兄弟！這單能賺約 **NT$ {profit_twd:,.0f}** 塊錢！ 🍖")
            st.balloons()
        else:
            st.error(f"兄弟小心！這單預計會賠 **NT$ {abs(profit_twd):,.0f}**，請嚴格設定停損！")