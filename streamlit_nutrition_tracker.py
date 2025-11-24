import streamlit as st
import json
from datetime import datetime

# -----------------------------
# Load foods dataset
# -----------------------------
with open("ciqual_2020_foods.json", "r", encoding="utf-8") as f:
    FOOD_DB = json.load(f)

# -----------------------------
# Initialize session state
# -----------------------------
if "users" not in st.session_state:
    st.session_state.users = []

if "active_user" not in st.session_state:
    st.session_state.active_user = None

# -----------------------------
# Helper functions
# -----------------------------
def calculate_tdee(user):
    # Simple TDEE calc
    weight, height, age = user["weight"], user["height"], user["age"]
    bmr = 10*weight + 6.25*height - 5*age + (5 if user["gender"]=="male" else -161)
    activity_factor = {"sedentary":1.2,"light":1.375,"moderate":1.55,"active":1.725,"very active":1.9}
    tdee = bmr * activity_factor.get(user.get("activity","moderate"),1.55)
    return tdee

def daily_calories(user):
    tdee = calculate_tdee(user)
    goal = user.get("goal","maintain")
    if goal=="lose":
        return tdee - 500
    elif goal=="gain":
        return tdee + 500
    else:
        return tdee

def log_food():
    st.subheader("🍽️ Log Food")
    if not st.session_state.active_user:
        st.warning("Please select a user first!")
        return

    food_input = st.text_input("Type food name (partial is fine):")
    gram_input = st.number_input("Grams:", min_value=1, value=100)
    if st.button("Add Food"):
        matches = [f for f in FOOD_DB if food_input.lower() in f["name"].lower()]
        if matches:
            food = matches[0]
            log_entry = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "food": food["name"],
                "grams": gram_input,
                "nutrition": {
                    "calories": food.get("calories",0)*(gram_input/100),
                    "protein": food.get("protein",0)*(gram_input/100),
                    "carbs": food.get("carbs",0)*(gram_input/100),
                    "fat": food.get("fat",0)*(gram_input/100),
                }
            }
            st.session_state.active_user["logs"].append(log_entry)
            st.success(f"Added {gram_input}g {food['name']} to {st.session_state.active_user['name']}'s log!")
        else:
            st.error("No matching food found.")

def show_users():
    st.subheader("👥 Registered Users")
    if not st.session_state.users:
        st.info("No users yet.")
    else:
        for u in st.session_state.users:
            st.write(f"- {u['name']} | {u['age']}y | {u['weight']}kg | {len(u['logs'])} logs")

def switch_user():
    st.subheader("🔄 Switch/Create User")
    username = st.text_input("Enter username:")
    if st.button("Switch/Create"):
        user = next((u for u in st.session_state.users if u["name"]==username), None)
        if user:
            st.session_state.active_user = user
            st.success(f"Switched to existing user → {username}")
        else:
            new_user = {
                "name": username,
                "age": 25,
                "gender": "female",
                "weight": 60,
                "height": 165,
                "goal": "maintain",
                "activity": "moderate",
                "logs": []
            }
            st.session_state.users.append(new_user)
            st.session_state.active_user = new_user
            st.success(f"Created and switched to new user → {username}")

def daily_summary():
    if not st.session_state.active_user:
        st.warning("No active user. Please select/create a user first.")
        return
    
    st.subheader("📊 Daily Summary")
    user = st.session_state.active_user
    today = datetime.now().strftime("%Y-%m-%d")
    logs = [x for x in user["logs"] if x["timestamp"].startswith(today)]
    
    target_cal = daily_calories(user)
    target_protein = 135  # placeholder, could be calculated

    total_cal = sum(x["nutrition"]["calories"] for x in logs)
    total_pro = sum(x["nutrition"]["protein"] for x in logs)
    total_carbs = sum(x["nutrition"]["carbs"] for x in logs)
    total_fat = sum(x["nutrition"]["fat"] for x in logs)

    st.metric("🔥 Calories", f"{total_cal:.0f} / {target_cal:.0f} kcal")
    st.progress(min(total_cal / target_cal, 1.0) if target_cal>0 else 0)
    
    st.metric("💪 Protein", f"{total_pro:.1f} / {target_protein:.1f} g")
    st.write(f"🥖 Carbs: {total_carbs:.1f} g  |  🥑 Fat: {total_fat:.1f} g")
    
    st.markdown("💧 **Hydration:** 2-3 L recommended today.")
    st.markdown("💡 **Tips:**")
    if total_cal < target_cal:
        st.markdown("- Plenty of calories left – eat balanced meals")
    else:
        st.markdown("- Calories goal reached, avoid extra snacking")
    if total_pro < target_protein:
        st.markdown("- Add more protein: chicken, fish, eggs, legumes")

def show_profile():
    if not st.session_state.active_user:
        st.warning("No active user. Please select/create a user first.")
        return
    user = st.session_state.active_user
    st.subheader(f"👤 {user['name']}'s Profile")
    st.write(user)

def delete_user():
    if not st.session_state.active_user:
        st.warning("No active user.")
        return
    if st.button(f"Delete {st.session_state.active_user['name']}"):
        st.session_state.users = [u for u in st.session_state.users if u != st.session_state.active_user]
        st.session_state.active_user = None
        st.success("User deleted.")

# -----------------------------
# Main UI
# -----------------------------
st.title("🍏 Smart Nutrition Tracker")
st.markdown("**Eat smart, live healthy!**")
st.markdown("💡 Tip: Log your meals daily and track your progress.")

menu = ["Home", "List Users", "Switch/Create User", "Log Food", "Daily Summary", "Show Profile", "Delete User"]
choice = st.radio("Navigation", menu)

if choice=="Home":
    st.subheader("Welcome to Smart Nutrition Tracker!")
    st.markdown("""
    🥗 Track your meals, calories, and macros easily  
    🏋️‍♀️ Set goals for weight loss, gain, or maintenance  
    💧 Stay hydrated and follow tips to eat smart
    """)
elif choice=="List Users":
    show_users()
elif choice=="Switch/Create User":
    switch_user()
elif choice=="Log Food":
    log_food()
elif choice=="Daily Summary":
    daily_summary()
elif choice=="Show Profile":
    show_profile()
elif choice=="Delete User":
    delete_user()
