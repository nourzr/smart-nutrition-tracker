import json
import streamlit as st
from datetime import datetime
import re
import os
import hashlib
import pandas as pd
import requests
import base64

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
# 2. GitHub-Based Data Storage
# ----------------------------
# IMPORTANT: Set these in your Streamlit secrets!
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
# Update this to your actual GitHub repository (format: "username/repository-name")
GITHUB_REPO = "your_username/your_repo_name"  # 👈 CHANGE THIS!
CENTRAL_DATASET_FILE = "all_users_dataset.json"

def create_empty_dataset():
    """Create an empty dataset structure"""
    return {
        "users": {},
        "statistics": {
            "total_users": 0,
            "total_food_logs": 0,
            "total_water_logs": 0,
            "last_updated": datetime.now().isoformat()
        }
    }

def load_central_dataset_from_github():
    """Load the central dataset from GitHub"""
    if not GITHUB_TOKEN:
        # If no token, use temporary storage (will reset on app restart)
        return create_empty_dataset()
    
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CENTRAL_DATASET_FILE}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            content = response.json()['content']
            # GitHub API returns base64 encoded content
            decoded_content = base64.b64decode(content).decode('utf-8')
            return json.loads(decoded_content)
        elif response.status_code == 404:
            # File doesn't exist yet, create empty structure
            return create_empty_dataset()
        else:
            st.error(f"❌ GitHub API error: {response.status_code}")
            return create_empty_dataset()
            
    except Exception as e:
        st.error(f"❌ Error loading from GitHub: {e}")
        return create_empty_dataset()

def save_central_dataset_to_github(dataset):
    """Save the central dataset to GitHub"""
    if not GITHUB_TOKEN:
        st.error("❌ GitHub token not configured. Data will not persist between app restarts.")
        return False
    
    try:
        # First, try to get the existing file to get its SHA (for updates)
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CENTRAL_DATASET_FILE}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        get_response = requests.get(url, headers=headers)
        sha = None
        if get_response.status_code == 200:
            sha = get_response.json().get('sha')
        
        # Prepare the file content
        dataset["statistics"]["last_updated"] = datetime.now().isoformat()
        content = json.dumps(dataset, indent=2, ensure_ascii=False)
        encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        # Create the payload
        payload = {
            "message": f"Update nutrition tracker data - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "content": encoded_content,
            "branch": "main"
        }
        
        if sha:
            payload["sha"] = sha
            
        # Save to GitHub
        response = requests.put(url, headers=headers, json=payload)
        
        if response.status_code in [200, 201]:
            return True
        else:
            st.error(f"❌ GitHub API error: {response.status_code} - {response.text}")
            return False
        
    except Exception as e:
        st.error(f"❌ Error saving to GitHub: {e}")
        return False

# Update the existing functions to use GitHub storage
def load_central_dataset():
    return load_central_dataset_from_github()

def save_central_dataset(dataset):
    return save_central_dataset_to_github(dataset)

def update_central_dataset(username, user_data, action="update"):
    """Update the central dataset with user information"""
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

# ----------------------------
# 3. User Management Functions
# ----------------------------
def get_user_file(username):
    """Get user file path (local temp storage)"""
    username_hash = hashlib.sha256(username.lower().encode()).hexdigest()[:16]
    return f"/tmp/{username_hash}.json"  # Temp directory

def load_user_data(username):
    """Load user data from local temp storage"""
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
    except Exception as e:
        st.error(f"Error loading user data: {e}")
    return None

def save_user_data(username, user_data):
    """Save user data to local temp storage and update GitHub"""
    try:
        user_file = get_user_file(username)
        with open(user_file, "w", encoding="utf-8") as f:
            json.dump(user_data, f, indent=2, ensure_ascii=False)
        
        # Update central dataset on GitHub
        update_central_dataset(username, user_data, "update")
        return True
    except Exception as e:
        st.error(f"Error saving user data: {e}")
        return False

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(username, password):
    user_data = load_user_data(username)
    if user_data and "auth" in user_data:
        return user_data["auth"]["password_hash"] == hash_password(password)
    return False

def create_new_user(username, password, profile_data):
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
    if save_user_data(username, user_data):
        update_central_dataset(username, user_data, "create")
        return True
    return False

def save_current_user_data():
    """Save current user's data"""
    if st.session_state.current_user and st.session_state.user_data:
        return save_user_data(st.session_state.current_user, st.session_state.user_data)
    return False

# ----------------------------
# 4. Admin Panel
# ----------------------------
ADMIN_PASSWORD = "admin123"  # Change this to your secure password!

def show_admin_login():
    """Admin login"""
    st.header("🔐 Admin Access")
    
    admin_password = st.text_input("Admin Password", type="password", placeholder="Enter admin password")
    
    if st.button("Access Admin Panel"):
        if admin_password == ADMIN_PASSWORD:
            st.session_state.admin_logged_in = True
            st.rerun()
        else:
            st.error("❌ Invalid admin password")
    
    if st.button("← Back to Main App"):
        st.session_state.show_admin = False
        st.rerun()

def show_admin_panel():
    """Admin panel to view all user data"""
    st.header("🔐 Admin Panel - All User Data")
    
    # Show GitHub status
    st.subheader("🔧 Storage Status")
    if GITHUB_TOKEN:
        st.success("✅ GitHub storage configured")
        st.info(f"Data is saved to: `{GITHUB_REPO}/{CENTRAL_DATASET_FILE}`")
    else:
        st.error("❌ GitHub token not configured!")
        st.warning("""
        **To enable permanent data storage:**
        1. Create a GitHub Personal Access Token
        2. Add it to Streamlit secrets as `GITHUB_TOKEN`
        3. Update `GITHUB_REPO` in the code with your username/repo
        """)
    
    dataset = load_central_dataset()
    
    if not dataset["users"]:
        st.info("📊 No user data collected yet.")
        if st.button("← Back to Main App"):
            st.session_state.admin_logged_in = False
            st.session_state.show_admin = False
            st.rerun()
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
        # Export full dataset
        dataset_json = json.dumps(dataset, indent=2, ensure_ascii=False)
        st.download_button(
            label="💾 Download Full Dataset as JSON",
            data=dataset_json,
            file_name="all_users_complete_dataset.json",
            mime="application/json"
        )
    
    with col2:
        # Export user summary
        if dataset["users"]:
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
                label="📊 Download User Summary as CSV",
                data=csv_summary,
                file_name="user_summary.csv",
                mime="text/csv"
            )
    
    if st.button("🚪 Exit Admin Panel"):
        st.session_state.admin_logged_in = False
        st.session_state.show_admin = False
        st.rerun()

# ----------------------------
# 5. Session State Management
# ----------------------------
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'user_data' not in st.session_state:
    st.session_state.user_data = None
if 'show_login' not in st.session_state:
    st.session_state.show_login = True
if 'show_create_user' not in st.session_state:
    st.session_state.show_create_user = False
if 'show_admin' not in st.session_state:
    st.session_state.show_admin = False
if 'admin_logged_in' not in st.session_state:
    st.session_state.admin_logged_in = False
if 'recent_meal_logs' not in st.session_state:
    st.session_state.recent_meal_logs = []
if 'meal_summary' not in st.session_state:
    st.session_state.meal_summary = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
if 'recent_water_logs' not in st.session_state:
    st.session_state.recent_water_logs = []

# ----------------------------
# 6. Helper Functions (Your existing ones)
# ----------------------------
def validate_user_data(user_data):
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
# 7. UI Components (Your existing ones - shortened for example)
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
                    # Update central dataset with login
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

# [Include your other UI functions: log_food_ui(), log_water_ui(), show_daily_summary_ui(), show_user_profile()]

# ----------------------------
# 8. Main App
# ----------------------------
def main():
    st.title("🍎 Smart Nutrition Tracker")
    st.markdown("Track your nutrition and hydration with basic ingredients only!")
    
    # Check for admin access via URL parameter
    query_params = st.experimental_get_query_params()
    if query_params.get("admin"):
        if not st.session_state.admin_logged_in:
            show_admin_login()
        else:
            show_admin_panel()
        return
    
    # Show admin panel if requested
    if st.session_state.show_admin:
        if not st.session_state.admin_logged_in:
            show_admin_login()
        else:
            show_admin_panel()
        return
    
    # Normal user flow
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
    
    # Add hidden admin access button (only visible when holding Shift)
    with st.sidebar.expander("⚙️ Developer Options", expanded=False):
        if st.button("🔐 Admin Access"):
            st.session_state.show_admin = True
            st.rerun()
    
    # [Rest of your main app interface...]
    # For brevity, I'll include a simplified version - you should paste your full UI here
    
    st.info("🚀 Your nutrition tracker is running with GitHub storage!")
    st.write("To access admin panel, add `?admin=true` to your URL")

if __name__ == "__main__":
    main()
