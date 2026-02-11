import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# PAGE CONFIG
st.set_page_config(page_title="My Private Tracker", layout="wide")

# --- USDA API CONFIG ---
USDA_API_KEY = "bg2FpzvDUSiUDflmbHBeAxIpTxbYfhU7ubcRYyyh"  # <--- PASTE YOUR ACTUAL USDA API KEY HERE

# --- SESSION STATE INITIALIZATION ---
if "consumed_cals" not in st.session_state: st.session_state.consumed_cals = 0
if "consumed_prot" not in st.session_state: st.session_state.consumed_prot = 0
if "consumed_fat" not in st.session_state: st.session_state.consumed_fat = 0
if "consumed_carbs" not in st.session_state: st.session_state.consumed_carbs = 0
if "logged_foods" not in st.session_state: st.session_state.logged_foods = []

if "workout_history" not in st.session_state: 
    dummy_data = pd.DataFrame({
        "Date": [pd.to_datetime("2026-01-15"), pd.to_datetime("2026-01-22"), pd.to_datetime("2026-01-29")],
        "Exercise": ["Bench Press", "Bench Press", "Bench Press"],
        "Weight": [50.0, 55.0, 60.0],
        "Reps": [8, 8, 6]
    })
    st.session_state.workout_history = dummy_data

# --- EXPANDED INDIAN FOOD DATABASE (IFCT) ---
indian_db_data = {
    "Food": [
        "Roti (Whole Wheat)", "Paneer (Raw)", "Toor Dal (Cooked)", "White Rice (Cooked)", 
        "Chicken Curry (Standard)", "Mutton Dhansak", "Chicken Fried Rice", "Mutton Curry",
        "Beef Fry (Kerala Style)", "Pork Vindaloo", "Chicken Tikka (Dry)", "Egg Curry"
    ],
    "Calories": [297, 265, 116, 130, 145, 180, 160, 140, 220, 250, 150, 135],
    "Protein": [9, 18, 6, 2.7, 14, 9, 6, 12, 18, 14, 20, 11],
    "Fats": [1, 20, 0.4, 0.3, 8, 8, 5, 8, 15, 18, 7, 9],
    "Carbs": [61, 1.2, 21, 28, 5, 18, 22, 5, 3, 8, 2, 3]
}
indian_df = pd.DataFrame(indian_db_data)

# --- APP LOGIC: CALCULATIONS ---
def calculate_metrics(weight, height, age, gender, goal_weight, months):
    if gender == "Male":
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
    
    tdee = bmr * 1.3 
    
    total_kg_to_lose = weight - goal_weight
    total_deficit_needed = total_kg_to_lose * 7700
    daily_deficit = total_deficit_needed / (months * 30)
    target_cal = tdee - daily_deficit
    
    protein = weight * 2.2
    fats = (target_cal * 0.25) / 9
    carbs = (target_cal - (protein * 4) - (fats * 9)) / 4
    
    return round(target_cal), round(protein), round(fats), round(carbs)

# --- UI SIDEBAR & DATA MANAGEMENT ---
with st.sidebar:
    st.header("⚙️ Onboarding Info")
    gender = st.selectbox("Gender", ["Male", "Female"], index=0)
    age = st.number_input("Age", 10, 100, 17)
    w = st.number_input("Weight (kg)", 40.0, 200.0, 75.0)
    h = st.number_input("Height (cm)", 100.0, 250.0, 175.0) 
    gw = st.number_input("Goal Weight (kg)", 40.0, 200.0, 65.0)
    m = st.number_input("Months to Goal", 1, 12, 4)
    
    st.divider()
    
    st.header("💾 Data Management")
    csv_workout = st.session_state.workout_history.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="⬇️ Download Workout Backup",
        data=csv_workout,
        file_name='my_workout_backup.csv',
        mime='text/csv',
    )
    
    st.write("Upload a backup file to restore history:")
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
    if uploaded_file is not None:
        st.session_state.workout_history = pd.read_csv(uploaded_file)
        st.session_state.workout_history['Date'] = pd.to_datetime(st.session_state.workout_history['Date'])
        st.success("History Restored!")
    
    st.divider()
    
    if st.button("Reset Today's Food Log"):
        st.session_state.consumed_cals = 0
        st.session_state.consumed_prot = 0
        st.session_state.consumed_fat = 0
        st.session_state.consumed_carbs = 0
        st.session_state.logged_foods = []
        st.rerun()

st.title("🚀 Private Health & Lift Tracker")

cal_target, prot_target, fat_target, carb_target = calculate_metrics(w, h, age, gender, gw, m)

rem_cal = cal_target - st.session_state.consumed_cals
rem_prot = prot_target - st.session_state.consumed_prot
rem_fat = fat_target - st.session_state.consumed_fat
rem_carb = carb_target - st.session_state.consumed_carbs

# --- DASHBOARD ---
st.subheader("📊 Today's Remaining Macros")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Calories", f"{rem_cal} kcal", f"Target: {cal_target}", delta_color="off")
col2.metric("Protein", f"{rem_prot} g", f"Target: {prot_target}", delta_color="off")
col3.metric("Fats", f"{rem_fat} g", f"Target: {fat_target}", delta_color="off")
col4.metric("Carbs", f"{rem_carb} g", f"Target: {carb_target}", delta_color="off")

if st.session_state.logged_foods:
    with st.expander("🍔 View Today's Meals"):
        for food in st.session_state.logged_foods:
            st.write(f"- {food}")

st.divider()

# --- FOOD SEARCH TABS ---
st.subheader("🔍 Precision Food Search")
tab1, tab2, tab3 = st.tabs(["🇺🇸 USDA Database", "🇮🇳 Indian Foods (Local DB)", "📷 Barcode Scan"])

with tab1:
    search_query = st.text_input("Search USDA (e.g., 'Raw Chicken Breast')")
    if st.button("Search USDA") and search_query:
        url = f"https://api.nal.usda.gov/fdc/v1/foods/search?api_key={USDA_API_KEY}&query={search_query}&pageSize=5"
        with st.spinner("Searching USDA..."):
            try:
                response = requests.get(url)
                data = response.json()
                if "foods" in data and len(data["foods"]) > 0:
                    for food in data["foods"]:
                        desc = food.get("description", "Unknown Food").title()
                        brand = food.get("brandOwner", "Generic")
                        
                        base_cals, base_prot, base_fat, base_carbs = 0, 0, 0, 0
                        for nutrient in food.get("foodNutrients", []):
                            name = nutrient.get("nutrientName", "").lower()
                            val = nutrient.get("value", 0)
                            if "energy" in name and "kcal" in nutrient.get("unitName", "").lower(): base_cals = val
                            elif "protein" in name: base_prot = val
                            elif "total lipid (fat)" in name or name == "fat": base_fat = val
                            elif "carbohydrate" in name: base_carbs = val
                        
                        with st.expander(f"🍽️ {desc} ({brand})"):
                            serving_grams = st.number_input(f"Amount consumed (grams)", min_value=1, value=100, key=f"usda_{food['fdcId']}")
                            multiplier = serving_grams / 100.0
                            
                            adj_cals = round(base_cals * multiplier)
                            adj_prot = round(base_prot * multiplier)
                            adj_fat = round(base_fat * multiplier)
                            adj_carb = round(base_carbs * multiplier)
                            
                            c1, c2, c3, c4 = st.columns(4)
                            c1.metric("Calories", f"{adj_cals} kcal")
                            c2.metric("Protein", f"{adj_prot} g")
                            c3.metric("Fats", f"{adj_fat} g")
                            c4.metric("Carbs", f"{adj_carb} g")
                            
                            if st.button("Log this amount", key=f"log_usda_{food['fdcId']}"):
                                st.session_state.consumed_cals += adj_cals
                                st.session_state.consumed_prot += adj_prot
                                st.session_state.consumed_fat += adj_fat
                                st.session_state.consumed_carbs += adj_carb
                                st.session_state.logged_foods.append(f"{serving_grams}g of {desc} ({adj_cals} kcal)")
                                st.success(f"Logged! Dashboard updated.")
                                st.rerun()
                else:
                    st.warning("No foods found.")
            except Exception as e:
                st.error("API Error. Check your API key or connection.")

with tab2:
    indian_query = st.text_input("Search Local Indian DB (e.g., 'Dhansak' or 'Pork')")
    if indian_query:
        results = indian_df[indian_df["Food"].str.contains(indian_query, case=False)]
        
        if not results.empty:
            for index, row in results.iterrows():
                with st.expander(f"🇮🇳 {row['Food']}"):
                    serving_grams = st.number_input(f"Amount consumed (grams)", min_value=1, value=100, key=f"ind_{index}")
                    multiplier = serving_grams / 100.0
                    
                    adj_cals = round(row["Calories"] * multiplier)
                    adj_prot = round(row["Protein"] * multiplier)
                    adj_fat = round(row["Fats"] * multiplier)
                    adj_carb = round(row["Carbs"] * multiplier)
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Calories", f"{adj_cals} kcal")
                    c2.metric("Protein", f"{adj_prot} g")
                    c3.metric("Fats", f"{adj_fat} g")
                    c4.metric("Carbs", f"{adj_carb} g")
                    
                    if st.button("Log this amount", key=f"log_ind_{index}"):
                        st.session_state.consumed_cals += adj_cals
                        st.session_state.consumed_prot += adj_prot
                        st.session_state.consumed_fat += adj_fat
                        st.session_state.consumed_carbs += adj_carb
                        st.session_state.logged_foods.append(f"{serving_grams}g of {row['Food']} ({adj_cals} kcal)")
                        st.success(f"Logged! Dashboard updated.")
                        st.rerun()
        else:
            st.warning("Not found in local DB. Try a different spelling.")

with tab3:
    st.write("Scan a packaged food barcode (powered by Open Food Facts).")
    
    barcode_to_search = ""
    manual_barcode = st.text_input("Type Barcode Number manually (if camera fails):")
    if manual_barcode:
        barcode_to_search = manual_barcode
        
    camera_photo = st.camera_input("Take a picture of the barcode")
    
    if camera_photo is not None:
        try:
            from pyzbar.pyzbar import decode
            from PIL import Image
            img = Image.open(camera_photo)
            decoded = decode(img)
            
            if decoded:
                barcode_to_search = decoded[0].data.decode("utf-8")
                st.success(f"Barcode detected: {barcode_to_search}")
            else:
                st.error("Could not read barcode. Try moving closer or type it manually.")
        except ImportError:
            st.error("⚠️ System missing pyzbar. Ensure you added it to requirements.txt and libzbar0 to packages.txt.")

    if st.button("Lookup Packaged Food") and barcode_to_search:
        off_url = f"https://world.openfoodfacts.org/api/v0/product/{barcode_to_search}.json"
        with st.spinner("Fetching packaged food data..."):
            try:
                off_res = requests.get(off_url).json()
                if off_res.get("status") == 1:
                    product = off_res["product"]
                    brand = product.get("brands", "Unknown Brand")
                    name = product.get("product_name", "Unknown Product")
                    nutriments = product.get("nutriments", {})
                    
                    base_cals = nutriments.get("energy-kcal_100g", 0)
                    base_prot = nutriments.get("proteins_100g", 0)
                    base_fat = nutriments.get("fat_100g", 0)
                    base_carbs = nutriments.get("carbohydrates_100g", 0)
                    
                    if base_cals == 0 and base_prot == 0:
                        st.warning("Product found, but macro data is missing in the database.")
                    else:
                        with st.expander(f"📦 {name} ({brand})"):
                            serving_grams = st.number_input("Amount consumed (grams/ml)", min_value=1, value=100, key=f"off_{barcode_to_search}")
                            multiplier = serving_grams / 100.0
                            
                            adj_cals = round(base_cals * multiplier)
                            adj_prot = round(base_prot * multiplier)
                            adj_fat = round(base_fat * multiplier)
                            adj_carb = round(base_carbs * multiplier)
                            
                            c1, c2, c3, c4 = st.columns(4)
                            c1.metric("Calories", f"{adj_cals} kcal")
                            c2.metric("Protein", f"{adj_prot} g")
                            c3.metric("Fats", f"{adj_fat} g")
                            c4.metric("Carbs", f"{adj_carb} g")
                            
                            if st.button("Log this amount", key=f"log_off_{barcode_to_search}"):
                                st.session_state.consumed_cals += adj_cals
                                st.session_state.consumed_prot += adj_prot
                                st.session_state.consumed_fat += adj_fat
                                st.session_state.consumed_carbs += adj_carb
                                st.session_state.logged_foods.append(f"{serving_grams}g of {name} ({adj_cals} kcal)")
                                st.success("Logged! Dashboard updated.")
                                st.rerun()
                else:
                    st.warning("Product not found in Open Food Facts database.")
            except Exception as e:
                st.error("API Error connecting to Open Food Facts.")

st.divider()

# --- LIFTING LOG & GRAPHING ---
st.subheader("🏋️ Lifting Log & Analytics")

with st.expander("Add New Set"):
    exercise = st.text_input("Exercise Name (e.g., Bench Press)")
    weight_lifted = st.number_input("Weight (kg)", 0.0)
    reps = st.number_input("Reps", 0)
    if st.button("Save Set"):
        new_set = pd.DataFrame([{
            "Date": pd.to_datetime(datetime.today().date()), 
            "Exercise": exercise.title(), 
            "Weight": weight_lifted, 
            "Reps": reps
        }])
        st.session_state.workout_history = pd.concat([st.session_state.workout_history, new_set], ignore_index=True)
        st.success(f"Saved {exercise}: {weight_lifted}kg x {reps}")

if not st.session_state.workout_history.empty:
    st.write("📈 **Strength Progression**")
    exercises_logged = st.session_state.workout_history["Exercise"].unique()
    selected_ex = st.selectbox("Select exercise to graph:", exercises_logged)
    
    ex_data = st.session_state.workout_history[st.session_state.workout_history["Exercise"] == selected_ex]
    max_weight_per_day = ex_data.groupby("Date")["Weight"].max().reset_index()
    
    max_weight_per_day.set_index("Date", inplace=True)
    st.line_chart(max_weight_per_day, y="Weight")

    st.write("💪 **Estimated 1-Rep Max (1RM)**")
    recent_sets = st.session_state.workout_history.sort_values(by=["Date", "Weight"], ascending=[False, False]).drop_duplicates(subset=["Exercise"])
    
    c1, c2 = st.columns(2)
    for index, row in recent_sets.iterrows():
        estimated_1rm = round(row["Weight"] * (1 + (row["Reps"] / 30.0)), 1)
        st.info(f"**{row['Exercise']}**: {estimated_1rm} kg *(from {row['Weight']}kg x {row['Reps']})*")
