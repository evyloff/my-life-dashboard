import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Rashif's Dashboard", layout="wide")

# --- KONEKSI DATABASE (SMART DETECTOR) ---
@st.cache_resource
def init_connection():
    # Cek apakah aplikasi sudah terinisialisasi
    if not firebase_admin._apps:
        # Coba cara 1: Menggunakan Streamlit Secrets (Saat Online)
        if 'firebase_key' in st.secrets:
            # Membuat objek cred dari dictionary secrets
            key_dict = dict(st.secrets['firebase_key'])
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred)
        
        # Coba cara 2: Menggunakan File Lokal (Saat di Laptop)
        else:
            try:
                cred = credentials.Certificate("firebase_key.json")
                firebase_admin.initialize_app(cred)
            except:
                st.error("Gagal login: File 'firebase_key.json' tidak ditemukan dan Secrets kosong.")
                return None
                
    return firestore.client()

db = init_connection()

# --- INTERFACE ---
st.title("🚀 Rashif's Personal Dashboard")

if db:
    st.success("✅ Koneksi Database Berhasil!")
    
    # Tes Input Data Sederhana
    with st.form("tes_koneksi"):
        catatan = st.text_input("Tes Catatan:")
        submit = st.form_submit_button("Kirim ke Firebase")
        
        if submit and catatan:
            db.collection("logs_test").add({"pesan": catatan, "waktu": firestore.SERVER_TIMESTAMP})
            st.info("Data terkirim! Cek Firestore Anda.")
else:
    st.warning("Menunggu konfigurasi kunci database...")
