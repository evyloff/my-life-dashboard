import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from google.oauth2 import service_account
from googleapiclient.discovery import build
import datetime
import re
import pandas as pd # Wajib untuk manipulasi data Excel/CSV

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
        # ID Kalender Kuliah Anda
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

# --- MODUL 1: JADWAL KULIAH ---
with col_jadwal:
    st.subheader("📅 Agenda Kuliah & Kegiatan")
    
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

                raw_desc = event.get('description', '')
                clean_desc = clean_html(raw_desc)
                
                with st.expander(f"⏰ {tanggal} | {jam_menit} - {event['summary']}"):
                    if clean_desc:
                        st.write(f"**Detail:** {clean_desc}")
                    else:
                        st.caption("Tidak ada detail ruangan.")
    else:
        st.warning("Servis Kalender belum aktif.")

# --- MODUL 2: KEUANGAN (FULL FITUR) ---
with col_keuangan:
    st.subheader("💰 Manajemen Keuangan")
    
    # --- FORM INPUT ---
    with st.expander("📝 Catat Transaksi Baru", expanded=True):
        tipe_transaksi = st.radio("Jenis", ["Pengeluaran 📉", "Pemasukan 📈"], horizontal=True)

        if tipe_transaksi == "Pemasukan 📈":
            kategori_list = ["Uang Saku", "Gaji/Freelance", "Hadiah/Bonus", "Investasi Return", "Lainnya"]
            label_nominal = "Jumlah Masuk (Rp)"
        else:
            kategori_list = ["Makan & Minum", "Transportasi", "Pendidikan/Buku", "Hobi & Game", "Belanja Bulanan", "Investasi Keluar"]
            label_nominal = "Jumlah Keluar (Rp)"

        with st.form("form_keuangan"):
            item = st.text_input("Keterangan", placeholder="Contoh: Beli Buku Kalkulus")
            nominal = st.number_input(label_nominal, min_value=0, step=1000)
            kategori = st.selectbox("Kategori", kategori_list)
            
            if st.form_submit_button("Simpan Transaksi"):
                if db:
                    db.collection("transactions").add({
                        "type": "IN" if "Pemasukan" in tipe_transaksi else "OUT",
                        "item": item,
                        "amount": nominal,
                        "category": kategori,
                        "timestamp": firestore.SERVER_TIMESTAMP # Waktu Server
                    })
                    st.success("Data berhasil disimpan!")
                    st.rerun() # Refresh halaman otomatis

    # --- LAPORAN & DOWNLOAD ---
    st.write("---")
    st.subheader("📊 Laporan Transaksi")
    
    if db:
        # 1. Tarik Data dari Firebase
        docs = db.collection("transactions").order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
        data = []
        for doc in docs:
            d = doc.to_dict()
            # Bersihkan Timestamp agar bisa masuk Excel
            if d.get("timestamp"):
                d["timestamp"] = d["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            data.append(d)
        
        # 2. Buat DataFrame (Tabel) Pandas
        if data:
            df = pd.DataFrame(data)
            
            # Rapikan nama kolom
            df = df.rename(columns={
                "timestamp": "Waktu",
                "item": "Keterangan",
                "amount": "Nominal",
                "category": "Kategori",
                "type": "Tipe"
            })
            
            # Tampilkan Tabel Preview (5 Teratas)
            st.dataframe(df.head(5), use_container_width=True)
            
            # 3. Tombol Download CSV
            csv = df.to_csv(index=False).encode('utf-8')
            
            st.download_button(
                label="📥 Download Laporan (Excel/CSV)",
                data=csv,
                file_name=f'laporan_keuangan_{datetime.date.today()}.csv',
                mime='text/csv',
            )
        else:
            st.info("Belum ada data transaksi.")
