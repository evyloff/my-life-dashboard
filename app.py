import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from google.oauth2 import service_account
from googleapiclient.discovery import build
import datetime
import re
import pandas as pd
import pytz
import io

# ==========================================
# --- 1. KONFIGURASI HALAMAN & CSS ---
# ==========================================
st.set_page_config(page_title="Rashif's Dashboard", page_icon="🚀", layout="wide", initial_sidebar_state="collapsed")

# CSS: Menggunakan Variabel Streamlit agar otomatis Terang/Gelap & Responsif HP
st.markdown("""
<style>
    /* Variabel Warna Adaptif (Ikut Tema HP/Laptop) */
    :root {
        --card-bg: var(--secondary-background-color);
        --text-color: var(--text-color);
        --border-color: rgba(128, 128, 128, 0.2);
    }

    /* Padding Halaman untuk HP */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 4rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    /* Card Style Modern */
    .custom-card {
        background-color: var(--card-bg);
        color: var(--text-color);
        padding: 15px;
        border-radius: 12px;
        margin-bottom: 12px;
        border: 1px solid var(--border-color);
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border-left-width: 6px;
        border-left-style: solid;
        transition: transform 0.2s;
    }
    
    .custom-card:active {
        transform: scale(0.98); /* Efek tekan di HP */
    }

    /* Warna Kategori (Border Kiri) */
    .b-kuliah { border-left-color: #7286ff !important; }
    .b-acara { border-left-color: #ffb74d !important; }
    .b-tugas { border-left-color: #e57373 !important; }
    .b-in { border-left-color: #66bb6a !important; }
    .b-out { border-left-color: #ef5350 !important; }

    /* Typography di dalam Card */
    .card-title { font-weight: 600; font-size: 1rem; margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center; }
    .card-meta { font-size: 0.8rem; opacity: 0.8; display: flex; flex-wrap: wrap; gap: 8px; }
    .card-badge { background: rgba(128,128,128,0.2); padding: 2px 8px; border-radius: 6px; font-size: 0.75rem; }
    .money-in { color: #66bb6a; font-weight: bold; }
    .money-out { color: #ef5350; font-weight: bold; }

    /* Tombol Full Width di HP */
    @media (max-width: 600px) {
        div.stButton > button { width: 100%; margin-top: 5px; }
        [data-testid="stMetric"] { background-color: var(--card-bg); padding: 10px; border-radius: 8px; text-align: center; }
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# --- 2. SETUP & KONEKSI ---
# ==========================================
WIB = pytz.timezone('Asia/Jakarta')

DAFTAR_KALENDER = {
    "KULIAH": "7286ff9cd810710bdbc49eb44e4beb288b12b0cd1c7278d741c860eda4dfa019@group.calendar.google.com",
    "ACARA" : "39a66f64cea2cdb4188f78befbcd721976fc5766304e1b029bf99ab746f6ae64@group.calendar.google.com",
    "TUGAS" : "c22e46406c3e93a487dadce76387bed31e0068bb258cf0bb3cc255095abed019@group.calendar.google.com" 
}
ICON_MAP = {"KULIAH": "🎓", "ACARA" : "📌", "TUGAS" : "🔥"}

if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False
    st.session_state.edit_id = None
    st.session_state.edit_data = {}

@st.cache_resource
def init_services():
    key_dict = None
    if 'firebase_key' in st.secrets:
        key_dict = dict(st.secrets['firebase_key'])
    else:
        try:
            import json
            with open("firebase_key.json") as f: key_dict = json.load(f)
        except: pass
    if not key_dict: return None, None

    # Firebase
    if not firebase_admin._apps:
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    # Google Calendar
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    creds = service_account.Credentials.from_service_account_info(key_dict, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=creds)
    return db, service

db, calendar_service = init_services()

# --- FUNGSI BANTUAN ---
def clean_html(raw_html):
    if not raw_html: return ""
    return re.sub('<.*?>', '', raw_html).strip()

def get_merged_events(service):
    if not service: return []
    all_events = []
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        for label, cal_id in DAFTAR_KALENDER.items():
            if not cal_id or "@" not in cal_id: continue
            events_result = service.events().list(
                calendarId=cal_id, timeMin=now_utc, maxResults=8, 
                singleEvents=True, orderBy='startTime'
            ).execute()
            items = events_result.get('items', [])
            for item in items:
                item['_source'] = label 
                all_events.append(item)
        all_events.sort(key=lambda x: x['start'].get('dateTime', x['start'].get('date')))
        return all_events
    except: return []

def format_rupiah(angka):
    return f"Rp{int(angka):,}".replace(",", ".")

# ==========================================
# --- 3. UI DASHBOARD ---
# ==========================================
st.title("🚀 Rashif's Space")
st.caption(f"📅 {datetime.datetime.now(WIB).strftime('%A, %d %B %Y')}")

# Layout: Di HP akan stack (atas-bawah), di Laptop (kiri-kanan)
col_jadwal, col_gap, col_uang = st.columns([1, 0.1, 1.3])

# --- MODUL AGENDA ---
with col_jadwal:
    st.subheader("📅 Agenda Mendatang")
    if calendar_service:
        events = get_merged_events(calendar_service)
        if not events:
            st.info("Santai dulu, tidak ada agenda! 😎")
        else:
            for event in events:
                start = event['start']
                source = event.get('_source', 'UMUM')
                icon = ICON_MAP.get(source, "📅")
                
                # Parsing Waktu
                if 'dateTime' in start:
                    dt_obj = datetime.datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                    dt_wib = dt_obj.astimezone(WIB)
                    jam_str = dt_wib.strftime("%H:%M")
                    tgl_str = dt_wib.strftime("%d %b")
                else:
                    t_obj = datetime.datetime.strptime(start['date'], "%Y-%m-%d")
                    tgl_str = t_obj.strftime("%d %b")
                    jam_str = "Seharian"
                
                # HTML Card untuk Tampilan Utama
                css_class = f"b-{source.lower()}"
                st.markdown(f"""
                <div class="custom-card {css_class}">
                    <div class="card-title">
                        <span>{icon} {event['summary']}</span>
                        <span class="card-badge">{jam_str}</span>
                    </div>
                    <div class="card-meta">
                        <span>🗓️ {tgl_str}</span>
                        <span>{f"📍 {event.get('location')}" if event.get('location') else ""}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Expander untuk Detail/Deskripsi (Tergabung rapi di bawah card)
                desc = clean_html(event.get('description', ''))
                if desc:
                    with st.expander("📖 Lihat Rincian"):
                        st.write(desc)
                
    else:
        st.warning("Google Calendar Disconnected.")

# --- MODUL KEUANGAN ---
with col_uang:
    st.subheader("💰 Keuangan")
    
    # Ambil Data
    df = pd.DataFrame()
    raw_data = []
    if db:
        docs = db.collection("transactions").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(100).stream()
        for doc in docs:
            d = doc.to_dict()
            d['id'] = doc.id
            raw_data.append(d)
        if raw_data:
            df = pd.DataFrame(raw_data)

    # Dashboard Angka (Metrics)
    if not df.empty:
        tot_in = df[df['type']=='IN']['amount'].sum()
        tot_out = df[df['type']=='OUT']['amount'].sum()
        saldo = tot_in - tot_out
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Sisa Saldo", f"{saldo/1000:.0f}k")
        m2.metric("Masuk", f"{tot_in/1000:.0f}k", delta="📈")
        m3.metric("Keluar", f"{tot_out/1000:.0f}k", delta="-📉")
        st.divider()

    # Tab Navigasi
    tab_in, tab_hist = st.tabs(["📝 Input Transaksi", "📜 Riwayat & Excel"])

    # --- TAB 1: INPUT ---
    with tab_in:
        # Handling Edit Mode
        if st.session_state.edit_mode:
            st.warning(f"✏️ Mengedit: {st.session_state.edit_data.get('item')}")
            def_tipe = 1 if st.session_state.edit_data.get('type') == 'IN' else 0
            def_item = st.session_state.edit_data.get('item')
            def_amt = st.session_state.edit_data.get('amount')
            btn_txt = "💾 Update Data"
        else:
            def_tipe, def_item, def_amt = 0, "", 0
            btn_txt = "✅ Simpan"

        with st.form("finance_form", clear_on_submit=not st.session_state.edit_mode):
            c1, c2 = st.columns(2)
            with c1: t_pilih = st.radio("Tipe", ["Pengeluaran 📉", "Pemasukan 📈"], index=def_tipe)
            with c2: tgl_pilih = st.date_input("Tanggal", datetime.date.today())

            if "Pemasukan" in t_pilih:
                kat_list = ["Uang Saku", "Gaji", "Bonus", "Lainnya"]
                t_db = "IN"
            else:
                kat_list = ["Makan", "Transport", "Jajan", "Pendidikan", "Belanja", "Lainnya"]
                t_db = "OUT"
            
            f_item = st.text_input("Keterangan", value=def_item, placeholder="Contoh: Nasi Padang")
            f_amt = st.number_input("Nominal (Rp)", value=int(def_amt), min_value=0, step=1000)
            f_kat = st.selectbox("Kategori", kat_list)
            
            if st.form_submit_button(btn_txt, use_container_width=True):
                if db:
                    waktu_fix = datetime.datetime.combine(tgl_pilih, datetime.datetime.now().time())
                    payload = {"type": t_db, "item": f_item, "amount": f_amt, "category": f_kat, "timestamp": waktu_fix}
                    
                    if st.session_state.edit_mode:
                        db.collection("transactions").document(st.session_state.edit_id).update(payload)
                        st.toast("Data berhasil diperbarui!")
                        st.session_state.edit_mode = False
                        st.session_state.edit_data = {}
                    else:
                        db.collection("transactions").add(payload)
                        st.toast("Data tersimpan!")
                    st.rerun()

        if st.session_state.edit_mode:
            if st.button("Batal Edit", use_container_width=True):
                st.session_state.edit_mode = False
                st.rerun()

    # --- TAB 2: RIWAYAT & EXCEL ---
    with tab_hist:
        if raw_data:
            # --- FIX: DOWNLOAD EXCEL ---
            # Kita buat copy data khusus untuk Excel agar tidak error Timezone
            df_export = df.copy()
            # Konversi kolom timestamp (timezone aware) menjadi string WIB yang bersih
            df_export['timestamp'] = df_export['timestamp'].apply(
                lambda x: x.astimezone(WIB).strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(x) else ""
            )
            
            # Buat file Excel di memori
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Keuangan')
            
            st.download_button(
                label="📥 Download Excel (.xlsx)",
                data=output.getvalue(),
                file_name=f"Laporan_Keuangan_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            st.divider()

            # --- LIST TRANSAKSI ---
            for item in raw_data:
                is_in = item['type'] == 'IN'
                css_class = "b-in" if is_in else "b-out"
                money_class = "money-in" if is_in else "money-out"
                symbol = "+" if is_in else "-"
                
                # Card HTML
                st.markdown(f"""
                <div class="custom-card {css_class}" style="padding: 10px; margin-bottom: 8px;">
                    <div class="card-title">
                        <span>{item['item']}</span>
                        <span class="{money_class}">{symbol} {format_rupiah(item['amount'])}</span>
                    </div>
                    <div class="card-meta">
                        <span>🕒 {item['timestamp'].strftime("%d %b %H:%M")}</span>
                        <span class="card-badge">{item['category']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Tombol Aksi (Edit/Delete)
                c_edit, c_del = st.columns(2)
                if c_edit.button("✏️ Edit", key=f"e_{item['id']}", use_container_width=True):
                    st.session_state.edit_mode = True
                    st.session_state.edit_id = item['id']
                    st.session_state.edit_data = item
                    st.rerun()
                if c_del.button("🗑️ Hapus", key=f"d_{item['id']}", use_container_width=True):
                    db.collection("transactions").document(item['id']).delete()
                    st.toast("Data dihapus")
                    st.rerun()
        else:
            st.info("Belum ada data transaksi.")
