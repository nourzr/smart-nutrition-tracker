import json
import streamlit as st
from datetime import datetime
import re
import os

# ----------------------------
# Load food database
# ----------------------------
@st.cache_data
def load_food_database():
    with open("ciqual_2020_foods.json", "r", encoding="utf-8") as f:
        foods = json.load(f)
    search_index = {food["names"]["en"].lower(): food for food in foods}
    return foods, search_index

foods, search_index = load_food_database()

# ----------------------------
# Load / save users
# ----------------------------
USERS_FILE = "nutrition_users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

users = load_users()

# ----------------------------
# Streamlit session state
# ----------------------------
if "active_user" not in st.session_state:
    st.session_state.active_user = None
if "menu_choice" not in st.session_state:
    st.session_state.menu_choice = "home"

# ----------------------------
# Helper functions
# ----------------------------
COOKING_WORDS = ["grilled", "roasted", "baked", "steamed", "fried", "cooked", "boiled", "raw", "fresh"]

def normalize_food_input(text):
    text = text.lower().strip()
    for word in COOKING_WORDS:
        text = re.sub(r'\b' + word + r'\b', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def find_basic_ingredients(name):
    name = normalize_food_input(name)
    matches = []
    for food in foods:
        food_name = food["names"]["en"].lower()
        if name in food_name:
            matches.append(food)
    return matches[:5]

def calculate_bmr(user):
    w, h, age = user["weight"], user["height"], user["age"]
    if user["gender"]=="male":
        return 10*w + 6.25*h - 5*age + 5
    else:
        return 10*w + 6.25*h - 5*age - 161

def calculate_tdee(user):
    factors = {"sedentary":1.2,"light":1.375,"moderate":1.55,"active":1.725,"very active":1.9}
    return calculate_bmr(user) * factors[user["activity"]]

def daily_calories(user):
    base = calculate_tdee(user)
    if user["goal"]=="lose": return base-500
    if user["goal"]=="gain": return base+500
    return base

def log_food_step():
    st.subheader("🍽️ Log Food (Basic Ingredients Only)")
    food_input = st.text_input("Type a food name:")
    if food_input:
        matches = find_basic_ingredients(food_input)
        if not matches:
            st.warning("No basic ingredient found. Try more specific terms.")
            return
        # Select ingredient
        names = [f"{f['names']['en']} ({f['nutrition']['calories']} kcal / 100g)" for f in matches]
        choice = st.selectbox("Select the ingredient:", names)
        selected_food = matches[names.index(choice)]
        grams = st.number_input("Enter grams:", min_value=1.0, value=100.0)
        if st.button("Log this food"):
            ratio = grams / 100
            log_entry = {
                "food": selected_food["names"]["en"],
                "food_id": selected_food["id"],
                "grams": grams,
                "nutrition": {
                    "calories": round(selected_food["nutrition"]["calories"]*ratio,1),
                    "protein": round(selected_food["nutrition"]["protein"]*ratio,1),
                    "carbs": round(selected_food["nutrition"]["carbs"]*ratio,1),
                    "fat": round(selected_food["nutrition"]["fat"]*ratio,1)
                },
                "timestamp": datetime.now().isoformat()
            }
            st.session_state.active_user["logs"].append(log_entry)
            save_users(users)
            st.success(f"Logged {selected_food['names']['en']} ({grams}g)")

def daily_summary():
    st.subheader("📊 Daily Summary")
    today = datetime.now().strftime("%Y-%m-%d")
    logs = [x for x in st.session_state.active_user["logs"] if x["timestamp"].startswith(today)]
    if not logs:
        st.info("No food logged today.")
        return
    total_cal = sum(x["nutrition"]["calories"] for x in logs)
    total_pro = sum(x["nutrition"]["protein"] for x in logs)
    total_carbs = sum(x["nutrition"]["carbs"] for x in logs)
    total_fat = sum(x["nutrition"]["fat"] for x in logs)
    target_cal = daily_calories(st.session_state.active_user)
    st.metric("Calories", f"{total_cal} / {round(target_cal)} kcal")
    st.metric("Protein", f"{total_pro} g")
    st.metric("Carbs", f"{total_carbs} g")
    st.metric("Fat", f"{total_fat} g")
    st.progress(min(100,total_cal/target_cal*100))

def create_or_switch_user():
    st.subheader("👤 Create / Switch User")
    username = st.text_input("Enter username:")
    if username:
        if username in users:
            st.session_state.active_user = users[username]
            st.success(f"Switched to existing user → {username}")
        else:
            age = st.number_input("Age:", min_value=15, max_value=100)
            gender = st.selectbox("Gender:", ["male","female"])
            weight = st.number_input("Weight (kg):", min_value=30.0, max_value=300.0)
            height = st.number_input("Height (cm):", min_value=100.0, max_value=250.0)
            goal = st.selectbox("Goal:", ["lose","maintain","gain"])
            activity = st.selectbox("Activity level:", ["sedentary","light","moderate","active","very active"])
            if st.button("Create user"):
                user = {"name":username,"age":age,"gender":gender,"weight":weight,"height":height,
                        "goal":goal,"activity":activity,"logs":[],"created_at":datetime.now().isoformat()}
                users[username] = user
                st.session_state.active_user = user
                save_users(users)
                st.success(f"Created user → {username}")

def show_user_summary():
    st.subheader("👤 User Profile")
    user = st.session_state.active_user
    st.write(f"**Name:** {user['name']}  |  **Age:** {user['age']}  |  **Gender:** {user['gender']}")
    st.write(f"**Weight:** {user['weight']} kg  |  **Height:** {user['height']} cm")
    st.write(f"**Goal:** {user['goal']}  |  **Activity:** {user['activity']}")
    daily_summary()

# ----------------------------
# Main page layout
# ----------------------------
st.title("🍎 Smart Nutrition Tracker")
st.markdown("**Stay healthy, log your meals, and track your progress!**")
st.markdown("---")
st.markdown("### Menu")
menu = ["Home","List Users","Switch/Create User","Log Food","Daily Summary","Profile","Delete User"]
choice = st.radio("Select an option:", menu)
st.session_state.menu_choice = choice

if st.session_state.menu_choice == "Home":
    st.subheader("💡 Health Tip of the Day")
    st.info("Drink at least 8 glasses of water and include protein in every meal.")
elif st.session_state.menu_choice == "List Users":
    st.subheader("👥 Registered Users")
    if users:
        for u, data in users.items():
            st.write(f"{u} | Age: {data['age']} | Weight: {data['weight']} kg | Logs: {len(data['logs'])}")
    else:
        st.info("No users yet. Create one!")
elif st.session_state.menu_choice == "Switch/Create User":
    create_or_switch_user()
elif st.session_state.menu_choice == "Log Food":
    if not st.session_state.active_user:
        st.warning("❌ No active user. Please switch/create a user first.")
    else:
        log_food_step()
elif st.session_state.menu_choice == "Daily Summary":
    if not st.session_state.active_user:
        st.warning("❌ No active user. Please switch/create a user first.")
    else:
        daily_summary()
elif st.session_state.menu_choice == "Profile":
    if not st.session_state.active_user:
        st.warning("❌ No active user. Please switch/create a user first.")
    else:
        show_user_summary()
elif st.session_state.menu_choice == "Delete User":
    st.subheader("🗑️ Delete User")
    user_to_delete = st.selectbox("Select user to delete:", list(users.keys()))
    if st.button("Delete"):
        del users[user_to_delete]
        save_users(users)
        st.success(f"Deleted {user_to_delete}")
        if st.session_state.active_user and st.session_state.active_user["name"]==user_to_delete:
            st.session_state.active_user=None
