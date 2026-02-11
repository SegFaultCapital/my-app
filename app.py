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

# --- 1. UI & THEME ---
st.set_page_config(page_title="Health OS v11.5", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 24px; color: #00E676; font-weight: bold; }
    div[data-testid="stVerticalBlock"] > div:has(div.stMetric) {
        background-color: #161B22; border-radius: 12px; padding: 15px; border: 1px solid #30363D;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. PERMANENT MEMORY ---
USDA_KEY = "bg2FpzvDUSiUDflmbHBeAxIpTxbYfhU7ubcRYyyh"
GEMINI_KEY = "AIzaSyBhFeFbbpiT68oQwZwTwRWvkXEZOGBulw8"

cookie_manager = stx.CookieManager(key="health_os_final_v11_5")

# --- 3. DATA PERSISTENCE (The Fix) ---
# We use st.session_state as the live hub, but sync to cookies on every change
if "profile" not in st.session_state:
    saved_p = cookie_manager.get("p_data")
    st.session_state.profile = saved_p if saved_p else {
        "weight": 75.0, "height": 175.0, "age": 17, "neck": 38.0, "waist": 85.0,
        "bf": 15.0, "goal_bf": 12.0, "water_goal": 3000, "gender": "Male"
    }

if "food_history" not in st.session_state:
    saved_f = cookie_manager.get("f_data")
    st.session_state.food_history = pd.DataFrame(saved_f) if saved_f else pd.DataFrame(columns=["Date", "Name", "Cals", "P", "F", "C"])

if "water_history" not in st.session_state:
    saved_w = cookie_manager.get("w_data")
    st.session_state.water_history = saved_w if saved_w else {}

def sync():
    cookie_manager.set("p_data", st.session_state.profile, key="sync_p")
    cookie_manager.set("f_data", st.session_state.food_history.tail(100).to_dict('records'), key="sync_f")
    cookie_manager.set("w_data", st.session_state.water_history, key="sync_w")

# --- 4. THE MATH: NAVY BF & MACROS ---

def calculate_navy_bf(p):
    try:
        # Standard Navy Formula for Men
        # $$BF = 495 / (1.0324 - 0.19077 \cdot \log_{10}(waist - neck) + 0.15456 \cdot \log_{10}(height)) - 450$$
        bf = 495 / (1.0324 - 0.19077 * math.log10(p['waist'] - p['neck']) + 0.15456 * math.log10(p['height'])) - 450
        return round(bf, 1)
    except: return p['bf']

def get_macro_targets(p):
    lbm = p['weight'] * (1 - (p['bf']/100))
    bmr = 370 + (21.6 * lbm) # Katch-McArdle
    tdee = bmr * 1.35 
    target_cal = tdee - 500
    return round(target_cal), round(lbm * 2.2), round((target_cal*0.25)/9), round((target_cal*0.45)/4)

# --- 5. NAVIGATION ---
with st.sidebar:
    st.title("🛡️ Health OS v11.5")
    nav = st.radio("Menu", ["📊 Dashboard", "🍴 Logger", "⚙️ Profile"])
    sel_date = str(st.date_input("Date", datetime.today().date(), max_value=datetime.today().date()))

# ==========================================
# PAGE: DASHBOARD (Includes BF Calculator)
# ==========================================
if nav == "📊 Dashboard":
    st.header(f"Status Overview ({sel_date})")
    cal_t, prot_t, fat_t, carb_t = get_macro_targets(st.session_state.profile)
    daily = st.session_state.food_history[st.session_state.food_history['Date'] == sel_date]
    
    # 1. Macro Summary
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kcal Left", f"{cal_t - daily['Cals'].sum()}")
    c2.metric("Protein Left", f"{prot_t - daily['P'].sum()}g")
    c3.metric("Fats Left", f"{fat_t - daily['F'].sum()}g")
    c4.metric("Carbs Left", f"{carb_t - daily['C'].sum()}g")

    st.divider()

    # 2. Precise Body Fat Calculator
    with st.expander("🧬 Navy Body Fat Calculator & Weight Update", expanded=True):
        col_bf1, col_bf2 = st.columns(2)
        cur_w = col_bf1.number_input("Update Weight (kg)", value=float(st.session_state.profile['weight']))
        neck = col_bf1.number_input("Neck (cm)", value=float(st.session_state.profile['neck']))
        waist = col_bf2.number_input("Waist (cm)", value=float(st.session_state.profile['waist']))
        
        if st.button("Calculate & Save to Device"):
            st.session_state.profile['weight'] = cur_w
            st.session_state.profile['neck'] = neck
            st.session_state.profile['waist'] = waist
            st.session_state.profile['bf'] = calculate_navy_bf(st.session_state.profile)
            sync()
            st.success(f"Body Fat calculated at {st.session_state.profile['bf']}% and saved!")
            st.rerun()

    st.divider()
    
    # 3. Water Logger
    st.subheader("💧 Hydration")
    if sel_date not in st.session_state.water_history: st.session_state.water_history[sel_date] = 0
    w_curr, w_goal = st.session_state.water_history[sel_date], st.session_state.profile["water_goal"]
    st.progress(min(w_curr / w_goal, 1.0))
    st.write(f"**{w_curr}ml** / {w_goal}ml")
    wc1, wc2 = st.columns(2)
    if wc1.button("+ 250ml"): 
        st.session_state.water_history[sel_date] += 250
        sync(); st.rerun()
    if wc2.button("+ 500ml"): 
        st.session_state.water_history[sel_date] += 500
        sync(); st.rerun()

    st.divider()

    # 4. Meal Management (Delete/View)
    st.subheader("🥘 Today's Log")
    if not daily.empty:
        for idx, row in daily.iterrows():
            col_n, col_d = st.columns([5, 1])
            col_n.write(f"**{row['Name']}** — {row['Cals']} kcal (P:{row['P']}g F:{row['F']}g C:{row['C']}g)")
            if col_d.button("❌", key=f"del_{idx}"):
                st.session_state.food_history = st.session_state.food_history.drop(idx)
                sync(); st.rerun()
    else: st.info("No meals logged yet.")

# ==========================================
# PAGE: LOGGER (USDA & IFCT INCLUDED)
# ==========================================
elif nav == "🍴 Logger":
    st.header("Search & Scan")
    t1, t2, t3, t4 = st.tabs(["🇺🇸 USDA", "🇮🇳 Indian", "🤖 AI Vision", "⚡ Barcode"])
    
    def log_meal(n, c, p, f, carb):
        new_row = pd.DataFrame([{"Date": sel_date, "Name": n, "Cals": c, "P": p, "F": f, "C": carb}])
        st.session_state.food_history = pd.concat([st.session_state.food_history, new_row], ignore_index=True)
        sync()
        st.success(f"Logged {n}!")

    with t1:
        u_query = st.text_input("Search USDA Database")
        if u_query:
            url = f"https://api.nal.usda.gov/fdc/v1/foods/search?api_key={USDA_KEY}&query={u_query}&pageSize=5"
            foods = requests.get(url).json().get("foods", [])
            for food in foods:
                with st.expander(f"{food['description']}"):
                    g = st.number_input("Grams", 1, 1000, 100, key=f"u_{food['fdcId']}")
                    # Map Nutrients (1008=Kcal, 1003=P, 1004=F, 1005=C)
                    c, pr, ft, cb = 0, 0, 0, 0
                    for nut in food['foodNutrients']:
                        if nut['nutrientId'] == 1008: c = nut['value'] * (g/100)
                        elif nut['nutrientId'] == 1003: pr = nut['value'] * (g/100)
                        elif nut['nutrientId'] == 1004: ft = nut['value'] * (g/100)
                        elif nut['nutrientId'] == 1005: cb = nut['value'] * (g/100)
                    if st.button("Log USDA", key=f"b_u_{food['fdcId']}"):
                        log_meal(food['description'], round(c), round(pr), round(ft), round(cb))

    with t2:
        i_query = st.text_input("Search Indian Database (IFCT)")
        indian_db = pd.DataFrame({
            "Food": ["Roti", "Paneer", "Toor Dal", "Rice", "Chicken Curry", "Egg Bhurji"],
            "Cals": [297, 265, 116, 130, 145, 185],
            "P": [9, 18, 6, 2.7, 14, 12], "F": [1, 20, 0.4, 0.3, 8, 14], "C": [61, 1.2, 21, 28, 5, 3]
        })
        res = indian_db[indian_db['Food'].str.contains(i_query, case=False)]
        for idx, row in res.iterrows():
            with st.expander(row['Food']):
                gi = st.number_input("Grams", 1, 1000, 100, key=f"i_{idx}")
                if st.button("Log Indian", key=f"b_i_{idx}"):
                    log_meal(row['Food'], round(row['Cals']*gi/100), round(row['P']*gi/100), round(row['F']*gi/100), round(row['C']*gi/100))

    with t3:
        cam = st.camera_input("AI Plate Scan")
        if cam and st.button("Run AI Analysis"):
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(["JSON only: {name:str, calories:int, protein:int, fat:int, carbs:int} per 100g", Image.open(cam)])
            data = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
            st.write(f"### Detected: {data['name']}")
            g_ai = st.number_input("Portion Grams", 1, 1000, 100)
            if st.button("Confirm AI Log"):
                log_meal(data['name'], round(data['calories']*g_ai/100), round(data['protein']*g_ai/100), round(data['fat']*g_ai/100), round(data['carbs']*g_ai/100))

# --- PROFILE PAGE (REMAINS AS FINAL BACKUP) ---
elif nav == "⚙️ Profile":
    st.header("Body Parameters")
    p = st.session_state.profile
    p['age'] = st.number_input("Age", 10, 100, int(p['age']))
    p['height'] = st.number_input("Height (cm)", 100, 250, int(p['height']))
    p['goal_bf'] = st.number_input("Goal BF %", 5.0, 30.0, float(p['goal_bf']))
    p['water_goal'] = st.number_input("Water Goal (ml)", 1000, 5000, int(p['water_goal']))
    if st.button("Permanently Save Variable Baseline"):
        sync(); st.success("Baseline stats locked to device!")
