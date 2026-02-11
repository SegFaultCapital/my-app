import streamlit as st
import pandas as pd
import requests
import math
from datetime import datetime
import extra_streamlit_components as stx

# PAGE CONFIG
st.set_page_config(page_title="My Health OS", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    div[data-testid="metric-container"] {
        background-color: #1E1E1E;
        border: 1px solid #333;
        border-radius: 12px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- API CONFIGS ---
USDA_API_KEY = "bg2FpzvDUSiUDflmbHBeAxIpTxbYfhU7ubcRYyyh"  # <--- PASTE YOUR ACTUAL USDA API KEY HERE
GEMINI_API_KEY = "AIzaSyBhFeFbbpiT68oQwZwTwRWvkXEZOGBulw8" # <--- PASTE YOUR NEW GEMINI API KEY HERE

# --- COOKIE MANAGER (BUG FIXED) ---
cookie_manager = stx.CookieManager(key="cookie_manager")

# --- INITIALIZE OR LOAD PROFILE ---
default_profile = {
    "gender": "Male", "age": 17, "weight": 75.0, "goal_weight": 65.0, 
    "months": 4, "water_goal_ml": 3000, "bf_percent": 15.0, 
    "goal_bf_percent": 10.0, "neck_cm": 38.0, "waist_cm": 80.0
}

saved_profile = cookie_manager.get("user_profile")
if saved_profile:
    st.session_state.profile = saved_profile
elif "profile" not in st.session_state:
    st.session_state.profile = default_profile

# --- SESSION STATE INITIALIZATION (DATABASES) ---
current_date = str(datetime.today().date())

if "food_history" not in st.session_state:
    st.session_state.food_history = pd.DataFrame(columns=["Date", "Food_Name", "Calories", "Protein", "Fat", "Carbs"])

if "workout_history" not in st.session_state: 
    st.session_state.workout_history = pd.DataFrame(columns=["Date", "Exercise", "Weight", "Reps"])

if "weight_history" not in st.session_state:
    st.session_state.weight_history = pd.DataFrame({"Date": [current_date], "Weight": [st.session_state.profile["weight"]]})

if "water_log" not in st.session_state:
    st.session_state.water_log = {current_date: 0}

# --- EXPANDED INDIAN FOOD DATABASE (IFCT) ---
indian_db_data = {
    "Food": ["Roti (Whole Wheat)", "Paneer (Raw)", "Toor Dal (Cooked)", "White Rice (Cooked)", "Chicken Curry", "Mutton Dhansak", "Chicken Fried Rice", "Mutton Curry", "Beef Fry", "Pork Vindaloo", "Chicken Tikka (Dry)", "Egg Curry"],
    "Calories": [297, 265, 116, 130, 145, 180, 160, 140, 220, 250, 150, 135],
    "Protein": [9, 18, 6, 2.7, 14, 9, 6, 12, 18, 14, 20, 11],
    "Fats": [1, 20, 0.4, 0.3, 8, 8, 5, 8, 15, 18, 7, 9],
    "Carbs": [61, 1.2, 21, 28, 5, 18, 22, 5, 3, 8, 2, 3]
}
indian_df = pd.DataFrame(indian_db_data)

# --- APP LOGIC: CALCULATIONS ---
def calculate_bf_navy(gender, height, neck, waist, hip=None):
    try:
        if gender == "Male":
            return 495.0 / (1.0324 - 0.19077 * math.log10(waist - neck) + 0.15456 * math.log10(height)) - 450.0
        else:
            return 495.0 / (1.29579 - 0.35004 * math.log10(waist + hip - neck) + 0.22100 * math.log10(height)) - 450.0
    except:
        return 15.0 

def calculate_metrics(p):
    lean_body_mass = p["weight"] * (1 - (p["bf_percent"] / 100.0))
    bmr = 370 + (21.6 * lean_body_mass)
    tdee = bmr * 1.3 
    
    total_kg_to_lose = p["weight"] - p["goal_weight"]
    daily_deficit = (total_kg_to_lose * 7700) / (p["months"] * 30) if p["months"] > 0 else 0
    target_cal = tdee - daily_deficit
    
    protein = lean_body_mass * 2.2
    fats = (target_cal * 0.25) / 9
    carbs = (target_cal - (protein * 4) - (fats * 9)) / 4
    
    return round(target_cal), round(protein), round(fats), round(carbs)

# --- GLOBAL NAVIGATION ---
st.sidebar.title("📱 Menu")
page = st.sidebar.radio("Go to", ["📊 Dashboard", "🍎 Log Food", "🏋️ Log Workout", "👤 My Profile (Settings)"])

st.sidebar.divider()
active_date_obj = st.sidebar.date_input("📅 Log data for:", datetime.today().date())
active_date = str(active_date_obj)

if active_date not in st.session_state.water_log:
    st.session_state.water_log[active_date] = 0

cal_target, prot_target, fat_target, carb_target = calculate_metrics(st.session_state.profile)
daily_food = st.session_state.food_history[st.session_state.food_history["Date"] == active_date]
consumed_cals = daily_food["Calories"].sum()
rem_cal = cal_target - consumed_cals
rem_prot = prot_target - daily_food["Protein"].sum()
rem_fat = fat_target - daily_food["Fat"].sum()
rem_carb = carb_target - daily_food["Carbs"].sum()

# ==========================================
# PAGE 1: DASHBOARD
# ==========================================
if page == "📊 Dashboard":
    st.header("Daily Summary")
    st.caption(f"Viewing data for: {active_date}")
    
    c_a, c_b, c_c = st.columns(3)
    c_a.metric("⚖️ Weight", f"{st.session_state.profile['weight']} kg", f"Goal: {st.session_state.profile['goal_weight']} kg", delta_color="off")
    c_b.metric("🧬 Body Fat", f"{round(st.session_state.profile['bf_percent'], 1)}%", f"Goal: {st.session_state.profile['goal_bf_percent']}%", delta_color="off")
    lbm = round(st.session_state.profile['weight'] * (1 - (st.session_state.profile['bf_percent'] / 100.0)), 1)
    c_c.metric("💪 Lean Mass", f"{lbm} kg")
    
    st.divider()
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔥 Kcal Left", f"{rem_cal}", f"Goal: {cal_target}", delta_color="off")
    c2.metric("🥩 Pro Left", f"{rem_prot}g", f"Goal: {prot_target}g", delta_color="off")
    c3.metric("🥑 Fat Left", f"{rem_fat}g", f"Goal: {fat_target}g", delta_color="off")
    c4.metric("🍞 Carb Left", f"{rem_carb}g", f"Goal: {carb_target}g", delta_color="off")

    st.divider()

    st.subheader("💧 Hydration Tracker")
    current_water = st.session_state.water_log[active_date]
    water_goal = st.session_state.profile["water_goal_ml"]
    progress = min(current_water / water_goal, 1.0)
    
    st.progress(progress)
    st.write(f"**{current_water} ml** / {water_goal} ml")
    
    w1, w2, w3, w4 = st.columns(4)
    if w1.button("+ 250ml"): st.session_state.water_log[active_date] += 250; st.rerun()
    if w2.button("+ 500ml"): st.session_state.water_log[active_date] += 500; st.rerun()
    if w3.button("Undo (-250ml)"): st.session_state.water_log[active_date] = max(0, st.session_state.water_log[active_date] - 250); st.rerun()

    st.divider()

    with st.expander("🍔 View & Edit Today's Meals", expanded=True):
        if not daily_food.empty:
            for idx, row in daily_food.iterrows():
                c1, c2 = st.columns([5, 1])
                c1.write(f"**{row['Food_Name']}** — {row['Calories']} kcal")
                if c2.button("❌", key=f"del_food_{idx}"):
                    st.session_state.food_history = st.session_state.food_history.drop(idx)
                    st.rerun()
        else:
            st.info("No food logged for this date yet.")

# ==========================================
# PAGE 2: FOOD LOGGER
# ==========================================
elif page == "🍎 Log Food":
    st.header("Search & Log Food")
    tab1, tab2, tab3 = st.tabs(["🇺🇸 USDA", "🇮🇳 Indian Meals", "🤖 AI Vision Scanner"])

    def add_to_food_history(cals, prot, fat, carbs, display_text):
        new_entry = pd.DataFrame([{"Date": active_date, "Food_Name": display_text, "Calories": cals, "Protein": prot, "Fat": fat, "Carbs": carbs}])
        st.session_state.food_history = pd.concat([st.session_state.food_history, new_entry], ignore_index=True)

    with tab1:
        search_query = st.text_input("Search USDA (e.g., 'Raw Chicken')")
        if search_query:
            url = f"https://api.nal.usda.gov/fdc/v1/foods/search?api_key={USDA_API_KEY}&query={search_query}&pageSize=5"
            try:
                data = requests.get(url).json()
                if "foods" in data and len(data["foods"]) > 0:
                    for food in data["foods"]:
                        desc = food.get("description", "Unknown").title()
                        brand = food.get("brandOwner", "")
                        base_cals, base_prot, base_fat, base_carbs = 0, 0, 0, 0
                        for nutrient in food.get("foodNutrients", []):
                            name = nutrient.get("nutrientName", "").lower()
                            val = nutrient.get("value", 0)
                            if "energy" in name and "kcal" in nutrient.get("unitName", "").lower(): base_cals = val
                            elif "protein" in name: base_prot = val
                            elif "total lipid (fat)" in name or name == "fat": base_fat = val
                            elif "carbohydrate" in name: base_carbs = val
                        
                        with st.expander(f"🍽️ {desc} {f'({brand})' if brand else ''}"):
                            serving_grams = st.number_input("Amount (grams)", min_value=1, value=100, key=f"usda_{food['fdcId']}")
                            multiplier = serving_grams / 100.0
                            adj_cals, adj_prot, adj_fat, adj_carb = round(base_cals * multiplier), round(base_prot * multiplier), round(base_fat * multiplier), round(base_carbs * multiplier)
                            
                            c1, c2, c3, c4 = st.columns(4)
                            c1.metric("Cals", f"{adj_cals}")
                            c2.metric("Pro", f"{adj_prot}g")
                            c3.metric("Fat", f"{adj_fat}g")
                            c4.metric("Carb", f"{adj_carb}g")
                            
                            if st.button("Log this amount", key=f"log_usda_{food['fdcId']}"):
                                add_to_food_history(adj_cals, adj_prot, adj_fat, adj_carb, f"{serving_grams}g of {desc}")
                                st.success(f"Logged to {active_date}!")
                else:
                    st.warning("No foods found.")
            except Exception:
                st.error("API Error. Check your API key.")

    with tab2:
        indian_query = st.text_input("Search Indian DB (e.g., 'Paneer')")
        if indian_query:
            results = indian_df[indian_df["Food"].str.contains(indian_query, case=False)]
            if not results.empty:
                for index, row in results.iterrows():
                    with st.expander(f"🇮🇳 {row['Food']}"):
                        serving_grams = st.number_input("Amount (grams)", min_value=1, value=100, key=f"ind_{index}")
                        multiplier = serving_grams / 100.0
                        adj_cals, adj_prot, adj_fat, adj_carb = round(row["Calories"] * multiplier), round(row["Protein"] * multiplier), round(row["Fats"] * multiplier), round(row["Carbs"] * multiplier)
                        
                        if st.button("Log this amount", key=f"log_ind_{index}"):
                            add_to_food_history(adj_cals, adj_prot, adj_fat, adj_carb, f"{serving_grams}g of {row['Food']}")
                            st.success(f"Logged to {active_date}!")
            else:
                st.warning("Not found.")

    with tab3:
        st.write("🤖 **Snap a photo of your food. The AI will estimate the macros.**")
        camera_photo = st.camera_input("Take a picture")
        
        if camera_photo is not None:
            if st.button("Analyze with AI"):
                with st.spinner("Analyzing image..."):
                    try:
                        import google.generativeai as genai
                        from PIL import Image
                        import json
                        
                        genai.configure(api_key=GEMINI_API_KEY)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        img = Image.open(camera_photo)
                        prompt = """
                        You are a nutrition expert. Look at this food image.
                        Return ONLY a raw JSON object (no markdown, no backticks) with these keys: 
                        "name" (string), "calories" (number), "protein" (number), "fat" (number), "carbs" (number). 
                        Standardize these macros to roughly 100g of this food.
                        """
                        response = model.generate_content([prompt, img])
                        
                        # Clean the string for JSON parsing
                        cleaned_resp = response.text.strip().replace("```json", "").replace("```", "")
                        ai_data = json.loads(cleaned_resp)
                        
                        # Save result to session state so it survives a rerun
                        st.session_state.last_ai_scan = ai_data
                        st.success("Analysis Complete!")
                        
                    except Exception as e:
                        st.error(f"AI Vision Error. Check API Key. {e}")
                        
        # Display the AI results if they exist in memory
        if "last_ai_scan" in st.session_state:
            ai_data = st.session_state.last_ai_scan
            name = ai_data.get("name", "Unknown AI Food").title()
            base_cals = float(ai_data.get("calories", 0))
            base_prot = float(ai_data.get("protein", 0))
            base_fat = float(ai_data.get("fat", 0))
            base_carbs = float(ai_data.get("carbs", 0))
            
            with st.expander(f"🤖 Estimated: {name} (per 100g)", expanded=True):
                st.info("AI estimates macros per 100g. Adjust the grams below to match your actual portion.")
                serving_grams = st.number_input("How many grams are you eating?", min_value=1, value=100, key="ai_grams")
                multiplier = serving_grams / 100.0
                
                adj_cals = round(base_cals * multiplier)
                adj_prot = round(base_prot * multiplier)
                adj_fat = round(base_fat * multiplier)
                adj_carb = round(base_carbs * multiplier)
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Cals", f"{adj_cals}")
                c2.metric("Pro", f"{adj_prot}g")
                c3.metric("Fat", f"{adj_fat}g")
                c4.metric("Carb", f"{adj_carb}g")
                
                if st.button("Log AI Estimate", key="log_ai"):
                    add_to_food_history(adj_cals, adj_prot, adj_fat, adj_carb, f"{serving_grams}g of {name} (AI)")
                    del st.session_state.last_ai_scan # Clear memory after logging
                    st.success(f"Logged to {active_date}!")
                    st.rerun()

# ==========================================
# PAGE 3: WORKOUT LOGGER
# ==========================================
elif page == "🏋️ Log Workout":
    st.header("Lifting Log")

    with st.expander("➕ Add New Set", expanded=True):
        exercise = st.text_input("Exercise Name")
        weight_lifted = st.number_input("Weight (kg)", 0.0)
        reps = st.number_input("Reps", 0)
        if st.button("Save Set"):
            new_set = pd.DataFrame([{"Date": active_date, "Exercise": exercise.title(), "Weight": weight_lifted, "Reps": reps}])
            st.session_state.workout_history = pd.concat([st.session_state.workout_history, new_set], ignore_index=True)
            st.success(f"Saved!")

    if not st.session_state.workout_history.empty:
        st.write("📈 **Strength Progression**")
        exercises_logged = st.session_state.workout_history["Exercise"].unique()
        selected_ex = st.selectbox("Graph exercise:", exercises_logged)
        
        ex_data = st.session_state.workout_history[st.session_state.workout_history["Exercise"] == selected_ex].copy()
        ex_data['Date'] = pd.to_datetime(ex_data['Date'])
        max_weight_per_day = ex_data.groupby("Date")["Weight"].max().reset_index()
        max_weight_per_day.set_index("Date", inplace=True)
        st.line_chart(max_weight_per_day, y="Weight", color="#FF5252")

# ==========================================
# PAGE 4: PROFILE & SETTINGS
# ==========================================
elif page == "👤 My Profile (Settings)":
    st.header("👤 Body Metrics & Goals")
    st.write("Save your stats here. The app permanently remembers them.")
    
    p = st.session_state.profile
    
    c1, c2 = st.columns(2)
    p["gender"] = c1.selectbox("Gender", ["Male", "Female"], index=0 if p["gender"]=="Male" else 1)
    p["age"] = c2.number_input("Age", 10, 100, int(p["age"]))
    
    st.subheader("⚖️ Weight & Body Fat")
    c3, c4 = st.columns(2)
    p["weight"] = c3.number_input("Current Weight (kg)", 40.0, 200.0, float(p["weight"]))
    
    c_n, c_w = st.columns(2)
    p["neck_cm"] = c_n.number_input("Neck Circ. (cm)", 20.0, 80.0, float(p.get("neck_cm", 38.0)))
    p["waist_cm"] = c_w.number_input("Waist Circ. (cm)", 40.0, 150.0, float(p.get("waist_cm", 80.0)))
    
    # We removed height input here to respect your data correction command,
    # so we use a fallback math logic for the BF% equation if needed.
    p["bf_percent"] = st.number_input("Current Body Fat % (Estimate)", 3.0, 50.0, float(p["bf_percent"]))
    
    st.subheader("🎯 Goals")
    c5, c6 = st.columns(2)
    p["goal_weight"] = c5.number_input("Target Weight (kg)", 40.0, 200.0, float(p["goal_weight"]))
    p["goal_bf_percent"] = c6.number_input("Target Body Fat %", 3.0, 50.0, float(p.get("goal_bf_percent", 10.0)))
    
    c7, c8 = st.columns(2)
    p["months"] = c7.number_input("Months to Goal", 1, 24, int(p["months"]))
    p["water_goal_ml"] = c8.number_input("Daily Water Goal (ml)", 1000, 6000, int(p["water_goal_ml"]), step=250)
    
    if st.button("💾 Save Profile Permanently"):
        cookie_manager.set("user_profile", p, key="save_profile_cookie")
        st.session_state.profile = p
        
        new_w = pd.DataFrame({"Date": [active_date], "Weight": [p["weight"]]})
        st.session_state.weight_history = pd.concat([st.session_state.weight_history, new_w], ignore_index=True)
        
        st.success("Profile saved to your browser! It will auto-load tomorrow.")
