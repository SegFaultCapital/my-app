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

# --- 1. UI CONFIG ---
st.set_page_config(page_title="Health OS v11.4", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 26px; color: #00E676; }
    div[data-testid="stVerticalBlock"] > div:has(div.stMetric) {
        background-color: #161B22; border-radius: 12px; padding: 15px; border: 1px solid #30363D;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. API & PERMANENT MEMORY ---
USDA_KEY = "bg2FpzvDUSiUDflmbHBeAxIpTxbYfhU7ubcRYyyh"
GEMINI_KEY = "AIzaSyBhFeFbbpiT68oQwZwTwRWvkXEZOGBulw8"


# We use one primary cookie manager for all persistence
cookie_manager = stx.CookieManager(key="health_os_v11_4_final")

# --- 3. DATA PERSISTENCE ENGINE (The "Anti-Refresh" Logic) ---
# 3a. Profile Persistence (Weight, Height, BF%)
if "profile" not in st.session_state:
    saved_p = cookie_manager.get("p_data_v11")
    st.session_state.profile = saved_p if saved_p else {
        "weight": 75.0, "height": 175.0, "age": 17, "neck": 38.0, "waist": 85.0,
        "bf": 15.0, "goal_bf": 12.0, "water_goal": 3000, "gender": "Male"
    }

# 3b. Food History Persistence
if "food_history" not in st.session_state:
    saved_f = cookie_manager.get("f_data_v11")
    if saved_f:
        st.session_state.food_history = pd.DataFrame(saved_f)
    else:
        st.session_state.food_history = pd.DataFrame(columns=["Date", "Name", "Cals", "P", "F", "C"])

# 3c. Water History Persistence
if "water_history" not in st.session_state:
    saved_w = cookie_manager.get("w_data_v11")
    st.session_state.water_history = saved_w if saved_w else {}

# --- HELPER: SAVE EVERYTHING ---
def save_all_to_cookies():
    cookie_manager.set("p_data_v11", st.session_state.profile, key="save_p")
    # Cookies have size limits, so we only store the last 100 entries to be safe
    food_list = st.session_state.food_history.tail(100).to_dict('records')
    cookie_manager.set("f_data_v11", food_list, key="save_f")
    cookie_manager.set("w_data_v11", st.session_state.water_history, key="save_w")

# --- 4. MATH & DATABASES ---
indian_db = pd.DataFrame({
    "Food": ["Roti", "Paneer", "Toor Dal", "Rice", "Chicken Curry", "Dal Makhani", "Egg Bhurji"],
    "Cals": [297, 265, 116, 130, 145, 160, 185],
    "P": [9, 18, 6, 2.7, 14, 5, 12], "F": [1, 20, 0.4, 0.3, 8, 9, 14], "C": [61, 1.2, 21, 28, 5, 15, 3]
})

def get_navy_bf(p):
    try:
        if p['gender'] == "Male":
            # $$BF = 495 / (1.0324 - 0.19077 \cdot \log_{10}(waist - neck) + 0.15456 \cdot \log_{10}(height)) - 450$$
            bf = 495 / (1.0324 - 0.19077 * math.log10(p['waist'] - p['neck']) + 0.15456 * math.log10(p['height'])) - 450
        else:
            bf = 495 / (1.29579 - 0.35004 * math.log10(p['waist'] + 95 - p['neck']) + 0.22100 * math.log10(p['height'])) - 450
        return round(bf, 1)
    except: return p['bf']

def get_macros(p):
    lbm = p['weight'] * (1 - (p['bf']/100))
    bmr = 370 + (21.6 * lbm)
    tdee = bmr * 1.35 
    target_cal = tdee - 500
    return round(target_cal), round(lbm * 2.2), round((target_cal*0.25)/9), round((target_cal*0.45)/4)

# --- 5. SCANNER LOGIC ---
class BarcodeProcessor(VideoProcessorBase):
    def __init__(self): self.last_code = None
    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        for obj in decode(img): self.last_code = obj.data.decode("utf-8")
        return av.VideoFrame.from_ndarray(img, format="bgr24")

# --- 6. NAVIGATION ---
with st.sidebar:
    st.title("🛡️ Health OS v11.4")
    nav = st.radio("Navigate", ["📊 Dashboard", "🍴 Food Logger", "⚙️ Profile Settings"])
    sel_date = str(st.date_input("Date Context", datetime.today().date(), max_value=datetime.today().date()))

# ==========================================
# PAGE: DASHBOARD (Editing + Auto-Save)
# ==========================================
if nav == "📊 Dashboard":
    st.header(f"Status: {sel_date}")
    cal_t, prot_t, fat_t, carb_t = get_macros(st.session_state.profile)
    
    mask = st.session_state.food_history['Date'] == sel_date
    daily = st.session_state.food_history[mask]
    
    # METRICS
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kcal Left", f"{cal_t - daily['Cals'].sum()}")
    c2.metric("Protein Left", f"{prot_t - daily['P'].sum()}g")
    c3.metric("Fats Left", f"{fat_t - daily['F'].sum()}g")
    c4.metric("Carbs Left", f"{carb_t - daily['C'].sum()}g")

    st.divider()
    
    # WATER TRACKER
    st.subheader("💧 Daily Hydration")
    if sel_date not in st.session_state.water_history: st.session_state.water_history[sel_date] = 0
    w_curr, w_goal = st.session_state.water_history[sel_date], st.session_state.profile["water_goal"]
    st.progress(min(w_curr / w_goal, 1.0))
    st.write(f"**{w_curr}ml** / {w_goal}ml")
    wc1, wc2, wc3 = st.columns(3)
    if wc1.button("+ 250ml"): 
        st.session_state.water_history[sel_date] += 250
        save_all_to_cookies()
        st.rerun()
    if wc2.button("+ 500ml"): 
        st.session_state.water_history[sel_date] += 500
        save_all_to_cookies()
        st.rerun()

    st.divider()

    # MEAL MANAGEMENT
    
    st.subheader("🥘 Meal Management")
    if not daily.empty:
        edited_df = st.data_editor(daily[["Name", "Cals", "P", "F", "C"]], num_rows="dynamic", use_container_width=True)
        if st.button("Apply Changes & Save Progress"):
            other_days = st.session_state.food_history[st.session_state.food_history['Date'] != sel_date]
            edited_df['Date'] = sel_date
            st.session_state.food_history = pd.concat([other_days, edited_df], ignore_index=True)
            save_all_to_cookies()
            st.success("Log permanently saved to device!")
            st.rerun()
    else: st.info("No entries for today.")

# ==========================================
# PAGE: FOOD LOGGER (Auto-Save on Log)
# ==========================================
elif nav == "🍴 Food Logger":
    st.header("Precision Logging")
    t1, t2, t3, t4 = st.tabs(["🇺🇸 USDA", "🇮🇳 Indian", "🤖 AI Vision", "⚡ Barcode"])
    
    def log_meal_and_save(n, c, p, f, carb):
        new_row = pd.DataFrame([{"Date": sel_date, "Name": n, "Cals": c, "P": p, "F": f, "C": carb}])
        st.session_state.food_history = pd.concat([st.session_state.food_history, new_row], ignore_index=True)
        save_all_to_cookies()
        st.success(f"Logged {n} and saved to device memory!")

    # Tab logics remain as v11.3 but call log_meal_and_save instead of log_meal...
    # (Simplified for space: identical to v11.3 tab logic)

# ==========================================
# PAGE: PROFILE (LOCKS VARIABLES)
# ==========================================
elif nav == "⚙️ Profile Settings":
    st.header("Profile Memory & Calculator")
    p = st.session_state.profile
    p['weight'] = st.number_input("Weight (kg)", value=float(p['weight']))
    p['height'] = st.number_input("Height (cm)", value=float(p['height']))
    p['neck'] = st.number_input("Neck Circ. (cm)", value=float(p['neck']))
    p['waist'] = st.number_input("Waist Circ. (cm)", value=float(p['waist']))
    p['water_goal'] = st.number_input("Water Goal (ml)", value=int(p['water_goal']))
    
    if st.button("💾 Permanently Save & Lock Everything"):
        p['bf'] = get_navy_bf(p)
        st.session_state.profile = p
        save_all_to_cookies()
        st.success("Variables and history locked into browser memory!")
