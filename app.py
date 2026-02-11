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
st.set_page_config(page_title="Health OS v11.2", layout="wide", initial_sidebar_state="expanded")

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

cookie_manager = stx.CookieManager(key="health_os_final_stable")

# Load Permanent Profile from Browser
saved_p = cookie_manager.get("p_data")
if "profile" not in st.session_state:
    st.session_state.profile = saved_p if saved_p else {
        "weight": 105.0, "height": 185.0, "age": 17, "neck": 41.0, "waist": 99.0,
        "bf": 23.0, "goal_bf": 15.0, "water_goal": 3600, "gender": "Male"
    }

# --- 3. DATABASES & MATH ---
indian_db = pd.DataFrame({
    "Food": ["Roti", "Paneer", "Toor Dal", "Rice", "Chicken Curry", "Dal Makhani", "Egg Bhurji"],
    "Cals": [297, 265, 116, 130, 145, 160, 185],
    "P": [9, 18, 6, 2.7, 14, 5, 12], "F": [1, 20, 0.4, 0.3, 8, 9, 14], "C": [61, 1.2, 21, 28, 5, 15, 3]
})

def get_navy_bf(p):
    try:
        if p['gender'] == "Male":
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

# --- 4. SCANNER LOGIC ---
class BarcodeProcessor(VideoProcessorBase):
    def __init__(self): self.last_code = None
    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        for obj in decode(img): self.last_code = obj.data.decode("utf-8")
        return av.VideoFrame.from_ndarray(img, format="bgr24")

# --- 5. NAVIGATION & DATE LOCK ---
with st.sidebar:
    st.title("🛡️ Health OS v11.2")
    nav = st.radio("Navigate", ["📊 Dashboard", "🍴 Food Logger", "⚙️ Profile Settings"])
    # LOCK: max_value stops you from logging in the future
    sel_date = str(st.date_input("Date context:", datetime.today().date(), max_value=datetime.today().date()))

if "food_history" not in st.session_state: 
    st.session_state.food_history = pd.DataFrame(columns=["Date", "Name", "Cals", "P", "F", "C"])
if "water_history" not in st.session_state:
    st.session_state.water_history = {}

# ==========================================
# PAGE: DASHBOARD (Editing & Water)
# ==========================================
if nav == "📊 Dashboard":
    st.header(f"Day Context: {sel_date}")
    cal_t, prot_t, fat_t, carb_t = get_macros(st.session_state.profile)
    daily = st.session_state.food_history[st.session_state.food_history['Date'] == sel_date]
    
    # MACRO SUMMARY
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kcal Left", f"{cal_t - daily['Cals'].sum()}")
    c2.metric("Protein Left", f"{prot_t - daily['P'].sum()}g")
    c3.metric("Fats Left", f"{fat_t - daily['F'].sum()}g")
    c4.metric("Carbs Left", f"{carb_t - daily['C'].sum()}g")

    st.divider()
    
    # WATER TRACKER
    st.subheader("💧 Hydration")
    if sel_date not in st.session_state.water_history: st.session_state.water_history[sel_date] = 0
    w_curr = st.session_state.water_history[sel_date]
    w_goal = st.session_state.profile["water_goal"]
    st.progress(min(w_curr / w_goal, 1.0))
    st.write(f"Consumed: **{w_curr}ml** / {w_goal}ml")
    
    wc1, wc2, wc3 = st.columns(3)
    if wc1.button("+ 250ml"): st.session_state.water_history[sel_date] += 250; st.rerun()
    if wc2.button("+ 500ml"): st.session_state.water_history[sel_date] += 500; st.rerun()
    if wc3.button("Reset Water"): st.session_state.water_history[sel_date] = 0; st.rerun()

    st.divider()

    # EDIT/REMOVE MEALS
    with st.expander("🍔 Manage Logged Meals", expanded=True):
        if not daily.empty:
            for idx, row in daily.iterrows():
                col_n, col_d = st.columns([5, 1])
                col_n.write(f"**{row['Name']}** | {row['Cals']} kcal")
                if col_d.button("❌", key=f"del_{idx}"):
                    st.session_state.food_history = st.session_state.food_history.drop(idx)
                    st.rerun()
        else: st.info("No meals logged for this date.")

# ==========================================
# PAGE: FOOD LOGGER (4-WAY)
# ==========================================
elif nav == "🍴 Food Logger":
    st.header("Daily Fuel")
    t1, t2, t3, t4 = st.tabs(["🇺🇸 USDA", "🇮🇳 Indian", "🤖 AI Vision", "⚡ Barcode"])
    
    def log_meal(n, c, p, f, carb):
        new_row = pd.DataFrame([{"Date": sel_date, "Name": n, "Cals": c, "P": p, "F": f, "C": carb}])
        st.session_state.food_history = pd.concat([st.session_state.food_history, new_row], ignore_index=True)
        st.success(f"Logged {n}!")

    with t1:
        u_q = st.text_input("USDA Search")
        if u_q:
            url = f"https://api.nal.usda.gov/fdc/v1/foods/search?api_key={USDA_KEY}&query={u_q}&pageSize=5"
            foods = requests.get(url).json().get("foods", [])
            for f in foods:
                with st.expander(f['description']):
                    g = st.number_input("Grams", 1, 1000, 100, key=f"u_{f['fdcId']}")
                    c, p = 0, 0
                    for n in f['foodNutrients']:
                        if n['nutrientId'] == 1008: c = n['value'] * (g/100)
                        if n['nutrientId'] == 1003: p = n['value'] * (g/100)
                    if st.button("Log", key=f"b_u_{f['fdcId']}"): log_meal(f['description'], round(c), round(p), 0, 0)

    with t2:
        i_q = st.text_input("Indian Search")
        if i_q:
            res = indian_db[indian_db['Food'].str.contains(i_q, case=False)]
            for idx, row in res.iterrows():
                with st.expander(row['Food']):
                    g_i = st.number_input("Grams", 1, 1000, 100, key=f"i_{idx}")
                    if st.button("Log", key=f"b_i_{idx}"): log_meal(row['Food'], round(row['Cals']*g_i/100), round(row['P']*g_i/100), round(row['F']*g_i/100), round(row['C']*g_i/100))

    with t3:
        cam = st.camera_input("AI Snap")
        if cam and st.button("Analyze"):
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            res = model.generate_content(["Return JSON only: {'name':str, 'calories':int, 'protein':int, 'fat':int, 'carbs':int} per 100g", Image.open(cam)])
            d = json.loads(res.text.strip().replace("```json", "").replace("```", ""))
            st.write(f"### Detected: {d['name']}")
            g_ai = st.number_input("Portion Grams", 1, 1000, 100)
            if st.button("Confirm AI Log"): log_meal(d['name'], round(d['calories']*g_ai/100), round(d['protein']*g_ai/100), round(d['fat']*g_ai/100), round(d['carbs']*g_ai/100))

    with t4:
        st.write("Live Scanner (30fps)")
        ctx = webrtc_streamer(key="barcode", video_processor_factory=BarcodeProcessor)
        if ctx.video_processor and ctx.video_processor.last_code: st.success(f"Barcode: {ctx.video_processor.last_code}")

# ==========================================
# PAGE: PROFILE (MEMORY)
# ==========================================
elif nav == "⚙️ Profile Settings":
    st.header("User Stats & BF% Calculator")
    p = st.session_state.profile
    p['weight'] = st.number_input("Weight (kg)", value=float(p['weight']))
    p['height'] = st.number_input("Height (cm)", value=float(p['height']))
    p['neck'] = st.number_input("Neck (cm)", value=float(p['neck']))
    p['waist'] = st.number_input("Waist (cm)", value=float(p['waist']))
    p['water_goal'] = st.number_input("Water Goal (ml)", value=int(p['water_goal']))
    
    if st.button("💾 Permanently Lock Variable Memory"):
        p['bf'] = get_navy_bf(p)
        cookie_manager.set("p_v11_2", p)
        st.session_state.profile = p
        st.success("Variables locked and Body Fat recalculated!")
