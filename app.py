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
st.set_page_config(
    page_title="Rashif's Dashboard", 
    page_icon="🚀", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* === VARIABEL & RESET === */
    :root {
        --primary-color: #6366f1;
        --secondary-color: #8b5cf6;
        --success-color: #10b981;
        --danger-color: #ef4444;
        --warning-color: #f59e0b;
        --info-color: #3b82f6;
        
        --bg-primary: var(--background-color);
        --bg-secondary: var(--secondary-background-color);
        --text-primary: var(--text-color);
        --border-color: rgba(128, 128, 128, 0.15);
        
        --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
        
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;
        --radius-xl: 20px;
        
        --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    /* Container */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
        max-width: 1400px !important;
    }

    /* === HEADER === */
    .main-header {
        margin-bottom: 2rem;
    }
    
    .main-header h1 {
        font-size: clamp(1.75rem, 4vw, 2.5rem);
        font-weight: 800;
        background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.25rem;
        letter-spacing: -0.02em;
    }
    
    .header-caption {
        font-size: 0.95rem;
        opacity: 0.7;
        font-weight: 500;
    }

    /* === SECTION HEADER === */
    .section-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 1.25rem;
        padding-bottom: 0.75rem;
        border-bottom: 2px solid var(--border-color);
    }
    
    .section-header h3 {
        font-size: 1.35rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.01em;
    }

    /* === CARD STYLES === */
    .card {
        background: var(--bg-secondary);
        border-radius: var(--radius-md);
        padding: 1rem;
        border: 1px solid var(--border-color);
        box-shadow: var(--shadow-sm);
        transition: var(--transition);
        position: relative;
        overflow: hidden;
    }
    
    .card:hover {
        box-shadow: var(--shadow-md);
        transform: translateY(-2px);
    }

    .card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 3px;
        background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
        opacity: 0;
        transition: var(--transition);
    }
    
    .card:hover::before {
        opacity: 1;
    }

    /* === AGENDA CARD === */
    .agenda-card {
        background: var(--bg-secondary);
        border-radius: var(--radius-md);
        padding: 1rem;
        margin-bottom: 0.75rem;
        border: 1px solid var(--border-color);
        border-left: 4px solid;
        box-shadow: var(--shadow-sm);
        transition: var(--transition);
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 1rem;
    }
    
    .agenda-card:hover {
        box-shadow: var(--shadow-md);
        transform: translateX(4px);
    }

    .agenda-kuliah { border-left-color: var(--primary-color); }
    .agenda-acara { border-left-color: var(--warning-color); }
    .agenda-tugas { border-left-color: var(--danger-color); }

    .agenda-left {
        flex: 1;
        min-width: 0;
    }
    
    .agenda-title {
        font-weight: 600;
        font-size: 1rem;
        line-height: 1.4;
        margin-bottom: 0.25rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .agenda-location {
        font-size: 0.85rem;
        opacity: 0.7;
        margin-top: 0.25rem;
        display: flex;
        align-items: center;
        gap: 0.35rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .agenda-right {
        text-align: right;
        flex-shrink: 0;
        min-width: 100px;
    }
    
    .agenda-date {
        font-weight: 700;
        font-size: 0.95rem;
        margin-bottom: 0.5rem;
        color: var(--primary-color);
    }
    
    .agenda-time {
        display: inline-block;
        background: var(--border-color);
        padding: 0.35rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        white-space: nowrap;
    }

    /* === FINANCE STATS === */
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    
    .stat-card {
        background: var(--bg-secondary);
        border-radius: var(--radius-md);
        padding: 1.25rem;
        text-align: center;
        border: 1px solid var(--border-color);
        box-shadow: var(--shadow-sm);
        transition: var(--transition);
        position: relative;
        overflow: hidden;
    }
    
    .stat-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        transition: var(--transition);
    }
    
    .stat-card:hover {
        box-shadow: var(--shadow-md);
        transform: translateY(-4px);
    }
    
    .stat-card.balance::before { background: var(--info-color); }
    .stat-card.income::before { background: var(--success-color); }
    .stat-card.expense::before { background: var(--danger-color); }
    
    .stat-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        opacity: 0.7;
        margin-bottom: 0.5rem;
        font-weight: 600;
    }
    
    .stat-value {
        font-size: 1.75rem;
        font-weight: 800;
        letter-spacing: -0.02em;
    }
    
    .stat-card.balance .stat-value { color: var(--info-color); }
    .stat-card.income .stat-value { color: var(--success-color); }
    .stat-card.expense .stat-value { color: var(--danger-color); }

    /* === TRANSACTION CARD === */
    .transaction-card {
        background: var(--bg-secondary);
        border-radius: var(--radius-md);
        padding: 1rem;
        margin-bottom: 0.75rem;
        border: 1px solid var(--border-color);
        border-left: 4px solid;
        box-shadow: var(--shadow-sm);
        transition: var(--transition);
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
    }
    
    .transaction-card:hover {
        box-shadow: var(--shadow-md);
    }
    
    .transaction-card.income { border-left-color: var(--success-color); }
    .transaction-card.expense { border-left-color: var(--danger-color); }

    .transaction-left {
        flex: 1;
        min-width: 0;
    }
    
    .transaction-title {
        font-weight: 600;
        font-size: 1rem;
        margin-bottom: 0.25rem;
    }
    
    .transaction-meta {
        font-size: 0.85rem;
        opacity: 0.7;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .transaction-right {
        text-align: right;
        flex-shrink: 0;
    }
    
    .transaction-amount {
        font-weight: 700;
        font-size: 1.1rem;
        letter-spacing: -0.01em;
    }
    
    .transaction-card.income .transaction-amount { color: var(--success-color); }
    .transaction-card.expense .transaction-amount { color: var(--danger-color); }

    /* === BUTTONS === */
    .stButton > button {
        border-radius: var(--radius-sm);
        font-weight: 600;
        transition: var(--transition);
        border: none;
        box-shadow: var(--shadow-sm);
    }
    
    .stButton > button:hover {
        box-shadow: var(--shadow-md);
        transform: translateY(-2px);
    }

    .action-buttons {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.5rem;
        margin-top: 0.75rem;
    }

    /* === EMPTY STATE === */
    .empty-state {
        text-align: center;
        padding: 3rem 1rem;
        opacity: 0.6;
    }
    
    .empty-state-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
        opacity: 0.5;
    }
    
    .empty-state-text {
        font-size: 1rem;
        font-weight: 500;
    }

    /* === FORMS === */
    .stRadio > label {
        font-weight: 600;
        font-size: 0.9rem;
    }
    
    .stTextInput > label,
    .stNumberInput > label,
    .stSelectbox > label,
    .stDateInput > label {
        font-weight: 600;
        font-size: 0.9rem;
        margin-bottom: 0.25rem;
    }

    /* === TABS === */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        border-bottom: 2px solid var(--border-color);
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: var(--radius-sm) var(--radius-sm) 0 0;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
    }

    /* === EXPANDER === */
    .streamlit-expanderHeader {
        font-weight: 600;
        border-radius: var(--radius-sm);
        transition: var(--transition);
    }
    
    .streamlit-expanderHeader:hover {
        background-color: var(--border-color);
    }

    /* === RESPONSIVE === */
    @media (max-width: 768px) {
        .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        
        .stats-grid {
            grid-template-columns: 1fr;
            gap: 0.75rem;
        }
        
        .stat-card {
            padding: 1rem;
        }
        
        .stat-value {
            font-size: 1.5rem;
        }
        
        .agenda-card,
        .transaction-card {
            flex-direction: column;
            align-items: flex-start;
        }
        
        .agenda-right,
        .transaction-right {
            width: 100%;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 0.5rem;
            padding-top: 0.5rem;
            border-top: 1px solid var(--border-color);
        }
        
        .agenda-date,
        .transaction-amount {
            margin-bottom: 0;
        }
    }

    @media (max-width: 480px) {
        .main-header h1 {
            font-size: 1.5rem;
        }
        
        .section-header h3 {
            font-size: 1.1rem;
        }
        
        .agenda-title,
        .transaction-title {
            font-size: 0.95rem;
        }
    }

    /* === SCROLLBAR === */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: var(--bg-secondary);
    }
    
    ::-webkit-scrollbar-thumb {
        background: var(--border-color);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(128, 128, 128, 0.3);
    }

    /* === ANIMATIONS === */
    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .card,
    .agenda-card,
    .transaction-card,
    .stat-card {
        animation: slideIn 0.3s ease-out;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# --- 2. BACKEND ---
# ==========================================
WIB = pytz.timezone('Asia/Jakarta')
DAFTAR_KALENDER = {
    "KULIAH": "7286ff9cd810710bdbc49eb44e4beb288b12b0cd1c7278d741c860eda4dfa019@group.calendar.google.com",
    "ACARA": "39a66f64cea2cdb4188f78befbcd721976fc5766304e1b029bf99ab746f6ae64@group.calendar.google.com",
    "TUGAS": "c22e46406c3e93a487dadce76387bed31e0068bb258cf0bb3cc255095abed019@group.calendar.google.com" 
}
ICON_MAP = {"KULIAH": "🎓", "ACARA": "📌", "TUGAS": "🔥"}

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
            with open("firebase_key.json") as f: 
                key_dict = json.load(f)
        except: 
            pass
    if not key_dict: 
        return None, None
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
    if not raw_html: 
        return ""
    return re.sub('<.*?>', '', raw_html).strip()

def get_merged_events(service):
    if not service: 
        return []
    all_events = []
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        for label, cal_id in DAFTAR_KALENDER.items():
            if not cal_id or "@" not in cal_id: 
                continue
            res = service.events().list(
                calendarId=cal_id, 
                timeMin=now_utc, 
                maxResults=8, 
                singleEvents=True, 
                orderBy='startTime'
            ).execute()
            for item in res.get('items', []):
                item['_source'] = label 
                all_events.append(item)
        all_events.sort(key=lambda x: x['start'].get('dateTime', x['start'].get('date')))
        return all_events
    except: 
        return []

def format_rupiah(angka):
    if angka >= 1000000: 
        return f"{angka/1000000:.1f}Jt"
    if angka >= 1000: 
        return f"{angka/1000:.0f}k"
    return str(int(angka))

def format_rupiah_full(angka):
    return f"Rp{int(angka):,}".replace(",", ".")

# ==========================================
# --- 3. UI UTAMA ---
# ==========================================

# Header
st.markdown(f"""
<div class="main-header">
    <h1>🚀 Rashif's Space</h1>
    <div class="header-caption">📅 {datetime.datetime.now(WIB).strftime('%A, %d %B %Y')}</div>
</div>
""", unsafe_allow_html=True)

# Layout columns
col_kiri, col_kanan = st.columns([1, 1.4], gap="large")

# ==========================================
# --- MODUL AGENDA ---
# ==========================================
with col_kiri:
    st.markdown('<div class="section-header"><h3>📅 Agenda</h3></div>', unsafe_allow_html=True)
    
    if calendar_service:
        events = get_merged_events(calendar_service)
        if not events:
            st.markdown("""
<div class="empty-state">
    <div class="empty-state-icon">📭</div>
    <div class="empty-state-text">Tidak ada agenda mendatang</div>
</div>
""", unsafe_allow_html=True)
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
                    jam = "All Day"
                
                loc_html = ""
                if 'location' in event:
                    loc_display = event['location'][:30] + "..." if len(event['location']) > 30 else event['location']
                    loc_html = f'<div class="agenda-location">📍 {loc_display}</div>'
                
                st.markdown(f"""
<div class="agenda-card agenda-{source.lower()}">
<div class="agenda-left">
<div class="agenda-title">{icon} {event['summary']}</div>
{loc_html}
</div>
<div class="agenda-right">
<div class="agenda-date">{tgl}</div>
<div class="agenda-time">⏰ {jam}</div>
</div>
</div>
""", unsafe_allow_html=True)
                
                desc = clean_html(event.get('description', ''))
                if desc:
                    with st.expander("📝 Lihat Detail", expanded=False):
                        st.write(desc)
    else:
        st.warning("⚠️ Tidak dapat terhubung ke Google Calendar")

# ==========================================
# --- MODUL KEUANGAN ---
# ==========================================
with col_kanan:
    st.markdown('<div class="section-header"><h3>💰 Keuangan</h3></div>', unsafe_allow_html=True)
    
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

    # Stats Cards
    if not df.empty:
        tot_in = df[df['type']=='IN']['amount'].sum()
        tot_out = df[df['type']=='OUT']['amount'].sum()
        saldo = tot_in - tot_out
        
        st.markdown(f"""
<div class="stats-grid">
<div class="stat-card balance">
<div class="stat-label">Saldo</div>
<div class="stat-value">{format_rupiah(saldo)}</div>
</div>
<div class="stat-card income">
<div class="stat-label">Pemasukan</div>
<div class="stat-value">+{format_rupiah(tot_in)}</div>
</div>
<div class="stat-card expense">
<div class="stat-label">Pengeluaran</div>
<div class="stat-value">-{format_rupiah(tot_out)}</div>
</div>
</div>
""", unsafe_allow_html=True)
    else:
        st.markdown("""
<div class="empty-state">
<div class="empty-state-icon">💳</div>
<div class="empty-state-text">Belum ada transaksi</div>
</div>
""", unsafe_allow_html=True)

    # Tabs
    tab_in, tab_hist = st.tabs(["📝 Input Transaksi", "📜 Riwayat"])

    with tab_in:
        if st.session_state.edit_mode:
            st.info(f"✏️ Mode Edit: {st.session_state.edit_data.get('item')}")
            def_tipe = 1 if st.session_state.edit_data.get('type') == 'IN' else 0
            def_item = st.session_state.edit_data.get('item')
            def_amt = st.session_state.edit_data.get('amount')
            def_kat = st.session_state.edit_data.get('category')
            btn_txt = "💾 Simpan Perubahan"
        else:
            def_tipe, def_item, def_amt, def_kat = 0, "", 0, None
            btn_txt = "➕ Tambah Transaksi"

        with st.form("finance_form", clear_on_submit=not st.session_state.edit_mode):
            c1, c2 = st.columns(2)
            with c1: 
                t_pilih = st.radio("Tipe Transaksi", ["📉 Pengeluaran", "📈 Pemasukan"], index=def_tipe)
            with c2: 
                tgl_pilih = st.date_input("Tanggal", datetime.date.today())

            if "Pemasukan" in t_pilih:
                kat_list = ["Uang Saku", "Gaji", "Bonus", "Lainnya"]
                t_db = "IN"
            else:
                kat_list = ["Makan", "Transport", "Jajan", "Pendidikan", "Belanja", "Lainnya"]
                t_db = "OUT"
            
            f_item = st.text_input("Keterangan", value=def_item, placeholder="Contoh: Makan Siang")
            f_amt = st.number_input("Nominal (Rp)", value=int(def_amt), min_value=0, step=1000)
            
            if def_kat and def_kat in kat_list:
                kat_index = kat_list.index(def_kat)
            else:
                kat_index = 0
            f_kat = st.selectbox("Kategori", kat_list, index=kat_index)
            
            if st.form_submit_button(btn_txt, use_container_width=True, type="primary"):
                if db and f_item and f_amt > 0:
                    waktu_fix = datetime.datetime.combine(tgl_pilih, datetime.datetime.now(WIB).time())
                    payload = {
                        "type": t_db, 
                        "item": f_item, 
                        "amount": f_amt, 
                        "category": f_kat, 
                        "timestamp": waktu_fix
                    }
                    
                    if st.session_state.edit_mode:
                        db.collection("transactions").document(st.session_state.edit_id).update(payload)
                        st.toast("✅ Transaksi berhasil diupdate!", icon="✅")
                        st.session_state.edit_mode = False
                        st.session_state.edit_data = {}
                    else:
                        db.collection("transactions").add(payload)
                        st.toast("✅ Transaksi berhasil ditambahkan!", icon="✅")
                    st.rerun()
                else:
                    st.error("⚠️ Mohon lengkapi semua field dengan benar")
        
        if st.session_state.edit_mode:
            if st.button("❌ Batal Edit", use_container_width=True):
                st.session_state.edit_mode = False
                st.session_state.edit_data = {}
                st.rerun()

    with tab_hist:
        if raw_data:
            # Export Button
            df_export = df.copy()
            df_export['timestamp'] = df_export['timestamp'].apply(
                lambda x: x.astimezone(WIB).strftime('%Y-%m-%d %H:%M') if pd.notnull(x) else ""
            )
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer: 
                df_export.to_excel(writer, index=False, sheet_name='Transaksi')
            
            st.download_button(
                "📥 Download Excel", 
                data=buf.getvalue(), 
                file_name=f"Keuangan_{datetime.date.today()}.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                use_container_width=True
            )
            st.markdown("<br>", unsafe_allow_html=True)

            # Transaction List
            for item in raw_data:
                is_in = item['type'] == 'IN'
                css_cls = "income" if is_in else "expense"
                symbol = "+" if is_in else "-"
                
                tgl_display = item['timestamp'].strftime("%d %b %Y")
                
                st.markdown(f"""
<div class="transaction-card {css_cls}">
<div class="transaction-left">
<div class="transaction-title">{item['item']}</div>
<div class="transaction-meta">📅 {tgl_display} • 🏷️ {item['category']}</div>
</div>
<div class="transaction-right">
<div class="transaction-amount">{symbol} {format_rupiah_full(item['amount'])}</div>
</div>
</div>
""", unsafe_allow_html=True)
                
                # Action buttons
                c1, c2 = st.columns([1, 1])
                if c1.button("✏️ Edit", key=f"e_{item['id']}", use_container_width=True):
                    st.session_state.edit_mode = True
