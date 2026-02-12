import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from google.oauth2 import service_account
from googleapiclient.discovery import build
import datetime
import re
import pandas as pd
import io

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Rashif's Dashboard", page_icon="🚀", layout="wide")

# --- INITIALIZE SESSION STATE (Untuk Fitur Edit) ---
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False
    st.session_state.edit_id = None
    st.session_state.edit_data = {}

# --- KONEKSI DATABASE & KALENDER (CACHED) ---
@st.cache_resource
def init_services():
    # 1. Siapkan Kunci
    key_dict = None
    if 'firebase_key' in st.secrets:
        key_dict = dict(st.secrets['firebase_key'])
    else:
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
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred)
        db = firestore.client()
    except Exception as e:
        st.warning(f"Error Firebase: {e}")
        db = None

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
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.strip()

def get_upcoming_events(service, max_results=10):
    if not service: return []
    try:
        now = datetime.datetime.utcnow().isoformat() + 'Z'
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

col_jadwal, col_keuangan = st.columns([1, 1.5]) 

# --- MODUL 1: JADWAL KULIAH ---
with col_jadwal:
    st.subheader("📅 Agenda Kuliah")
    
    if calendar_service:
        events = get_upcoming_events(calendar_service)
        if not events:
            st.info("Tidak ada agenda dalam waktu dekat.")
        else:
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                try:
                    waktu_obj = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
                    waktu_wib = waktu_obj + datetime.timedelta(hours=7)
                    jam_menit = waktu_wib.strftime("%H:%M")
                    tanggal = waktu_wib.strftime("%d %b")
                except:
                    jam_menit = "Full Day"
                    tanggal = "N/A"

                clean_desc = clean_html(event.get('description', ''))
                
                with st.expander(f"⏰ {tanggal} | {jam_menit} - {event['summary']}"):
                    if clean_desc:
                        st.write(f"**Detail:** {clean_desc}")
    else:
        st.warning("Servis Kalender belum aktif.")

# --- MODUL 2: FULL CRUD KEUANGAN ---
with col_keuangan:
    st.subheader("💰 Manajemen Keuangan")
    
    # Tab Navigasi
    tab_input, tab_data = st.tabs(["📝 Form Input & Edit", "📊 Data & Laporan"])

    # === TAB 1: CREATE & UPDATE ===
    with tab_input:
        # Judul Form berubah tergantung Mode (Tambah Baru / Edit)
        if st.session_state.edit_mode:
            st.warning(f"✏️ Sedang Mengedit Transaksi: {st.session_state.edit_data.get('item')}")
            # Load data lama ke variabel default
            default_tipe = 1 if st.session_state.edit_data.get('type') == 'IN' else 0
            default_item = st.session_state.edit_data.get('item')
            default_amount = st.session_state.edit_data.get('amount')
            
            # Cek kategori agar tidak error jika kategori lama tidak ada di list
            cat_val = st.session_state.edit_data.get('category')
            # List gabungan sementara untuk menghindari error index
            temp_options = [cat_val] + ["Makan & Minum", "Transportasi", "Pendidikan/Buku", "Hobi & Game", "Uang Saku", "Gaji", "Lainnya"]
            default_cat_index = 0 
        else:
            st.info("➕ Tambah Transaksi Baru")
            default_tipe = 0
            default_item = ""
            default_amount = 0
            default_cat_index = 0

        # --- FORMULIR ---
        with st.form("form_keuangan"):
            c1, c2 = st.columns(2)
            
            with c1:
                tipe_opsi = ["Pengeluaran 📉", "Pemasukan 📈"]
                tipe_transaksi = st.radio("Jenis", tipe_opsi, index=default_tipe, horizontal=True)
            
            with c2:
                tanggal_transaksi = st.date_input("Tanggal", datetime.date.today())

            # Logika List Kategori
            if tipe_transaksi == "Pemasukan 📈":
                kategori_list = ["Uang Saku", "Gaji/Freelance", "Hadiah/Bonus", "Investasi Return", "Lainnya"]
                tipe_db = "IN"
            else:
                kategori_list = ["Makan & Minum", "Transportasi", "Pendidikan/Buku", "Hobi & Game", "Belanja Bulanan", "Investasi Keluar", "Lainnya"]
                tipe_db = "OUT"
            
            # Input Fields
            item = st.text_input("Keterangan", value=default_item, placeholder="Contoh: Beli Makan")
            nominal = st.number_input("Nominal (Rp)", value=default_amount, min_value=0, step=1000)
            kategori = st.selectbox("Kategori", kategori_list)
            
            # Tombol Submit (Dinamis: Simpan Baru / Update)
            btn_text = "💾 Update Data" if st.session_state.edit_mode else "✅ Simpan Transaksi
