import streamlit as st
import json
from datetime import datetime
import re
import os

# ----------------------------
# 1. Load food database
# ----------------------------
@st.cache_data
def load_food_database():
    try:
        with open("ciqual_2020_foods.json", "r", encoding="utf-8") as f:
            foods = json.load(f)
        search_index = {food["names"]["en"].lower().strip(): food for food in foods}
        return foods, search_index
    except FileNotFoundError:
        st.error("❌ Food database not found. Please upload ciqual_2020_foods.json")
        return [], {}

foods, search_index = load_food_database()

# ----------------------------
# 2. User persistence
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

# Initialize session state
if "users" not in st.session_state:
    st.session_state.users = load_users()
if "active_user" not in st.session_state:
    st.session_state.active_user = None

# ----------------------------
# 3. Helper functions
# ----------------------------
def normalize_food_input(text):
    COOKING_WORDS = ["grilled", "roasted", "baked", "steamed", "fried", "cooked", "boiled", "raw", "fresh"]
    text = text.lower().strip()
    for word in COOKING_WORDS:
        text = re.sub(r'\b' + word + r'\b', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def improve_ingredient_parsing(meal_input):
    ingredients = []
    parts = re.split(r'\band\b|,|\+', meal_input)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        weight_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:g|grams?)\b', part, re.IGNORECASE)
        if weight_match:
            weight = float(weight_match.group(1))
            food_name = re.sub(r'(\d+(?:\.\d+)?)\s*(?:g|grams?)\b', '', part).strip()
        else:
            weight = 100
            food_name = part
        food_name = normalize_food_input(food_name)
        if food_name:
            ingredients.append({"name": food_name, "weight": weight})
    return ingredients

def is_basic_ingredient(food):
    food_name = food["names"]["en"].lower()
    complex_indicators = [",", "(", ")", "with", "and", "or", "prepared", "canned",
                          "mix", "salad", "soup", "sauce", "dish", "recipe", "meal",
                          "cooked", "fried", "grilled", "roasted", "baked", "steamed",
                          "pizza", "pasta", "stew", "curry", "breaded"]
    for indicator in complex_indicators:
        if indicator in food_name:
            return False
    return True

def find_basic_ingredients(name):
    name = normalize_food_input(name)
    exact_basic_matches = []
    partial_basic_matches = []
    complex_matches = []
    for food in foods:
        food_name = food["names"]["en"].lower()
        is_basic = is_basic_ingredient(food)
        if name == food_name and is_basic:
            exact_basic_matches.append(food)
        elif is_basic and (food_name.startswith(name + " ") or food_name.endswith(" " + name)):
            partial_basic_matches.append(food)
        elif not exact_basic_matches and not partial_basic_matches:
            if name in food_name:
                complex_matches.append(food)
    all_matches = exact_basic_matches + partial_basic_matches
    if all_matches:
        return all_matches[:5]
    if complex_matches:
        return complex_matches[:2]
    return []

def calculate_bmr(user):
    weight, height, age = user["weight"], user["height"], user["age"]
    if user["gender"] == "male":
        return 10 * weight + 6.25 * height - 5 * age + 5
    else:
        return 10 * weight + 6.25 * height - 5 * age - 161

def calculate_tdee(user):
    factors = {"sedentary":1.2, "light":1.375, "moderate":1.55, "active":1.725, "very active":1.9}
    return calculate_bmr(user) * factors[user["activity"]]

def daily_calories(user):
    base = calculate_tdee(user)
    if user["goal"] == "lose": return base - 500
    elif user["goal"] == "gain": return base + 500
    return base

# ----------------------------
# 4. Streamlit UI
# ----------------------------
st.title("🍎 Smart Nutrition Tracker")
st.markdown("**Your personal food companion for healthier choices!**")
st.markdown("---")
st.markdown("💡 **Health Tip:** Drink at least 2 liters of water per day, include colorful vegetables, and balance your macros.")

st.subheader("Main Menu")
menu_options = ["Create / Switch User", "Log Food", "Daily Summary", "Show Profile"]
for option in menu_options:
    if st.button(option):
        st.session_state.selected_menu = option

# Initialize selected_menu
if "selected_menu" not in st.session_state:
    st.session_state.selected_menu = None

# ----------------------------
# 5. Menu functions
# ----------------------------
def create_or_switch_user():
    st.subheader("👤 Create / Switch User")
    username = st.text_input("Enter username")
    if username:
        if username in st.session_state.users:
            st.session_state.active_user = st.session_state.users[username]
            st.success(f"✨ Switched to existing user: {username}")
        else:
            age = st.number_input("Age", 15, 100, 25)
            gender = st.selectbox("Gender", ["male", "female"])
            weight = st.number_input("Weight (kg)", 30, 300, 70)
            height = st.number_input("Height (cm)", 100, 250, 170)
            goal = st.selectbox("Goal", ["lose", "maintain", "gain"])
            activity = st.selectbox("Activity level", ["sedentary","light","moderate","active","very active"])
            if st.button("Create User"):
                user = {"name":username,"age":age,"gender":gender,"weight":weight,
                        "height":height,"goal":goal,"activity":activity,"logs":[],"created_at":datetime.now().isoformat()}
                st.session_state.users[username] = user
                st.session_state.active_user = user
                save_users(st.session_state.users)
                st.success(f"✨ User {username} created and active!")

def log_food():
    if not st.session_state.active_user:
        st.warning("❌ No active user. Please create or switch user first.")
        return
    st.subheader("🍽️ Log Food (Basic Ingredients Only)")
    meal_input = st.text_input("Enter food items (e.g., '150g chicken, 50g rice')")
    if st.button("Log Meal"):
        ingredients = improve_ingredient_parsing(meal_input)
        if not ingredients:
            st.warning("❌ No valid ingredients found.")
            return
        total_cal = total_pro = total_carbs = total_fat = 0
        for ing in ingredients:
            matches = find_basic_ingredients(ing["name"])
            if not matches:
                st.info(f"❌ No matches for {ing['name']}, skipped.")
                continue
            selected = matches[0]
            ratio = ing["weight"]/100
            cal = selected["nutrition"]["calories"]*ratio
            pro = selected["nutrition"]["protein"]*ratio
            carbs = selected["nutrition"]["carbs"]*ratio
            fat = selected["nutrition"]["fat"]*ratio
            total_cal += cal
            total_pro += pro
            total_carbs += carbs
            total_fat += fat
            st.session_state.active_user["logs"].append({
                "food": selected["names"]["en"],
                "food_id": selected["id"],
                "grams": ing["weight"],
                "nutrition":{"calories":round(cal,1),"protein":round(pro,1),"carbs":round(carbs,1),"fat":round(fat,1)},
                "timestamp": datetime.now().isoformat()
            })
        save_users(st.session_state.users)
        st.success(f"✅ Meal logged! Calories: {total_cal:.1f}, Protein: {total_pro:.1f}g")

def daily_summary():
    if not st.session_state.active_user:
        st.warning("❌ No active user. Please create or switch user first.")
        return
    st.subheader("📊 Daily Summary")
    today = datetime.now().strftime("%Y-%m-%d")
    logs = [x for x in st.session_state.active_user["logs"] if x["timestamp"].startswith(today)]
    if not logs:
        st.info("📋 No food logged today.")
        return
    total_cal = sum(x["nutrition"]["calories"] for x in logs)
    total_pro = sum(x["nutrition"]["protein"] for x in logs)
    total_carbs = sum(x["nutrition"]["carbs"] for x in logs)
    total_fat = sum(x["nutrition"]["fat"] for x in logs)
    target_cal = daily_calories(st.session_state.active_user)
    st.write(f"🔥 Calories: {total_cal:.1f} / {target_cal:.1f} kcal")
    st.write(f"💪 Protein: {total_pro:.1f} g")
    st.write(f"🥖 Carbs: {total_carbs:.1f} g")
    st.write(f"🥑 Fat: {total_fat:.1f} g")

def show_profile():
    if not st.session_state.active_user:
        st.warning("❌ No active user. Please create or switch user first.")
        return
    user = st.session_state.active_user
    st.subheader("👤 Profile")
    st.write(f"**Name:** {user['name']}")
    st.write(f"**Age:** {user['age']} years")
    st.write(f"**Gender:** {user['gender']}")
    st.write(f"**Weight:** {user['weight']} kg")
    st.write(f"**Height:** {user['height']} cm")
    st.write(f"**Goal:** {user['goal']}")
    st.write(f"**Activity:** {user['activity']}")

# ----------------------------
# 6. Display selected menu
# ----------------------------
if st.session_state.selected_menu == "Create / Switch User":
    create_or_switch_user()
elif st.session_state.selected_menu == "Log Food":
    log_food()
elif st.session_state.selected_menu == "Daily Summary":
    daily_summary()
elif st.session_state.selected_menu == "Show Profile":
    show_profile()
