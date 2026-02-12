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
# --- KONFIGURASI ZONA WAKTU & KALENDER ---
# ==========================================
# Paksa zona waktu ke Asia/Jakarta (WIB)
WIB = pytz.timezone('Asia/Jakarta')

DAFTAR_KALENDER = {
    "KULIAH": "7286ff9cd810710bdbc49eb44e4beb288b12b0cd1c7278d741c860eda4dfa019@group.calendar.google.com",
    "ACARA" : "39a66f64cea2cdb4188f78befbcd721976fc5766304e1b029bf99ab746f6ae64@group.calendar.google.com",
    "TUGAS" : "c22e46406c3e93a487dadce76387bed31e0068bb258cf0bb3cc255095abed019@group.calendar.google.com" 
}

ICON_MAP = {
    "KULIAH": "🎓", 
    "ACARA" : "📌", 
    "TUGAS" : "🔥"  
}

# --- SETTING HALAMAN ---
st.set_page_config(page_title="Rashif's Dashboard", page_icon="🚀", layout="wide")

# Initialize Session State untuk fitur Edit Keuangan
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False
    st.session_state.edit_id = None
    st.session_state.edit_data = {}

# --- KONEKSI SERVICES ---
@st.cache_resource
def init_services():
    key_dict = None
    # Coba ambil dari Streamlit Secrets (untuk Cloud Deployment)
    if 'firebase_key' in st.secrets:
        key_dict = dict(st.secrets['firebase_key'])
    # Coba ambil dari file lokal (untuk Testing)
    else:
        try:
            import json
            with open("firebase_key.json") as f:
                key_dict = json.load(f)
        except: pass

    if not key_dict:
        st.error("Kunci JSON tidak ditemukan! Pastikan sudah diunggah ke Secrets atau file lokal.")
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
def clean_html(raw_html):
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html).strip()

def get_merged_events(service):
    if not service: return []
    all_events = []
    # Waktu sekarang dalam UTC untuk query
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

        # Urutkan semua event gabungan berdasarkan waktu mulai
        all_events.sort(key=lambda x: x['start'].get('dateTime', x['start'].get('date')))
        return all_events[:15]
    except Exception as e:
        st.error(f"Gagal mengambil data kalender: {e}")
        return []

# --- UI UTAMA ---
st.title("🚀 Rashif's Command Center")

col_jadwal, col_keuangan = st.columns([1, 1.3]) 

# --- MODUL 1: JADWAL GABUNGAN (ZONA WAKTU WIB FIXED) ---
with col_jadwal:
    st.subheader("📅 Agenda Gabungan (WIB)")
    if calendar_service:
        events = get_merged_events(calendar_service)
        if not events:
            st.info("Tidak ada agenda mendatang.")
        else:
            for event in events:
                start = event['start']
                source = event.get('_source', 'UMUM')
                icon = ICON_MAP.get(source, "📅")

                if 'dateTime' in start:
                    # Parsing waktu asli (ISO Format)
                    dt_obj = datetime.datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                    # Konversi ke WIB secara presisi
                    dt_wib = dt_obj.astimezone(WIB)
                    
                    jam = dt_wib.strftime("%H:%M")
                    tgl = dt_wib.strftime("%d %b")
                    header = f"{icon} {jam} | {event['summary']}"
                else:
                    # Event Seharian
                    t_obj = datetime.datetime.strptime(start['date'], "%Y-%m-%d")
                    tgl = t_obj.strftime("%d %b")
                    header = f"{icon} Seharian | {event['summary']}"
                
                with st.expander(f"{tgl} - {header}"):
                    st.caption(f"Sumber: Kalender {source}")
                    desc = clean_html(event.get('description', ''))
                    if desc: st.write(desc)
                    if 'location' in event:
                        st.caption(f"📍 {event['location']}")
    else:
        st.warning("Google Calendar Service tidak aktif.")

# --- MODUL 2: KEUANGAN FULL CRUD ---
with col_keuangan:
    st.subheader("💰 Manajemen Keuangan")
    tab_in, tab_data = st.tabs(["📝 Input & Edit", "📊 Laporan & Riwayat"])

    with tab_in:
        if st.session_state.edit_mode:
            st.warning(f"✏️ Mode Edit: {st.session_state.edit_data.get('item')}")
            def_tipe = 1 if st.session_state.edit_data.get('type') == 'IN' else 0
            def_item = st.session_state.edit_data.get('item')
            def_amt = st.session_state.edit_data.get('amount')
        else:
            st.info("➕ Tambah Transaksi")
            def_tipe, def_item, def_amt = 0, "", 0

        with st.form("form_finance"):
            c1, c2 = st.columns(2)
            with c1:
                t_pilih = st.radio("Jenis", ["Pengeluaran 📉", "Pemasukan 📈"], index=def_tipe, horizontal=True)
            with c2:
                tgl_pilih = st.date_input("Tanggal", datetime.date.today())

            if "Pemasukan" in t_pilih:
                kat_list = ["Uang Saku", "Gaji/Freelance", "Hadiah/Bonus", "Lainnya"]
                t_db = "IN"
            else:
                kat_list = ["Makan & Minum", "Transportasi", "Pendidikan", "Hobi", "Belanja", "Lainnya"]
                t_db = "OUT"
            
            f_item = st.text_input("Keterangan", value=def_item)
            f_amt = st.number_input("Nominal (Rp)", value=int(def_amt), min_value=0, step=1000)
            f_kat = st.selectbox("Kategori", kat_list)
            
            if st.form_submit_button("💾 Update Data" if st.session_state.edit_mode else "✅ Simpan"):
                if db:
                    waktu_fix = datetime.datetime.combine(tgl_pilih, datetime.datetime.now().time())
                    payload = {"type": t_db, "item": f_item, "amount": f_amt, "category": f_kat, "timestamp": waktu_fix}
                    
                    if st.session_state.edit_mode:
                        db.collection("transactions").document(st.session_state.edit_id).update(payload)
                        st.session_state.edit_mode = False
                    else:
                        db.collection("transactions").add(payload)
                    st.rerun()

    with tab_data:
        if db:
            docs = db.collection("transactions").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(50).stream()
            raw_data = []
            for doc in docs:
                d = doc.to_dict()
                d['id'] = doc.id
                raw_data.append(d)
            
            if raw_data:
                df = pd.DataFrame(raw_data)
                df_c = df.copy()
                df_c['Tanggal'] = pd.to_datetime(df_c['timestamp']).dt.date
                df_c['Tipe'] = df_c['type'].map({'IN': 'Pemasukan', 'OUT': 'Pengeluaran'})
                st.line_chart(df_c.pivot_table(index='Tanggal', columns='Tipe', values='amount', aggfunc='sum', fill_value=0))

                st.write("### Riwayat Transaksi")
                for item in raw_data:
                    c1, c2, c3, c4 = st.columns([2, 4, 2, 1.5])
                    c1.caption(item['timestamp'].strftime("%d %b %H:%M"))
                    c2.write(f"{'🟢' if item['type']=='IN' else '🔴'} **{item['item']}**")
                    c3.write(f"Rp{item['amount']:,}")
                    
                    ed_col, del_col = c4.columns(2)
                    if ed_col.button("✏️", key=f"e_{item['id']}"):
                        st.session_state.edit_mode, st.session_state.edit_id, st.session_state.edit_data = True, item['id'], item
                        st.rerun()
                    if del_col.button("🗑️", key=f"d_{item['id']}"):
                        db.collection("transactions").document(item['id']).delete()
                        st.rerun()
                    st.divider()
