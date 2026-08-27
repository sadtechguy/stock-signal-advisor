# ==============================================================================
# PROYEK: ASISTEN SINYAL SAHAM (STOCK SIGNAL ADVISOR)
# FILE  : app.py
# FUNGSI: Antarmuka Visual Web Dashboard (Streamlit UI - Optimized Layout)
# ==============================================================================

import streamlit as st
import requests

# Konfigurasi Halaman Streamlit
st.set_page_config(
    page_title="Stock Signal Advisor Dashboard",
    page_icon="📈",
    layout="wide"
)

# Custom CSS untuk mengecilkan ukuran font metric & mencegah teks terpotong (...)
st.markdown("""
    <style>
    [data-testid="stMetricValue"] {
        font-size: 1.3rem !important;
        white-space: normal !important;
        word-break: break-word !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.9rem !important;
    }
    </style>
""", unsafe_allow_html=True)

API_BASE_URL = "http://127.0.0.1:8000"

st.title("📈 Asisten Sinyal Saham (BEI)")
st.caption("Dashboard Analisis Sinyal Otomatis & Trading Plan Berbasis AI & Safety Filter")

# Sidebar - Navigasi Modul
st.sidebar.header("Navigasi Aplikasi")
menu = st.sidebar.radio("Pilih Fitur:", ["Pencarian Saham (Single Stock)", "Pemindai Harian (Screener)"])

# ------------------------------------------------------------------------------
# FITUR 1: ANALISIS SAHAM TUNGGAL
# ------------------------------------------------------------------------------
if menu == "Pencarian Saham (Single Stock)":
    st.subheader("🔍 Analisis Rekomendasi Saham")
    
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        symbol = st.text_input("Masukkan Kode Saham (Contoh: BBCA, TLKM, ASII):", value="BBCA").upper()
    with col_btn:
        st.write("") # Spacer
        st.write("")
        btn_search = st.button("Analisis Saham", type="primary")

    if btn_search or symbol:
        with st.spinner(f"Mengambil data & menganalisis {symbol}..."):
            try:
                res = requests.get(f"{API_BASE_URL}/api/v1/stock/{symbol}")
                if res.status_code == 200:
                    response_json = res.json()
                    
                    if response_json.get("status") == "success":
                        data = response_json["data"]
                        
                        # Banner Status Sinyal
                        signal = data["signal"]
                        if signal == "STRONG BUY":
                            st.success(f"### STATUS SISTEM: 🟢 {signal} (Skor: {data['score']}/9)")
                        elif signal == "BUY":
                            st.info(f"### STATUS SISTEM: 🔵 {signal} (Skor: {data['score']}/9)")
                        elif signal == "HOLD":
                            st.warning(f"### STATUS SISTEM: 🟡 {signal} (Skor: {data['score']}/9)")
                        else:
                            st.error(f"### STATUS SISTEM: 🔴 {signal} (Skor: {data['score']}/9)")
                        
                        st.write(f"**Nama Perusahaan:** {data['company_name']} | **Harga Terkini:** Rp {data['current_price']:,}")
                        st.divider()

                        # 1. TRADING PLAN GRID (Layout 2x2)
                        st.markdown("#### 🎯 **1. Rencana Eksekusi (Trading Plan)**")
                        tp = data["trading_plan"]
                        metrics = data["metrics"]
                        
                        row1_col1, row1_col2 = st.columns(2)
                        with row1_col1:
                            st.metric("Area Beli (Buy Zone)", tp["buy_zone"])
                        with row1_col2:
                            st.metric("Target Profit 1 (TP1)", tp["target_profit_1"])
                            
                        st.write("") # Margin spacing
                        
                        row2_col1, row2_col2 = st.columns(2)
                        with row2_col1:
                            st.metric("Batas Rugi (Stop Loss)", tp["stop_loss"])
                        with row2_col2:
                            st.metric("Rata-rata Transaksi Harian", f"Rp {metrics['daily_turnover_m']} M/hari")

                        st.divider()
                        
                        # 2. RINGKASAN NARASI
                        st.markdown("#### 📝 **2. Ringkasan Narasi (Untuk Klien / Presentasi)**")
                        st.info(f'"{data["symbol"]} direkomendasikan **{signal}** (Skor: {data["score"]}/9) karena kombinasi indikator teknikal dan fundamentalnya berada dalam kondisi yang menguntungkan. Saham mendekati area penopang harga (Support) dengan valuasi bisnis yang tergolong murah. Saham ini juga lolos Safety Filter dengan likuiditas Rp {metrics["daily_turnover_m"]} Miliar/hari."')

                        st.divider()

                        # 3. RINCIAN ALASAN DAN PENJELASAN INDIKATOR
                        st.markdown("#### 💡 **3. Alasan dan Penjelasan Indikator**")
                        col_tech, col_fund = st.columns(2)

                        with col_tech:
                            st.markdown("##### 📈 **[A] Analisis Teknikal**")
                            for r in data.get("reasons_tech", []):
                                st.markdown(f"- {r}")

                        with col_fund:
                            st.markdown("##### 📊 **[B] Analisis Fundamental**")
                            for r in data.get("reasons_fund", []):
                                st.markdown(f"- {r}")

                    else:
                        st.error(response_json.get("message", "Terjadi kesalahan saat pemrosesan."))
                else:
                    st.error("Gagal terhubung ke API Backend. Pastikan uvicorn berjalan.")
            except Exception as e:
                st.error(f"Error koneksi: {e}")

# ------------------------------------------------------------------------------
# FITUR 2: PEMINDAI HARIAN (SCREENER)
# ------------------------------------------------------------------------------
elif menu == "Pemindai Harian (Screener)":
    st.subheader("🚀 Screener Pemindai Saham Potensial Hari Ini")
    watchlist_input = st.text_area("Daftar Watchlist Saham (pisahkan dengan koma):", "BBCA, BBRI, BMRI, TLKM, ASII, UNVR, ICBP, GOTO, BREN")
    
    if st.button("Jalankan Pemindaian", type="primary"):
        with st.spinner("Memindai seluruh watchlist pasar..."):
            try:
                res = requests.get(f"{API_BASE_URL}/api/v1/screener?tickers={watchlist_input}")
                if res.status_code == 200:
                    json_data = res.json()
                    st.write(f"**Total Dipindai:** {json_data['total_scanned']} Saham | **Ditemukan Potensial:** {json_data['total_potentials']} Saham")
                    
                    potentials = json_data["data"]
                    if potentials:
                        for item in potentials:
                            with st.expander(f"🟢 {item['symbol']} - {item['signal']} (Harga: Rp {item['current_price']:,})"):
                                tp = item["trading_plan"]
                                st.write(f"**Nama Perusahaan:** {item['company_name']}")
                                st.write(f"**Buy Zone:** {tp['buy_zone']} | **Target Profit:** {tp['target_profit_1']} | **Stop Loss:** {tp['stop_loss']}")
                                st.write(f"**Transaksi Harian:** Rp {item['metrics']['daily_turnover_m']} Miliar/hari")
                                
                                st.markdown("---")
                                col_t, col_f = st.columns(2)
                                with col_t:
                                    st.markdown("**Analisis Teknikal:**")
                                    for r in item.get("reasons_tech", []):
                                        st.markdown(f"- {r}")
                                with col_f:
                                    st.markdown("**Analisis Fundamental:**")
                                    for r in item.get("reasons_fund", []):
                                        st.markdown(f"- {r}")
                    else:
                        st.warning("Tidak ada saham di watchlist yang memenuhi kriteria BUY hari ini.")
                else:
                    st.error("Gagal memanggil data Screener dari API Backend.")
            except Exception as e:
                st.error(f"Error koneksi: {e}")