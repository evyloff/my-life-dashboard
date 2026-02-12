import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from google.oauth2 import service_account
from googleapiclient.discovery import build
import datetime
import re  # Library untuk bersih-bersih teks

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Rashif's Dashboard", page_icon="🚀", layout="wide")

# --- KONEKSI DATABASE & KALENDER (CACHED) ---
@st.cache_resource
def init_services():
    # 1. Siapkan Kunci
    key_dict = None
    if 'firebase_key' in st.secrets:
        key_dict = dict(st.secrets['firebase_key'])
    else:
        # Fallback untuk lokal
        try:
            import json
            with open("firebase_key.json") as f:
                key_dict = json.load(f)
        except:
            pass

    if not key_dict:
        st.error("Kunci rahasia tidak ditemukan!")
        return None, None

    # 2. Koneksi Firebase
    if not firebase_admin._apps:
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    # 3. Koneksi Google Calendar
    try:
        SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
        creds = service_account.Credentials.from_service_account_info(
            key_dict, scopes=SCOPES
        )
        service = build('calendar', 'v3', credentials=creds)
    except Exception as e:
        st.warning(f"Gagal konek kalender: {e}")
        service = None

    return db, service

db, calendar_service = init_services()

# --- FUNGSI BANTUAN ---
def clean_html(raw_html):
    # Hapus tag HTML seperti <table>, <tr>, <td>
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.strip()

def get_upcoming_events(service, max_results=10):
    if not service: return []
    try:
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        # GANTI ID KALENDER DI SINI (Pastikan ID Panjang tadi tetap dipakai)
        calendar_id = '7286ff9cd810710bdbc49eb44e4beb288b12b0cd1c7278d741c860eda4dfa019@group.calendar.google.com' 
        
        events_result = service.events().list(
            calendarId=calendar_id, timeMin=now,
            maxResults=max_results, singleEvents=True,
            orderBy='startTime'
        ).execute()
        return events_result.get('items', [])
    except Exception as e:
        st.error(f"Error API Kalender: {e}")
        return []

# --- UI UTAMA ---
st.title("🚀 Rashif's Command Center")

col_jadwal, col_keuangan = st.columns([1, 1])

# --- MODUL 1: JADWAL ---
with col_jadwal:
    st.subheader("📅 Agenda Kuliah & Kegiatan")
    
    if calendar_service:
        events = get_upcoming_events(calendar_service)
        if not events:
            st.info("Tidak ada agenda dalam waktu dekat.")
        else:
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                # Format waktu: Ambil Jam & Menit saja (contoh: 08:50)
                waktu_obj = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
                # Sesuaikan ke WIB (UTC+7) secara manual sederhana
                waktu_wib = waktu_obj + datetime.timedelta(hours=7)
                jam_menit = waktu_wib.strftime("%H:%M")
                tanggal = waktu_wib.strftime("%d %b")
                
                # Bersihkan Deskripsi
                raw_desc = event.get('description', '')
                clean_desc = clean_html(raw_desc)
                
                with st.expander(f"⏰ {tanggal} | {jam_menit} - {event['summary']}"):
                    if clean_desc:
                        st.write(clean_desc)
                    else:
                        st.caption("Tidak ada detail ruangan.")
    else:
        st.warning("Servis Kalender belum aktif.")

# --- MODUL 2: KEUANGAN ---
with col_keuangan:
    st.subheader("💸 Quick Expense")
    with st.form("form_keuangan"):
        item = st.text_input("Nama Pengeluaran")
        nominal = st.number_input("Nominal (Rp)", min_value=0, step=1000)
        kategori = st.selectbox("Kategori", ["Makan", "Transport", "Edu", "Hobi", "Investasi"])
        
        if st.form_submit_button("Simpan Data"):
            if db:
                db.collection("transactions").add({
                    "item": item,
                    "amount": nominal,
                    "category": kategori,
                    "timestamp": firestore.SERVER_TIMESTAMP
                })
                st.success("Tersimpan!")
