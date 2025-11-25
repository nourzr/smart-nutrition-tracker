import json
import streamlit as st
from datetime import datetime
import re
import os
import hashlib
import pandas as pd

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
# 2. User management with SILENT DATA COLLECTION
# ----------------------------
USERS_DIR = "user_data"
CENTRAL_DATASET = "all_users_dataset.json"
ADMIN_PASSWORD = "admin123"  # Change this to your secure password

def ensure_users_dir():
    """Create user data directory if it doesn't exist"""
    if not os.path.exists(USERS_DIR):
        os.makedirs(USERS_DIR)

def get_user_file(username):
    """Get the file path for a specific user's data"""
    username_hash = hashlib.sha256(username.lower().encode()).hexdigest()[:16]
    return os.path.join(USERS_DIR, f"{username_hash}.json")

def hash_password(password):
    """Hash a password for storage"""
    return hashlib.sha256(password.encode()).hexdigest()

def load_central_dataset():
    """Load the central dataset with all user information"""
    try:
        if os.path.exists(CENTRAL_DATASET):
            with open(CENTRAL_DATASET, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        print(f"⚠️ Could not load central dataset: {e}")
    
    # Return empty structure if no file exists
    return {
        "users": {},
        "statistics": {
            "total_users": 0,
            "total_food_logs": 0,
            "total_water_logs": 0,
            "last_updated": datetime.now().isoformat()
        }
    }

def save_central_dataset(dataset):
    """Save the central dataset with all user information"""
    try:
        dataset["statistics"]["last_updated"] = datetime.now().isoformat()
        with open(CENTRAL_DATASET, "w", encoding="utf-8") as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Error saving central dataset: {e}")
        return False

def update_central_dataset(username, user_data, action="update"):
    """Silently update the central dataset with user information"""
    dataset = load_central_dataset()
    
    if action == "create":
        # Add new user to central dataset
        dataset["users"][username] = {
            "profile": user_data["profile"].copy(),
            "auth_info": {
                "hashed_password": user_data["auth"]["password_hash"],
                "created_at": user_data["auth"]["created_at"],
                "last_login": datetime.now().isoformat()
            },
            "statistics": {
                "food_logs_count": 0,
                "water_logs_count": 0,
                "last_activity": datetime.now().isoformat()
            },
            "food_logs": [],
            "water_logs": []
        }
    elif action == "update" and username in dataset["users"]:
        # Update existing user data
        dataset["users"][username]["profile"] = user_data["profile"].copy()
        dataset["users"][username]["auth_info"]["last_login"] = datetime.now().isoformat()
        dataset["users"][username]["statistics"]["last_activity"] = datetime.now().isoformat()
        
        # Update food logs
        dataset["users"][username]["food_logs"] = user_data.get("food_logs", [])
        dataset["users"][username]["statistics"]["food_logs_count"] = len(user_data.get("food_logs", []))
        
        # Update water logs
        dataset["users"][username]["water_logs"] = user_data.get("water_logs", [])
        dataset["users"][username]["statistics"]["water_logs_count"] = len(user_data.get("water_logs", []))
    
    # Update global statistics
    dataset["statistics"]["total_users"] = len(dataset["users"])
    dataset["statistics"]["total_food_logs"] = sum(
        user["statistics"]["food_logs_count"] for user in dataset["users"].values()
    )
    dataset["statistics"]["total_water_logs"] = sum(
        user["statistics"]["water_logs_count"] for user in dataset["users"].values()
    )
    
    return save_central_dataset(dataset)

def load_user_data(username):
    """Load data for a specific user"""
    ensure_users_dir()
    user_file = get_user_file(username)
    
    try:
        if os.path.exists(user_file):
            with open(user_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "food_logs" not in data:
                    data["food_logs"] = []
                if "water_logs" not in data:
                    data["water_logs"] = []
                return data
    except (json.JSONDecodeError, Exception) as e:
        st.warning(f"⚠️ Could not load user data: {e}")
    
    return None

def save_user_data(username, user_data):
    """Save data for a specific user and silently update central dataset"""
    try:
        ensure_users_dir()
        user_file = get_user_file(username)
        
        with open(user_file, "w", encoding="utf-8") as f:
            json.dump(user_data, f, indent=2, ensure_ascii=False)
        
        # SILENTLY update central dataset (no user notification)
        update_central_dataset(username, user_data, "update")
        return True
    except Exception as e:
        st.error(f"❌ Error saving user data: {e}")
        return False

def verify_password(username, password):
    """Verify a user's password"""
    user_data = load_user_data(username)
    if user_data and "auth" in user_data:
        return user_data["auth"]["password_hash"] == hash_password(password)
    return False

def create_new_user(username, password, profile_data):
    """Create a new user with password protection"""
    user_data = {
        "auth": {
            "username": username,
            "password_hash": hash_password(password),
            "created_at": datetime.now().isoformat()
        },
        "profile": profile_data,
        "food_logs": [],
        "water_logs": []
    }
    
    # Save individual user data
    if save_user_data(username, user_data):
        # SILENTLY add to central dataset (no user notification)
        update_central_dataset(username, user_data, "create")
        return True
    return False

# ----------------------------
# 3. SEPARATE ADMIN TOOL (Not shown to users)
# ----------------------------
def show_admin_login():
    """Hidden admin login - only you know about this"""
    st.header("🔐 Admin Access")
    
    # Simple password protection
    admin_password = st.text_input("Admin Password", type="password", placeholder="Enter admin password")
    
    if st.button("Access Admin Panel"):
        if admin_password == ADMIN_PASSWORD:
            st.session_state.admin_logged_in = True
            st.rerun()
        else:
            st.error("❌ Invalid admin password")
    
    # Instructions for owner
    with st.expander("ℹ️ Admin Instructions"):
        st.write("""
        **As the owner, you can:**
        - View all user data (profiles, food logs, water logs)
        - Export data to CSV/JSON for analysis
        - Monitor user statistics and activity
        
        **The central dataset file is:** `all_users_dataset.json`
        **Admin password is:** `admin123` (change this in the code)
        """)

def show_admin_panel():
    """Admin panel to view all user data"""
    st.header("🔐 Admin Panel - All User Data")
    
    dataset = load_central_dataset()
    
    if not dataset["users"]:
        st.info("📊 No user data collected yet.")
        return
    
    # Show statistics
    st.subheader("📈 Global Statistics")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Users", dataset["statistics"]["total_users"])
    with col2:
        st.metric("Total Food Logs", dataset["statistics"]["total_food_logs"])
    with col3:
        st.metric("Total Water Logs", dataset["statistics"]["total_water_logs"])
    with col4:
        last_updated = dataset["statistics"]["last_updated"][:16].replace("T", " ")
        st.metric("Last Updated", last_updated)
    
    # User selection
    user_names = list(dataset["users"].keys())
    selected_user = st.selectbox("Select User to View Details", user_names)
    
    if selected_user:
        user_data = dataset["users"][selected_user]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("👤 Profile Information")
            profile = user_data["profile"]
            st.write(f"**Username:** {selected_user}")
            st.write(f"**Age:** {profile['age']} years")
            st.write(f"**Gender:** {profile['gender']}")
            st.write(f"**Weight:** {profile['weight']} kg")
            st.write(f"**Height:** {profile['height']} cm")
            st.write(f"**Goal:** {profile['goal']}")
            st.write(f"**Activity Level:** {profile['activity']}")
            st.write(f"**Account Created:** {user_data['auth_info']['created_at'][:16].replace('T', ' ')}")
            st.write(f"**Last Login:** {user_data['auth_info']['last_login'][:16].replace('T', ' ')}")
        
        with col2:
            st.subheader("📊 User Statistics")
            stats = user_data["statistics"]
            st.metric("Food Logs", stats["food_logs_count"])
            st.metric("Water Logs", stats["water_logs_count"])
            st.write(f"**Last Activity:** {stats['last_activity'][:16].replace('T', ' ')}")
        
        # Food logs
        st.subheader("🍽️ Food Logs")
        if user_data["food_logs"]:
            food_df_data = []
            for log in user_data["food_logs"]:
                food_df_data.append({
                    "Food": log["food"],
                    "Grams": log["grams"],
                    "Calories": log["nutrition"]["calories"],
                    "Protein (g)": log["nutrition"]["protein"],
                    "Carbs (g)": log["nutrition"]["carbs"],
                    "Fat (g)": log["nutrition"]["fat"],
                    "Timestamp": log["timestamp"][:16].replace("T", " ")
                })
            food_df = pd.DataFrame(food_df_data)
            st.dataframe(food_df, use_container_width=True)
            
            # Export food data
            csv_food = food_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Food Logs as CSV",
                data=csv_food,
                file_name=f"{selected_user}_food_logs.csv",
                mime="text/csv"
            )
        else:
            st.info("No food logs recorded.")
        
        # Water logs
        st.subheader("💧 Water Logs")
        if user_data["water_logs"]:
            water_df_data = []
            for log in user_data["water_logs"]:
                water_df_data.append({
                    "Amount (ml)": log["amount"],
                    "Timestamp": log["timestamp"][:16].replace("T", " ")
                })
            water_df = pd.DataFrame(water_df_data)
            st.dataframe(water_df, use_container_width=True)
            
            # Export water data
            csv_water = water_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Water Logs as CSV",
                data=csv_water,
                file_name=f"{selected_user}_water_logs.csv",
                mime="text/csv"
            )
        else:
            st.info("No water logs recorded.")
    
    # Export all data
    st.subheader("📤 Export All Data")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 Export Complete Dataset as JSON"):
            dataset_json = json.dumps(dataset, indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 Download Full Dataset",
                data=dataset_json,
                file_name="all_users_complete_dataset.json",
                mime="application/json"
            )
    
    with col2:
        if st.button("📊 Export User Summary as CSV"):
            summary_data = []
            for username, user_data in dataset["users"].items():
                summary_data.append({
                    "Username": username,
                    "Age": user_data["profile"]["age"],
                    "Gender": user_data["profile"]["gender"],
                    "Weight": user_data["profile"]["weight"],
                    "Height": user_data["profile"]["height"],
                    "Goal": user_data["profile"]["goal"],
                    "Activity": user_data["profile"]["activity"],
                    "Food Logs": user_data["statistics"]["food_logs_count"],
                    "Water Logs": user_data["statistics"]["water_logs_count"],
                    "Account Created": user_data["auth_info"]["created_at"][:10],
                    "Last Login": user_data["auth_info"]["last_login"][:10]
                })
            summary_df = pd.DataFrame(summary_data)
            csv_summary = summary_df.to_csv(index=False)
            st.download_button(
                label="📥 Download User Summary",
                data=csv_summary,
                file_name="user_summary.csv",
                mime="text/csv"
            )
    
    # Show raw data
    with st.expander("🔍 View Raw Dataset Structure"):
        st.json(dataset)
    
    if st.button("🚪 Exit Admin Panel"):
        st.session_state.admin_logged_in = False
        st.rerun()

# ----------------------------
# 4. Session State Management
# ----------------------------
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'user_data' not in st.session_state:
    st.session_state.user_data = None
if 'show_login' not in st.session_state:
    st.session_state.show_login = True
if 'show_create_user' not in st.session_state:
    st.session_state.show_create_user = False
if 'admin_logged_in' not in st.session_state:
    st.session_state.admin_logged_in = False

# ... (rest of your session state variables) ...
if 'recent_meal_logs' not in st.session_state:
    st.session_state.recent_meal_logs = []
if 'meal_summary' not in st.session_state:
    st.session_state.meal_summary = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
if 'recent_water_logs' not in st.session_state:
    st.session_state.recent_water_logs = []

# ----------------------------
# 5. Helper functions (keep all your existing helper functions)
# ----------------------------
def save_current_user_data():
    """Save current user's data to file"""
    if st.session_state.current_user and st.session_state.user_data:
        return save_user_data(st.session_state.current_user, st.session_state.user_data)
    return False

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
    return user["weight"] * 35

# ... (include all your other helper functions like normalize_food_input, is_basic_ingredient, etc.) ...

def normalize_food_input(text):
    COOKING_WORDS = ["grilled", "roasted", "baked", "steamed", "fried", "cooked", "boiled", "raw", "fresh"]
    text = text.lower().strip()
    for word in COOKING_WORDS:
        text = re.sub(r'\b' + word + r'\b', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_basic_ingredient(food):
    food_name = food["names"]["en"].lower()
    complex_indicators = [",", "(", ")", "with", "and", "or", "prepared", "canned", "packed", "packaged", "prepacked", "prepackaged", "mix", "mixed", "salad", "soup", "sauce", "gravy", "broth", "stock", "dish", "recipe", "meal", "dinner", "lunch", "breakfast", "cooked", "boiled", "fried", "grilled", "roasted", "baked", "steamed", "w/", "with", "au", "à la", "style", "flavored", "seasoned", "sandwich", "burger", "pizza", "pasta", "stew", "curry", "stir-fry", "casserole", "marinated", "breaded", "coated", "stuffed", "meal", "dish", "plate", "serving", "portion"]
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
    name = name.lower()
    basic_categories = {
        "chicken": ["meat, egg and fish"], "beef": ["meat, egg and fish"], "pork": ["meat, egg and fish"],
        "lamb": ["meat, egg and fish"], "turkey": ["meat, egg and fish"], "duck": ["meat, egg and fish"],
        "fish": ["meat, egg and fish"], "salmon": ["meat, egg and fish"], "tuna": ["meat, egg and fish"],
        "cod": ["meat, egg and fish"], "egg": ["dairy and eggs", "meat, egg and fish"], "milk": ["dairy and eggs"],
        "cheese": ["dairy and eggs"], "yogurt": ["dairy and eggs"], "butter": ["dairy and eggs"],
        "cream": ["dairy and eggs"], "rice": ["cereals and potatoes"], "pasta": ["cereals and potatoes"],
        "potato": ["cereals and potatoes"], "bread": ["cereals and potatoes"], "oat": ["cereals and potatoes"],
        "wheat": ["cereals and potatoes"], "flour": ["cereals and potatoes"], "apple": ["fruits, vegetables, legumes and nuts"],
        "banana": ["fruits, vegetables, legumes and nuts"], "orange": ["fruits, vegetables, legumes and nuts"],
        "berry": ["fruits, vegetables, legumes and nuts"], "grape": ["fruits, vegetables, legumes and nuts"],
        "mango": ["fruits, vegetables, legumes and nuts"], "tomato": ["fruits, vegetables, legumes and nuts"],
        "carrot": ["fruits, vegetables, legumes and nuts"], "broccoli": ["fruits, vegetables, legumes and nuts"],
        "spinach": ["fruits, vegetables, legumes and nuts"], "lettuce": ["fruits, vegetables, legumes and nuts"],
        "onion": ["fruits, vegetables, legumes and nuts"], "pepper": ["fruits, vegetables, legumes and nuts"],
        "cucumber": ["fruits, vegetables, legumes and nuts"],
    }
    for basic_name, groups in basic_categories.items():
        if basic_name == name:
            return groups
    return ["meat, egg and fish", "fruits, vegetables, legumes and nuts", "cereals and potatoes", "dairy and eggs"]

# ----------------------------
# 6. Streamlit UI Components (keep all your existing UI functions)
# ----------------------------
def show_user_login():
    st.header("🔐 Login to Your Account")
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        col1, col2 = st.columns(2)
        with col1:
            login_button = st.form_submit_button("🔓 Login", use_container_width=True)
        with col2:
            create_account_button = st.form_submit_button("🆕 Create Account", use_container_width=True)
        if login_button and username and password:
            with st.spinner("Verifying credentials..."):
                user_data = load_user_data(username)
                if user_data and verify_password(username, password):
                    st.session_state.current_user = username
                    st.session_state.user_data = user_data
                    st.session_state.show_login = False
                    # SILENTLY update central dataset with login
                    update_central_dataset(username, user_data, "update")
                    st.success(f"✨ Welcome back, {username}!")
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password")
        if create_account_button:
            st.session_state.show_create_user = True
            st.session_state.show_login = False
            st.rerun()

def show_user_creation():
    st.header("👤 Create New Account")
    with st.form("create_user"):
        st.subheader("🔐 Account Details")
        username = st.text_input("Choose a Username", placeholder="Enter a unique username")
        password = st.text_input("Choose a Password", type="password", placeholder="Create a strong password")
        confirm_password = st.text_input("Confirm Password", type="password", placeholder="Re-enter your password")
        st.subheader("📋 Profile Information")
        col1, col2 = st.columns(2)
        with col1:
            age = st.number_input("Age", min_value=15, max_value=100, value=25)
            weight = st.number_input("Weight (kg)", min_value=30.0, max_value=300.0, value=70.0)
        with col2:
            gender = st.selectbox("Gender", ["male", "female"])
            height = st.number_input("Height (cm)", min_value=100, max_value=250, value=170)
        goal = st.selectbox("Goal", ["lose", "maintain", "gain"])
        activity = st.selectbox("Activity Level", ["sedentary", "light", "moderate", "active", "very active"])
        if st.form_submit_button("Create Account"):
            if not username:
                st.error("❌ Username cannot be empty.")
                return
            if not password:
                st.error("❌ Password cannot be empty.")
                return
            if password != confirm_password:
                st.error("❌ Passwords do not match.")
                return
            if len(password) < 4:
                st.error("❌ Password must be at least 4 characters long.")
                return
            if load_user_data(username) is not None:
                st.error("❌ Username already exists. Please choose a different one.")
                return
            user_profile = {
                "name": username, "age": age, "gender": gender, "weight": weight, "height": height,
                "goal": goal, "activity": activity, "created_at": datetime.now().isoformat()
            }
            errors = validate_user_data(user_profile)
            if errors:
                for error in errors:
                    st.error(error)
            else:
                if create_new_user(username, password, user_profile):
                    user_data = load_user_data(username)
                    if user_data:
                        st.session_state.current_user = username
                        st.session_state.user_data = user_data
                        st.session_state.show_create_user = False
                        st.session_state.show_login = False
                        st.success(f"✨ Account created successfully! Welcome, {username}!")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("❌ Account created but failed to load data. Please login.")
                else:
                    st.error("❌ Failed to create account. Please try again.")

# ... (include all your existing log_food_ui(), log_water_ui(), show_daily_summary_ui(), show_user_profile() functions) ...
# [PASTE ALL YOUR EXISTING UI FUNCTIONS HERE - they remain unchanged]

def log_food_ui():
    """Food logging interface - SILENTLY updates central dataset"""
    if not st.session_state.current_user:
        st.warning("❌ Please login first.")
        return
        
    st.header("🍽️ Log Food")
    
    # [KEEP ALL YOUR EXISTING FOOD LOGGING CODE]
    # The only change is that save_current_user_data() now silently updates central dataset
    
    # Show recent meal logs immediately
    if st.session_state.recent_meal_logs:
        st.subheader("📝 Recently Logged Foods")
        for i, log in enumerate(st.session_state.recent_meal_logs[-5:]):
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            with col1:
                st.write(f"**{log['food']}** ({log['grams']}g)")
            with col2:
                st.write(f"🔥 {log['nutrition']['calories']:.0f} cal")
            with col3:
                st.write(f"🥩 {log['nutrition']['protein']:.1f}g")
            with col4:
                st.write(f"⏰ {log['timestamp'][11:16]}")
        
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
        category_groups = detect_food_category(food_input)
        matches = find_basic_ingredients(food_input, category_groups)
        
        if matches:
            st.subheader("🔍 Matching Foods")
            
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
                        ratio = serving_size / 100
                        cal = nutrition["calories"] * ratio
                        pro = nutrition["protein"] * ratio
                        carbs = nutrition["carbs"] * ratio
                        fat = nutrition["fat"] * ratio
                        
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
                        
                        st.session_state.user_data["food_logs"].append(log_entry)
                        st.session_state.recent_meal_logs.append(log_entry)
                        st.session_state.meal_summary["calories"] += cal
                        st.session_state.meal_summary["protein"] += pro
                        st.session_state.meal_summary["carbs"] += carbs
                        st.session_state.meal_summary["fat"] += fat
                        
                        # SILENTLY save and update central dataset
                        if save_current_user_data():
                            st.success(f"✅ Added {food['names']['en']} ({serving_size}g)")
                        else:
                            st.error("❌ Failed to save food log!")
                        st.rerun()
            
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
                    
                    st.session_state.user_data["food_logs"].append(log_entry)
                    st.session_state.recent_meal_logs.append(log_entry)
                    st.session_state.meal_summary["calories"] += cal
                    st.session_state.meal_summary["protein"] += pro
                    st.session_state.meal_summary["carbs"] += carbs
                    st.session_state.meal_summary["fat"] += fat
                    
                    if save_current_user_data():
                        st.success(f"✅ Added {food_input} ({serving_size}g) - Manual Entry")
                    else:
                        st.error("❌ Failed to save food log!")
                    st.rerun()
        
        else:
            st.warning("❌ No basic ingredients found. Try more specific terms like 'chicken breast' or 'brown rice'")
            
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
                
                st.session_state.user_data["food_logs"].append(log_entry)
                st.session_state.recent_meal_logs.append(log_entry)
                st.session_state.meal_summary["calories"] += cal
                st.session_state.meal_summary["protein"] += pro
                st.session_state.meal_summary["carbs"] += carbs
                st.session_state.meal_summary["fat"] += fat
                
                if save_current_user_data():
                    st.success(f"✅ Added {food_input} ({serving_size}g) - Manual Entry")
                else:
                    st.error("❌ Failed to save food log!")
                st.rerun()
    
    if st.session_state.recent_meal_logs:
        if st.button("🔄 Clear Current Meal", type="secondary"):
            st.session_state.recent_meal_logs = []
            st.session_state.meal_summary = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
            st.rerun()

def log_water_ui():
    """Water logging interface - SILENTLY updates central dataset"""
    if not st.session_state.current_user:
        st.warning("❌ Please login first.")
        return
        
    st.header("💧 Log Water")
    
    user_profile = st.session_state.user_data["profile"]
    water_target_ml = calculate_water_target(user_profile)
    
    today = datetime.now().strftime("%Y-%m-%d")
    water_logs_today = [x for x in st.session_state.user_data.get("water_logs", []) if x["timestamp"].startswith(today)]
    total_water_today = sum(x["amount"] for x in water_logs_today)
    water_percentage = min(100, (total_water_today / water_target_ml) * 100)
    
    st.subheader("📊 Hydration Progress")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Today's Water", f"{total_water_today:.0f} ml")
    with col2:
        st.metric("Daily Target", f"{water_target_ml:.0f} ml")
    with col3:
        st.metric("Progress", f"{water_percentage:.1f}%")
    
    st.progress(water_percentage / 100)
    
    if st.session_state.recent_water_logs:
        st.subheader("🕒 Recent Water Logs")
        for log in st.session_state.recent_water_logs[-5:]:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"💧 {log['amount']} ml")
            with col2:
                st.write(f"⏰ {log['timestamp'][11:16]}")
    
    st.subheader("➕ Log Water Intake")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write("**Quick Add:**")
        if st.button("🥛 Glass (240ml)", use_container_width=True):
            log_water_amount(240)
        if st.button("💧 Bottle (500ml)", use_container_width=True):
            log_water_amount(500)
        if st.button("🚰 Large (1000ml)", use_container_width=True):
            log_water_amount(1000)
    
    with col2:
        st.write("**Custom Amount:**")
        custom_amount = st.number_input("Amount (ml)", min_value=50, max_value=2000, value=250, step=50)
        if st.button("💧 Add Custom Amount", use_container_width=True):
            log_water_amount(custom_amount)
    
    with col3:
        st.write("💡 **Hydration Tips:**")
        st.caption("• Drink 2 glasses after waking up")
        st.caption("• 1 glass before each meal")
        st.caption("• Keep water bottle nearby")
        st.caption("• Drink during workouts")

def log_water_amount(amount):
    """Log water intake - SILENTLY updates central dataset"""
    if not st.session_state.current_user:
        return
        
    water_log = {
        "amount": amount,
        "timestamp": datetime.now().isoformat()
    }
    
    if "water_logs" not in st.session_state.user_data:
        st.session_state.user_data["water_logs"] = []
    st.session_state.user_data["water_logs"].append(water_log)
    
    st.session_state.recent_water_logs.append(water_log)
    
    # SILENTLY save and update central dataset
    if save_current_user_data():
        st.success(f"✅ Logged {amount} ml of water!")
    else:
        st.error("❌ Failed to save water log!")
    st.rerun()

def show_daily_summary_ui():
    """Daily summary interface"""
    if not st.session_state.current_user:
        st.warning("❌ Please login first.")
        return
        
    st.header("📊 Daily Summary")
    
    user_data = st.session_state.user_data
    today = datetime.now().strftime("%Y-%m-%d")
    logs = [x for x in user_data["food_logs"] if x["timestamp"].startswith(today)]
    water_logs = [x for x in user_data.get("water_logs", []) if x["timestamp"].startswith(today)]
    
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
    
    if water_logs:
        st.subheader("💧 Today's Water Log")
        total_water = sum(x["amount"] for x in water_logs)
        water_target = calculate_water_target(user_data["profile"])
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
    
    total_cal = sum(x["nutrition"]["calories"] for x in logs)
    total_pro = sum(x["nutrition"]["protein"] for x in logs)
    total_carbs = sum(x["nutrition"]["carbs"] for x in logs)
    total_fat = sum(x["nutrition"]["fat"] for x in logs)
    
    target_cal = daily_calories(user_data["profile"])
    target_protein = user_data["profile"]["weight"] * 1.8
    remaining_calories = target_cal - total_cal
    
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
        
        cal_percentage = min(100, (total_cal / target_cal) * 100) if target_cal > 0 else 0
        st.progress(cal_percentage / 100)
        st.write(f"Calorie Progress: {cal_percentage:.1f}%")
    
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
    
    if water_logs:
        total_water = sum(x["amount"] for x in water_logs)
        water_target = calculate_water_target(user_data["profile"])
        if total_water < water_target * 0.7:
            st.warning("• Drink more water to meet your hydration goal")
        elif total_water >= water_target:
            st.success("• ✅ Excellent hydration today!")
        else:
            st.info("• Good hydration progress, keep going!")

def show_user_profile():
    """User profile display"""
    if not st.session_state.current_user:
        st.warning("❌ Please login first.")
        return
        
    user_data = st.session_state.user_data
    user_profile = user_data["profile"]
    
    st.header("👤 Your Profile")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Name:** {user_profile['name']}")
        st.write(f"**Age:** {user_profile['age']} years")
        st.write(f"**Gender:** {user_profile['gender']}")
    with col2:
        st.write(f"**Weight:** {user_profile['weight']} kg")
        st.write(f"**Height:** {user_profile['height']} cm")
        st.write(f"**Goal:** {user_profile['goal']}")
    
    total_food_logs = len(user_data["food_logs"])
    total_water_logs = len(user_data.get("water_logs", []))
    unique_days = len(set(log["timestamp"][:10] for log in user_data["food_logs"]))
    
    st.subheader("📊 History Stats")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Food Logs", total_food_logs)
    with col2:
        st.metric("Water Logs", total_water_logs)
    with col3:
        st.metric("Days Tracked", unique_days)
    
    bmr = calculate_bmr(user_profile)
    tdee = calculate_tdee(user_profile)
    target_cal = daily_calories(user_profile)
    target_protein = user_profile["weight"] * 1.8
    water_target = calculate_water_target(user_profile)
    
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
    
    water_target_cups = round(water_target / 240, 1)
    st.subheader("💧 Hydration")
    st.write(f"Daily water target: **{water_target:.0f} ml** ({water_target_cups} cups)")

# ----------------------------
# 7. Main App
# ----------------------------
def main():
    st.title("🍎 Smart Nutrition Tracker")
    st.markdown("Track your nutrition and hydration with basic ingredients only!")
    
    # HIDDEN ADMIN ACCESS - Add ?admin=true to URL to access
    query_params = st.experimental_get_query_params()
    if query_params.get("admin") == ["true"]:
        if not st.session_state.admin_logged_in:
            show_admin_login()
        else:
            show_admin_panel()
        return
    
    # Show login screen if no user is logged in
    if not st.session_state.current_user:
        if st.session_state.show_create_user:
            show_user_creation()
            if st.button("← Back to Login"):
                st.session_state.show_create_user = False
                st.session_state.show_login = True
                st.rerun()
        else:
            show_user_login()
        return
    
    # User is logged in - show main app
    st.sidebar.header("👤 User Session")
    st.sidebar.success(f"Logged in as: **{st.session_state.current_user}**")
    
    today = datetime.now().strftime("%Y-%m-%d")
    today_food_logs = [x for x in st.session_state.user_data["food_logs"] if x["timestamp"].startswith(today)]
    today_water_logs = [x for x in st.session_state.user_data.get("water_logs", []) if x["timestamp"].startswith(today)]
    
    total_cal_today = sum(x["nutrition"]["calories"] for x in today_food_logs)
    total_water_today = sum(x["amount"] for x in today_water_logs)
    target_cal = daily_calories(st.session_state.user_data["profile"])
    water_target = calculate_water_target(st.session_state.user_data["profile"])
    
    st.sidebar.subheader("📊 Today's Progress")
    col1, col2 = st.columns(2)
    with col1:
        st.sidebar.metric("Calories", f"{total_cal_today:.0f}", f"{total_cal_today - target_cal:.0f}")
    with col2:
        st.sidebar.metric("Water", f"{total_water_today} ml", f"{total_water_today - water_target:.0f}")
    
    if st.sidebar.button("🚪 Logout", type="secondary"):
        st.session_state.current_user = None
        st.session_state.user_data = None
        st.session_state.recent_meal_logs = []
        st.session_state.recent_water_logs = []
        st.session_state.meal_summary = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
        st.session_state.show_login = True
        st.rerun()
    
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
