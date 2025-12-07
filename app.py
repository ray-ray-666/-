import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import streamlit.components.v1 as components

# --- 1. 頁面設定 ---
st.set_page_config(page_title="全市場趨勢分析 (含4H版)", layout="wide", page_icon="📈")
st.title("📈 投資分析中控台")

# --- 2. 側邊欄：設定 ---
st.sidebar.header("🎯 參數設定")
market_type = st.sidebar.selectbox("市場類別", ["美股 (US)", "台股 (TW)", "加密貨幣 (Crypto)"])

if market_type == "美股 (US)":
    default_ticker = "NVDA"
    tv_exchange = "NASDAQ" 
elif market_type == "台股 (TW)":
    default_ticker = "2330"
    tv_exchange = "TWSE"
else:
    default_ticker = "BTC-USD"
    tv_exchange = "BINANCE"

user_input = st.sidebar.text_input("輸入代號", default_ticker)

# 處理代號
if market_type == "台股 (TW)" and not user_input.endswith(".TW"):
    yf_ticker = f"{user_input}.TW"
    tv_symbol = user_input 
else:
    yf_ticker = user_input
    tv_symbol = user_input.replace("-USD", "USDT")

# 週期對照表 (新增 4小時)
interval_map = {
    "15分鐘": "15m", 
    "30分鐘": "30m", 
    "1小時": "1h",
    "4小時": "4h",  # 這是我們自定義的標籤
    "日線": "1d", 
    "周線": "1wk", 
    "月線": "1mo"
}
selected_label = st.sidebar.selectbox("K線週期", list(interval_map.keys()), index=3) # 預設選 4小時
interval_code = interval_map[selected_label]

# --- 3. 數據處理核心 (含 4H 合成魔法) ---
def get_data(ticker, interval_label):
    try:
        # === 情況 A: 使用 Yahoo 原生支援的週期 ===
        if interval_label == "15m" or interval_label == "30m":
            df = yf.Ticker(ticker).history(period="60d", interval=interval_label)
        elif interval_label == "1h":
            df = yf.Ticker(ticker).history(period="730d", interval="1h")
        elif interval_label == "1d":
            df = yf.Ticker(ticker).history(period="5y", interval="1d")
        elif interval_label == "1wk":
            df = yf.Ticker(ticker).history(period="5y", interval="1wk")
        elif interval_label == "1mo":
            df = yf.Ticker(ticker).history(period="max", interval="1mo")
            
        # === 情況 B: 處理 4小時 (Yahoo 不支援，需人工合成) ===
        elif interval_label == "4h":
            # 1. 先抓 1 小時數據 (最多抓 730 天)
            df_1h = yf.Ticker(ticker).history(period="730d", interval="1h")
            if df_1h.empty: return None
            
            # 2. 進行重採樣 (Resampling): 將 1h 聚合為 4h
            # 邏輯：Open取第一筆, High取最大值, Low取最小值, Close取最後一筆, Volume取總和
            agg_dict = {
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }
            # 這裡簡單使用 4H 聚合，不處理特定開盤時間偏移，對於趨勢判斷已足夠
            df = df_1h.resample('4h').agg(agg_dict)
            
            # 3. 移除因為休市產生的空值行
            df = df.dropna() 
            
        return df if not df.empty else None
    except Exception as e:
        return None

df = get_data(yf_ticker, interval_code)

# --- 4. 介面分頁 ---
tab1, tab2 = st.tabs(["🤖 AI 技術分析 (Yahoo數據)", "📊 TradingView 圖表 (嵌入版)"])

# === 分頁 1: AI 計算 ===
with tab1:
    if df is not None and len(df) > 50:
        # 技術指標計算
        close = df['Close']
        
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1]
        
        # 均線 (SMA)
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()
        price = close.iloc[-1]
        
        # 顯示指標
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("最新價格", f"{price:.2f}")
        col_b.metric("RSI (14)", f"{current_rsi:.1f}", 
                     "超買区" if current_rsi > 70 else "超賣区" if current_rsi < 30 else "中性区")
        
        # 簡易 AI 判讀
        score = 0
        reasons = []
        
        if current_rsi < 30: 
            score += 2
            reasons.append("RSI 低檔超賣")
        elif current_rsi > 70: 
            score -= 2
            reasons.append("RSI 高檔超買")
            
        if price > ma20.iloc[-1]:
            score += 1
            reasons.append("價格在月線(MA20)之上")
        else:
            score -= 1
            
        status = "🟢 多方優勢" if score > 0 else "🔴 空方優勢" if score < 0 else "⚪ 盤整"
        col_c.metric("AI 趨勢判斷", status)
        if reasons:
            st.caption(f"主要依據: {', '.join(reasons)}")

        # 繪圖
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K線'))
        fig.add_trace(go.Scatter(x=df.index, y=ma20, line=dict(color='orange', width=1), name='MA20'))
        fig.add_trace(go.Scatter(x=df.index, y=ma60, line=dict(color='blue', width=1), name='MA60'))
        
        title_text = f"{yf_ticker} - {selected_label} 走勢圖"
        fig.update_layout(title=title_text, height=550, xaxis_rangeslider_visible=False, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.warning("數據載入中或無法取得數據 (請檢查代號是否正確)")

# === 分頁 2: TradingView Widget ===
with tab2:
    st.write("這是來自 TradingView 的即時圖表")
    
    tv_symbol_full = f"{tv_exchange}:{tv_symbol}"
    
    # 將我們的中文選項轉換為 TradingView 的代碼
    # 4小時在 TradingView API 是 "240" (分鐘) 或 "4H"
    tv_interval_map = {
        "15分鐘": "15",
        "30分鐘": "30",
        "1小時": "60",
        "4小時": "240", 
        "日線": "D",
        "周線": "W",
        "月線": "M"
    }
    tv_interval = tv_interval_map.get(selected_label, "D")
    
    html_code = f"""
    <div class="tradingview-widget-container">
      <div id="tradingview_chart"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {{
        "width": "100%",
        "height": 650,
        "symbol": "{tv_symbol_full}",
        "interval": "{tv_interval}",
        "timezone": "Asia/Taipei",
        "theme": "dark",
        "style": "1",
        "locale": "zh_TW",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "container_id": "tradingview_chart"
      }}
      );
      </script>
    </div>
    """
    components.html(html_code, height=700)