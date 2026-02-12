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
# --- 1. KONFIGURASI & CSS (UI/UX) ---
# ==========================================
st.set_page_config(page_title="Rashif's Dashboard", page_icon="🚀", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* Variabel Warna & Font */
    :root {
        --bg-color: var(--secondary-background-color);
        --text-color: var(--text-color);
        --card-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }

    /* Layout Halaman */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 5rem;
        padding-left: 1rem;
        padding-right: 1rem;
        max-width: 1200px;
    }

    /* --- STYLE UTAMA CARD --- */
    .list-card {
        background-color: var(--bg-color);
        padding: 15px;
        border-radius: 12px;
        margin-bottom: 8px; /* Jarak antar kartu */
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-left-width: 5px;
        border-left-style: solid;
        box-shadow: var(--card-shadow);
        
        /* Layout Flexbox: Kiri & Kanan */
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
    }

    /* Warna Border Kiri */
    .b-kuliah { border-left-color: #7286ff; }
    .b-acara { border-left-color: #ffb74d; }
    .b-tugas { border-left-color: #e57373; }
    .b-in { border-left-color: #66bb6a; }
    .b-out { border-left-color: #ef5350; }

    /* Typography dalam Card */
    .item-main { 
        font-weight: 600; 
        font-size: 1rem; 
        line-height: 1.2;
    }
    .item-sub { 
        font-size: 0.8rem; 
        opacity: 0.7; 
        margin-top: 2px;
    }
    
    /* Bagian Kanan Card (Tanggal/Uang) */
    .right-content {
        text-align: right;
        min-width: 80px; /* Supaya tanggal tidak gepeng */
        flex-shrink: 0;
    }
    .date-text { font-weight: bold; font-size: 0.9rem; }
    .time-badge { 
        background-color: rgba(128,128,128,0.15); 
        padding: 2px 6px; 
        border-radius: 4px; 
        font-size: 0.75rem; 
        display: inline-block;
        margin-top: 4px;
    }
    .money-val { font-weight: bold; font-size: 1rem; }

    /* --- DASHBOARD KEUANGAN (STATISTIK) --- */
    .stat-container { display: flex; gap: 10px; margin-bottom: 20px; }
    .stat-card {
        background-color: var(--bg-color);
        border-radius: 12px; padding: 15px; flex: 1; text-align: center;
        border: 1px solid rgba(128, 128, 128, 0.2);
        box-shadow: var(--card-shadow);
    }
    .stat-title { font-size: 0.85rem; opacity: 0.8; }
    .stat-value { font-size: 1.3rem; font-weight: 700; margin-top: 5px; }
    .acc-blue { border-top: 4px solid #4da6ff; color: #4da6ff; }
    .acc-green { border-top: 4px solid #66bb6a; color: #66bb6a; }
    .acc-red { border-top: 4px solid #ef5350; color: #ef5350; }

    /* Responsif HP */
    @media (max-width: 600px) {
        .stat-container { flex-wrap: wrap; }
        .stat-card { min-width: 30%; padding: 10px; }
        .stButton > button { width: 100%; }
        .item-main { font-size: 0.95rem; }
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# --- 2. BACKEND & SERVICES ---
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
    if not firebase_admin._apps:
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    creds = service_account.Credentials.from_service_account_info(key_dict, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=creds)
    return db, service

db, calendar_service = init_services()

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

# Layout Columns
col_kiri, col_spacer, col_kanan = st.columns([1, 0.1, 1.4])

# --- MODULE AGENDA ---
with col_kiri:
    st.subheader("📅 Agenda")
    if calendar_service:
        events = get_merged_events(calendar_service)
        if not events:
            st.info("Agenda kosong.")
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
                    jam = "Seharian"
                
                # --- STRUKTUR HTML BARU ---
                # Kiri: Judul
                # Kanan: Tanggal & Jam
                st.markdown(f"""
                <div class="list-card b-{source.lower()}">
                    <div style="flex-grow: 1;">
                        <div class="item-main">{icon} {event['summary']}</div>
                        {f'<div class="item-sub">📍 {event["location"][:20]}...</div>' if 'location' in event else ''}
                    </div>
                    <div class="right-content">
                        <div class="date-text">{tgl}</div>
                        <div class="time-badge">⏰ {jam}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Expander Rincian (Hidden by default)
                desc = clean_html(event.get('description', ''))
                if desc:
                    with st.expander("📝 Rincian", expanded=False):
                        st.write(desc)

    else:
        st.warning("Gagal memuat Kalender.")

# --- MODULE KEUANGAN ---
with col_kanan:
    st.subheader("💰 Keuangan")
    
    # Get Data
    df = pd.DataFrame()
    raw_data = []
    if db:
        docs = db.collection("transactions").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(50).stream()
        for doc in docs:
            d = doc.to_dict()
            d['id'] = doc.id
            raw_data.append(d)
        if raw_data: df = pd.DataFrame(raw_data)

    # --- Statistik ---
    if not df.empty:
        tot_in = df[df['type']=='IN']['amount'].sum()
        tot_out = df[df['type']=='OUT']['amount'].sum()
        saldo = tot_in - tot_out
        
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
        st.info("Belum ada data.")

    # --- Tabs ---
    tab_in, tab_hist = st.tabs(["📝 Input", "📜 Riwayat"])

    with tab_in:
        # Form
        if st.session_state.edit_mode:
            st.info(f"✏️ Edit: {st.session_state.edit_data.get('item')}")
            def_tipe = 1 if st.session_state.edit_data.get('type') == 'IN' else 0
            def_item = st.session_state.edit_data.get('item')
            def_amt = st.session_state.edit_data.get('amount')
            btn_txt = "Simpan Perubahan"
        else:
            def_tipe, def_item, def_amt = 0, "", 0
            btn_txt = "Tambah"

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
            
            f_item = st.text_input("Keterangan", value=def_item, placeholder="Cth: Nasi Goreng")
            f_amt = st.number_input("Nominal (Rp)", value=int(def_amt), min_value=0, step=1000)
            f_kat = st.selectbox("Kategori", kat_list)
            
            if st.form_submit_button(btn_txt, use_container_width=True, type="primary"):
                if db:
                    waktu_fix = datetime.datetime.combine(tgl_pilih, datetime.datetime.now().time())
                    payload = {"type": t_db, "item": f_item, "amount": f_amt, "category": f_kat, "timestamp": waktu_fix}
                    
                    if st.session_state.edit_mode:
                        db.collection("transactions").document(st.session_state.edit_id).update(payload)
                        st.toast("Berhasil diupdate!")
                        st.session_state.edit_mode = False
                        st.session_state.edit_data = {}
                    else:
                        db.collection("transactions").add(payload)
                        st.toast("Berhasil disimpan!")
                    st.rerun()
        
        if st.session_state.edit_mode:
            if st.button("Batal Edit", use_container_width=True):
                st.session_state.edit_mode = False; st.rerun()

    with tab_hist:
        if raw_data:
            # Excel
            df_export = df.copy()
            df_export['timestamp'] = df_export['timestamp'].apply(lambda x: x.astimezone(WIB).strftime('%Y-%m-%d %H:%M') if pd.notnull(x) else "")
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer: df_export.to_excel(writer, index=False, sheet_name='Data')
            st.download_button("📥 Excel", data=buf.getvalue(), file_name="Keuangan.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            st.write("")

            for item in raw_data:
                is_in = item['type'] == 'IN'
                css_cls = "b-in" if is_in else "b-out"
                color = "#66bb6a" if is_in else "#ef5350"
                symbol = "+" if is_in else "-"

                # List Transaksi (Tetap menggunakan style sebelumnya karena sudah cocok)
                st.markdown(f"""
                <div class="list-card {css_cls}">
                    <div style="flex-grow:1;">
                        <div class="item-main">{item['item']}</div>
                        <div class="item-sub">{item['timestamp'].strftime("%d %b")} • {item['category']}</div>
                    </div>
                    <div class="right-content">
                        <div class="money-val" style="color:{color};">{symbol} {format_rupiah_full(item['amount'])}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2 = st.columns([1,1])
                if c1.button("✏️", key=f"e_{item['id']}", use_container_width=True):
                    st.session_state.edit_mode = True; st.session_state.edit_id = item['id']; st.session_state.edit_data = item; st.rerun()
                if c2.button("🗑️", key=f"d_{item['id']}", use_container_width=True):
                    db.collection("transactions").document(item['id']).delete(); st.rerun()
