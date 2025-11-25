import json
import streamlit as st
from datetime import datetime
import re
import os
import hashlib
import pandas as pd

# ----------------------------
# Page configuration
# ----------------------------
st.set_page_config(
    page_title="Smart Nutrition Tracker",
    page_icon="🍎",
    layout="wide"
)

# ----------------------------
# Load food database
# ----------------------------
@st.cache_data
def load_food_database():
    try:
        with open("ciqual_2020_foods.json", "r", encoding="utf-8") as f:
            foods = json.load(f)
        search_index = {food["names"]["en"].lower().strip(): food for food in foods}
        return foods, search_index
    except FileNotFoundError:
        st.error("❌ Food database not found.")
        return [], {}

foods, search_index = load_food_database()

# ----------------------------
# User and Central Dataset Handling
# ----------------------------
USERS_DIR = "user_data"
CENTRAL_DATASET = "all_users_dataset.json"
ADMIN_PASSWORD = "admin123"

def ensure_users_dir():
    if not os.path.exists(USERS_DIR):
        os.makedirs(USERS_DIR)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_user_file(username):
    username_hash = hashlib.sha256(username.lower().encode()).hexdigest()[:16]
    return os.path.join(USERS_DIR, f"{username_hash}.json")

def load_user_data(username):
    ensure_users_dir()
    file = get_user_file(username)
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_user_data(username, user_data):
    ensure_users_dir()
    file = get_user_file(username)
    with open(file, "w", encoding="utf-8") as f:
        json.dump(user_data, f, indent=2, ensure_ascii=False)
    update_central_dataset(username, user_data, "update")
    return True

def verify_password(username, password):
    user_data = load_user_data(username)
    if user_data:
        return user_data["auth"]["password_hash"] == hash_password(password)
    return False

def create_new_user(username, password, profile):
    user_data = {
        "auth": {"username": username, "password_hash": hash_password(password), "created_at": datetime.now().isoformat()},
        "profile": profile,
        "food_logs": [],
        "water_logs": []
    }
    save_user_data(username, user_data)
    update_central_dataset(username, user_data, "create")
    return True

# ----------------------------
# Central Dataset
# ----------------------------
def load_central_dataset():
    if os.path.exists(CENTRAL_DATASET):
        with open(CENTRAL_DATASET, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"users": {}, "statistics": {"total_users": 0, "total_food_logs": 0, "total_water_logs": 0, "last_updated": datetime.now().isoformat()}}

def save_central_dataset(dataset):
    dataset["statistics"]["last_updated"] = datetime.now().isoformat()
    with open(CENTRAL_DATASET, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

def update_central_dataset(username, user_data, action="update"):
    dataset = load_central_dataset()
    if action == "create":
        dataset["users"][username] = {
            "profile": user_data["profile"],
            "auth_info": {"hashed_password": user_data["auth"]["password_hash"], "created_at": user_data["auth"]["created_at"], "last_login": datetime.now().isoformat()},
            "statistics": {"food_logs_count": 0, "water_logs_count": 0, "last_activity": datetime.now().isoformat()},
            "food_logs": [],
            "water_logs": []
        }
    else:
        dataset["users"][username] = {
            "profile": user_data["profile"],
            "auth_info": {"hashed_password": user_data["auth"]["password_hash"], "created_at": user_data["auth"]["created_at"], "last_login": datetime.now().isoformat()},
            "statistics": {"food_logs_count": len(user_data.get("food_logs", [])), "water_logs_count": len(user_data.get("water_logs", [])), "last_activity": datetime.now().isoformat()},
            "food_logs": user_data.get("food_logs", []),
            "water_logs": user_data.get("water_logs", [])
        }
    dataset["statistics"]["total_users"] = len(dataset["users"])
    dataset["statistics"]["total_food_logs"] = sum(u["statistics"]["food_logs_count"] for u in dataset["users"].values())
    dataset["statistics"]["total_water_logs"] = sum(u["statistics"]["water_logs_count"] for u in dataset["users"].values())
    save_central_dataset(dataset)

# ----------------------------
# Streamlit Session State
# ----------------------------
if 'current_user' not in st.session_state: st.session_state.current_user = None
if 'user_data' not in st.session_state: st.session_state.user_data = None
if 'show_login' not in st.session_state: st.session_state.show_login = True
if 'show_create_user' not in st.session_state: st.session_state.show_create_user = False
if 'admin_logged_in' not in st.session_state: st.session_state.admin_logged_in = False
if 'recent_meal_logs' not in st.session_state: st.session_state.recent_meal_logs = []
if 'meal_summary' not in st.session_state: st.session_state.meal_summary = {"calories":0,"protein":0,"carbs":0,"fat":0}
if 'recent_water_logs' not in st.session_state: st.session_state.recent_water_logs = []

# ----------------------------
# Admin Panel
# ----------------------------
def show_admin_panel():
    st.header("🔐 Admin Panel")
    dataset = load_central_dataset()
    st.write("📊 Global Stats", dataset["statistics"])
    for username in dataset["users"]:
        st.write(f"👤 {username}")
    if st.button("Export Dataset as JSON"):
        dataset_json = json.dumps(dataset, indent=2, ensure_ascii=False)
        st.download_button("Download JSON", data=dataset_json, file_name="all_users_dataset.json", mime="application/json")

# ----------------------------
# User Login / Create UI
# ----------------------------
def show_user_login():
    st.header("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if verify_password(username, password):
            st.session_state.current_user = username
            st.session_state.user_data = load_user_data(username)
            st.success(f"Welcome {username}!")
        else:
            st.error("Invalid credentials")
    if st.button("Create Account"):
        st.session_state.show_create_user = True
        st.session_state.show_login = False

def show_user_creation():
    st.header("👤 Create Account")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    age = st.number_input("Age", 15, 100)
    weight = st.number_input("Weight (kg)", 30, 300)
    height = st.number_input("Height (cm)", 100, 250)
    gender = st.selectbox("Gender", ["male","female"])
    goal = st.selectbox("Goal", ["lose","maintain","gain"])
    activity = st.selectbox("Activity Level", ["sedentary","light","moderate","active","very active"])
    if st.button("Create Account"):
        profile = {"name": username,"age":age,"weight":weight,"height":height,"gender":gender,"goal":goal,"activity":activity}
        create_new_user(username,password,profile)
        st.success("Account created!")

# ----------------------------
# Main App Logic
# ----------------------------
if st.session_state.admin_logged_in:
    show_admin_panel()
elif st.session_state.show_create_user:
    show_user_creation()
elif st.session_state.show_login:
    show_user_login()
else:
    st.write(f"Hello {st.session_state.current_user}!")
