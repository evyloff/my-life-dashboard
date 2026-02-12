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
# --- 1. KONFIGURASI HALAMAN & CSS MODERN ---
# ==========================================
st.set_page_config(page_title="Rashif's Dashboard", page_icon="🚀", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* Variabel Warna */
    :root {
        --bg-color: var(--secondary-background-color);
        --text-color: var(--text-color);
        --card-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    /* Padding Halaman HP & Laptop */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 5rem;
        padding-left: 1rem;
        padding-right: 1rem;
        max-width: 1200px;
    }

    /* --- STYLE 1: KARTU STATISTIK (SALDO/MASUK/KELUAR) --- */
    .stat-container {
        display: flex;
        gap: 10px;
        margin-bottom: 20px;
        width: 100%;
    }
    
    .stat-card {
        background-color: var(--bg-color);
        border-radius: 12px;
        padding: 15px;
        flex: 1; /* Agar lebar rata */
        text-align: center;
        border: 1px solid rgba(128, 128, 128, 0.2);
        box-shadow: var(--card-shadow);
        transition: transform 0.2s;
        min-width: 90px; /* Mencegah terlalu gepeng di HP */
    }

    .stat-card:hover { transform: translateY(-2px); }

    .stat-title { font-size: 0.85rem; opacity: 0.8; margin-bottom: 5px; font-weight: 500; }
    .stat-value { font-size: 1.4rem; font-weight: 700; margin: 0; }
    
    /* Warna Aksen Khusus Statistik */
    .acc-blue { border-top: 4px solid #4da6ff; color: #4da6ff; }
    .acc-green { border-top: 4px solid #66bb6a; color: #66bb6a; }
    .acc-red { border-top: 4px solid #ef5350; color: #ef5350; }

    /* --- STYLE 2: AGENDA & TRANSAKSI LIST --- */
    .list-card {
        background-color: var(--bg-color);
        padding: 12px;
        border-radius: 10px;
        margin-bottom: 10px;
        border: 1px solid rgba(128, 128, 128, 0.15);
        border-left-width: 5px;
        border-left-style: solid;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    /* Warna Kategori List */
    .b-kuliah { border-left-color: #7286ff; }
    .b-acara { border-left-color: #ffb74d; }
    .b-tugas { border-left-color: #e57373; }
    .b-in { border-left-color: #66bb6a; }
    .b-out { border-left-color: #ef5350; }

    .item-main { font-weight: 600; font-size: 0.95rem; }
    .item-sub { font-size: 0.8rem; opacity: 0.7; }
    .money-val { font-weight: bold; font-size: 1rem; }

    /* RESPONSIVE HP: Stack kolom & Font Size */
    @media (max-width: 600px) {
        .stat-container { flex-direction: row; flex-wrap: wrap; } 
        .stat-card { min-width: 28%; padding: 10px; } /* 3 kolom di HP tapi rapat */
        .stat-value { font-size: 1.1rem; }
        .stButton > button { width: 100%; margin-top: 5px; }
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# --- 2. LOGIC BACKEND ---
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

    # Init Apps
    if not firebase_admin._apps:
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    creds = service_account.Credentials.from_service_account_info(key_dict, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=creds)
    return db, service

db, calendar_service = init_services()

# --- Helpers ---
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
            res = service.events().list(calendarId=cal_id, timeMin=now_utc, maxResults=8, singleEvents=True, orderBy='startTime').execute()
            for item in res.get('items', []):
                item['_source'] = label 
                all_events.append(item)
        all_events.sort(key=lambda x: x['start'].get('dateTime', x['start'].get('date')))
        return all_events
    except: return []

def format_rupiah(angka):
    # Format K (Ribuan) untuk Card Statistik agar muat di HP
    if angka >= 1000000: return f"{angka/1000000:.1f}Jt"
    if angka >= 1000: return f"{angka/1000:.0f}k"
    return str(angka)

def format_rupiah_full(angka):
    return f"Rp{int(angka):,}".replace(",", ".")

# ==========================================
# --- 3. UI DASHBOARD ---
# ==========================================
st.title("🚀 Rashif's Space")
st.caption(f"📅 {datetime.datetime.now(WIB).strftime('%A, %d %B %Y')}")

# Layout 2 Kolom (Desktop) / Stack (Mobile)
col_kiri, col_spacer, col_kanan = st.columns([1, 0.1, 1.4])

# --- KOLOM KIRI: JADWAL ---
with col_kiri:
    st.subheader("📅 Agenda")
    if calendar_service:
        events = get_merged_events(calendar_service)
        if not events:
            st.info("Tidak ada agenda.")
        else:
            for event in events:
                start = event['start']
                source = event.get('_source', 'UMUM')
                icon = ICON_MAP.get(source, "📅")
                
                if 'dateTime' in start:
                    dt_obj = datetime.datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00')).astimezone(WIB)
                    jam = dt_obj.strftime("%H:%M")
                    tgl = dt_obj.strftime("%d %b")
                else:
                    tgl = datetime.datetime.strptime(start['date'], "%Y-%m-%d").strftime("%d %b")
                    jam = "Full"
                
                # Render Agenda Card
                st.markdown(f"""
                <div class="list-card b-{source.lower()}">
                    <div>
                        <div class="item-main">{icon} {event['summary']}</div>
                        <div class="item-sub">🗓️ {tgl} • ⏰ {jam}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Deskripsi di dalam Expander (Lebih bersih)
                desc = clean_html(event.get('description', ''))
                if desc:
                    with st.expander("Rincian"):
                        st.write(desc)
    else:
        st.warning("Google Calendar Disconnected.")

# --- KOLOM KANAN: KEUANGAN ---
with col_kanan:
    st.subheader("💰 Keuangan")
    
    # Ambil Data
    df = pd.DataFrame()
    raw_data = []
    if db:
        docs = db.collection("transactions").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(50).stream()
        for doc in docs:
            d = doc.to_dict()
            d['id'] = doc.id
            raw_data.append(d)
        if raw_data: df = pd.DataFrame(raw_data)

    # --- UI STATISTIK BARU (KOTAK BERWARNA) ---
    if not df.empty:
        tot_in = df[df['type']=='IN']['amount'].sum()
        tot_out = df[df['type']=='OUT']['amount'].sum()
        saldo = tot_in - tot_out
        
        # HTML Custom untuk Kotak Statistik
        st.markdown(f"""
        <div class="stat-container">
            <div class="stat-card acc-blue">
                <div class="stat-title">Saldo</div>
                <div class="stat-value">{format_rupiah(saldo)}</div>
            </div>
            <div class="stat-card acc-green">
                <div class="stat-title">Masuk</div>
                <div class="stat-value">+{format_rupiah(tot_in)}</div>
            </div>
            <div class="stat-card acc-red">
                <div class="stat-title">Keluar</div>
                <div class="stat-value">-{format_rupiah(tot_out)}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Belum ada data transaksi.")

    # --- TABS INPUT & RIWAYAT ---
    tab_in, tab_hist = st.tabs(["📝 Input Transaksi", "📜 Riwayat & Data"])

    with tab_in:
        # Form Handling
        if st.session_state.edit_mode:
            st.markdown(f"**✏️ Mode Edit:** `{st.session_state.edit_data.get('item')}`")
            def_tipe = 1 if st.session_state.edit_data.get('type') == 'IN' else 0
            def_item = st.session_state.edit_data.get('item')
            def_amt = st.session_state.edit_data.get('amount')
            btn_txt = "Simpan Perubahan"
        else:
            def_tipe, def_item, def_amt = 0, "", 0
            btn_txt = "Tambah Transaksi"

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
            
            f_item = st.text_input("Keterangan", value=def_item, placeholder="Cth: Makan Siang")
            f_amt = st.number_input("Nominal (Rp)", value=int(def_amt), min_value=0, step=1000)
            f_kat = st.selectbox("Kategori", kat_list)
            
            if st.form_submit_button(btn_txt, use_container_width=True, type="primary"):
                if db:
                    waktu_fix = datetime.datetime.combine(tgl_pilih, datetime.datetime.now().time())
                    payload = {"type": t_db, "item": f_item, "amount": f_amt, "category": f_kat, "timestamp": waktu_fix}
                    
                    if st.session_state.edit_mode:
                        db.collection("transactions").document(st.session_state.edit_id).update(payload)
                        st.toast("Data Updated!")
                        st.session_state.edit_mode = False
                        st.session_state.edit_data = {}
                    else:
                        db.collection("transactions").add(payload)
                        st.toast("Data Saved!")
                    st.rerun()

        if st.session_state.edit_mode:
            if st.button("Batal", use_container_width=True):
                st.session_state.edit_mode = False
                st.rerun()

    with tab_hist:
        if raw_data:
            # Download Excel Logic
            df_export = df.copy()
            # Convert timezone aware datetime to string to avoid Excel Error
            df_export['timestamp'] = df_export['timestamp'].apply(lambda x: x.astimezone(WIB).strftime('%Y-%m-%d %H:%M') if pd.notnull(x) else "")
            
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Data')
            
            st.download_button("📥 Download Excel", data=buf.getvalue(), file_name="Keuangan.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            st.write("") # Spacer

            # List Transaksi
            for item in raw_data:
                is_in = item['type'] == 'IN'
                css_cls = "b-in" if is_in else "b-out"
                color = "#66bb6a" if is_in else "#ef5350"
                symbol = "+" if is_in else "-"

                # Tampilan List yang Rapi (Menyerupai Mobile App)
                st.markdown(f"""
                <div class="list-card {css_cls}">
                    <div style="flex-grow:1;">
                        <div class="item-main">{item['item']}</div>
                        <div class="item-sub">{item['timestamp'].strftime("%d %b %H:%M")} • {item['category']}</div>
                    </div>
                    <div class="money-val" style="color:{color}; text-align:right;">
                        {symbol} {format_rupiah_full(item['amount'])}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Tombol Edit/Delete (Icon Only agar hemat tempat)
                c_act1, c_act2 = st.columns([1,1])
                if c_act1.button("✏️ Edit", key=f"e_{item['id']}", use_container_width=True):
                    st.session_state.edit_mode = True
                    st.session_state.edit_id = item['id']
                    st.session_state.edit_data = item
                    st.rerun()
                if c_act2.button("🗑️ Hapus", key=f"d_{item['id']}", use_container_width=True):
                    db.collection("transactions").document(item['id']).delete()
                    st.toast("Terhapus")
                    st.rerun()
