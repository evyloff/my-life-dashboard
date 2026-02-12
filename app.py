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
# --- KONFIGURASI HALAMAN & CSS ADAPTIF ---
# ==========================================
st.set_page_config(page_title="Rashif's Dashboard", page_icon="🚀", layout="wide")

st.markdown("""
<style>
    :root {
        --card-bg: var(--secondary-background-color);
        --text-main: var(--text-color);
    }
    
    /* Responsive adjustment for Mobile */
    @media (max-width: 600px) {
        .block-container { padding: 1rem !important; }
        h1 { font-size: 1.5rem !important; }
        .stButton > button { width: 100%; margin-bottom: 5px; }
    }

    .custom-card {
        background-color: var(--card-bg);
        color: var(--text-main);
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 10px;
        border-left: 5px solid #ccc;
    }
    .b-kuliah { border-left-color: #7286ff !important; }
    .b-acara { border-left-color: #ffb74d !important; }
    .b-tugas { border-left-color: #e57373 !important; }
    .b-in { border-left-color: #66bb6a !important; }
    .b-out { border-left-color: #ef5350 !important; }
</style>
""", unsafe_allow_html=True)

# --- KONFIGURASI ZONA WAKTU ---
WIB = pytz.timezone('Asia/Jakarta')
DAFTAR_KALENDER = {
    "KULIAH": "7286ff9cd810710bdbc49eb44e4beb288b12b0cd1c7278d741c860eda4dfa019@group.calendar.google.com",
    "ACARA" : "39a66f64cea2cdb4188f78befbcd721976fc5766304e1b029bf99ab746f6ae64@group.calendar.google.com",
    "TUGAS" : "c22e46406c3e93a487dadce76387bed31e0068bb258cf0bb3cc255095abed019@group.calendar.google.com" 
}
ICON_MAP = {"KULIAH": "🎓", "ACARA" : "📌", "TUGAS" : "🔥"}

# --- INIT SESSION STATE ---
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False
    st.session_state.edit_id = None
    st.session_state.edit_data = {}

# --- KONEKSI SERVICES (Sama seperti sebelumnya) ---
@st.cache_resource
def init_services():
    key_dict = None
    if 'firebase_key' in st.secrets: key_dict = dict(st.secrets['firebase_key'])
    else:
        try:
            import json
            with open("firebase_key.json") as f: key_dict = json.load(f)
        except: pass
    if not key_dict: return None, None
    if not firebase_admin._apps: cred = credentials.Certificate(key_dict); firebase_admin.initialize_app(cred)
    db = firestore.client()
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    creds = service_account.Credentials.from_service_account_info(key_dict, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=creds)
    return db, service

db, calendar_service = init_services()

# --- FUNGSI HELPER ---
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
            events_result = service.events().list(calendarId=cal_id, timeMin=now_utc, maxResults=8, singleEvents=True, orderBy='startTime').execute()
            items = events_result.get('items', [])
            for item in items:
                item['_source'] = label
                all_events.append(item)
        all_events.sort(key=lambda x: x['start'].get('dateTime', x['start'].get('date')))
        return all_events
    except: return []

# --- UI UTAMA ---
st.title("🚀 Rashif's Space")
col1, col2 = st.columns([1, 1]) # Gunakan 2 kolom utama yang seimbang untuk desktop/mobile

# --- MODUL 1: AGENDA ---
with col1:
    st.subheader("📅 Agenda")
    if calendar_service:
        events = get_merged_events(calendar_service)
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
            
            # Gunakan Expander agar bisa menampilkan Deskripsi tanpa memenuhi layar
            with st.expander(f"{icon} {jam} | {event['summary'][:25]}..."):
                st.write(f"**{event['summary']}**")
                st.caption(f"Waktu: {tgl} {jam}")
                desc = clean_html(event.get('description', ''))
                if desc: st.info(desc)
                if 'location' in event: st.write(f"📍 {event['location']}")
    else: st.warning("Calendar offline")

# --- MODUL 2: KEUANGAN ---
with col2:
    st.subheader("💰 Keuangan")
    docs = db.collection("transactions").order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
    raw_data = [ {**d.to_dict(), 'id': d.id} for d in docs ]
    df = pd.DataFrame(raw_data)

    if not df.empty:
        df['Tanggal'] = pd.to_datetime(df['timestamp']).dt.date
        tot_in = df[df['type']=='IN']['amount'].sum()
        tot_out = df[df['type']=='OUT']['amount'].sum()
        
        # Tombol Download Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Data')
        st.download_button("📥 Download Excel", data=output.getvalue(), file_name="keuangan.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        # Tabs
        tab1, tab2 = st.tabs(["📝 Transaksi", "📜 History"])
        with tab1:
            # Form input (sama seperti sebelumnya)
            with st.form("add_form"):
                type_input = st.radio("Jenis", ["Pengeluaran 📉", "Pemasukan 📈"], horizontal=True)
                item = st.text_input("Keterangan")
                amount = st.number_input("Nominal", min_value=0, step=1000)
                if st.form_submit_button("Simpan"):
                    t_db = "IN" if "Pemasukan" in type_input else "OUT"
                    db.collection("transactions").add({"type": t_db, "item": item, "amount": amount, "timestamp": datetime.datetime.now()})
                    st.rerun()
        
        with tab2:
            for item in raw_data:
                st.markdown(f"""
                <div class="custom-card {'b-in' if item['type']=='IN' else 'b-out'}">
                    <b>{item['item']}</b> <br> Rp{item['amount']:,}
                </div>
                """, unsafe_allow_html=True)
