import json
import re
from datetime import datetime
import streamlit as st
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
        st.error("Food database not found. Please upload ciqual_2020_foods.json.")
        return [], {}

foods, search_index = load_food_database()

# ----------------------------
# 2. User database
# ----------------------------
USERS_FILE = "nutrition_users.json"

def load_users():
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        st.warning(f"Could not load users: {e}")
    return {}

def save_users(users):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Error saving users: {e}")
        return False

users = load_users()
active_user = None

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
            food_name = re.sub(r'^\s*(?:of|with|\-)\s*', '', food_name).strip()
        else:
            weight = 100
            food_name = part
        food_name = normalize_food_input(food_name)
        if food_name:
            ingredients.append({"name": food_name, "weight": weight})
    return ingredients

def is_basic_ingredient(food):
    food_name = food["names"]["en"].lower()
    complex_indicators = [
        ",", "(", ")", "with", "and", "or", 
        "prepared", "canned", "mix", "salad", "soup", "sauce", 
        "dish", "recipe", "meal", "dinner", "lunch", "breakfast",
        "cooked", "boiled", "fried", "grilled", "roasted", "baked", "steamed",
        "sandwich", "burger", "pizza", "pasta", "stew", "curry", "stir-fry",
        "casserole", "marinated", "breaded", "coated", "stuffed"
    ]
    for indicator in complex_indicators:
        if indicator in food_name:
            return False
    main_ingredients = ["chicken", "beef", "pork", "fish", "rice", "pasta", "potato", "vegetable", "fruit", "cheese"]
    found_count = sum(1 for ing in main_ingredients if ing in food_name)
    if found_count > 1:
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
    if user["gender"] == "male":
        return 10*user["weight"] + 6.25*user["height"] - 5*user["age"] + 5
    else:
        return 10*user["weight"] + 6.25*user["height"] - 5*user["age"] - 161

def calculate_tdee(user):
    factors = {"sedentary":1.2, "light":1.375, "moderate":1.55, "active":1.725, "very active":1.9}
    return calculate_bmr(user)*factors[user["activity"]]

def daily_calories(user):
    base = calculate_tdee(user)
    if user["goal"] == "lose":
        return base-500
    elif user["goal"] == "gain":
        return base+500
    return base

# ----------------------------
# 4. Streamlit UI
# ----------------------------
st.title("🍎 Smart Nutrition Tracker")

menu = ["Home", "Create/Switch User", "Log Food", "Daily Summary", "Show Profile"]
choice = st.sidebar.selectbox("Menu", menu)

# Create/Switch User
if choice == "Create/Switch User":
    username = st.text_input("Enter username")
    if st.button("Select/Create User"):
        if not username:
            st.warning("Enter a valid username")
        elif username in users:
            active_user = users[username]
            st.success(f"Switched to existing user → {username}")
        else:
            age = st.number_input("Age", 15, 100, 25)
            gender = st.selectbox("Gender", ["male", "female"])
            weight = st.number_input("Weight (kg)", 30, 300, 70)
            height = st.number_input("Height (cm)", 100, 250, 170)
            goal = st.selectbox("Goal", ["lose", "maintain", "gain"])
            activity = st.selectbox("Activity level", ["sedentary", "light", "moderate", "active", "very active"])
            active_user = {
                "name": username, "age": age, "gender": gender, "weight": weight,
                "height": height, "goal": goal, "activity": activity, "logs": [],
                "created_at": datetime.now().isoformat()
            }
            users[username] = active_user
            save_users(users)
            st.success(f"User {username} created!")

# Log Food
if choice == "Log Food":
    if not active_user:
        st.warning("Please create/select a user first.")
    else:
        meal_input = st.text_input("Enter what you ate (e.g., '150g chicken and 50g rice')")
        if st.button("Log Meal") and meal_input:
            ingredients = improve_ingredient_parsing(meal_input)
            total_cal = total_pro = total_carbs = total_fat = 0
            meal_logs = []
            for ing in ingredients:
                matches = find_basic_ingredients(ing["name"])
                if not matches:
                    st.warning(f"No basic ingredients found for '{ing['name']}'")
                    continue
                selected_food = matches[0]
                ratio = ing["weight"]/100
                cal = selected_food["nutrition"]["calories"]*ratio
                pro = selected_food["nutrition"]["protein"]*ratio
                carbs = selected_food["nutrition"]["carbs"]*ratio
                fat = selected_food["nutrition"]["fat"]*ratio
                total_cal += cal
                total_pro += pro
                total_carbs += carbs
                total_fat += fat
                meal_logs.append({"food": selected_food["names"]["en"], "grams": ing["weight"], "nutrition": {"calories":round(cal,1),"protein":round(pro,1),"carbs":round(carbs,1),"fat":round(fat,1)}, "timestamp":datetime.now().isoformat()})
            active_user["logs"].extend(meal_logs)
            save_users(users)
            st.success("Meal logged!")
            st.write("Total Calories:", round(total_cal,1))
            st.write("Protein:", round(total_pro,1), "g")
            st.write("Carbs:", round(total_carbs,1), "g")
            st.write("Fat:", round(total_fat,1), "g")

# Daily Summary
if choice == "Daily Summary":
    if not active_user:
        st.warning("Please create/select a user first.")
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        logs = [x for x in active_user["logs"] if x["timestamp"].startswith(today)]
        if not logs:
            st.info("No food logged today")
        else:
            total_cal = sum(x["nutrition"]["calories"] for x in logs)
            target_cal = daily_calories(active_user)
            st.write("🔥 Calories:", round(total_cal,1), "/", round(target_cal,1))
            st.write("💪 Protein:", round(sum(x["nutrition"]["protein"] for x in logs),1))
            st.write("🥖 Carbs:", round(sum(x["nutrition"]["carbs"] for x in logs),1))
            st.write("🥑 Fat:", round(sum(x["nutrition"]["fat"] for x in logs),1))

# Show Profile
if choice == "Show Profile":
    if not active_user:
        st.warning("Please create/select a user first.")
    else:
        st.subheader(f"Profile: {active_user['name']}")
        st.write(active_user)
