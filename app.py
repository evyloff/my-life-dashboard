import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from google.oauth2 import service_account
from googleapiclient.discovery import build
import datetime
import re
import pandas as pd
import pytz

# --- KONFIGURASI ---
WIB = pytz.timezone('Asia/Jakarta')
DAFTAR_KALENDER = {
    "KULIAH": "7286ff9cd810710bdbc49eb44e4beb288b12b0cd1c7278d741c860eda4dfa019@group.calendar.google.com",
    "ACARA" : "39a66f64cea2cdb4188f78befbcd721976fc5766304e1b029bf99ab746f6ae64@group.calendar.google.com",
    "TUGAS" : "c22e46406c3e93a487dadce76387bed31e0068bb258cf0bb3cc255095abed019@group.calendar.google.com" 
}
ICON_MAP = {"KULIAH": "🎓", "ACARA" : "📌", "TUGAS" : "🔥"}

st.set_page_config(page_title="Rashif's Dashboard", page_icon="🚀", layout="wide")

# Custom CSS untuk mempercantik tampilan
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stExpander { border: none !important; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-radius: 8px !important; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False
    st.session_state.edit_id = None
    st.session_state.edit_data = {}

@st.cache_resource
def init_services():
    key_dict = dict(st.secrets['firebase_key']) if 'firebase_key' in st.secrets else None
    if not key_dict: return None, None
    if not firebase_admin._apps:
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    creds = service_account.Credentials.from_service_account_info(key_dict, scopes=['https://www.googleapis.com/auth/calendar.readonly'])
    service = build('calendar', 'v3', credentials=creds)
    return db, service

db, calendar_service = init_services()

def clean_html(raw_html):
    return re.sub(re.compile('<.*?>'), '', raw_html).strip() if raw_html else ""

def get_merged_events(service):
    if not service: return []
    all_events = []
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for label, cal_id in DAFTAR_KALENDER.items():
        try:
            res = service.events().list(calendarId=cal_id, timeMin=now_utc, maxResults=10, singleEvents=True, orderBy='startTime').execute()
            for item in res.get('items', []):
                item['_source'] = label
                all_events.append(item)
        except: continue
    all_events.sort(key=lambda x: x['start'].get('dateTime', x['start'].get('date')))
    return all_events[:12]

# --- HEADER SECTION ---
st.title("🚀 Rashif's Digital HQ")
st.caption(f"Update Terakhir: {datetime.datetime.now(WIB).strftime('%d %B %Y | %H:%M')} WIB")

# --- FINANCIAL SUMMARY METRICS ---
if db:
    docs = db.collection("transactions").stream()
    all_data = [d.to_dict() for d in docs]
    if all_data:
        df_all = pd.DataFrame(all_data)
        inc = df_all[df_all['type'] == 'IN']['amount'].sum()
        out = df_all[df_all['type'] == 'OUT']['amount'].sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("Pemasukan (Total)", f"Rp {inc:,.0f}", delta_color="normal")
        m2.metric("Pengeluaran (Total)", f"Rp {out:,.0f}", delta=f"-{out:,.0f}", delta_color="inverse")
        m3.metric("Saldo Saat Ini", f"Rp {inc-out:,.0f}")

st.write("---")
col_left, col_right = st.columns([1, 1.4], gap="large")

# --- LEFT COLUMN: CALENDAR ---
with col_left:
    st.subheader("📅 Timeline Agenda")
    events = get_merged_events(calendar_service)
    if not events:
        st.info("Santai dulu, belum ada agenda!")
    for e in events:
        start = e['start']
        src = e.get('_source', 'UMUM')
        ic = ICON_MAP.get(src, "📅")
        if 'dateTime' in start:
            dt = datetime.datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00')).astimezone(WIB)
            time_str = dt.strftime("%H:%M")
            date_str = dt.strftime("%d %b")
        else:
            time_str = "Seharian"
            date_str = datetime.datetime.strptime(start['date'], "%Y-%m-%d").strftime("%d %b")
        
        with st.expander(f"**{date_str}** | {ic} **{time_str}** - {e['summary']}"):
            st.markdown(f"**Kategori:** `{src}`")
            desc = clean_html(e.get('description', ''))
            if desc: st.info(desc)
            if 'location' in e: st.caption(f"📍 {e['location']}")

# --- RIGHT COLUMN: FINANCE ---
with col_right:
    st.subheader("💸 Pengelola Keuangan")
    t_in, t_hist = st.tabs(["➕ Catat Baru", "📈 Analisis & Riwayat"])

    with t_in:
        with st.form("fm"):
            cc1, cc2 = st.columns(2)
            tipe = cc1.radio("Aksi", ["Keluar 📉", "Masuk 📈"], horizontal=True)
            tgl = cc2.date_input("Tanggal", datetime.date.today())
            
            item = st.text_input("Nama Transaksi", placeholder="Misal: Nasi Padang")
            col_a, col_b = st.columns(2)
            amt = col_a.number_input("Nominal (Rp)", min_value=0, step=5000)
            kat = col_b.selectbox("Kategori", ["Makan", "Transport", "Pendidikan", "Uang Saku", "Lainnya"])
            
            if st.form_submit_button("Simpan Data"):
                tp = "IN" if "Masuk" in tipe else "OUT"
                db.collection("transactions").add({"type": tp, "item": item, "amount": amt, "category": kat, "timestamp": datetime.datetime.combine(tgl, datetime.datetime.now().time())})
                st.success("Tersimpan!")
                st.rerun()

    with t_hist:
        if all_data:
            df = pd.DataFrame(all_data)
            df['Tgl'] = pd.to_datetime(df['timestamp']).dt.date
            df['Tipe'] = df['type'].map({'IN': 'Masuk', 'OUT': 'Keluar'})
            st.line_chart(df.pivot_table(index='Tgl', columns='Tipe', values='amount', aggfunc='sum', fill_value=0))
            
            st.write("#### 10 Transaksi Terakhir")
            for _, r in df.sort_values('timestamp', ascending=False).head(10).iterrows():
                with st.container():
                    c_a, c_b, c_c = st.columns([2, 5, 2])
                    c_a.caption(r['timestamp'].strftime("%d/%m %H:%M"))
                    icon_t = "🟢" if r['type'] == 'IN' else "🔴"
                    c_b.markdown(f"{icon_t} **{r['item']}** \n*{r['category']}*")
                    c_c.write(f"Rp {r['amount']:,}")
                    st.divider()
