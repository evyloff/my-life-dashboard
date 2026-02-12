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

col_jadwal, col_keuangan = st.columns([1, 1.2]) # Kolom kanan sedikit lebih lebar

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

# --- MODUL 2: MANAJEMEN KEUANGAN (TABS) ---
with col_keuangan:
    st.subheader("💰 Dompet Digital")
    
    # MEMBUAT 3 TAB TERPISAH
    tab_input, tab_grafik, tab_hapus = st.tabs(["📝 Input Data", "📊 Grafik & Laporan", "🗑️ Riwayat & Hapus"])

    # === TAB 1: INPUT DATA ===
    with tab_input:
        tipe_transaksi = st.radio("Jenis", ["Pengeluaran 📉", "Pemasukan 📈"], horizontal=True)

        if tipe_transaksi == "Pemasukan 📈":
            kategori_list = ["Uang Saku", "Gaji/Freelance", "Hadiah/Bonus", "Investasi Return", "Lainnya"]
            label_nominal = "Jumlah Masuk (Rp)"
            tipe_db = "IN"
        else:
            kategori_list = ["Makan & Minum", "Transportasi", "Pendidikan/Buku", "Hobi & Game", "Belanja Bulanan", "Investasi Keluar"]
            label_nominal = "Jumlah Keluar (Rp)"
            tipe_db = "OUT"

        with st.form("form_keuangan"):
            item = st.text_input("Keterangan", placeholder="Contoh: Beli Buku Kalkulus")
            nominal = st.number_input(label_nominal, min_value=0, step=1000)
            kategori = st.selectbox("Kategori", kategori_list)
            tanggal_transaksi = st.date_input("Tanggal", datetime.date.today())
            
            if st.form_submit_button("Simpan Transaksi"):
                if db:
                    jam_sekarang = datetime.datetime.now().time()
                    waktu_fix = datetime.datetime.combine(tanggal_transaksi, jam_sekarang)
                    db.collection("transactions").add({
                        "type": tipe_db,
                        "item": item,
                        "amount": nominal,
                        "category": kategori,
                        "timestamp": waktu_fix
                    })
                    st.success("Data berhasil disimpan!")
                    st.rerun()

    # === TAB 2: GRAFIK & LAPORAN ===
    with tab_grafik:
        if db:
            docs = db.collection("transactions").order_by("timestamp", direction=firestore.Query.ASCENDING).stream()
            data = [doc.to_dict() for doc in docs]
            
            if data:
                df = pd.DataFrame(data)
                df['Tanggal'] = pd.to_datetime(df['timestamp']).dt.date
                df['Tipe'] = df['type'].map({'IN': 'Pemasukan', 'OUT': 'Pengeluaran'})
                
                # Grafik
                st.caption("Tren Keuangan Harian")
                chart_data = df.pivot_table(index='Tanggal', columns='Tipe', values='amount', aggfunc='sum', fill_value=0)
                st.line_chart(chart_data, color=["#FF4B4B", "#00CC96"])

                # Download Excel
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_export = df[['Tanggal', 'Tipe', 'category', 'item', 'amount']].copy()
                    df_export.to_excel(writer, sheet_name='Laporan Keuangan', index=False)
                
                st.download_button(
                    label="📥 Download Excel (.xlsx)",
                    data=buffer.getvalue(),
                    file_name=f'Laporan_Keuangan_{datetime.date.today()}.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
            else:
                st.info("Belum ada data.")

    # === TAB 3: RIWAYAT & HAPUS (BARU) ===
    with tab_hapus:
        st.write("Daftar 10 Transaksi Terakhir (Klik tombol 'Hapus' untuk membatalkan)")
        
        if db:
            # Ambil data beserta ID Dokumennya
            docs = db.collection("transactions").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(10).stream()
            
            # Kita loop manual agar bisa pasang tombol di sebelah setiap item
            found_data = False
            for doc in docs:
                found_data = True
                d = doc.to_dict()
                doc_id = doc.id # Kunci Unik Dokumen
                
                # Format Tampilan Baris
                tgl = d['timestamp'].strftime("%d %b")
                keterangan = f"**{d['item']}** ({d['category']})"
                nominal_fmt = f"Rp{d['amount']:,}"
                warna = "🟢" if d['type'] == 'IN' else "🔴"
                
                # Layout Kolom: [Icon] [Tanggal] [Keterangan] [Nominal] [Tombol Hapus]
                c1, c2, c3, c4, c5 = st.columns([0.5, 2, 4, 2, 1.5])
                
                c1.write(warna)
                c2.write(tgl)
                c3.write(keterangan)
                c4.write(nominal_fmt)
                
                # Tombol Hapus dengan ID Unik
                if c5.button("Hapus", key=doc_id):
                    # Hapus dari Firebase
                    db.collection("transactions").document(doc_id).delete()
                    st.toast(f"Transaksi '{d['item']}' berhasil dihapus!", icon="🗑️")
                    st.rerun() # Refresh halaman
                
                st.divider() # Garis pemisah antar item
            
            if not found_data:
                st.info("Belum ada riwayat transaksi.")
