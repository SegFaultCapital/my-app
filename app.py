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

# --- 1. PROFESSIONAL UI CONFIG ---
st.set_page_config(page_title="Health OS v11.1", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 26px; color: #00E676; }
    div[data-testid="stVerticalBlock"] > div:has(div.stMetric) {
        background-color: #161B22; border-radius: 12px; padding: 15px; border: 1px solid #30363D;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { background-color: #21262D; border-radius: 8px; }
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
# IFCT-based Indian Database
indian_db = pd.DataFrame({
    "Food": ["Roti (Whole Wheat)", "Paneer (Raw)", "Toor Dal (Cooked)", "White Rice (Cooked)", "Chicken Curry", "Dal Makhani", "Egg Bhurji", "Mutton Dhansak", "Fish Fry"],
    "Cals": [297, 265, 116, 130, 145, 160, 185, 180, 220],
    "P": [9, 18, 6, 2.7, 14, 5, 12, 9, 18],
    "F": [1, 20, 0.4, 0.3, 8, 9, 14, 8, 12],
    "C": [61, 1.2, 21, 28, 5, 15, 3, 18, 5]
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

# --- 4. BARCODE LOGIC ---
class BarcodeProcessor(VideoProcessorBase):
    def __init__(self): self.last_code = None
    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        for obj in decode(img): self.last_code = obj.data.decode("utf-8")
        return av.VideoFrame.from_ndarray(img, format="bgr24")

# --- 5. NAVIGATION ---
with st.sidebar:
    st.title("🛡️ Health OS v11.1")
    nav = st.radio("Navigate", ["📊 Dashboard", "🍴 Food Logger", "🏋️ Progress", "⚙️ Profile Settings"])
    sel_date = str(st.date_input("Date context:", datetime.today().date()))

if "food_history" not in st.session_state: 
    st.session_state.food_history = pd.DataFrame(columns=["Date", "Name", "Cals", "P", "F", "C"])

# ==========================================
# PAGE: DASHBOARD
# ==========================================
if nav == "📊 Dashboard":
    st.header(f"Summary for {sel_date}")
    cal_t, prot_t, fat_t, carb_t = get_macros(st.session_state.profile)
    daily = st.session_state.food_history[st.session_state.food_history['Date'] == sel_date]
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kcal Left", f"{cal_t - daily['Cals'].sum()}")
    c2.metric("Protein Left", f"{prot_t - daily['P'].sum()}g")
    c3.metric("Fats Left", f"{fat_t - daily['F'].sum()}g")
    c4.metric("Carbs Left", f"{carb_t - daily['C'].sum()}g")

    st.divider()
    st.subheader("🧬 Body Composition")
    v1, v2, v3 = st.columns(3)
    v1.metric("Body Fat", f"{st.session_state.profile['bf']}%")
    v2.metric("Weight", f"{st.session_state.profile['weight']}kg")
    v3.metric("Lean Mass", f"{round(st.session_state.profile['weight']*(1-st.session_state.profile['bf']/100), 1)}kg")
    
    with st.expander("🍔 View Logged Meals", expanded=True):
        if not daily.empty:
            st.dataframe(daily[["Name", "Cals", "P", "F", "C"]], use_container_width=True)
        else: st.info("No meals logged yet.")

# ==========================================
# PAGE: FOOD LOGGER (THE COMPLETE 4-WAY SYSTEM)
# ==========================================
elif nav == "🍴 Food Logger":
    st.header("Log Your Fuel")
    tab1, tab2, tab3, tab4 = st.tabs(["🇺🇸 USDA", "🇮🇳 Indian (IFCT)", "🤖 AI Vision", "⚡ Live Barcode"])
    
    def log_meal(n, c, p, f, carb):
        new_row = pd.DataFrame([{"Date": sel_date, "Name": n, "Cals": c, "P": p, "F": f, "C": carb}])
        st.session_state.food_history = pd.concat([st.session_state.food_history, new_row], ignore_index=True)
        st.success(f"Logged {n}!")

    with tab1:
        u_query = st.text_input("Search USDA Database")
        if u_query:
            url = f"https://api.nal.usda.gov/fdc/v1/foods/search?api_key={USDA_KEY}&query={u_query}&pageSize=5"
            foods = requests.get(url).json().get("foods", [])
            for f in foods:
                with st.expander(f"{f['description']} ({f.get('brandOwner', 'Generic')})"):
                    grams = st.number_input("Grams", 1, 1000, 100, key=f"u_{f['fdcId']}")
                    # Simple macro parsing
                    c, p, ft, cb = 0, 0, 0, 0
                    for n in f['foodNutrients']:
                        if n['nutrientId'] == 1008: c = n['value'] * (grams/100)
                        if n['nutrientId'] == 1003: p = n['value'] * (grams/100)
                    if st.button("Log USDA", key=f"btn_u_{f['fdcId']}"):
                        log_meal(f['description'], round(c), round(p), 0, 0)

    with tab2:
        i_query = st.text_input("Search Indian Database")
        if i_query:
            res = indian_db[indian_db['Food'].str.contains(i_query, case=False)]
            for idx, row in res.iterrows():
                with st.expander(row['Food']):
                    g = st.number_input("Grams", 1, 1000, 100, key=f"i_{idx}")
                    if st.button("Log IFCT", key=f"btn_i_{idx}"):
                        log_meal(row['Food'], round(row['Cals']*g/100), round(row['P']*g/100), round(row['F']*g/100), round(row['C']*g/100))

    with tab3:
        cam = st.camera_input("Snap for AI Analysis")
        if cam and st.button("Analyze with Gemini"):
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = "Analyze food image. Return JSON ONLY: {'name': str, 'calories': int, 'protein': int, 'fat': int, 'carbs': int} for 100g."
            res = model.generate_content([prompt, Image.open(cam)])
            data = json.loads(res.text.strip().replace("```json", "").replace("```", ""))
            st.write(f"### Detected: {data['name']}")
            g_ai = st.number_input("Portion Grams", 1, 1000, 100)
            if st.button("Log AI Meal"):
                log_meal(data['name'], round(data['calories']*g_ai/100), round(data['protein']*g_ai/100), round(data['fat']*g_ai/100), round(data['carbs']*g_ai/100))

    with tab4:
        st.write("Instant Barcode Detection")
        scanner = webrtc_streamer(key="live_bar", video_processor_factory=BarcodeProcessor)
        if scanner.video_processor and scanner.video_processor.last_code:
            st.success(f"Code: {scanner.video_processor.last_code}")
            # Placeholder for Open Food Facts logic...

# ==========================================
# PAGE: PROFILE SETTINGS (PERMANENT)
# ==========================================
elif nav == "⚙️ Profile Settings":
    st.header("Body Variables")
    p = st.session_state.profile
    p['weight'] = st.number_input("Current Weight (kg)", value=float(p['weight']))
    p['height'] = st.number_input("Height (cm)", value=float(p['height']))
    p['neck'] = st.number_input("Neck Circ. (cm)", value=float(p['neck']))
    p['waist'] = st.number_input("Waist Circ. (cm)", value=float(p['waist']))
    p['goal_bf'] = st.number_input("Goal Body Fat %", value=float(p['goal_bf']))
    
    if st.button("💾 Permanently Save & Lock Variables"):
        p['bf'] = get_navy_bf(p)
        cookie_manager.set("p_data", p)
        st.session_state.profile = p
        st.success("Stats locked into browser memory!")
