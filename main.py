# ==============================================================================
# PROYEK: ASISTEN SINYAL SAHAM (STOCK SIGNAL ADVISOR)
# FILE  : main.py
# FUNGSI: Screener Multisaham (Pemindai Otomatis Data Riil)
# ==============================================================================

import yfinance as yf
import pandas as pd
import numpy as np

def fetch_real_stock_data(symbol_ticker):
    ticker_code = f"{symbol_ticker}.JK" if not symbol_ticker.endswith(".JK") and "." not in symbol_ticker else symbol_ticker
    stock = yf.Ticker(ticker_code)
    
    try:
        df = stock.history(period="1y")
        if df.empty:
            return None, f"Data kosong/tidak ditemukan."

        current_price = int(df['Close'].iloc[-1])
        recent_volume = df['Volume'].tail(5).mean()
        turnover_m = (recent_volume * current_price) / 1_000_000_000

        # Hitung RSI (14 Hari)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        current_rsi = (100 - (100 / (1 + rs))).iloc[-1]

        # Hitung EMA 200 & Level Support/Resistance
        current_ema_200 = int(df['Close'].ewm(span=200, adjust=False).mean().iloc[-1])
        support_level = int(df['Low'].tail(30).min())
        resistance_level = int(df['High'].tail(30).max())

        return {
            "symbol": symbol_ticker.upper().replace(".JK", ""),
            "company_name": stock.info.get("shortName", symbol_ticker),
            "current_price": current_price,
            "daily_turnover_m": round(turnover_m, 2),
            "rsi_14": current_rsi,
            "support_level": support_level,
            "resistance_level": resistance_level,
            "ema_200": current_ema_200,
            "per": stock.info.get("forwardPE", 15.0) or 15.0,
            "avg_per_5y": 18.0, 
            "roe": (stock.info.get("returnOnEquity", 0.15) or 0.15) * 100,
        }, None
    except Exception as e:
        return None, str(e)


def evaluate_stock(data):
    symbol = data["symbol"]
    price = data["current_price"]
    turnover = data["daily_turnover_m"]
    
    # 1. PASSER / SAFETY FILTER
    if turnover < 5.0:
        return {"status": "REJECTED", "reason": f"Likuiditas Rendah (Rp {turnover}M/hari)"}

    # 2. SKORING ANALISIS
    score = 0
    rsi = data["rsi_14"]
    support = data["support_level"]
    resistance = data["resistance_level"]
    ema_200 = data["ema_200"]
    per = data["per"]
    avg_per = data["avg_per_5y"]
    roe = data["roe"]

    if rsi < 30: score += 2
    elif rsi < 45: score += 1
    
    dist_to_support = ((price - support) / support) * 100 if support > 0 else 999
    if 0 <= dist_to_support <= 3.5: score += 2
    
    if price > ema_200: score += 1
    if per > 0 and per < avg_per: score += 2
    if roe >= 15: score += 1

    # 3. KEPUTUSAN SINYAL
    if score >= 6: signal = "STRONG BUY"
    elif score >= 4: signal = "BUY"
    elif score >= 2: signal = "HOLD"
    else: signal = "AVOID"

    tp1 = int(resistance) if resistance > price else int(price * 1.08)
    sl = int(support * 0.96)

    return {
        "status": "PASSED",
        "signal": signal,
        "score": score,
        "price": price,
        "buy_zone": f"Rp {int(support * 0.99):,} - Rp {int(price * 1.01):,}",
        "tp1": f"Rp {tp1:,} (+{((tp1-price)/price)*100:.1f}%)",
        "sl": f"Rp {sl:,} (-{((price-sl)/price)*100:.1f}%)",
        "turnover": turnover
    }


# ==============================================================================
# MODUL SCREENER MULTISAAM
# ==============================================================================
if __name__ == "__main__":
    # Daftar Saham Pantauan (Watchlist Saham Likuid Indonesia)
    watchlist = ["BBCA", "BBRI", "BMRI", "TLKM", "ASII", "UNVR", "ICBP", "GOTO", "BREN"]
    
    print("================================================================================")
    print(f" PEMINDAI SAHAM HARIAN (SCREENER) - MEMINDAI {len(watchlist)} SAHAM...")
    print("================================================================================")

    results = []
    rejected_count = 0

    for ticker in watchlist:
        print(f"-> Memproses {ticker}...", end="\r")
        data, err = fetch_real_stock_data(ticker)
        
        if err:
            continue
            
        res = evaluate_stock(data)
        if res["status"] == "REJECTED":
            rejected_count += 1
        else:
            results.append({"symbol": ticker, "name": data["company_name"], **res})

    print(" " * 60, end="\r") # Clear line status
    print("\nHASIL PEMINDAIAN PASAR SAHAM HARIAN:\n")

    # Tampilkan Saham Berpotensi (BUY / STRONG BUY)
    potential_stocks = [r for r in results if r["signal"] in ["BUY", "STRONG BUY"]]

    if potential_stocks:
        for idx, item in enumerate(potential_stocks, 1):
            print(f"{idx}. {item['symbol']} ({item['name']})")
            print(f"   Sinyal        : 🟢 {item['signal']} (Skor: {item['score']}/9)")
            print(f"   Harga Saat Ini: Rp {item['price']:,}")
            print(f"   Buy Zone      : {item['buy_zone']}")
            print(f"   Target Profit : {item['tp1']}")
            print(f"   Stop Loss     : {item['sl']}")
            print(f"   Transaksi     : Rp {item['turnover']} Miliar/hari")
            print("-" * 65)
    else:
        print("Tidak ada saham yang memenuhi kriteria BUY hari ini.")

    print(f"\n[Catatan Sistem: {rejected_count} saham diabaikan oleh Safety Filter karena transaksi sepi/risiko].")
    print("================================================================================")