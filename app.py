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
# --- KONFIGURASI HALAMAN & CSS ---
# ==========================================
st.set_page_config(page_title="Rashif's Dashboard", page_icon="🚀", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS untuk UI yang lebih modern dan Mobile Friendly
st.markdown("""
<style>
    /* Hilangkan padding atas default agar lebih compact di HP */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Card Style untuk Event dan Transaksi */
    .stCard {
        background-color: #262730;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        border-left: 5px solid #4CAF50;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    
    /* Warna border berbeda untuk tipe event */
    .border-KULIAH { border-left-color: #7286ff !important; }
    .border-ACARA { border-left-color: #ffb74d !important; }
    .border-TUGAS { border-left-color: #e57373 !important; }
    .border-IN { border-left-color: #66bb6a !important; } /* Hijau */
    .border-OUT { border-left-color: #ef5350 !important; } /* Merah */

    /* Typography */
    h3 { font-size: 1.2rem !important; margin-bottom: 0.5rem !important; }
    p { margin-bottom: 0.2rem !important; font-size: 0.9rem; }
    .small-text { font-size: 0.8rem; color: #a0a0a0; }
    .big-amt { font-weight: bold; font-size: 1.1rem; }
    
    /* Tombol Action (Edit/Delete) agar sejajar */
    .action-btn-container { display: flex; gap: 5px; }
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
def clean_html(raw_html):
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html).strip()

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
        st.error(f"Gagal mengambil data kalender: {e}")
        return []

def format_rupiah(angka):
    return f"Rp{int(angka):,}".replace(",", ".")

# ==========================================
# --- UI UTAMA ---
# ==========================================

st.title("🚀 Rashif's Space")
st.caption(f"Update Terakhir: {datetime.datetime.now(WIB).strftime('%d %B %Y %H:%M WIB')}")

# Layout kolom: Di HP akan otomatis stack ke bawah
col_jadwal, col_dummy, col_keuangan = st.columns([1, 0.1, 1.2]) 

# --- MODUL 1: JADWAL (CARD STYLE) ---
with col_jadwal:
    st.subheader("📅 Agenda")
    
    if calendar_service:
        events = get_merged_events(calendar_service)
        if not events:
            st.info("🎉 Tidak ada agenda mendatang.")
        else:
            # Grouping sederhana untuk UX lebih baik
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

                # Tentukan Label Group
                if ev_date == today: group_label = "Hari Ini"
                elif ev_date == tomorrow: group_label = "Besok"
                else: group_label = ev_date.strftime("%d %B %Y") # Format tanggal lainnya

                # Tampilkan Header Group jika berubah
                if group_label != current_group:
                    st.markdown(f"**{group_label}**")
                    current_group = group_label

                # Render Card HTML
                loc = f"📍 {event['location'][:20]}..." if 'location' in event else ""
                html_card = f"""
                <div class="stCard border-{source}">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="font-weight:bold;">{icon} {event['summary']}</span>
                        <span style="background:#333; padding:2px 6px; border-radius:4px; font-size:0.8rem;">{jam_str}</span>
                    </div>
                    <div class="small-text" style="margin-top:5px;">
                        {loc}
                    </div>
                </div>
                """
                st.markdown(html_card, unsafe_allow_html=True)
                
    else:
        st.warning("Google Service Offline")

# --- MODUL 2: KEUANGAN (DASHBOARD STYLE) ---
with col_keuangan:
    st.subheader("💰 Keuangan")
    
    # Ambil Data dulu untuk Dashboard
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
            df['Tanggal'] = pd.to_datetime(df['timestamp']).dt.date
    
    # 1. Dashboard Mini (Metrics)
    if not df.empty:
        # Filter bulan ini sederhana (opsional, disini ambil total dari 50 transaksi terakhir)
        tot_in = df[df['type']=='IN']['amount'].sum()
        tot_out = df[df['type']=='OUT']['amount'].sum()
        saldo = tot_in - tot_out
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Saldo", f"{saldo/1000:.0f}k", delta_color="normal")
        m2.metric("Masuk", f"{tot_in/1000:.0f}k", delta="📈")
        m3.metric("Keluar", f"{tot_out/1000:.0f}k", delta="-📉")
        st.divider()

    # Tabs UI
    tab_in, tab_hist = st.tabs(["📝 Input / Edit", "📜 Riwayat"])

    with tab_in:
        # Mode Edit UI
        if st.session_state.edit_mode:
            st.warning(f"Sedang mengedit: {st.session_state.edit_data.get('item')}")
            def_tipe = 1 if st.session_state.edit_data.get('type') == 'IN' else 0
            def_item = st.session_state.edit_data.get('item')
            def_amt = st.session_state.edit_data.get('amount')
            btn_label = "💾 Update Perubahan"
        else:
            def_tipe, def_item, def_amt = 0, "", 0
            btn_label = "✅ Simpan Transaksi"

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
            
            f_item = st.text_input("Nama Transaksi", value=def_item, placeholder="Contoh: Nasi Goreng")
            f_amt = st.number_input("Nominal (Rp)", value=int(def_amt), min_value=0, step=1000)
            f_kat = st.selectbox("Kategori", kat_list)
            
            submitted = st.form_submit_button(btn_label, use_container_width=True)
            
            if submitted:
                if db:
                    waktu_fix = datetime.datetime.combine(tgl_pilih, datetime.datetime.now().time())
                    payload = {"type": t_db, "item": f_item, "amount": f_amt, "category": f_kat, "timestamp": waktu_fix}
                    
                    if st.session_state.edit_mode:
                        db.collection("transactions").document(st.session_state.edit_id).update(payload)
                        st.success("Data berhasil diupdate!")
                        st.session_state.edit_mode = False
                        st.session_state.edit_id = None
                        st.session_state.edit_data = {}
                    else:
                        db.collection("transactions").add(payload)
                        st.success("Data tersimpan!")
                    st.rerun()
                else:
                    st.error("Database tidak terkoneksi.")

        if st.session_state.edit_mode:
            if st.button("Batal Edit", use_container_width=True):
                st.session_state.edit_mode = False
                st.rerun()

    with tab_hist:
        if raw_data:
            # Grafik simple
            st.area_chart(df.pivot_table(index='timestamp', columns='type', values='amount', aggfunc='sum', fill_value=0), height=150, color=["#66bb6a", "#ef5350"])
            
            st.write("### Daftar Transaksi")
            for item in raw_data:
                # Menentukan warna dan simbol
                is_in = item['type'] == 'IN'
                color_class = "border-IN" if is_in else "border-OUT"
                symbol = "+" if is_in else "-"
                color_text = "#66bb6a" if is_in else "#ef5350"
                
                # Layout Custom Card untuk Transaksi
                with st.container():
                    col_info, col_act = st.columns([4, 1])
                    
                    with col_info:
                        # Render HTML Card
                        st.markdown(f"""
                        <div class="stCard {color_class}" style="padding: 10px; margin-bottom: 5px;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <div>
                                    <div style="font-weight:bold;">{item['item']}</div>
                                    <div class="small-text">{item['timestamp'].strftime("%d %b %H:%M")} • {item['category']}</div>
                                </div>
                                <div class="big-amt" style="color:{color_text};">
                                    {symbol} {format_rupiah(item['amount'])}
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col_act:
                        # Tombol Edit & Delete
                        # Menggunakan columns lagi agar tombol tidak terlalu besar
                        st.write("") # Spacer
                        b1, b2 = st.columns(2)
                        if b1.button("✏️", key=f"e_{item['id']}"):
                            st.session_state.edit_mode = True
                            st.session_state.edit_id = item['id']
                            st.session_state.edit_data = item
                            st.rerun()
                        
                        if b2.button("🗑️", key=f"d_{item['id']}"):
                            db.collection("transactions").document(item['id']).delete()
                            st.toast("Transaksi dihapus!")
                            st.rerun()
        else:
            st.info("Belum ada data transaksi.")
