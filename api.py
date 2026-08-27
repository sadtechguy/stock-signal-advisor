# ==============================================================================
# PROYEK: ASISTEN SINYAL SAHAM (STOCK SIGNAL ADVISOR)
# FILE  : api.py
# FUNGSI: Server Web API (FastAPI Endpoint) dengan Analisis Terperinci
# ==============================================================================

import os
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from typing import List
import yfinance as yf
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from contextlib import asynccontextmanager

# Muat variabel lingkungan dari file .env
load_dotenv()
# ==============================================================================
# KONFIGURASI TELEGRAM BOT
# (Ganti teks di bawah dengan Token dan Chat ID asli Anda)
# ==============================================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_notification(stock_data: dict):
    """
    Mengirimkan pesan ringkasan sinyal saham ke Telegram HP secara otomatis
    """
    if TELEGRAM_BOT_TOKEN == "MASUKKAN_HTTP_API_TOKEN_ANDA_DI_SINI":
        return False  # Belum diisi token

    symbol = stock_data["symbol"]
    name = stock_data["company_name"]
    signal = stock_data["signal"]
    score = stock_data["score"]
    price = stock_data["current_price"]
    tp = stock_data["trading_plan"]
    metrics = stock_data["metrics"]

    # Format Pesan Telegram (Menggunakan HTML Formatting)
    message = (
        f"🚨 <b>SINYAL SAHAM TERDETEKSI!</b> 🚨\n\n"
        f"<b>Saham:</b> {symbol} ({name})\n"
        f"<b>Status Sinyal:</b> 🟢 <b>{signal}</b> (Skor: {score}/9)\n"
        f"<b>Harga Terkini:</b> Rp {price:,}\n\n"
        f"🎯 <b>TRADING PLAN:</b>\n"
        f"• <b>Buy Zone:</b> {tp['buy_zone']}\n"
        f"• <b>Target Profit:</b> {tp['target_profit_1']}\n"
        f"• <b>Stop Loss:</b> {tp['stop_loss']}\n"
        f"• <b>Transaksi:</b> Rp {metrics['daily_turnover_m']} M/hari\n\n"
        f"💡 <i>Analisis otomatis dari Stock Signal Advisor API</i>"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except Exception as e:
        print(f"Gagal mengirim pesan Telegram: {e}")
        return False
    
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inisialisasi Scheduler
    scheduler = BackgroundScheduler(timezone="Asia/Jakarta")
    # Atur jadwal: Setiap hari Senin-Jumat jam 08.00 WIB
    scheduler.add_job(auto_daily_screener_job, 'cron', day_of_week='mon-fri', hour=8, minute=0)
    scheduler.start()
    print("⏱️ [SCHEDULER] Sistem Pemindai Otomatis Jam 08.00 WIB telah Aktif!")

    yield # Server berjalan

    # Matikan Scheduler saat server shutdown
    scheduler.shutdown()

# Buat App FastAPI dengan lifespan scheduler

app = FastAPI(
    title="Stock Signal Advisor API",
    description="API untuk menganalisis dan menyajikan sinyal rekomendasi saham BEI",
    version="1.2.0",
    lifespan=lifespan
)

def fetch_and_evaluate(symbol_ticker: str):
    # Tambahkan sufiks .JK secara otomatis untuk saham Indonesia jika belum ada
    ticker_code = f"{symbol_ticker}.JK" if not symbol_ticker.endswith(".JK") and "." not in symbol_ticker else symbol_ticker
    stock = yf.Ticker(ticker_code)
    
    try:
        df = stock.history(period="1y")
        if df.empty:
            return None

        current_price = int(df['Close'].iloc[-1])
        recent_volume = df['Volume'].tail(5).mean()
        turnover_m = (recent_volume * current_price) / 1_000_000_000

        # ----------------------------------------------------------------------
        # 1. PASSER / SAFETY FILTER (Minimal Transaksi Rp 5 Miliar / Hari)
        # ----------------------------------------------------------------------
        if turnover_m < 5.0:
            return None

        # ----------------------------------------------------------------------
        # 2. PERHITUNGAN INDIKATOR TEKNIKAL & FUNDAMENTAL
        # ----------------------------------------------------------------------
        # RSI 14-Hari
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        current_rsi = (100 - (100 / (1 + rs))).iloc[-1]

        # EMA 200 & Level Support/Resistance
        current_ema_200 = int(df['Close'].ewm(span=200, adjust=False).mean().iloc[-1])
        support_level = int(df['Low'].tail(30).min())
        resistance_level = int(df['High'].tail(30).max())

        # Fundamental (PE & ROE)
        per = stock.info.get("forwardPE", 15.0) or 15.0
        avg_per = 18.0  # Rata-rata industri historis
        roe = (stock.info.get("returnOnEquity", 0.15) or 0.15) * 100

        # ----------------------------------------------------------------------
        # 3. SKORING DAN PEMBENTUKAN POIN PENJELASAN
        # ----------------------------------------------------------------------
        score = 0
        reasons_tech = []
        reasons_fund = []

        # A. Evaluasi Teknikal
        if current_rsi < 30:
            score += 2
            reasons_tech.append(f"RSI (14) = {current_rsi:.1f} (<30): Mengindikasikan oversold (jenuh jual), berpotensi rebound naik.")
        elif current_rsi < 45:
            score += 1
            reasons_tech.append(f"RSI (14) = {current_rsi:.1f}: Berada di area bawah konsolidasi (cukup murah).")
        elif current_rsi > 70:
            score -= 2
            reasons_tech.append(f"RSI (14) = {current_rsi:.1f} (>70): Mengindikasikan overbought (jenuh beli), rawan koreksi.")
        else:
            reasons_tech.append(f"RSI (14) = {current_rsi:.1f}: Berada dalam rentang konsolidasi normal.")

        dist_to_support = ((current_price - support_level) / support_level) * 100 if support_level > 0 else 999
        if 0 <= dist_to_support <= 3.5:
            score += 2
            reasons_tech.append(f"Harga (Rp {current_price:,}) sangat dekat ({dist_to_support:.1f}%) dari Support kuat (Rp {support_level:,}).")
        else:
            reasons_tech.append(f"Level Support 30 hari berada di Rp {support_level:,} (jarak {dist_to_support:.1f}%).")

        if current_price > current_ema_200 and current_ema_200 > 0:
            score += 1
            reasons_tech.append(f"Harga konsisten di atas EMA 200 (Rp {current_ema_200:,}): Tren besar jangka panjang BULLISH.")
        else:
            reasons_tech.append(f"Harga di bawah EMA 200 (Rp {current_ema_200:,}): Tren besar jangka panjang BEARISH.")

        # B. Evaluasi Fundamental
        if per > 0 and per < avg_per:
            score += 2
            per_discount = ((avg_per - per) / avg_per) * 100
            reasons_fund.append(f"P/E Ratio ({per:.1f}x) terdiskon {per_discount:.1f}% dari rata-rata industri ({avg_per:.1f}x) -> UNDERVALUED.")
        else:
            reasons_fund.append(f"P/E Ratio ({per:.1f}x) wajar mendekati rata-rata industri.")

        if roe >= 15:
            score += 1
            reasons_fund.append(f"Profitabilitas solid dengan Return on Equity (ROE) = {roe:.1f}% (≥15%).")
        else:
            reasons_fund.append(f"Return on Equity (ROE) = {roe:.1f}%.")

        # ----------------------------------------------------------------------
        # 4. KEPUTUSAN SINYAL & TRADING PLAN
        # ----------------------------------------------------------------------
        if score >= 6: signal = "STRONG BUY"
        elif score >= 4: signal = "BUY"
        elif score >= 2: signal = "HOLD"
        else: signal = "AVOID"

        tp1 = int(resistance_level) if resistance_level > current_price else int(current_price * 1.08)
        sl = int(support_level * 0.96)

        return {
            "symbol": symbol_ticker.upper().replace(".JK", ""),
            "company_name": stock.info.get("shortName", symbol_ticker),
            "signal": signal,
            "score": score,
            "current_price": current_price,
            "trading_plan": {
                "buy_zone": f"Rp {int(support_level * 0.99):,} - Rp {int(current_price * 1.01):,}",
                "target_profit_1": f"Rp {tp1:,} (+{((tp1-current_price)/current_price)*100:.1f}%)",
                "stop_loss": f"Rp {sl:,} (-{((current_price-sl)/current_price)*100:.1f}%)"
            },
            "metrics": {
                "rsi_14": round(current_rsi, 2),
                "daily_turnover_m": round(turnover_m, 2)
            },
            "reasons_tech": reasons_tech,
            "reasons_fund": reasons_fund
        }
    except Exception:
        return None
    
def auto_daily_screener_job():
    """
    Tugas Otomatis: Memindai Watchlist Saham setiap Jam 08.00 WIB
    dan mengirimkan notifikasi ke Telegram.
    """
    print("\n[SCHEDULER] Menjalankan pemindaian saham otomatis harian (08.00 WIB)...")
    watchlist = ["BBCA", "BBRI", "BMRI", "TLKM", "ASII", "UNVR", "ICBP", "GOTO", "BREN"]
    lq45_watchlist = [
        # Perbankan & Keuangan
        "BBCA", "BBRI", "BMRI", "BBNI", "BRIS", "ARTO",
        
        # Telekomunikasi & Menara
        "TLKM", "ISAT", "EXCL", "TOWR", "MTEL",
        
        # Barang Konsumsi, Ritel & Unggas
        "ICBP", "INDF", "UNVR", "MYOR", "AMRT", "ACES", "CPIN",
        
        # Otomotif & Konglomerasi
        "ASII", "SRTG",
        
        # Energi, Tambang & Migas
        "ADRO", "PTBA", "ITMG", "UNTR", "PGAS", "AKRA", "MEDC", "HRUM", "ESSA",
        
        # Logam Mineral & Emas
        "AMMN", "MDKA", "INCO", "ANTM", "MBMA",
        
        # Infrastruktur & Semen
        "JSMR", "SMGR", "INTP",
        
        # Energi Terbarukan & Petrokimia
        "PGEO", "BRPT", 
        
        # Kertas & Kehutanan
        "INKP", "TKIM",
        
        # Properti & Konstruksi
        "CTRA", "BSDE",
        
        # Kesehatan & Farmasi
        "KLBF",
        
        # Teknologi
        "GOTO"
    ]

    found_count = 0

    for ticker in lq45_watchlist:
        data = fetch_and_evaluate(ticker)
        if data and data["signal"] in ["BUY", "STRONG BUY"]:
            send_telegram_notification(data)
            found_count += 1

    print(f"[SCHEDULER] Pemindaian selesai. {found_count} sinyal potensial dikirim ke Telegram.\n")


# ==============================================================================
# ENDPOINTS API
# ==============================================================================

@app.get("/")
def root():
    return {"status": "online", "message": "Stock Signal Advisor API is Running"}


@app.get("/api/v1/stock/{symbol}")
def get_stock_signal(symbol: str):
    result = fetch_and_evaluate(symbol)
    if not result:
        return {"status": "error", "message": f"Saham {symbol} tidak ditemukan atau tidak lolos Safety Filter (Likuiditas < Rp 5M/hari)."}
    return {"status": "success", "data": result}


@app.get("/api/v1/screener")
def run_screener(tickers: str = Query("BBCA,BBRI,BMRI,TLKM,ASII", description="Daftar saham dipisah koma")):
    ticker_list = [t.strip() for t in tickers.split(",")]
    results = []

    for ticker in ticker_list:
        data = fetch_and_evaluate(ticker)
        if data and data["signal"] in ["BUY", "STRONG BUY"]:
            results.append(data)

    return {
        "status": "success",
        "total_scanned": len(ticker_list),
        "total_potentials": len(results),
        "data": results
    }

@app.get("/api/v1/test-telegram/{symbol}")
def test_telegram_alert(symbol: str):
    data = fetch_and_evaluate(symbol)
    if not data:
        return {"status": "error", "message": f"Saham {symbol} tidak ditemukan atau tidak lolos Safety Filter."}
    
    success = send_telegram_notification(data)
    if success:
        return {"status": "success", "message": f"Notifikasi sinyal saham {symbol} berhasil dikirim ke Telegram!"}
    else:
        return {"status": "error", "message": "Gagal mengirim ke Telegram. Periksa Token API atau Chat ID Anda."}
    

# ------------------------------------------------------------------------------
# ENDPOINT TEST MANUAL SCHEDULER (Menjalankan Tugas Jam 8 Pagi Seketika)
# Contoh URL: /api/v1/trigger-daily-screener
# ------------------------------------------------------------------------------
@app.get("/api/v1/trigger-daily-screener")
def trigger_screener_manual():
    auto_daily_screener_job()
    return {
        "status": "success", 
        "message": "Pemindaian otomatis berhasil dipicu manual! Periksa Telegram Anda."
    }