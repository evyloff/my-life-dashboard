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
            # PERBAIKAN DI SINI: Tanda kutip sudah dilengkapi
            btn_text = "💾 Update Data" if st.session_state.edit_mode else "✅ Simpan Transaksi"
            submitted = st.form_submit_button(btn_text)
            
            if submitted:
                if db:
                    jam_sekarang = datetime.datetime.now().time()
                    waktu_fix = datetime.datetime.combine(tanggal_transaksi, jam_sekarang)
                    
                    data_payload = {
                        "type": tipe_db,
                        "item": item,
                        "amount": nominal,
                        "category": kategori,
                        "timestamp": waktu_fix
                    }

                    if st.session_state.edit_mode:
                        # LOGIKA UPDATE
                        db.collection("transactions").document(st.session_state.edit_id).update(data_payload)
                        st.success("Data berhasil diperbarui!")
                        # Reset Mode Edit
                        st.session_state.edit_mode = False
                        st.session_state.edit_id = None
                        st.session_state.edit_data = {}
                    else:
                        # LOGIKA CREATE
                        db.collection("transactions").add(data_payload)
                        st.success("Data berhasil disimpan!")
                    
                    st.rerun()

        # Tombol Batal Edit
        if st.session_state.edit_mode:
            if st.button("❌ Batal Edit"):
                st.session_state.edit_mode = False
                st.rerun()

    # === TAB 2: READ & DELETE & REPORT ===
    with tab_data:
        if db:
            # Kontrol View (Limit)
            col_filter, col_download = st.columns([2, 1])
            with col_filter:
                limit_view = st.selectbox("Tampilkan Data:", [10, 50, 100, "Semua (Hati-hati berat)"])
            
            # Logic Query Firebase
            query = db.collection("transactions").order_by("timestamp", direction=firestore.Query.DESCENDING)
            
            if limit_view != "Semua (Hati-hati berat)":
                query = query.limit(limit_view)
            
            docs = query.stream()
            
            # Konversi ke List of Dict dengan ID
            data_list = []
            for doc in docs:
                d = doc.to_dict()
                d['id'] = doc.id # Penting untuk Edit/Delete
                data_list.append(d)
            
            if data_list:
                df = pd.DataFrame(data_list)
                
                # --- AREA GRAFIK ---
                with st.expander("📊 Lihat Grafik Tren", expanded=True):
                    df_chart = df.copy()
                    df_chart['Tanggal'] = pd.to_datetime(df_chart['timestamp']).dt.date
                    df_chart['Tipe'] = df_chart['type'].map({'IN': 'Pemasukan', 'OUT': 'Pengeluaran'})
                    chart_data = df_chart.pivot_table(index='Tanggal', columns='Tipe', values='amount', aggfunc='sum', fill_value=0)
                    st.line_chart(chart_data, color=["#FF4B4B", "#00CC96"])

                # --- AREA TABEL MANAJEMEN ---
                st.write("---")
                st.write("### 🗂️ Daftar Transaksi")
                
                # Header Tabel Manual
                c1, c2, c3, c4, c5 = st.columns([1.5, 3, 2, 1, 1])
                c1.write("**Waktu**")
                c2.write("**Keterangan**")
                c3.write("**Nominal**")
                c4.write("**Aksi**")
                
                for item in data_list:
                    c1, c2, c3, c4, c5 = st.columns([1.5, 3, 2, 0.5, 0.5])
                    
                    # Formatting
                    tgl = item['timestamp'].strftime("%d %b %H:%M")
                    warna_uang = "🟢" if item['type'] == 'IN' else "🔴"
                    nom = f"Rp{item['amount']:,}"
                    
                    c1.caption(tgl)
                    c2.write(f"{warna_uang} **{item['item']}**\n\n*{item['category']}*")
                    c3.write(nom)
                    
                    # TOMBOL EDIT ✏️
                    if c4.button("✏️", key=f"edit_{item['id']}"):
                        st.session_state.edit_mode = True
                        st.session_state.edit_id = item['id']
                        st.session_state.edit_data = item
                        st.rerun() # Refresh untuk pindah ke Tab 1 otomatis
                        
                    # TOMBOL DELETE 🗑️
                    if c5.button("🗑️", key=f"del_{item['id']}"):
                        db.collection("transactions").document(item['id']).delete()
                        st.toast("Data dihapus!")
                        st.rerun()
                    
                    st.divider()

                # --- AREA DOWNLOAD ---
                with col_download:
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        df_export = pd.DataFrame(data_list)
                        # Bersihkan kolom ID dan Timestamp object sebelum export
                        df_export['timestamp'] = df_export['timestamp'].apply(lambda x: x.strftime("%Y-%m-%d %H:%M"))
                        df_export = df_export.drop(columns=['id'])
                        df_export.to_excel(writer, sheet_name='Laporan', index=False)
                    
                    st.download_button(
                        label="📥 Download Excel",
                        data=buffer.getvalue(),
                        file_name=f'Laporan_Keuangan_{datetime.date.today()}.xlsx',
                        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )

            else:
                st.info("Belum ada data transaksi.")
