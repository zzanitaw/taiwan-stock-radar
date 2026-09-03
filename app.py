import streamlit as st
import pandas as pd
import yfinance as yf
import re

# ================= 設定區 =================
EXCEL_URL = "https://docs.google.com/spreadsheets/d/1C28Y0nG-ii_gFDRMVw3y9Q5JfwJV_AjE/export?format=xlsx"

import streamlit as st

st.set_page_config(page_title="台股防區與獲利追蹤雷達", layout="wide")

# 加入這段 CSS 來優化手機與電腦版的 UI 留白與標題大小
st.markdown("""
    <style>
        /* 縮小手機版頂部區塊的間距 */
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }
        /* 調整標題在手機上的顯示大小 */
        h1 {
            font-size: 1.8rem !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🎯 台股防區與獲利追蹤雷達")

# ================= 核心函式 =================
@st.cache_data(ttl=60)
def load_data():
    try:
        df = pd.read_excel(EXCEL_URL, header=1, engine='openpyxl')
        if "股票/ETF" in df.columns:
            df = df.dropna(subset=["股票/ETF"])
        return df
    except Exception as e:
        st.error(f"讀取試算表失敗，請確認檔案權限。錯誤訊息: {e}")
        return pd.DataFrame()

def get_realtime_price(stock_str):
    try:
        stock_str_clean = str(stock_str).strip()
        match = re.search(r'([0-9]+[A-Za-z]*)', stock_str_clean)
        if not match:
            return None
        
        raw_code = match.group(1).upper()
        candidates = [raw_code, f"{raw_code}.TW", f"{raw_code}.TWO"]
        
        for ticker in candidates:
            stock = yf.Ticker(ticker)
            todays_data = stock.history(period='5d')
            if not todays_data.empty:
                return round(todays_data['Close'].iloc[-1], 2)
        return None
    except:
        return None

def find_col_name(df, keyword):
    for col in df.columns:
        if keyword in str(col):
            return col
    return None

# ================= 主程式邏輯 =================
df = load_data()

if not df.empty:
    st.info("資料讀取成功！正在抓取即時股價中，請稍候...")
    
    col_5 = find_col_name(df, "5%防區")
    col_12 = find_col_name(df, "12%防區")
    col_20 = find_col_name(df, "20%防區")
    col_sell = find_col_name(df, "最高賣") or find_col_name(df, "賣價") or find_col_name(df, "歷史最高")
    
    realtime_prices = []
    buy_status_list = []
    sell_status_list = []
    progress_bar = st.progress(0)
    
    for i, row in df.reset_index().iterrows():
        stock_name = row.get("股票/ETF", "")
        current_price = get_realtime_price(stock_name)
        realtime_prices.append(current_price)
        
        buy_status = "安全觀察中"
        sell_status = "持有中"
        
        if current_price is None:
            buy_status = "⚠️ 抓不到股價"
            sell_status = "⚠️ 抓不到股價"
        else:
            price_5 = pd.to_numeric(row.get(col_5), errors='coerce') if col_5 else pd.NA
            price_12 = pd.to_numeric(row.get(col_12), errors='coerce') if col_12 else pd.NA
            price_20 = pd.to_numeric(row.get(col_20), errors='coerce') if col_20 else pd.NA
            sell_price = pd.to_numeric(row.get(col_sell), errors='coerce') if col_sell else pd.NA
            
            # 獨立判斷：買入防區狀態
            if pd.notna(price_20) and current_price <= price_20:
                buy_status = "🔥 20%極端恐慌區 (強烈加碼)"
            elif pd.notna(price_12) and current_price <= price_12:
                buy_status = "⚠️ 12%防區 (主要加碼)"
            elif pd.notna(price_5) and current_price <= price_5:
                buy_status = "✅ 5%防區 (零股試單)"
                
            # 獨立判斷：賣出獲利狀態
            if pd.notna(sell_price) and current_price >= sell_price:
                sell_status = "💰 達到最高賣價 (建議獲利入袋！)"
                
        buy_status_list.append(buy_status)
        sell_status_list.append(sell_status)
        progress_bar.progress((i + 1) / len(df))
        
    df["即時股價"] = realtime_prices
    df["📉 買入狀態"] = buy_status_list
    df["💰 賣出狀態"] = sell_status_list
    
    # 組合要顯示的欄位順序
    display_columns = ["股票/ETF", "即時股價", "📉 買入狀態", "💰 賣出狀態"]
    if col_sell: display_columns.append(col_sell)
    if col_5: display_columns.append(col_5)
    if col_12: display_columns.append(col_12)
    if col_20: display_columns.append(col_20)
    
    existing_cols = [col for col in display_columns if col in df.columns]
    
    # 雙欄位顏色標示
    def color_status(val):
        val_str = str(val)
        if "最高賣價" in val_str: return 'background-color: #d4edda; color: #155724; font-weight: bold'
        elif "20%" in val_str: return 'background-color: #ffcccc; color: red; font-weight: bold'
        elif "12%" in val_str: return 'background-color: #ffe6cc; color: #ff8c00; font-weight: bold'
        elif "5%" in val_str: return 'background-color: #e6ffcc; color: green; font-weight: bold'
        elif "抓不到" in val_str: return 'color: gray; font-style: italic'
        return ''

    st.subheader("📊 追蹤清單與買賣雙向雷達")
    # 同時對買入狀態與賣出狀態套用顏色樣式
    styled_df = df[existing_cols].style.map(color_status, subset=['📉 買入狀態', '💰 賣出狀態'])
    st.dataframe(styled_df, height=600, use_container_width=True)
    
    if st.button("🔄 手動更新即時股價"):
        st.cache_data.clear()
        st.rerun()
else:
    st.warning("無法解析資料。")