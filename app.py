import streamlit as st
import pandas as pd
import requests
import math
import json
import av
from datetime import datetime
from PIL import Image
from pyzbar.pyzbar import decode
from streamlit_webrtc import webrtc_streamer, VideoProcessorBase
import extra_streamlit_components as stx
import google.generativeai as genai

# --- 1. MODERN UI CONFIGURATION ---
st.set_page_config(page_title="Health OS v11", layout="wide", initial_sidebar_state="expanded")

# Custom Professional CSS
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 28px; color: #00E676; }
    .main { background-color: #0E1117; }
    div[data-testid="stVerticalBlock"] > div:has(div.stMetric) {
        background-color: #161B22;
        border-radius: 15px;
        padding: 20px;
        border: 1px solid #30363D;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; background-color: #21262D; border-radius: 10px; padding: 10px 20px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. PERMANENT MEMORY & API KEYS ---
USDA_KEY = "bg2FpzvDUSiUDflmbHBeAxIpTxbYfhU7ubcRYyyh"
GEMINI_KEY = "AIzaSyBhFeFbbpiT68oQwZwTwRWvkXEZOGBulw8"

cookie_manager = stx.CookieManager(key="health_os_v11_final")

# Load Permanent Profile
saved_p = cookie_manager.get("p_v11")
if "profile" not in st.session_state:
    st.session_state.profile = saved_p if saved_p else {
        "weight": 105, "height": 185.0, "age": 17, "neck": 41.0, "waist": 99.0,
        "bf": 23.0, "goal_bf": 16.0, "water_goal": 3640
    }

# --- 3. THE MATH: NAVY BODY FAT & MACROS ---
def get_navy_bf(p):
    # Navy Formula for Men (Metric)
    try:
        bf = 495 / (1.0324 - 0.19077 * math.log10(p['waist'] - p['neck']) + 0.15456 * math.log10(p['height'])) - 450
        return round(bf, 1)
    except: return p['bf']

def get_macros(p):
    lbm = p['weight'] * (1 - (p['bf']/100))
    bmr = 370 + (21.6 * lbm)
    tdee = bmr * 1.35 
    target_cal = tdee - 500 # Default deficit
    return round(target_cal), round(lbm * 2.2), round((target_cal*0.25)/9), round((target_cal*0.45)/4)

# --- 4. LIVE BARCODE SCANNER ENGINE ---
class BarcodeProcessor(VideoProcessorBase):
    def __init__(self): self.last_code = None
    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        decoded_objs = decode(img)
        for obj in decoded_objs:
            self.last_code = obj.data.decode("utf-8")
        return av.VideoFrame.from_ndarray(img, format="bgr24")

# --- 5. APP NAVIGATION ---
with st.sidebar:
    st.title("🛡️ Health OS v11")
    nav = st.radio("Navigate", ["📊 Dashboard", "🍴 Meal Logger", "🏋️ Performance", "⚙️ Profile Settings"])
    sel_date = st.date_input("Date Context", datetime.today())

# Ensure Databases
if "food_db" not in st.session_state: st.session_state.food_db = pd.DataFrame(columns=["Date", "Name", "Cals", "P", "F", "C"])

# --- PAGE: DASHBOARD ---
if nav == "📊 Dashboard":
    st.header(f"Status: {sel_date.strftime('%A, %b %d')}")
    
    cal_t, prot_t, fat_t, carb_t = get_macros(st.session_state.profile)
    daily = st.session_state.food_db[st.session_state.food_db['Date'] == str(sel_date)]
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kcal Remaining", f"{cal_t - daily['Cals'].sum()}")
    c2.metric("Protein (Target)", f"{prot_t - daily['P'].sum()}g")
    c3.metric("Fats", f"{fat_t - daily['F'].sum()}g")
    c4.metric("Carbs", f"{carb_t - daily['C'].sum()}g")

    st.divider()
    st.subheader("🧬 Body Composition Visuals")
    v1, v2, v3 = st.columns(3)
    v1.metric("Body Fat", f"{st.session_state.profile['bf']}%", f"Goal: {st.session_state.profile['goal_bf']}%")
    v2.metric("Lean Mass", f"{round(st.session_state.profile['weight']*(1-st.session_state.profile['bf']/100), 1)}kg")
    v3.metric("Current Weight", f"{st.session_state.profile['weight']}kg")
    
    # Simple Weight Chart
    st.line_chart(pd.DataFrame({"Weight": [st.session_state.profile['weight']-2, st.session_state.profile['weight']-1, st.session_state.profile['weight']]}))

# --- PAGE: MEAL LOGGER (DUAL SCANNER) ---
elif nav == "🍴 Meal Logger":
    st.header("Precision Entry")
    t1, t2 = st.tabs(["⚡ Live Barcode Scan", "👁️ AI Vision Analysis"])
    
    with t1:
        st.write("Hover camera over barcode for instant detection.")
        ctx = webrtc_streamer(key="barcode", video_processor_factory=BarcodeProcessor)
        if ctx.video_processor and ctx.video_processor.last_code:
            code = ctx.video_processor.last_code
            st.success(f"Barcode Detected: {code}")
            # Insert Open Food Facts API logic here as per v10
            
    with t2:
        cam = st.camera_input("Snap meal for AI")
        if cam and st.button("AI Analyze"):
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            res = model.generate_content(["Identify food & return JSON: {name, calories, protein, fat, carbs} per 100g", Image.open(cam)])
            data = json.loads(res.text.strip().replace("```json", "").replace("```", ""))
            st.json(data)
            # Logic to log into session_state.food_db...

# --- PAGE: PROFILE SETTINGS (PERMANENT) ---
elif nav == "⚙️ Profile Settings":
    st.header("Permanent User Variables")
    p = st.session_state.profile
    p['weight'] = st.number_input("Weight (kg)", value=float(p['weight']))
    p['height'] = st.number_input("Height (cm)", value=float(p['height']))
    p['neck'] = st.number_input("Neck (cm)", value=float(p['neck']))
    p['waist'] = st.number_input("Waist (cm)", value=float(p['waist']))
    
    if st.button("💾 Save & Lock Variables"):
        p['bf'] = get_navy_bf(p)
        cookie_manager.set("p_v11", p)
        st.session_state.profile = p
        st.success("Variables locked and Body Fat recalculated!")
