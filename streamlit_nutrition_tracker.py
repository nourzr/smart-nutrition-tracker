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
        # For Streamlit sharing, you'll need to upload this file
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

# ----------------------------
# 3. Helper functions (keep your existing functions)
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

# Keep all your other helper functions (normalize_food_input, improve_ingredient_parsing, 
# is_basic_ingredient, find_basic_ingredients, detect_food_category) exactly as they are

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
        # Use your existing log_food logic here
        # This would call your improve_ingredient_parsing and find_basic_ingredients functions
        st.info("Food logging functionality would be implemented here")
        # You'd need to adapt your log_food function to work with Streamlit

def show_daily_summary_ui():
    """Daily summary interface"""
    if not st.session_state.active_user:
        st.warning("❌ Please create or select a user first.")
        return
        
    st.header("📊 Daily Summary")
    
    # Calculate today's nutrition using your existing logic
    user = st.session_state.active_user
    today = datetime.now().strftime("%Y-%m-%d")
    logs = [x for x in user["logs"] if x["timestamp"].startswith(today)]
    
    if not logs:
        st.info("📊 No food logged today.")
        return
    
    # Display summary metrics
    total_cal = sum(x["nutrition"]["calories"] for x in logs)
    total_pro = sum(x["nutrition"]["protein"] for x in logs)
    target_cal = daily_calories(user)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🔥 Calories", f"{total_cal:.0f}", f"{total_cal - target_cal:.0f}")
    with col2:
        st.metric("💪 Protein", f"{total_pro:.1f}g")
    with col3:
        progress = min(100, (total_cal / target_cal) * 100)
        st.metric("📈 Progress", f"{progress:.1f}%")

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
    
    st.subheader("🎯 Daily Targets")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("BMR", f"{bmr:.0f} kcal")
    with col2:
        st.metric("TDEE", f"{tdee:.0f} kcal")
    with col3:
        st.metric("Target", f"{target_cal:.0f} kcal")

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
                del st.session_state.users[st.session_state.active_user['name']]
                st.session_state.active_user = None
                st.rerun()
    
    # Main content area
    if hasattr(st.session_state, 'show_create_user') and st.session_state.show_create_user:
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
