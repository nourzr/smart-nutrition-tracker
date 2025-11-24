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
# 2. User management with PERSISTENT storage
# ----------------------------
USERS_FILE = "nutrition_users.json"

def load_users():
    """Safely load user data from file"""
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        st.warning(f"⚠️ Could not load user data: {e}")
    return {}

def save_users(users_data):
    """Save user data to file"""
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"❌ Error saving user data: {e}")
        return False

# Initialize session state
if 'users' not in st.session_state:
    st.session_state.users = load_users()
    
if 'active_user' not in st.session_state:
    st.session_state.active_user = None
    
if 'show_create_user' not in st.session_state:
    st.session_state.show_create_user = False
    
if 'recent_meal_logs' not in st.session_state:
    st.session_state.recent_meal_logs = []
    
if 'meal_summary' not in st.session_state:
    st.session_state.meal_summary = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}

if 'recent_water_logs' not in st.session_state:
    st.session_state.recent_water_logs = []

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

def calculate_water_target(user):
    """Calculate daily water target based on weight (35ml per kg)"""
    return user["weight"] * 35

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
                "water_logs": [],
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
                # Save to file
                save_users(st.session_state.users)
                st.success(f"✨ Successfully created user: {name}")
                st.rerun()

def show_user_selection():
    """User selection dropdown"""
    if st.session_state.users:
        user_names = list(st.session_state.users.keys())
        current_user = st.session_state.active_user["name"] if st.session_state.active_user else user_names[0] if user_names else None
        
        selected_user = st.selectbox(
            "Select User",
            user_names,
            index=user_names.index(current_user) if current_user in user_names else 0
        )
        
        if selected_user and (not st.session_state.active_user or selected_user != st.session_state.active_user["name"]):
            st.session_state.active_user = st.session_state.users[selected_user]
            st.rerun()

def log_water_ui():
    """Water logging interface"""
    if not st.session_state.active_user:
        st.warning("❌ Please create or select a user first.")
        return
        
    st.header("💧 Log Water")
    
    # Calculate water target and progress
    user = st.session_state.active_user
    water_target_ml = calculate_water_target(user)
    water_target_cups = round(water_target_ml / 240, 1)
    
    today = datetime.now().strftime("%Y-%m-%d")
    water_logs_today = [x for x in user.get("water_logs", []) if x["timestamp"].startswith(today)]
    total_water_today = sum(x["amount"] for x in water_logs_today)
    water_percentage = min(100, (total_water_today / water_target_ml) * 100)
    
    # Show water progress
    st.subheader("📊 Hydration Progress")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Today's Water", f"{total_water_today:.0f} ml")
    with col2:
        st.metric("Daily Target", f"{water_target_ml:.0f} ml")
    with col3:
        st.metric("Progress", f"{water_percentage:.1f}%")
    
    # Progress bar
    st.progress(water_percentage / 100)
    
    # Show recent water logs
    if st.session_state.recent_water_logs:
        st.subheader("🕒 Recent Water Logs")
        for log in st.session_state.recent_water_logs[-5:]:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"💧 {log['amount']} ml")
            with col2:
                st.write(f"⏰ {log['timestamp'][11:16]}")
    
    # Water logging interface
    st.subheader("➕ Log Water Intake")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        # Quick add buttons
        st.write("**Quick Add:**")
        if st.button("🥛 Glass (240ml)", use_container_width=True):
            log_water_amount(240)
        if st.button("💧 Bottle (500ml)", use_container_width=True):
            log_water_amount(500)
        if st.button("🚰 Large (1000ml)", use_container_width=True):
            log_water_amount(1000)
    
    with col2:
        # Custom amount
        st.write("**Custom Amount:**")
        custom_amount = st.number_input("Amount (ml)", min_value=50, max_value=2000, value=250, step=50)
        if st.button("💧 Add Custom Amount", use_container_width=True):
            log_water_amount(custom_amount)
    
    with col3:
        # Water tips
        st.write("💡 **Hydration Tips:**")
        st.caption("• Drink 2 glasses after waking up")
        st.caption("• 1 glass before each meal")
        st.caption("• Keep water bottle nearby")
        st.caption("• Drink during workouts")

def log_water_amount(amount):
    """Log water intake"""
    if not st.session_state.active_user:
        return
        
    water_log = {
        "amount": amount,
        "timestamp": datetime.now().isoformat()
    }
    
    # Add to user's water logs
    if "water_logs" not in st.session_state.active_user:
        st.session_state.active_user["water_logs"] = []
    st.session_state.active_user["water_logs"].append(water_log)
    
    # Update recent logs
    st.session_state.recent_water_logs.append(water_log)
    
    # Update the main users dictionary and save
    st.session_state.users[st.session_state.active_user["name"]] = st.session_state.active_user
    save_users(st.session_state.users)
    
    st.success(f"✅ Logged {amount} ml of water!")
    st.rerun()

def log_food_ui():
    """Food logging interface"""
    if not st.session_state.active_user:
        st.warning("❌ Please create or select a user first.")
        return
        
    st.header("🍽️ Log Food")
    
    # Show recent meal logs immediately
    if st.session_state.recent_meal_logs:
        st.subheader("📝 Recently Logged Foods")
        for i, log in enumerate(st.session_state.recent_meal_logs[-5:]):  # Show last 5 items
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            with col1:
                st.write(f"**{log['food']}** ({log['grams']}g)")
            with col2:
                st.write(f"🔥 {log['nutrition']['calories']:.0f} cal")
            with col3:
                st.write(f"🥩 {log['nutrition']['protein']:.1f}g")
            with col4:
                st.write(f"⏰ {log['timestamp'][11:16]}")
        
        # Show meal summary
        if st.session_state.meal_summary["calories"] > 0:
            st.subheader("📊 Current Meal Summary")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🔥 Calories", f"{st.session_state.meal_summary['calories']:.1f}")
            with col2:
                st.metric("💪 Protein", f"{st.session_state.meal_summary['protein']:.1f}g")
            with col3:
                st.metric("🥖 Carbs", f"{st.session_state.meal_summary['carbs']:.1f}g")
            with col4:
                st.metric("🥑 Fat", f"{st.session_state.meal_summary['fat']:.1f}g")
    
    # Food input section
    st.subheader("➕ Add New Food")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        food_input = st.text_input(
            "Food Name",
            placeholder="e.g., chicken breast, brown rice, apple",
            help="Enter basic ingredients only"
        )
    with col2:
        serving_size = st.number_input(
            "Serving Size (g)",
            min_value=1,
            max_value=1000,
            value=100,
            help="Weight in grams"
        )
    
    if food_input and serving_size:
        # Auto-detect category
        category_groups = detect_food_category(food_input)
        
        # Find matching foods
        matches = find_basic_ingredients(food_input, category_groups)
        
        if matches:
            st.subheader("🔍 Matching Foods")
            
            # Create selection interface
            for idx, food in enumerate(matches):
                nutrition = food["nutrition"]
                is_basic = is_basic_ingredient(food)
                basic_indicator = "✅ BASIC" if is_basic else "⚠️ COMPLEX"
                
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.write(f"**{food['names']['en']}**")
                    st.caption(f"{basic_indicator} | {food['group']}")
                with col2:
                    st.write(f"🔥 {nutrition['calories']} cal/100g")
                    st.write(f"🥩 {nutrition['protein']}g protein")
                with col3:
                    if st.button(f"Add", key=f"add_{idx}"):
                        # Calculate nutrition for the serving size
                        ratio = serving_size / 100
                        cal = nutrition["calories"] * ratio
                        pro = nutrition["protein"] * ratio
                        carbs = nutrition["carbs"] * ratio
                        fat = nutrition["fat"] * ratio
                        
                        # Create log entry
                        log_entry = {
                            "food": food["names"]["en"],
                            "food_id": food["id"],
                            "grams": serving_size,
                            "nutrition": {
                                "calories": round(cal, 1),
                                "protein": round(pro, 1),
                                "carbs": round(carbs, 1),
                                "fat": round(fat, 1)
                            },
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        # Add to user's logs
                        st.session_state.active_user["logs"].append(log_entry)
                        
                        # Update recent logs and summary
                        st.session_state.recent_meal_logs.append(log_entry)
                        st.session_state.meal_summary["calories"] += cal
                        st.session_state.meal_summary["protein"] += pro
                        st.session_state.meal_summary["carbs"] += carbs
                        st.session_state.meal_summary["fat"] += fat
                        
                        # Update the main users dictionary and save
                        st.session_state.users[st.session_state.active_user["name"]] = st.session_state.active_user
                        save_users(st.session_state.users)
                        
                        st.success(f"✅ Added {food['names']['en']} ({serving_size}g)")
                        st.rerun()
            
            # Manual entry option
            with st.expander("🔧 Can't find your food? Enter manually"):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    manual_cal = st.number_input("Calories/100g", min_value=0.0, value=100.0, key="manual_cal")
                with col2:
                    manual_pro = st.number_input("Protein/100g", min_value=0.0, value=10.0, key="manual_pro")
                with col3:
                    manual_carbs = st.number_input("Carbs/100g", min_value=0.0, value=10.0, key="manual_carbs")
                with col4:
                    manual_fat = st.number_input("Fat/100g", min_value=0.0, value=5.0, key="manual_fat")
                
                if st.button("Add Manual Entry"):
                    ratio = serving_size / 100
                    cal = manual_cal * ratio
                    pro = manual_pro * ratio
                    carbs = manual_carbs * ratio
                    fat = manual_fat * ratio
                    
                    # Create log entry
                    log_entry = {
                        "food": f"{food_input} (manual)",
                        "food_id": 0,
                        "grams": serving_size,
                        "nutrition": {
                            "calories": round(cal, 1),
                            "protein": round(pro, 1),
                            "carbs": round(carbs, 1),
                            "fat": round(fat, 1)
                        },
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Add to user's logs
                    st.session_state.active_user["logs"].append(log_entry)
                    
                    # Update recent logs and summary
                    st.session_state.recent_meal_logs.append(log_entry)
                    st.session_state.meal_summary["calories"] += cal
                    st.session_state.meal_summary["protein"] += pro
                    st.session_state.meal_summary["carbs"] += carbs
                    st.session_state.meal_summary["fat"] += fat
                    
                    # Update the main users dictionary and save
                    st.session_state.users[st.session_state.active_user["name"]] = st.session_state.active_user
                    save_users(st.session_state.users)
                    
                    st.success(f"✅ Added {food_input} ({serving_size}g) - Manual Entry")
                    st.rerun()
        
        else:
            st.warning("❌ No basic ingredients found. Try more specific terms like 'chicken breast' or 'brown rice'")
            
            # Manual entry as fallback
            st.subheader("🔧 Enter Nutrition Manually")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                manual_cal = st.number_input("Calories per 100g", min_value=0.0, value=100.0, key="manual_cal_fallback")
            with col2:
                manual_pro = st.number_input("Protein per 100g", min_value=0.0, value=10.0, key="manual_pro_fallback")
            with col3:
                manual_carbs = st.number_input("Carbs per 100g", min_value=0.0, value=10.0, key="manual_carbs_fallback")
            with col4:
                manual_fat = st.number_input("Fat per 100g", min_value=0.0, value=5.0, key="manual_fat_fallback")
            
            if st.button("Add Food Manually"):
                ratio = serving_size / 100
                cal = manual_cal * ratio
                pro = manual_pro * ratio
                carbs = manual_carbs * ratio
                fat = manual_fat * ratio
                
                # Create log entry
                log_entry = {
                    "food": f"{food_input} (manual)",
                    "food_id": 0,
                    "grams": serving_size,
                    "nutrition": {
                        "calories": round(cal, 1),
                        "protein": round(pro, 1),
                        "carbs": round(carbs, 1),
                        "fat": round(fat, 1)
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
                # Add to user's logs
                st.session_state.active_user["logs"].append(log_entry)
                
                # Update recent logs and summary
                st.session_state.recent_meal_logs.append(log_entry)
                st.session_state.meal_summary["calories"] += cal
                st.session_state.meal_summary["protein"] += pro
                st.session_state.meal_summary["carbs"] += carbs
                st.session_state.meal_summary["fat"] += fat
                
                # Update the main users dictionary and save
                st.session_state.users[st.session_state.active_user["name"]] = st.session_state.active_user
                save_users(st.session_state.users)
                
                st.success(f"✅ Added {food_input} ({serving_size}g) - Manual Entry")
                st.rerun()
    
    # Clear current meal button
    if st.session_state.recent_meal_logs:
        if st.button("🔄 Clear Current Meal", type="secondary"):
            st.session_state.recent_meal_logs = []
            st.session_state.meal_summary = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
            st.rerun()

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
    water_logs = [x for x in user.get("water_logs", []) if x["timestamp"].startswith(today)]
    
    # Show food history
    if logs:
        st.subheader("📝 Today's Food Log")
        for i, log in enumerate(logs):
            with st.expander(f"{i+1}. {log['food']} ({log['grams']}g) - {log['timestamp'][11:16]}"):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Calories", f"{log['nutrition']['calories']:.1f}")
                with col2:
                    st.metric("Protein", f"{log['nutrition']['protein']:.1f}g")
                with col3:
                    st.metric("Carbs", f"{log['nutrition']['carbs']:.1f}g")
                with col4:
                    st.metric("Fat", f"{log['nutrition']['fat']:.1f}g")
    
    # Show water history
    if water_logs:
        st.subheader("💧 Today's Water Log")
        total_water = sum(x["amount"] for x in water_logs)
        water_target = calculate_water_target(user)
        water_percentage = min(100, (total_water / water_target) * 100)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Water", f"{total_water} ml")
        with col2:
            st.metric("Water Target", f"{water_target:.0f} ml")
        with col3:
            st.metric("Progress", f"{water_percentage:.1f}%")
        
        st.progress(water_percentage / 100)
        
        for i, log in enumerate(water_logs):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"💧 {log['amount']} ml")
            with col2:
                st.write(f"⏰ {log['timestamp'][11:16]}")
    
    if not logs and not water_logs:
        st.info("📊 No food or water logged today.")
        return
    
    # Calculate nutrition totals
    total_cal = sum(x["nutrition"]["calories"] for x in logs)
    total_pro = sum(x["nutrition"]["protein"] for x in logs)
    total_carbs = sum(x["nutrition"]["carbs"] for x in logs)
    total_fat = sum(x["nutrition"]["fat"] for x in logs)
    
    target_cal = daily_calories(user)
    target_protein = user["weight"] * 1.8
    remaining_calories = target_cal - total_cal
    
    # Display nutrition summary
    if logs:
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
    
    # Recommendations
    st.subheader("💡 Recommendations")
    if logs:
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
    
    # Water recommendations
    if water_logs:
        total_water = sum(x["amount"] for x in water_logs)
        water_target = calculate_water_target(user)
        if total_water < water_target * 0.7:
            st.warning("• Drink more water to meet your hydration goal")
        elif total_water >= water_target:
            st.success("• ✅ Excellent hydration today!")
        else:
            st.info("• Good hydration progress, keep going!")

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
    
    # Show user history stats
    total_logs = len(user["logs"])
    total_water_logs = len(user.get("water_logs", []))
    unique_days = len(set(log["timestamp"][:10] for log in user["logs"]))
    
    st.subheader("📊 History Stats")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Food Logs", total_logs)
    with col2:
        st.metric("Water Logs", total_water_logs)
    with col3:
        st.metric("Days Tracked", unique_days)
    
    # Calculate and display targets
    bmr = calculate_bmr(user)
    tdee = calculate_tdee(user)
    target_cal = daily_calories(user)
    target_protein = user["weight"] * 1.8
    water_target = calculate_water_target(user)
    
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
    water_target_cups = round(water_target / 240, 1)
    st.subheader("💧 Hydration")
    st.write(f"Daily water target: **{water_target:.0f} ml** ({water_target_cups} cups)")

# ----------------------------
# 5. Main App
# ----------------------------
def main():
    st.title("🍎 Smart Nutrition Tracker")
    st.markdown("Track your nutrition and hydration with basic ingredients only!")
    
    # Sidebar for user management
    with st.sidebar:
        st.header("User Management")
        
        if st.button("Create New User"):
            st.session_state.show_create_user = True
            
        show_user_selection()
        
        if st.session_state.active_user:
            st.success(f"Active: {st.session_state.active_user['name']}")
            
            # Show quick stats in sidebar
            today = datetime.now().strftime("%Y-%m-%d")
            today_logs = [x for x in st.session_state.active_user["logs"] if x["timestamp"].startswith(today)]
            today_water = [x for x in st.session_state.active_user.get("water_logs", []) if x["timestamp"].startswith(today)]
            
            total_cal_today = sum(x["nutrition"]["calories"] for x in today_logs)
            total_water_today = sum(x["amount"] for x in today_water)
            target_cal = daily_calories(st.session_state.active_user)
            water_target = calculate_water_target(st.session_state.active_user)
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Calories", f"{total_cal_today:.0f}", f"{total_cal_today - target_cal:.0f}")
            with col2:
                st.metric("Water", f"{total_water_today} ml", f"{total_water_today - water_target:.0f}")
            
            if st.button("Delete Current User"):
                if st.session_state.active_user['name'] in st.session_state.users:
                    del st.session_state.users[st.session_state.active_user['name']]
                    save_users(st.session_state.users)
                    st.session_state.active_user = None
                    st.session_state.recent_meal_logs = []
                    st.session_state.recent_water_logs = []
                    st.session_state.meal_summary = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
                    st.rerun()
    
    # Main content area
    if st.session_state.show_create_user:
        show_user_creation()
        if st.button("Back to Main"):
            st.session_state.show_create_user = False
            st.rerun()
    else:
        # Navigation
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "🍽️ Log Food", "💧 Log Water", "👤 Profile"])
        
        with tab1:
            show_daily_summary_ui()
        with tab2:
            log_food_ui()
        with tab3:
            log_water_ui()
        with tab4:
            show_user_profile()

if __name__ == "__main__":
    main()
