import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from google.oauth2 import service_account
from googleapiclient.discovery import build
import datetime
import re
import pandas as pd
import pytz

# ==========================================
# --- KONFIGURASI HALAMAN & CSS ADAPTIF ---
# ==========================================
st.set_page_config(page_title="Rashif's Dashboard", page_icon="🚀", layout="wide", initial_sidebar_state="collapsed")

# CSS: Menggunakan Variabel Streamlit agar otomatis Terang/Gelap
st.markdown("""
<style>
    /* CSS Variables untuk adaptasi tema otomatis */
    :root {
        --card-bg: var(--secondary-background-color);
        --text-main: var(--text-color);
        --border-color: var(--background-color);
    }

    /* Hilangkan padding atas default */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    
    /* Card Style Custom */
    .custom-card {
        background-color: var(--card-bg);
        color: var(--text-main);
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 12px;
        border: 1px solid rgba(128, 128, 128, 0.2); /* Border halus */
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border-left-width: 6px; /* Tebal border kiri */
        border-left-style: solid;
    }

    /* Warna Kategori (Border Kiri) */
    .b-kuliah { border-left-color: #7286ff !important; }
    .b-acara { border-left-color: #ffb74d !important; }
    .b-tugas { border-left-color: #e57373 !important; }
    .b-in { border-left-color: #66bb6a !important; }
    .b-out { border-left-color: #ef5350 !important; }

    /* Elemen di dalam Card */
    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-weight: 600;
        margin-bottom: 4px;
    }
    
    .card-time {
        font-size: 0.85rem;
        background-color: var(--background-color);
        padding: 2px 8px;
        border-radius: 12px;
        opacity: 0.9;
    }

    .card-sub {
        font-size: 0.85rem;
        opacity: 0.7;
    }
    
    .card-amt {
        font-weight: bold;
        font-size: 1.1rem;
    }

    /* Override tombol agar full width di mobile */
    div.stButton > button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# --- KONFIGURASI ZONA WAKTU & DATA ---
# ==========================================
WIB = pytz.timezone('Asia/Jakarta')

DAFTAR_KALENDER = {
    "KULIAH": "7286ff9cd810710bdbc49eb44e4beb288b12b0cd1c7278d741c860eda4dfa019@group.calendar.google.com",
    "ACARA" : "39a66f64cea2cdb4188f78befbcd721976fc5766304e1b029bf99ab746f6ae64@group.calendar.google.com",
    "TUGAS" : "c22e46406c3e93a487dadce76387bed31e0068bb258cf0bb3cc255095abed019@group.calendar.google.com" 
}

ICON_MAP = {
    "KULIAH": "🎓", "ACARA" : "📌", "TUGAS" : "🔥"  
}

# Initialize Session State
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False
    st.session_state.edit_id = None
    st.session_state.edit_data = {}

# --- KONEKSI SERVICES ---
@st.cache_resource
def init_services():
    key_dict = None
    if 'firebase_key' in st.secrets:
        key_dict = dict(st.secrets['firebase_key'])
    else:
        try:
            import json
            with open("firebase_key.json") as f:
                key_dict = json.load(f)
        except: pass

    if not key_dict:
        st.error("Kunci JSON tidak ditemukan!")
        return None, None

    # Firebase
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred)
        db = firestore.client()
    except Exception as e:
        st.error(f"Error Firebase: {e}")
        db = None

    # Google Calendar
    try:
        SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
        creds = service_account.Credentials.from_service_account_info(key_dict, scopes=SCOPES)
        service = build('calendar', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Error Google Calendar: {e}")
        service = None

    return db, service

db, calendar_service = init_services()

# --- FUNGSI HELPER ---
def get_merged_events(service):
    if not service: return []
    all_events = []
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    try:
        for label, cal_id in DAFTAR_KALENDER.items():
            if not cal_id or "@" not in cal_id: continue
            events_result = service.events().list(
                calendarId=cal_id, timeMin=now_utc,
                maxResults=10, singleEvents=True,
                orderBy='startTime'
            ).execute()
            items = events_result.get('items', [])
            for item in items:
                item['_source'] = label 
                all_events.append(item)

        all_events.sort(key=lambda x: x['start'].get('dateTime', x['start'].get('date')))
        return all_events[:15]
    except Exception as e:
        return []

def format_rupiah(angka):
    return f"Rp{int(angka):,}".replace(",", ".")

# ==========================================
# --- UI UTAMA ---
# ==========================================

st.title("🚀 Rashif's Space")
st.caption(f"Update: {datetime.datetime.now(WIB).strftime('%d %B %Y %H:%M WIB')}")

col_jadwal, col_dummy, col_keuangan = st.columns([1, 0.1, 1.2]) 

# --- MODUL 1: JADWAL ---
with col_jadwal:
    st.subheader("📅 Agenda")
    
    if calendar_service:
        events = get_merged_events(calendar_service)
        if not events:
            st.info("🎉 Tidak ada agenda mendatang.")
        else:
            today = datetime.datetime.now(WIB).date()
            tomorrow = today + datetime.timedelta(days=1)
            current_group = None
            
            for event in events:
                start = event['start']
                source = event.get('_source', 'UMUM')
                icon = ICON_MAP.get(source, "📅")
                
                # Parsing Waktu
                if 'dateTime' in start:
                    dt_obj = datetime.datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                    dt_wib = dt_obj.astimezone(WIB)
                    ev_date = dt_wib.date()
                    jam_str = dt_wib.strftime("%H:%M")
                else:
                    t_obj = datetime.datetime.strptime(start['date'], "%Y-%m-%d")
                    ev_date = t_obj.date()
                    jam_str = "Seharian"

                # Grouping Tanggal
                if ev_date == today: group_label = "Hari Ini"
                elif ev_date == tomorrow: group_label = "Besok"
                else: group_label = ev_date.strftime("%d %B %Y")

                if group_label != current_group:
                    st.markdown(f"**{group_label}**")
                    current_group = group_label

                # Render HTML (Tanpa Indentasi di dalam f-string untuk mencegah bug)
                loc = f"📍 {event['location'][:25]}..." if 'location' in event else ""
                
                # Tentukan class CSS berdasarkan sumber (b-kuliah, b-acara, dll)
                css_class = f"b-{source.lower()}"
                
                st.markdown(f"""
<div class="custom-card {css_class}">
    <div class="card-header">
        <span>{icon} {event['summary']}</span>
        <span class="card-time">{jam_str}</span>
    </div>
    <div class="card-sub">{loc}</div>
</div>
""", unsafe_allow_html=True)
                
    else:
        st.warning("Google Service Offline")

# --- MODUL 2: KEUANGAN ---
with col_keuangan:
    st.subheader("💰 Keuangan")
    
    df = pd.DataFrame()
    raw_data = []
    
    if db:
        docs = db.collection("transactions").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(50).stream()
        for doc in docs:
            d = doc.to_dict()
            d['id'] = doc.id
            raw_data.append(d)
        
        if raw_data:
            df = pd.DataFrame(raw_data)
    
    # Dashboard Metrics
    if not df.empty:
        tot_in = df[df['type']=='IN']['amount'].sum()
        tot_out = df[df['type']=='OUT']['amount'].sum()
        saldo = tot_in - tot_out
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Saldo", f"{saldo/1000:.0f}k")
        c2.metric("Masuk", f"{tot_in/1000:.0f}k", delta="📈")
        c3.metric("Keluar", f"{tot_out/1000:.0f}k", delta="-📉")
        st.divider()

    tab_in, tab_hist = st.tabs(["📝 Input", "📜 Riwayat"])

    with tab_in:
        # Mode Edit UI
        if st.session_state.edit_mode:
            st.info(f"✏️ Edit: **{st.session_state.edit_data.get('item')}**")
            def_tipe = 1 if st.session_state.edit_data.get('type') == 'IN' else 0
            def_item = st.session_state.edit_data.get('item')
            def_amt = st.session_state.edit_data.get('amount')
            btn_txt = "Update"
        else:
            def_tipe, def_item, def_amt = 0, "", 0
            btn_txt = "Simpan"

        with st.form("form_finance", clear_on_submit=not st.session_state.edit_mode):
            c_tipe, c_tgl = st.columns(2)
            with c_tipe:
                t_pilih = st.radio("Tipe", ["Pengeluaran 📉", "Pemasukan 📈"], index=def_tipe)
            with c_tgl:
                tgl_pilih = st.date_input("Tanggal", datetime.date.today())

            if "Pemasukan" in t_pilih:
                kat_list = ["Uang Saku", "Gaji", "Bonus", "Lainnya"]
                t_db = "IN"
            else:
                kat_list = ["Makan", "Transport", "Jajan", "Pendidikan", "Belanja", "Lainnya"]
                t_db = "OUT"
            
            f_item = st.text_input("Keterangan", value=def_item, placeholder="Makan Siang...")
            f_amt = st.number_input("Rp", value=int(def_amt), min_value=0, step=1000)
            f_kat = st.selectbox("Kategori", kat_list)
            
            # Tombol Submit
            submitted = st.form_submit_button(btn_txt, type="primary")
            
            if submitted:
                if db:
                    waktu_fix = datetime.datetime.combine(tgl_pilih, datetime.datetime.now().time())
                    payload = {"type": t_db, "item": f_item, "amount": f_amt, "category": f_kat, "timestamp": waktu_fix}
                    
                    if st.session_state.edit_mode:
                        db.collection("transactions").document(st.session_state.edit_id).update(payload)
                        st.toast("Data berhasil diperbarui!")
                        st.session_state.edit_mode = False
                        st.session_state.edit_id = None
                        st.session_state.edit_data = {}
                    else:
                        db.collection("transactions").add(payload)
                        st.toast("Data berhasil disimpan!")
                    st.rerun()

        if st.session_state.edit_mode:
            if st.button("Batal Edit"):
                st.session_state.edit_mode = False
                st.rerun()

    with tab_hist:
        if raw_data:
            st.caption("50 Transaksi Terakhir")
            for item in raw_data:
                is_in = item['type'] == 'IN'
                # Pilih class CSS (b-in atau b-out)
                css_class = "b-in" if is_in else "b-out"
                symbol = "+" if is_in else "-"
                color_text = "#66bb6a" if is_in else "#ef5350"
                
                # Container untuk Card + Tombol
                with st.container():
                    c_info, c_act = st.columns([5, 1.5])
                    with c_info:
                        # Render HTML Card Transaksi
                        st.markdown(f"""
<div class="custom-card {css_class}" style="padding:10px; margin-bottom:5px;">
    <div class="card-header">
        <span>{item['item']}</span>
        <span class="card-amt" style="color:{color_text};">{symbol} {format_rupiah(item['amount'])}</span>
    </div>
    <div class="card-sub">
        {item['timestamp'].strftime("%d %b %H:%M")} • {item['category']}
    </div>
</div>
""", unsafe_allow_html=True)

                    # Tombol Aksi di Kolom Sempit Kanan
                    with c_act:
                         # Jarak vertikal sedikit agar sejajar tengah
                        st.write("") 
                        b1, b2 = st.columns(2)
                        if b1.button("✏️", key=f"e_{item['id']}"):
                            st.session_state.edit_mode = True
                            st.session_state.edit_id = item['id']
                            st.session_state.edit_data = item
                            st.rerun()
                        if b2.button("🗑️", key=f"d_{item['id']}"):
                            db.collection("transactions").document(item['id']).delete()
                            st.toast("Terhapus")
                            st.rerun()
        else:
            st.info("Belum ada data.")
