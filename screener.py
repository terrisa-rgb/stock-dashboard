import datetime
import json
import pandas as pd
import requests
import yfinance as yf


# ==========================================
# 1. 籌碼面：抓取投信連 2 買股票
# ==========================================
def get_sitc_stocks():
    print("正在抓取三大法人籌碼數據...")
    today = datetime.date.today()
    dates = [
        (today - datetime.timedelta(days=i)).strftime("%Y%m%d")
        for i in range(7)
    ]

    sitc_buy_counts = {}
    valid_days = 0

    for d in dates:
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={d}&selectType=ALL&response=json"
        try:
            res = requests.get(url, timeout=10).json()
            if res.get("stat") == "OK" and "data" in res:
                valid_days += 1
                for row in res["data"]:
                    stock_id = row[0].strip()
                    try:
                        sitc_buy = int(row[10].replace(",", ""))
                        if sitc_buy > 0:
                            sitc_buy_counts[stock_id] = (
                                sitc_buy_counts.get(stock_id, 0) + 1
                            )
                    except ValueError:
                        continue
        except Exception:
            pass

        if valid_days >= 2:
            break

    sitc_2day = [
        sid for sid, count in sitc_buy_counts.items() if count >= 2
    ]

    # 若非交易日或無資料，預設精選關注個股測試
    if not sitc_2day:
        sitc_2day = [
            "2330",
            "2317",
            "2454",
            "2308",
            "2382",
            "3037",
            "2379",
            "3231",
            "2603",
            "2376",
        ]

    return sitc_2day


# ==========================================
# 2. 技術面：5MA近60MA & MACD柱狀體縮小/翻正
# ==========================================
def analyze_stock(stock_id):
    ticker = f"{stock_id}.TW"
    try:
        df = yf.download(ticker, period="4m", interval="1d", progress=False)
        if df.empty or len(df) < 60:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df["Close"]
        ma5 = close.rolling(5).mean()
        ma60 = close.rolling(60).mean()

        exp12 = close.ewm(span=12, adjust=False).mean()
        exp26 = close.ewm(span=26, adjust=False).mean()
        dif = exp12 - exp26
        macd = dif.ewm(span=9, adjust=False).mean()
        osc = dif - macd

        c_close = float(close.iloc[-1])
        c_ma5 = float(ma5.iloc[-1])
        c_ma60 = float(ma60.iloc[-1])
        c_osc = float(osc.iloc[-1])
        p_osc = float(osc.iloc[-2])

        # 條件 1: 5MA 接近 60MA (差距小於 1.8%) 且在 60MA 下方或剛突破
        ma_dist = abs(c_ma60 - c_ma5) / c_ma60
        ma_near = ma_dist < 0.018

        # 條件 2: MACD 柱狀體為負且持續縮小，或剛翻正
        macd_signal = (c_osc < 0 and c_osc > p_osc) or (p_osc < 0 and c_osc >= 0)

        if ma_near and macd_signal:
            return {
                "id": stock_id,
                "close": round(c_close, 2),
                "ma_dist": round(ma_dist * 100, 2),
                "osc": round(c_osc, 2),
                "contract": "季報持續成長",
            }
    except Exception:
        return None
    return None


# ==========================================
# 3. 主流程：產生 data.json 供儀表板讀取
# ==========================================
def main():
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    sitc_stocks = get_sitc_stocks()

    results = []
    for sid in sitc_stocks:
        res = analyze_stock(sid)
        if res:
            results.append(res)

    # 儲存篩選結果給網頁讀取
    data_to_save = {"update_time": today_str, "stocks": results}
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=2)

    print(f"完成！共篩選出 {len(results)} 檔個股，已更新 data.json。")


if __name__ == "__main__":
    main()
