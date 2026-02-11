import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# PAGE CONFIG
st.set_page_config(page_title="My Private Tracker", layout="wide")

# --- USDA API CONFIG ---
USDA_API_KEY = "YOUR_API_KEY_HERE"  # <--- PASTE YOUR ACTUAL USDA API KEY HERE

# --- SESSION STATE INITIALIZATION (PERMANENT DATABASES) ---
if "food_history" not in st.session_state:
    st.session_state.food_history = pd.DataFrame(columns=["Date", "Food_Name", "Calories", "Protein", "Fat", "Carbs"])

if "workout_history" not in st.session_state: 
    dummy_data = pd.DataFrame({
        "Date": [pd.to_datetime("2026-01-15").date(), pd.to_datetime("2026-01-22").date()],
        "Exercise": ["Bench Press", "Bench Press"],
        "Weight": [50.0, 55.0],
        "Reps": [8, 8]
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
    daily_deficit = (total_kg_to_lose * 7700) / (months * 30) if months > 0 else 0
    target_cal = tdee - daily_deficit
    protein = weight * 2.2
    fats = (target_cal * 0.25) / 9
    carbs = (target_cal - (protein * 4) - (fats * 9)) / 4
    return round(target_cal), round(protein), round(fats), round(carbs)

# --- GLOBAL DATE SELECTOR ---
col_title, col_date = st.columns([3, 1])
with col_title:
    st.title("🚀 Health & Lift Tracker")
with col_date:
    active_date = st.date_input("📅 Select Date to View/Log", datetime.today().date())

# --- SIDEBAR NAVIGATION & SETTINGS ---
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["📊 Dashboard", "🍎 Log Food", "🏋️ Log Workout", "⚙️ Settings & Data"])

# We calculate targets globally so the dashboard always has them
w = st.sidebar.number_input("Weight (kg)", 40.0, 200.0, 75.0, key="w_set")
h = st.sidebar.number_input("Height (cm)", 100.0, 250.0, 175.0, key="h_set")
age = st.sidebar.number_input("Age", 10, 100, 17, key="age_set")
gender = st.sidebar.selectbox("Gender", ["Male", "Female"], key="g_set")
gw = st.sidebar.number_input("Goal Weight (kg)", 40.0, 200.0, 65.0, key="gw_set")
m = st.sidebar.number_input("Months to Goal", 1, 12, 4, key="m_set")

cal_target, prot_target, fat_target, carb_target = calculate_metrics(w, h, age, gender, gw, m)

# Get today's consumed macros based on the active_date
daily_food = st.session_state.food_history[st.session_state.food_history["Date"] == active_date]
consumed_cals = daily_food["Calories"].sum()
consumed_prot = daily_food["Protein"].sum()
consumed_fat = daily_food["Fat"].sum()
consumed_carbs = daily_food["Carbs"].sum()

rem_cal = cal_target - consumed_cals
rem_prot = prot_target - consumed_prot
rem_fat = fat_target - consumed_fat
rem_carb = carb_target - consumed_carbs

# ==========================================
# PAGE 1: DASHBOARD
# ==========================================
if page == "📊 Dashboard":
    st.subheader(f"📊 Macros for {active_date.strftime('%b %d, %Y')}")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Calories", f"{rem_cal} kcal", f"Target: {cal_target}", delta_color="off")
    col2.metric("Protein", f"{rem_prot} g", f"Target: {prot_target}", delta_color="off")
    col3.metric("Fats", f"{rem_fat} g", f"Target: {fat_target}", delta_color="off")
    col4.metric("Carbs", f"{rem_carb} g", f"Target: {carb_target}", delta_color="off")

    st.divider()
    
    st.subheader("🍔 Meals Logged on this Date")
    if not daily_food.empty:
        for idx, row in daily_food.iterrows():
            c1, c2 = st.columns([5, 1])
            c1.write(f"**{row['Food_Name']}** — {row['Calories']} kcal (P: {row['Protein']}g | F: {row['Fat']}g | C: {row['Carbs']}g)")
            if c2.button("❌ Remove", key=f"del_food_{idx}"):
                st.session_state.food_history = st.session_state.food_history.drop(idx)
                st.rerun()
    else:
        st.info("No food logged for this date yet.")

# ==========================================
# PAGE 2: FOOD LOGGER
# ==========================================
elif page == "🍎 Log Food":
    st.subheader(f"🔍 Search & Log Food for {active_date.strftime('%b %d')}")
    tab1, tab2, tab3 = st.tabs(["🇺🇸 USDA Database", "🇮🇳 Indian Foods (Local DB)", "📷 Barcode Scan"])

    def add_to_food_history(cals, prot, fat, carbs, display_text):
        new_entry = pd.DataFrame([{
            "Date": active_date,
            "Food_Name": display_text,
            "Calories": cals,
            "Protein": prot,
            "Fat": fat,
            "Carbs": carbs
        }])
        st.session_state.food_history = pd.concat([st.session_state.food_history, new_entry], ignore_index=True)

    with tab1:
        search_query = st.text_input("Search USDA (e.g., 'Raw Chicken Breast')")
        if search_query:
            url = f"https://api.nal.usda.gov/fdc/v1/foods/search?api_key={USDA_API_KEY}&query={search_query}&pageSize=5"
            try:
                data = requests.get(url).json()
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
                            adj_cals, adj_prot, adj_fat, adj_carb = round(base_cals * multiplier), round(base_prot * multiplier), round(base_fat * multiplier), round(base_carbs * multiplier)
                            
                            c1, c2, c3, c4 = st.columns(4)
                            c1.metric("Calories", f"{adj_cals} kcal")
                            c2.metric("Protein", f"{adj_prot} g")
                            
                            if st.button("Log this amount", key=f"log_usda_{food['fdcId']}"):
                                add_to_food_history(adj_cals, adj_prot, adj_fat, adj_carb, f"{serving_grams}g of {desc}")
                                st.success(f"Logged to {active_date}!")
                else:
                    st.warning("No foods found.")
            except Exception:
                st.error("API Error. Check your API key.")

    with tab2:
        indian_query = st.text_input("Search Local Indian DB (e.g., 'Dhansak' or 'Pork')")
        if indian_query:
            results = indian_df[indian_df["Food"].str.contains(indian_query, case=False)]
            if not results.empty:
                for index, row in results.iterrows():
                    with st.expander(f"🇮🇳 {row['Food']}"):
                        serving_grams = st.number_input(f"Amount consumed (grams)", min_value=1, value=100, key=f"ind_{index}")
                        multiplier = serving_grams / 100.0
                        adj_cals, adj_prot, adj_fat, adj_carb = round(row["Calories"] * multiplier), round(row["Protein"] * multiplier), round(row["Fats"] * multiplier), round(row["Carbs"] * multiplier)
                        
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Calories", f"{adj_cals} kcal")
                        c2.metric("Protein", f"{adj_prot} g")
                        
                        if st.button("Log this amount", key=f"log_ind_{index}"):
                            add_to_food_history(adj_cals, adj_prot, adj_fat, adj_carb, f"{serving_grams}g of {row['Food']}")
                            st.success(f"Logged to {active_date}!")
            else:
                st.warning("Not found in local DB.")

    with tab3:
        st.write("Scan a packaged food barcode.")
        barcode_to_search = ""
        manual_barcode = st.text_input("Type Barcode Number manually:")
        if manual_barcode: barcode_to_search = manual_barcode
            
        camera_photo = st.camera_input("Take a picture of the barcode")
        if camera_photo is not None:
            try:
                from pyzbar.pyzbar import decode
                from PIL import Image
                decoded = decode(Image.open(camera_photo))
                if decoded:
                    barcode_to_search = decoded[0].data.decode("utf-8")
                    st.success(f"Barcode detected: {barcode_to_search}")
                else:
                    st.error("Could not read barcode.")
            except ImportError:
                st.error("⚠️ System missing pyzbar.")

        if barcode_to_search:
            off_url = f"https://world.openfoodfacts.org/api/v0/product/{barcode_to_search}.json"
            try:
                off_res = requests.get(off_url).json()
                if off_res.get("status") == 1:
                    product = off_res["product"]
                    name = product.get("product_name", "Unknown Product")
                    nutriments = product.get("nutriments", {})
                    base_cals = nutriments.get("energy-kcal_100g", 0)
                    base_prot = nutriments.get("proteins_100g", 0)
                    base_fat = nutriments.get("fat_100g", 0)
                    base_carbs = nutriments.get("carbohydrates_100g", 0)
                    
                    with st.expander(f"📦 {name}", expanded=True):
                        serving_grams = st.number_input("Amount (grams/ml)", min_value=1, value=100, key=f"off_{barcode_to_search}")
                        multiplier = serving_grams / 100.0
                        adj_cals, adj_prot, adj_fat, adj_carb = round(base_cals * multiplier), round(base_prot * multiplier), round(base_fat * multiplier), round(base_carbs * multiplier)
                        
                        c1, c2 = st.columns(2)
                        c1.metric("Calories", f"{adj_cals} kcal")
                        
                        if st.button("Log this amount", key=f"log_off_{barcode_to_search}"):
                            add_to_food_history(adj_cals, adj_prot, adj_fat, adj_carb, f"{serving_grams}g of {name}")
                            st.success(f"Logged to {active_date}!")
                else:
                    st.warning("Product not found.")
            except Exception:
                st.error("API Error.")

# ==========================================
# PAGE 3: WORKOUT LOGGER
# ==========================================
elif page == "🏋️ Log Workout":
    st.subheader(f"🏋️ Lifting Log for {active_date.strftime('%b %d')}")

    with st.expander("➕ Add New Set", expanded=True):
        exercise = st.text_input("Exercise Name (e.g., Bench Press)")
        weight_lifted = st.number_input("Weight (kg)", 0.0)
        reps = st.number_input("Reps", 0)
        if st.button("Save Set"):
            new_set = pd.DataFrame([{
                "Date": active_date, 
                "Exercise": exercise.title(), 
                "Weight": weight_lifted, 
                "Reps": reps
            }])
            st.session_state.workout_history = pd.concat([st.session_state.workout_history, new_set], ignore_index=True)
            st.success(f"Saved {exercise} to {active_date}!")

    if not st.session_state.workout_history.empty:
        st.write("📈 **Strength Progression**")
        exercises_logged = st.session_state.workout_history["Exercise"].unique()
        selected_ex = st.selectbox("Select exercise to graph:", exercises_logged)
        
        ex_data = st.session_state.workout_history[st.session_state.workout_history["Exercise"] == selected_ex].copy()
        # Convert to datetime for charting
        ex_data['Date'] = pd.to_datetime(ex_data['Date'])
        max_weight_per_day = ex_data.groupby("Date")["Weight"].max().reset_index()
        max_weight_per_day.set_index("Date", inplace=True)
        st.line_chart(max_weight_per_day, y="Weight")

        st.write("💪 **Estimated 1-Rep Max (1RM)**")
        recent_sets = st.session_state.workout_history.sort_values(by=["Date", "Weight"], ascending=[False, False]).drop_duplicates(subset=["Exercise"])
        for index, row in recent_sets.iterrows():
            estimated_1rm = round(row["Weight"] * (1 + (row["Reps"] / 30.0)), 1)
            st.info(f"**{row['Exercise']}**: {estimated_1rm} kg *(from {row['Weight']}kg x {row['Reps']})*")

        with st.expander("🗑️ Edit Workout History"):
            for idx, row in st.session_state.workout_history.tail(10).iterrows():
                col_a, col_b = st.columns([4, 1])
                col_a.write(f"{row['Date']} - **{row['Exercise']}**: {row['Weight']}kg x {row['Reps']}")
                if col_b.button("Delete", key=f"del_wo_{idx}"):
                    st.session_state.workout_history = st.session_state.workout_history.drop(idx)
                    st.rerun()

# ==========================================
# PAGE 4: SETTINGS & DATA
# ==========================================
elif page == "⚙️ Settings & Data":
    st.subheader("💾 Backup & Restore Your Data")
    st.write("Because this app runs securely in your browser without a backend server, download these files weekly to never lose your progress.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Food History Backup**")
        csv_food = st.session_state.food_history.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Download Food Backup", data=csv_food, file_name='my_food_backup.csv', mime='text/csv')
        
        uploaded_food = st.file_uploader("Restore Food History:", type="csv")
        if uploaded_food is not None:
            st.session_state.food_history = pd.read_csv(uploaded_food)
            st.session_state.food_history['Date'] = pd.to_datetime(st.session_state.food_history['Date']).dt.date
            st.success("Food History Restored!")

    with col2:
        st.write("**Workout History Backup**")
        csv_workout = st.session_state.workout_history.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Download Workout Backup", data=csv_workout, file_name='my_workout_backup.csv', mime='text/csv')
        
        uploaded_wo = st.file_uploader("Restore Workout History:", type="csv")
        if uploaded_wo is not None:
            st.session_state.workout_history = pd.read_csv(uploaded_wo)
            st.session_state.workout_history['Date'] = pd.to_datetime(st.session_state.workout_history['Date']).dt.date
            st.success("Workout History Restored!")
