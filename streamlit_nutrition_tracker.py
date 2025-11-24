import json
import streamlit as st
from datetime import datetime
import re
import os

# Page configuration
st.set_page_config(
    page_title="Smart Nutrition Tracker",
    page_icon="🍎",
    layout="wide"
)

# ----------------------------
# 1. Load food database
# ----------------------------
@st.cache_data
def load_food_database():
    """Load food database"""
    try:
        with open("ciqual_2020_foods.json", "r", encoding="utf-8") as f:
            foods = json.load(f)
        
        search_index = {}
        for food in foods:
            name_key = food["names"]["en"].lower().strip()
            search_index[name_key] = food
            
        return foods, search_index
    except FileNotFoundError:
        st.error("❌ Food database not found. Please make sure ciqual_2020_foods.json is uploaded.")
        return [], {}

# Load foods
foods, search_index = load_food_database()

# ----------------------------
# 2. User management with session state
# ----------------------------
if 'users' not in st.session_state:
    st.session_state.users = {}
if 'active_user' not in st.session_state:
    st.session_state.active_user = None
if 'show_create_user' not in st.session_state:
    st.session_state.show_create_user = False

# ----------------------------
# 3. Helper functions
# ----------------------------
def validate_user_data(user_data):
    """Validate user input ranges"""
    errors = []
    if not (15 <= user_data["age"] <= 100):
        errors.append("Age must be between 15-100")
    if not (30 <= user_data["weight"] <= 300):
        errors.append("Weight must be between 30-300 kg")
    if not (100 <= user_data["height"] <= 250):
        errors.append("Height must be between 100-250 cm")
    if user_data["gender"] not in ["male", "female"]:
        errors.append("Gender must be 'male' or 'female'")
    if user_data["goal"] not in ["lose", "maintain", "gain"]:
        errors.append("Goal must be 'lose', 'maintain', or 'gain'")
    if user_data["activity"] not in ["sedentary", "light", "moderate", "active", "very active"]:
        errors.append("Invalid activity level")
    return errors

def calculate_bmr(user):
    weight = user["weight"]
    height = user["height"]
    age = user["age"]
    if user["gender"] == "male":
        return 10 * weight + 6.25 * height - 5 * age + 5
    else:
        return 10 * weight + 6.25 * height - 5 * age - 161

def calculate_tdee(user):
    activity_factors = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very active": 1.9
    }
    return calculate_bmr(user) * activity_factors[user["activity"]]

def daily_calories(user):
    base = calculate_tdee(user)
    if user["goal"] == "lose":
        return base - 500
    elif user["goal"] == "gain":
        return base + 500
    return base

def normalize_food_input(text):
    """Clean and normalize food input"""
    COOKING_WORDS = ["grilled", "roasted", "baked", "steamed", "fried", "cooked", "boiled", "raw", "fresh"]
    text = text.lower().strip()
    for word in COOKING_WORDS:
        text = re.sub(r'\b' + word + r'\b', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def improve_ingredient_parsing(meal_input):
    """Better ingredient parsing that handles various formats"""
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
            ingredients.append({
                "name": food_name,
                "weight": weight
            })
    
    return ingredients

def is_basic_ingredient(food):
    """STRICT check if food is a basic ingredient"""
    food_name = food["names"]["en"].lower()
    
    complex_indicators = [
        ",", "(", ")", "with", "and", "or", 
        "prepared", "canned", "packed", "packaged", "prepacked", "prepackaged",
        "mix", "mixed", "salad", "soup", "sauce", "gravy", "broth", "stock",
        "dish", "recipe", "meal", "dinner", "lunch", "breakfast",
        "cooked", "boiled", "fried", "grilled", "roasted", "baked", "steamed",
        "w/", "with", "au", "à la", "style", "flavored", "seasoned",
        "sandwich", "burger", "pizza", "pasta", "stew", "curry", "stir-fry",
        "casserole", "marinated", "breaded", "coated", "stuffed",
        "meal", "dish", "plate", "serving", "portion"
    ]
    
    for indicator in complex_indicators:
        if indicator in food_name:
            return False
    
    main_ingredients = ["chicken", "beef", "pork", "fish", "rice", "pasta", "potato", "vegetable", "fruit", "cheese"]
    found_count = 0
    for ingredient in main_ingredients:
        if ingredient in food_name:
            found_count += 1
            if found_count > 1:
                return False
    
    return True

def find_basic_ingredients(name, category_groups=None):
    """STRICT food matching that ONLY shows basic ingredients"""
    name = normalize_food_input(name)
    
    if not name:
        return []
    
    exact_basic_matches = []
    partial_basic_matches = []
    complex_matches = []
    
    for food in foods:
        if category_groups and food["group"] not in category_groups:
            continue
            
        food_name = food["names"]["en"].lower()
        is_basic = is_basic_ingredient(food)
        
        if name == food_name and is_basic:
            exact_basic_matches.append(food)
        elif is_basic and (food_name.startswith(name + " ") or food_name.endswith(" " + name)):
            partial_basic_matches.append(food)
        elif is_basic and f" {name} " in f" {food_name} ":
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

def detect_food_category(name):
    """Strict category detection for basic ingredients"""
    name = name.lower()
    
    basic_categories = {
        "chicken": ["meat, egg and fish"],
        "beef": ["meat, egg and fish"], 
        "pork": ["meat, egg and fish"],
        "lamb": ["meat, egg and fish"],
        "turkey": ["meat, egg and fish"],
        "duck": ["meat, egg and fish"],
        "fish": ["meat, egg and fish"],
        "salmon": ["meat, egg and fish"],
        "tuna": ["meat, egg and fish"],
        "cod": ["meat, egg and fish"],
        "egg": ["dairy and eggs", "meat, egg and fish"],
        "milk": ["dairy and eggs"],
        "cheese": ["dairy and eggs"],
        "yogurt": ["dairy and eggs"],
        "butter": ["dairy and eggs"],
        "cream": ["dairy and eggs"],
        "rice": ["cereals and potatoes"],
        "pasta": ["cereals and potatoes"], 
        "potato": ["cereals and potatoes"],
        "bread": ["cereals and potatoes"],
        "oat": ["cereals and potatoes"],
        "wheat": ["cereals and potatoes"],
        "flour": ["cereals and potatoes"],
        "apple": ["fruits, vegetables, legumes and nuts"],
        "banana": ["fruits, vegetables, legumes and nuts"],
        "orange": ["fruits, vegetables, legumes and nuts"],
        "berry": ["fruits, vegetables, legumes and nuts"],
        "grape": ["fruits, vegetables, legumes and nuts"],
        "mango": ["fruits, vegetables, legumes and nuts"],
        "tomato": ["fruits, vegetables, legumes and nuts"],
        "carrot": ["fruits, vegetables, legumes and nuts"],
        "broccoli": ["fruits, vegetables, legumes and nuts"],
        "spinach": ["fruits, vegetables, legumes and nuts"],
        "lettuce": ["fruits, vegetables, legumes and nuts"],
        "onion": ["fruits, vegetables, legumes and nuts"],
        "pepper": ["fruits, vegetables, legumes and nuts"],
        "cucumber": ["fruits, vegetables, legumes and nuts"],
    }
    
    for basic_name, groups in basic_categories.items():
        if basic_name == name:
            return groups
    
    return ["meat, egg and fish", "fruits, vegetables, legumes and nuts", "cereals and potatoes", "dairy and eggs"]

# ----------------------------
# 4. Streamlit UI Components
# ----------------------------
def show_user_creation():
    """User creation form"""
    st.header("👤 Create New User")
    
    with st.form("create_user"):
        name = st.text_input("Username")
        col1, col2 = st.columns(2)
        with col1:
            age = st.number_input("Age", min_value=15, max_value=100, value=25)
            weight = st.number_input("Weight (kg)", min_value=30.0, max_value=300.0, value=70.0)
        with col2:
            gender = st.selectbox("Gender", ["male", "female"])
            height = st.number_input("Height (cm)", min_value=100, max_value=250, value=170)
        
        goal = st.selectbox("Goal", ["lose", "maintain", "gain"])
        activity = st.selectbox("Activity Level", 
                              ["sedentary", "light", "moderate", "active", "very active"])
        
        if st.form_submit_button("Create User"):
            if not name:
                st.error("❌ Username cannot be empty.")
                return
                
            user_data = {
                "name": name,
                "age": age,
                "gender": gender,
                "weight": weight,
                "height": height,
                "goal": goal,
                "activity": activity,
                "logs": [],
                "created_at": datetime.now().isoformat()
            }
            
            errors = validate_user_data(user_data)
            if errors:
                for error in errors:
                    st.error(error)
            else:
                st.session_state.users[name] = user_data
                st.session_state.active_user = user_data
                st.session_state.show_create_user = False
                st.success(f"✨ Successfully created user: {name}")
                st.rerun()

def show_user_selection():
    """User selection dropdown"""
    if st.session_state.users:
        user_names = list(st.session_state.users.keys())
        current_user = st.session_state.active_user["name"] if st.session_state.active_user else None
        
        selected_user = st.selectbox(
            "Select User",
            user_names,
            index=user_names.index(current_user) if current_user in user_names else 0
        )
        
        if selected_user and st.session_state.active_user and selected_user != st.session_state.active_user["name"]:
            st.session_state.active_user = st.session_state.users[selected_user]
            st.rerun()

def log_food_ui():
    """Food logging interface"""
    if not st.session_state.active_user:
        st.warning("❌ Please create or select a user first.")
        return
        
    st.header("🍽️ Log Food")
    
    meal_input = st.text_area(
        "What did you eat?",
        placeholder="e.g., '150g chicken and 50g rice' or 'chicken breast'",
        help="💡 Tip: You can include weights like 'chicken 150g' or just type food names"
    )
    
    if st.button("Log Food") and meal_input:
        with st.spinner("Processing your meal..."):
            # Parse ingredients
            ingredients = improve_ingredient_parsing(meal_input)
            
            if not ingredients:
                st.error("❌ No valid ingredients found. Please try again.")
                return
            
            total_cal = total_pro = total_carbs = total_fat = 0
            meal_logs = []
            
            st.write(f"🔍 Found {len(ingredients)} ingredient(s) to log...")
            
            for i, ing in enumerate(ingredients):
                st.write(f"**--- Ingredient {i+1}/{len(ingredients)}: '{ing['name']}' ({ing['weight']}g) ---**")
                
                # Auto-detect category
                category_groups = detect_food_category(ing['name'])
                
                # Find matching foods
                matches = find_basic_ingredients(ing['name'], category_groups)
                
                if not matches:
                    st.error(f"❌ No basic ingredients found for '{ing['name']}'.")
                    st.info("💡 Try searching for more specific terms like 'chicken breast' or 'brown rice'")
                    
                    # Manual entry option
                    with st.expander(f"Enter nutrition manually for '{ing['name']}'"):
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            manual_cal = st.number_input("Calories/100g", min_value=0.0, value=100.0, key=f"cal_{i}")
                        with col2:
                            manual_pro = st.number_input("Protein/100g", min_value=0.0, value=10.0, key=f"pro_{i}")
                        with col3:
                            manual_carbs = st.number_input("Carbs/100g", min_value=0.0, value=10.0, key=f"carbs_{i}")
                        with col4:
                            manual_fat = st.number_input("Fat/100g", min_value=0.0, value=5.0, key=f"fat_{i}")
                        
                        if st.button(f"Add Manual Entry", key=f"add_manual_{i}"):
                            ratio = ing['weight'] / 100
                            cal = manual_cal * ratio
                            pro = manual_pro * ratio
                            carbs = manual_carbs * ratio
                            fat = manual_fat * ratio
                            
                            total_cal += cal
                            total_pro += pro
                            total_carbs += carbs
                            total_fat += fat
                            
                            meal_logs.append({
                                "food": f"{ing['name']} (manual entry)",
                                "food_id": 0,
                                "grams": ing['weight'],
                                "nutrition": {
                                    "calories": round(cal, 1),
                                    "protein": round(pro, 1),
                                    "carbs": round(carbs, 1),
                                    "fat": round(fat, 1)
                                },
                                "timestamp": datetime.now().isoformat()
                            })
                            st.success(f"✅ Logged {ing['name']} (manual entry) ({ing['weight']}g)")
                    continue

                # Display matches
                st.write(f"🍎 Basic ingredient options for '{ing['name']}':")
                
                selected_food = None
                if matches:
                    # Create selection interface
                    food_options = []
                    for idx, food in enumerate(matches):
                        nutrition = food["nutrition"]
                        is_basic = is_basic_ingredient(food)
                        basic_indicator = "✅ BASIC" if is_basic else "⚠️ COMPLEX"
                        
                        option_text = (
                            f"{basic_indicator}: {food['names']['en']} | "
                            f"📊 {nutrition['calories']} kcal | 🥩 {nutrition['protein']}g protein | "
                            f"🥖 {nutrition['carbs']}g carbs | 🥑 {nutrition['fat']}g fat"
                        )
                        food_options.append(option_text)
                    
                    # Let user select
                    selected_option = st.selectbox(
                        f"Choose option for '{ing['name']}'",
                        options=range(len(food_options)),
                        format_func=lambda x: food_options[x],
                        key=f"select_{i}"
                    )
                    
                    selected_food = matches[selected_option]
                    grams = ing["weight"]

                    # Calculate nutrition
                    ratio = grams / 100
                    cal = selected_food["nutrition"]["calories"] * ratio
                    pro = selected_food["nutrition"]["protein"] * ratio
                    carbs = selected_food["nutrition"]["carbs"] * ratio
                    fat = selected_food["nutrition"]["fat"] * ratio

                    # Update totals
                    total_cal += cal
                    total_pro += pro
                    total_carbs += carbs
                    total_fat += fat

                    # Log this food
                    meal_logs.append({
                        "food": selected_food["names"]["en"],
                        "food_id": selected_food["id"],
                        "grams": grams,
                        "nutrition": {
                            "calories": round(cal, 1),
                            "protein": round(pro, 1),
                            "carbs": round(carbs, 1),
                            "fat": round(fat, 1)
                        },
                        "timestamp": datetime.now().isoformat()
                    })

                    st.success(f"✅ Logged {selected_food['names']['en']} ({grams}g)")

            # Add to user's logs
            if meal_logs:
                st.session_state.active_user["logs"].extend(meal_logs)
                
                # Show summary
                st.success("✨ MEAL LOGGED SUCCESSFULLY ✨")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("🔥 Calories", f"{total_cal:.1f} kcal")
                with col2:
                    st.metric("💪 Protein", f"{total_pro:.1f} g")
                with col3:
                    st.metric("🥖 Carbs", f"{total_carbs:.1f} g")
                with col4:
                    st.metric("🥑 Fat", f"{total_fat:.1f} g")
                
                st.write("📝 Logged items:")
                for log in meal_logs:
                    st.write(f"   • {log['food']} ({log['grams']}g)")
                
                st.balloons()
            else:
                st.error("❌ No foods were logged. Please try again.")

def show_daily_summary_ui():
    """Daily summary interface"""
    if not st.session_state.active_user:
        st.warning("❌ Please create or select a user first.")
        return
        
    st.header("📊 Daily Summary")
    
    # Calculate today's nutrition
    user = st.session_state.active_user
    today = datetime.now().strftime("%Y-%m-%d")
    logs = [x for x in user["logs"] if x["timestamp"].startswith(today)]
    
    if not logs:
        st.info("📊 No food logged today.")
        
        # Water reminder
        water_target_ml = user["weight"] * 35
        water_target_cups = round(water_target_ml / 240, 1)
        st.info(f"💧 Don't forget to drink {water_target_ml:.0f} ml ({water_target_cups} cups) of water today!")
        return
    
    # Calculate totals
    total_cal = sum(x["nutrition"]["calories"] for x in logs)
    total_pro = sum(x["nutrition"]["protein"] for x in logs)
    total_carbs = sum(x["nutrition"]["carbs"] for x in logs)
    total_fat = sum(x["nutrition"]["fat"] for x in logs)
    
    target_cal = daily_calories(user)
    target_protein = user["weight"] * 1.8
    remaining_calories = target_cal - total_cal
    
    # Water targets
    water_target_ml = user["weight"] * 35
    water_target_cups = round(water_target_ml / 240, 1)
    
    # Display summary
    st.subheader("📈 Nutrition Summary")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🔥 Calories", f"{total_cal:.1f}", f"{total_cal - target_cal:.1f}")
    with col2:
        st.metric("💪 Protein", f"{total_pro:.1f}g", f"{total_pro - target_protein:.1f}")
    with col3:
        st.metric("🥖 Carbs", f"{total_carbs:.1f}g")
    with col4:
        st.metric("🥑 Fat", f"{total_fat:.1f}g")
    
    # Progress bar for calories
    cal_percentage = min(100, (total_cal / target_cal) * 100) if target_cal > 0 else 0
    st.progress(cal_percentage / 100)
    st.write(f"Calorie Progress: {cal_percentage:.1f}%")
    
    # Water reminder
    st.subheader("💧 Hydration Status")
    st.write(f"💦 Daily water target: {water_target_ml:.0f} ml ({water_target_cups} cups)")
    
    # Time-based water reminder
    current_hour = datetime.now().hour
    if current_hour < 12:
        st.info("🌅 Morning: Aim for 3-4 glasses by lunch")
    elif current_hour < 18:
        st.info("☀️ Afternoon: Stay consistent with hydration")
    else:
        st.info("🌙 Evening: Complete your daily hydration")
    
    # Recommendations
    st.subheader("💡 Recommendations")
    if total_pro < target_protein * 0.7:
        st.warning("• Add protein: chicken, fish, eggs, tofu")
    elif total_pro >= target_protein:
        st.success("• ✅ Great protein intake!")
    
    if remaining_calories > 500:
        st.info("• You have room for 1-2 more meals/snacks")
    elif remaining_calories > 0:
        st.info("• Plan your remaining calories carefully")
    else:
        st.warning("• You've met your calorie target for today")

def show_user_profile():
    """User profile display"""
    if not st.session_state.active_user:
        st.warning("❌ Please create or select a user first.")
        return
        
    user = st.session_state.active_user
    st.header("👤 Your Profile")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Name:** {user['name']}")
        st.write(f"**Age:** {user['age']} years")
        st.write(f"**Gender:** {user['gender']}")
    with col2:
        st.write(f"**Weight:** {user['weight']} kg")
        st.write(f"**Height:** {user['height']} cm")
        st.write(f"**Goal:** {user['goal']}")
    
    # Calculate and display targets
    bmr = calculate_bmr(user)
    tdee = calculate_tdee(user)
    target_cal = daily_calories(user)
    target_protein = user["weight"] * 1.8
    
    st.subheader("🎯 Daily Targets")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("BMR", f"{bmr:.0f} kcal")
    with col2:
        st.metric("TDEE", f"{tdee:.0f} kcal")
    with col3:
        st.metric("Target Calories", f"{target_cal:.0f} kcal")
    with col4:
        st.metric("Target Protein", f"{target_protein:.1f} g")
    
    # Water recommendation
    water_target_ml = user["weight"] * 35
    water_target_cups = round(water_target_ml / 240, 1)
    st.subheader("💧 Hydration")
    st.write(f"Daily water target: **{water_target_ml:.0f} ml** ({water_target_cups} cups)")

# ----------------------------
# 5. Main App
# ----------------------------
def main():
    st.title("🍎 Smart Nutrition Tracker")
    st.markdown("Track your nutrition with basic ingredients only!")
    
    # Sidebar for user management
    with st.sidebar:
        st.header("User Management")
        
        if st.button("Create New User"):
            st.session_state.show_create_user = True
            
        show_user_selection()
        
        if st.session_state.active_user:
            st.success(f"Active: {st.session_state.active_user['name']}")
            if st.button("Delete Current User"):
                if st.session_state.active_user['name'] in st.session_state.users:
                    del st.session_state.users[st.session_state.active_user['name']]
                    st.session_state.active_user = None
                    st.rerun()
    
    # Main content area
    if st.session_state.show_create_user:
        show_user_creation()
        if st.button("Back to Main"):
            st.session_state.show_create_user = False
            st.rerun()
    else:
        # Navigation
        tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "🍽️ Log Food", "👤 Profile"])
        
        with tab1:
            show_daily_summary_ui()
        with tab2:
            log_food_ui()
        with tab3:
            show_user_profile()

if __name__ == "__main__":
    main()
