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
# --- 1. KONFIGURASI & CSS ---
# ==========================================
st.set_page_config(page_title="Rashif's Dashboard", page_icon="🚀", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');

    :root {
        --primary-color: #6C5CE7;
        --secondary-color: #a29bfe;
        --bg-color: #ffffff;
        --text-color: #2d3436;
        --card-bg: #ffffff;
        --gray-light: #dfe6e9;
        --shadow-light: 0 4px 6px rgba(0, 0, 0, 0.05);
        --shadow-hover: 0 10px 15px rgba(0, 0, 0, 0.1);
        --border-radius: 16px;
    }

    /* Dark Mode Support (Basic) */
    @media (prefers-color-scheme: dark) {
        :root {
            --bg-color: #2d3436;
            --text-color: #dfe6e9;
            --card-bg: #2d3436;
            --gray-light: #636e72;
        }
    }

    html, body, [class*="css"] {
        font-family: 'Poppins', sans-serif;
    }

    .stApp {
        /* background-color: var(--gray-light); */
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 5rem;
        max-width: 1200px;
    }

    /* --- CARD DESIGN --- */
    .list-card {
        background-color: var(--card-bg);
        padding: 16px 20px;
        border-radius: var(--border-radius);
        margin-bottom: 12px;
        border: 1px solid rgba(0,0,0,0.05);
        box-shadow: var(--shadow-light);
        transition: transform 0.2s, box-shadow 0.2s;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 15px;
        position: relative;
        overflow: hidden;
    }

    .list-card::before {
        content: "";
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 6px;
        border-top-left-radius: var(--border-radius);
        border-bottom-left-radius: var(--border-radius);
    }

    .list-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-hover);
    }

    .b-kuliah::before { background-color: #7286ff; }
    .b-acara::before { background-color: #ffb74d; }
    .b-tugas::before { background-color: #e57373; }
    .b-in::before { background-color: #00b894; }
    .b-out::before { background-color: #d63031; }

    /* Left Content */
    .left-content {
        flex-grow: 1;
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .item-main {
        font-weight: 600;
        font-size: 1.05rem;
        color: var(--text-color);
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .item-sub {
        font-size: 0.85rem;
        color: gray;
        display: flex;
        align-items: center;
        gap: 4px;
    }

    /* Right Content */
    .right-content {
        text-align: right;
        min-width: 100px;
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 4px;
    }

    .date-text {
        font-weight: 700;
        font-size: 0.95rem;
        color: var(--text-color);
    }

    .time-badge {
        background-color: var(--gray-light);
        color: var(--text-color);
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        white-space: nowrap;
    }

    /* --- STATS CARD --- */
    .stat-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
        gap: 15px;
        margin-bottom: 25px;
    }

    .stat-card {
        background: var(--card-bg);
        border-radius: var(--border-radius);
        padding: 20px;
        text-align: left;
        box-shadow: var(--shadow-light);
        border: 1px solid rgba(0,0,0,0.05);
        position: relative;
        overflow: hidden;
        transition: transform 0.2s;
    }
    
    .stat-card:hover { transform: translateY(-3px); }

    .stat-title {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: gray;
        margin-bottom: 8px;
    }

    .stat-value {
        font-size: 1.5rem;
        font-weight: 800;
        color: var(--text-color);
    }
    
    .acc-blue { border-bottom: 4px solid #74b9ff; }
    .acc-green { border-bottom: 4px solid #00b894; }
    .acc-red { border-bottom: 4px solid #d63031; }

    .money-val {
        font-weight: 700;
        font-size: 1rem;
    }
    
    /* --- MOBILE RESPONSIVENESS --- */
    @media (max-width: 600px) {
        .block-container { padding: 1rem; }
        .list-card {
            flex-direction: column;
            align-items: flex-start;
            gap: 10px;
            padding: 12px;
        }
        .list-card::before {
            width: 100%;
            height: 4px;
            top: 0;
            bottom: auto;
            border-radius: var(--border-radius) var(--border-radius) 0 0;
        }
        .right-content {
            width: 100%;
            flex-direction: row;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid rgba(0,0,0,0.05);
            padding-top: 8px;
            margin-top: 5px;
        }
        .stat-container {
            grid-template-columns: 1fr;
        }
        .stButton > button { width: 100%; }
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# --- 2. BACKEND ---
# ==========================================
WIB = pytz.timezone('Asia/Jakarta')
DAFTAR_KALENDER = {
    "KULIAH": "7286ff9cd810710bdbc49eb44e4beb288b12b0cd1c7278d741c860eda4dfa019@group.calendar.google.com",
    "ACARA" : "39a66f64cea2cdb4188f78befbcd721976fc5766304e1b029bf99ab746f6ae64@group.calendar.google.com",
    "TUGAS" : "c22e46406c3e93a487dadce76387bed31e0068bb258cf0bb3cc255095abed019@group.calendar.google.com" 
}
ICON_MAP = {"KULIAH": "🎓", "ACARA" : "📌", "TUGAS" : "🔥"}

if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False
    st.session_state.edit_id = None
    st.session_state.edit_data = {}

@st.cache_resource
def init_services():
    key_dict = None
    if 'firebase_key' in st.secrets:
        key_dict = dict(st.secrets['firebase_key'])
    else:
        try:
            import json
            with open("firebase_key.json") as f: key_dict = json.load(f)
        except: pass
    if not key_dict: return None, None
    if not firebase_admin._apps:
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    creds = service_account.Credentials.from_service_account_info(key_dict, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=creds)
    return db, service

db, calendar_service = init_services()

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
            res = service.events().list(calendarId=cal_id, timeMin=now_utc, maxResults=8, singleEvents=True, orderBy='startTime').execute()
            for item in res.get('items', []):
                item['_source'] = label 
                all_events.append(item)
        all_events.sort(key=lambda x: x['start'].get('dateTime', x['start'].get('date')))
        return all_events
    except Exception as e:
        st.error(f"Error fetching events: {e}")
        return []

def format_rupiah(angka):
    if angka >= 1000000: return f"{angka/1000000:.1f}Jt"
    if angka >= 1000: return f"{angka/1000:.0f}k"
    return str(angka)

def format_rupiah_full(angka):
    return f"Rp{int(angka):,}".replace(",", ".")

# ==========================================
# --- 3. UI UTAMA ---
# ==========================================
st.title("🚀 Rashif's Space")
st.caption(f"📅 {datetime.datetime.now(WIB).strftime('%A, %d %B %Y')}")

col_kiri, col_spacer, col_kanan = st.columns([1, 0.1, 1.4])

# --- MODUL AGENDA ---
with col_kiri:
    st.subheader("📅 Agenda")
    if calendar_service:
        events = get_merged_events(calendar_service)
        if not events:
            st.info("Agenda kosong.")
        else:
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
                
                # --- UPDATE: HTML STRUCTURE FOR AGENDA ---
                loc_html = f'<div class="item-sub">📍 {event["location"][:30]}...</div>' if 'location' in event else ''
                
                st.markdown(f"""
<div class="list-card b-{source.lower()}">
<div class="left-content">
<div class="item-main">{icon} {event['summary']}</div>
{loc_html}
</div>
<div class="right-content">
<div class="date-text">{tgl}</div>
<div class="time-badge">⏰ {jam}</div>
</div>
</div>
""", unsafe_allow_html=True)
                
                desc = clean_html(event.get('description', ''))
                if desc:
                    with st.expander("📝 Rincian", expanded=False):
                        st.write(desc)
    else:
        st.warning("Gagal memuat Kalender.")

# --- MODUL KEUANGAN ---
with col_kanan:
    st.subheader("💰 Keuangan")
    
    df = pd.DataFrame()
    raw_data = []
    if db:
        docs = db.collection("transactions").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(50).stream()
        for doc in docs:
            d = doc.to_dict()
            d['id'] = doc.id
            raw_data.append(d)
        if raw_data: df = pd.DataFrame(raw_data)

    if not df.empty:
        tot_in = df[df['type']=='IN']['amount'].sum()
        tot_out = df[df['type']=='OUT']['amount'].sum()
        saldo = tot_in - tot_out
        
        # FIX: Updated Stats HTML Structure
        st.markdown(f"""
<div class="stat-container">
<div class="stat-card acc-blue">
<div class="stat-title">Saldo</div>
<div class="stat-value">{format_rupiah(saldo)}</div>
</div>
<div class="stat-card acc-green">
<div class="stat-title">Masuk</div>
<div class="stat-value">+{format_rupiah(tot_in)}</div>
</div>
<div class="stat-card acc-red">
<div class="stat-title">Keluar</div>
<div class="stat-value">-{format_rupiah(tot_out)}</div>
</div>
</div>
""", unsafe_allow_html=True)
    else:
        st.info("Belum ada data.")

    tab_in, tab_hist = st.tabs(["📝 Input", "📜 Riwayat"])

    with tab_in:
        if st.session_state.edit_mode:
            st.info(f"✏️ Edit: {st.session_state.edit_data.get('item')}")
            def_tipe = 1 if st.session_state.edit_data.get('type') == 'IN' else 0
            def_item = st.session_state.edit_data.get('item')
            def_amt = st.session_state.edit_data.get('amount')
            btn_txt = "Simpan Perubahan"
        else:
            def_tipe, def_item, def_amt = 0, "", 0
            btn_txt = "Tambah"

        with st.form("finance_form", clear_on_submit=not st.session_state.edit_mode):
            c1, c2 = st.columns(2)
            with c1: t_pilih = st.radio("Tipe", ["Pengeluaran 📉", "Pemasukan 📈"], index=def_tipe)
            with c2: tgl_pilih = st.date_input("Tanggal", datetime.date.today())

            if "Pemasukan" in t_pilih:
                kat_list = ["Uang Saku", "Gaji", "Bonus", "Lainnya"]
                t_db = "IN"
            else:
                kat_list = ["Makan", "Transport", "Jajan", "Pendidikan", "Belanja", "Lainnya"]
                t_db = "OUT"
            
            f_item = st.text_input("Keterangan", value=def_item, placeholder="Cth: Nasi Goreng")
            f_amt = st.number_input("Nominal (Rp)", value=int(def_amt), min_value=0, step=1000)
            f_kat = st.selectbox("Kategori", kat_list)
            
            if st.form_submit_button(btn_txt, use_container_width=True, type="primary"):
                if db:
                    waktu_fix = datetime.datetime.combine(tgl_pilih, datetime.datetime.now().time())
                    payload = {"type": t_db, "item": f_item, "amount": f_amt, "category": f_kat, "timestamp": waktu_fix}
                    
                    if st.session_state.edit_mode:
                        db.collection("transactions").document(st.session_state.edit_id).update(payload)
                        st.toast("Berhasil diupdate!")
                        st.session_state.edit_mode = False; st.session_state.edit_data = {}
                    else:
                        db.collection("transactions").add(payload)
                        st.toast("Berhasil disimpan!")
                    st.rerun()
        
        if st.session_state.edit_mode:
            if st.button("Batal Edit", use_container_width=True):
                st.session_state.edit_mode = False; st.rerun()

    with tab_hist:
        if raw_data:
            df_export = df.copy()
            df_export['timestamp'] = df_export['timestamp'].apply(lambda x: x.astimezone(WIB).strftime('%Y-%m-%d %H:%M') if pd.notnull(x) else "")
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer: df_export.to_excel(writer, index=False, sheet_name='Data')
            st.download_button("📥 Excel", data=buf.getvalue(), file_name="Keuangan.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            st.write("")

            for item in raw_data:
                is_in = item['type'] == 'IN'
                css_cls = "b-in" if is_in else "b-out"
                color = "#00b894" if is_in else "#d63031"
                symbol = "+" if is_in else "-"

                # FIX: Updated Transaction List HTML Structure
                st.markdown(f"""
<div class="list-card {css_cls}">
<div class="left-content">
<div class="item-main">{item['item']}</div>
<div class="item-sub">{item['timestamp'].strftime("%d %b")} • {item['category']}</div>
</div>
<div class="right-content">
<div class="money-val" style="color:{color};">{symbol} {format_rupiah_full(item['amount'])}</div>
</div>
</div>
""", unsafe_allow_html=True)
                
                c1, c2 = st.columns([1,1])
                if c1.button("✏️", key=f"e_{item['id']}", use_container_width=True):
                    st.session_state.edit_mode = True; st.session_state.edit_id = item['id']; st.session_state.edit_data = item; st.rerun()
                if c2.button("🗑️", key=f"d_{item['id']}", use_container_width=True):
                    db.collection("transactions").document(item['id']).delete(); st.rerun()
