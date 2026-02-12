import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from google.oauth2 import service_account
from googleapiclient.discovery import build
import datetime

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
        # Fallback untuk lokal jika file json ada
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
        # Scope Read-Only
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
def get_upcoming_events(service, max_results=5):
    if not service: return []
    try:
        now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
        events_result = service.events().list(
            calendarId='7286ff9cd810710bdbc49eb44e4beb288b12b0cd1c7278d741c860eda4dfa019@group.calendar.google.com', timeMin=now,
            maxResults=max_results, singleEvents=True,
            orderBy='startTime'
        ).execute()
        return events_result.get('items', [])
    except Exception as e:
        st.error(f"Error API Kalender: {e}")
        return []

# --- UI UTAMA ---
st.title("🚀 Rashif's Command Center")

# Layout 2 Kolom
col_jadwal, col_keuangan = st.columns([1, 1])

# --- MODUL 1: JADWAL (GOOGLE CALENDAR) ---
with col_jadwal:
    st.subheader("📅 Agenda Mendatang")
    
    if calendar_service:
        events = get_upcoming_events(calendar_service)
        if not events:
            st.info("Tidak ada agenda dalam waktu dekat.")
        else:
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                # Format waktu sederhana
                waktu_bersih = start.replace('T', ' ')[:16] 
                
                with st.expander(f"⏰ {waktu_bersih} | {event['summary']}"):
                    if 'description' in event:
                        st.write(event['description'])
                    else:
                        st.caption("Tidak ada deskripsi.")
    else:
        st.warning("Servis Kalender belum aktif. Cek settings API.")

# --- MODUL 2: INPUT KEUANGAN (FIREBASE) ---
with col_keuangan:
    st.subheader("💸 Quick Expense")
    with st.form("form_keuangan"):
        item = st.text_input("Nama Pengeluaran", placeholder="Misal: Kopi Kenangan")
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
            else:
                st.error("Database offline.")
