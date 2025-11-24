import streamlit as st
import json
from datetime import datetime
import re
from difflib import get_close_matches

# ----------------------------
# Utilities
# ----------------------------
def normalize_food_input(text):
    text = text.lower().strip()
    cooking_words = ["grilled", "roasted", "baked", "steamed", "fried", "cooked", "boiled", "raw", "fresh"]
    for word in cooking_words:
        text = re.sub(r'\b' + re.escape(word) + r'\b', '', text)
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
            weight = 100.0
            food_name = part
        food_name = normalize_food_input(food_name)
        if food_name:
            ingredients.append({"name": food_name, "weight": weight})
    return ingredients

# ----------------------------
# Food database helpers
# ----------------------------
@st.cache_data(show_spinner=False)
def load_foods_from_file(file_bytes):
    try:
        obj = json.loads(file_bytes.decode('utf-8'))
        foods = obj if isinstance(obj, list) else obj.get('foods', [])
        # Expecting list of dicts where each has 'names':{'en':...}, 'nutrition', 'group', 'id'
        return foods
    except Exception as e:
        st.error(f"Failed to load foods JSON: {e}")
        return []

def build_search_index(foods):
    index = {}
    for food in foods:
        name = food.get('names', {}).get('en', '') or food.get('name', '')
        if name:
            index[name.lower().strip()] = food
    return index

def is_basic_ingredient(food):
    food_name = (food.get('names', {}).get('en', '') or '').lower()
    complex_indicators = [",", "(", ")", "with", "and", "or", "canned", "packaged", "salad", "soup", "sauce", "sandwich", "pizza", "pasta", "stew", "curry"]
    for ind in complex_indicators:
        if ind in food_name:
            return False
    main_ingredients = ["chicken", "beef", "pork", "fish", "rice", "pasta", "potato", "vegetable", "fruit", "cheese"]
    found = sum(1 for m in main_ingredients if m in food_name)
    return found <= 1

def find_basic_ingredients(name, foods, limit=5):
    name = normalize_food_input(name)
    if not name:
        return []
    exact = []
    partial = []
    complex_matches = []
    for food in foods:
        fname = (food.get('names', {}).get('en', '') or '').lower()
        if not fname:
            continue
        basic = is_basic_ingredient(food)
        if name == fname and basic:
            exact.append(food)
        elif basic and (fname.startswith(name + " ") or fname.endswith(" " + name) or f" {name} " in f" {fname} "):
            partial.append(food)
        elif name in fname:
            complex_matches.append(food)
    results = exact + partial
    if results:
        return results[:limit]
    if complex_matches:
        return complex_matches[:2]
    return []

# ----------------------------
# Streamlit App
# ----------------------------
st.set_page_config(page_title="Smart Nutrition Tracker", layout='wide')
st.title("🍎 Smart Nutrition Tracker — Web Edition")

# Sidebar: Data and navigation
st.sidebar.header("Data & Controls")
uploaded = st.sidebar.file_uploader("Upload ciqual_2020_foods.json (optional)", type=['json'])
if uploaded:
    foods = load_foods_from_file(uploaded.getvalue())
else:
    # Minimal fallback database (small) so app still runs
    foods = [
        {"id":1, "names":{"en":"chicken breast"}, "nutrition":{"calories":165, "protein":31, "carbs":0, "fat":3.6}, "group":"meat, egg and fish"},
        {"id":2, "names":{"en":"white rice"}, "nutrition":{"calories":130, "protein":2.7, "carbs":28, "fat":0.3}, "group":"cereals and potatoes"},
        {"id":3, "names":{"en":"apple"}, "nutrition":{"calories":52, "protein":0.3, "carbs":14, "fat":0.2}, "group":"fruits, vegetables, legumes and nuts"}
    ]

search_index = build_search_index(foods)

# Users stored in session_state (ephemeral). Provide upload/download for portability.
if 'users' not in st.session_state:
    st.session_state['users'] = {}
if 'active_user' not in st.session_state:
    st.session_state['active_user'] = None

st.sidebar.subheader("Users backup")
users_file = st.sidebar.file_uploader("Upload users JSON (optional)", type=['json'], key='users_upload')
if users_file:
    try:
        st.session_state['users'] = json.loads(users_file.getvalue().decode('utf-8'))
        st.success('Users loaded into session (ephemeral).')
    except Exception as e:
        st.error(f'Failed to load users JSON: {e}')

if st.sidebar.button('Download users JSON'):
    data = json.dumps(st.session_state['users'], indent=2, ensure_ascii=False)
    st.sidebar.download_button('Click to download', data, file_name='nutrition_users.json')

page = st.sidebar.radio('Navigate', ['Home', 'Create/Switch User', 'Log Food', 'Daily Summary', 'Profile'])

# ----------------------------
# Helper: validate and calculations
# ----------------------------
def calculate_bmr(user):
    if user['gender']=='male':
        return 10*user['weight'] + 6.25*user['height'] - 5*user['age'] + 5
    else:
        return 10*user['weight'] + 6.25*user['height'] - 5*user['age'] -161

def calculate_tdee(user):
    activity_factors = {"sedentary":1.2, "light":1.375, "moderate":1.55, "active":1.725, "very active":1.9}
    return calculate_bmr(user)*activity_factors.get(user['activity'],1.2)

def daily_calories(user):
    base = calculate_tdee(user)
    if user['goal']=='lose':
        return base - 500
    if user['goal']=='gain':
        return base + 500
    return base

# ----------------------------
# Pages
# ----------------------------
if page == 'Home':
    st.markdown("This is a web-friendly port of your nutrition tracker.\n\nUse the sidebar to create a user, log food, and view summaries. Data is ephemeral (stored in session). Upload your `ciqual_2020_foods.json` for a full database.)")
    st.write(f"Loaded foods: {len(foods)}")

elif page == 'Create/Switch User':
    st.header('Create or Switch User')
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input('Username')
        age = st.number_input('Age', min_value=15, max_value=100, value=30)
        gender = st.selectbox('Gender', ['male','female'])
        weight = st.number_input('Weight (kg)', min_value=30.0, max_value=300.0, value=70.0)
        height = st.number_input('Height (cm)', min_value=100.0, max_value=250.0, value=175.0)
    with col2:
        goal = st.selectbox('Goal', ['maintain','lose','gain'])
        activity = st.selectbox('Activity', ['sedentary','light','moderate','active','very active'])
        create_btn = st.button('Create user')
        st.write('Or select an existing user:')
        existing = list(st.session_state['users'].keys())
        sel = st.selectbox('Existing users', ['']+existing)
        if sel:
            if st.button('Switch to selected'):
                st.session_state['active_user'] = st.session_state['users'][sel]
                st.success(f"Switched to {sel}")

    if create_btn:
        if not name:
            st.error('Username required')
        elif name in st.session_state['users']:
            st.warning('User already exists — switch instead')
        else:
            user = {
                'name': name,
                'age': int(age),
                'gender': gender,
                'weight': float(weight),
                'height': float(height),
                'goal': goal,
                'activity': activity,
                'logs': [],
                'created_at': datetime.now().isoformat()
            }
            st.session_state['users'][name] = user
            st.session_state['active_user'] = user
            st.success(f'Created and switched to {name}')

elif page == 'Log Food':
    st.header('Log Food (Basic ingredients preferred)')
    if not st.session_state['active_user']:
        st.info('Create or switch to a user first (sidebar → Create/Switch User)')
    else:
        st.write('Active user:', st.session_state['active_user']['name'])
        meal_input = st.text_input("What did you eat? e.g. '150g chicken and 50g rice' or 'chicken breast'", key='meal')
        if st.button('Parse & Log'):
            if not meal_input.strip():
                st.error('Please enter something to log')
            else:
                ingredients = improve_ingredient_parsing(meal_input)
                if not ingredients:
                    st.error('No ingredients found — try different phrasing')
                else:
                    totals = {'cal':0,'protein':0,'carbs':0,'fat':0}
                    logs = []
                    for ing in ingredients:
                        matches = find_basic_ingredients(ing['name'], foods)
                        if not matches:
                            st.warning(f"No matches for '{ing['name']}'. You can enter manual nutrition below.")
                            with st.expander(f"Manual entry for {ing['name']}"):
                                mcal = st.number_input('Calories per 100g', value=100.0, key=f"mcal_{ing['name']}")
                                mpro = st.number_input('Protein per 100g', value=0.0, key=f"mpro_{ing['name']}")
                                mcar = st.number_input('Carbs per 100g', value=0.0, key=f"mcar_{ing['name']}")
                                mfat = st.number_input('Fat per 100g', value=0.0, key=f"mfat_{ing['name']}")
                                if st.button(f"Log manual {ing['name']}", key=f"log_manual_{ing['name']}"):
                                    ratio = ing['weight']/100.0
                                    cal = mcal*ratio; pro=mpro*ratio; car=mcar*ratio; fat=mfat*ratio
                                    totals['cal']+=cal; totals['protein']+=pro; totals['carbs']+=car; totals['fat']+=fat
                                    log = {'food':ing['name']+' (manual)','grams':ing['weight'],'nutrition':{'calories':round(cal,1),'protein':round(pro,1),'carbs':round(car,1),'fat':round(fat,1)},'timestamp':datetime.now().isoformat()}
                                    st.session_state['active_user']['logs'].append(log)
                                    st.success(f"Logged manual {ing['name']}")
                        else:
                            # Auto-select first match (simpler UX). Allow user to choose if multiple.
                            if len(matches) > 1:
                                opts = {i+1: m.get('names',{}).get('en','') for i,m in enumerate(matches)}
                                choice = st.selectbox(f"Choose match for {ing['name']}", options=list(opts.keys()), format_func=lambda x: opts[x], key=f"choice_{ing['name']}")
                                selected = matches[choice-1]
                            else:
                                selected = matches[0]
                            ratio = ing['weight']/100.0
                            nutrition = selected.get('nutrition',{})
                            cal = nutrition.get('calories',0)*ratio
                            pro = nutrition.get('protein',0)*ratio
                            car = nutrition.get('carbs',0)*ratio
                            fat = nutrition.get('fat',0)*ratio
                            totals['cal']+=cal; totals['protein']+=pro; totals['carbs']+=car; totals['fat']+=fat
                            log = {'food':selected.get('names',{}).get('en',''), 'food_id':selected.get('id',0),'grams':ing['weight'],'nutrition':{'calories':round(cal,1),'protein':round(pro,1),'carbs':round(car,1),'fat':round(fat,1)},'timestamp':datetime.now().isoformat()}
                            st.session_state['active_user']['logs'].append(log)
                            st.success(f"Logged {log['food']} ({log['grams']}g)")
                    st.metric('Calories logged', round(totals['cal'],1))

elif page == 'Daily Summary':
    st.header('Today\'s Nutrition Summary')
    if not st.session_state['active_user']:
        st.info('Create or switch to a user first')
    else:
        user = st.session_state['active_user']
        today = datetime.now().strftime('%Y-%m-%d')
        logs = [x for x in user.get('logs',[]) if x.get('timestamp','').startswith(today)]
        if not logs:
            st.info('No food logged today')
            water_target_ml = user['weight']*35
            st.write(f"💧 Water target: {water_target_ml:.0f} ml")
        else:
            total_cal = sum(x['nutrition']['calories'] for x in logs)
            total_pro = sum(x['nutrition']['protein'] for x in logs)
            total_carbs = sum(x['nutrition']['carbs'] for x in logs)
            total_fat = sum(x['nutrition']['fat'] for x in logs)
            target_cal = daily_calories(user)
            st.write(f"🔥 Calories: {total_cal:.1f} / {target_cal:.1f}")
            st.progress(min(1.0, total_cal/target_cal) if target_cal>0 else 0.0)
            st.write(f"💪 Protein: {total_pro:.1f} g")
            st.write(f"🥖 Carbs: {total_carbs:.1f} g")
            st.write(f"🥑 Fat: {total_fat:.1f} g")
            st.subheader('Logged items')
            for l in logs:
                st.write(f"• {l['food']} — {l['grams']} g — {l['nutrition']['calories']} kcal")

elif page == 'Profile':
    st.header('User Profile')
    if not st.session_state['active_user']:
        st.info('Create or switch to a user first')
    else:
        u = st.session_state['active_user']
        st.write('Name:', u['name'])
        st.write('Age:', u['age'])
        st.write('Gender:', u['gender'])
        st.write('Weight:', u['weight'])
        st.write('Height:', u['height'])
        st.write('Goal:', u['goal'])
        bmr = calculate_bmr(u)
        tdee = calculate_tdee(u)
        st.write(f'BMR: {bmr:.0f} kcal — TDEE: {tdee:.0f} kcal')

# Footer: tips
st.markdown('---')
st.caption('Notes: Data stored in session (ephemeral). Upload your JSON database for richer food matching. You can download users JSON from the sidebar to save your data.')
