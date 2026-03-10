import streamlit as st
import requests
import pandas as pd
import json

# Configuration
API_URL = "http://localhost:8000"

st.set_page_config(
    page_title="SmartPantry",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS ---
st.markdown("""
<style>
    /* Global Premium Dark Theme */
    .stApp {
        background-color: #121216 !important;
        color: #e0e0e0 !important;
    }
    
    /* Vibrant Gradients & Typography */
    .main-header {
        font-size: 3.5rem;
        font-weight: 900;
        background: -webkit-linear-gradient(45deg, #FF6B6B, #FFB86C);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
        letter-spacing: -1px;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #a0a0b0;
        margin-bottom: 2rem;
        font-weight: 300;
    }

    /* Input Styling */
    .stTextInput>div>div>input, .stSelectbox>div>div>div, .stNumberInput>div>div>input {
        background-color: #1e1e24 !important;
        color: #ffffff !important;
        border: 1px solid #3a3a4a !important;
        border-radius: 8px !important;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.1) !important;
    }
    .stTextInput>div>div>input:focus {
        border-color: #FF6B6B !important;
        box-shadow: 0 0 0 2px rgba(255, 107, 107, 0.2) !important;
    }

    /* Button Styling */
    .stButton>button {
        background: linear-gradient(90deg, #FF6B6B, #FF8E53) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        letter-spacing: 0.5px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 15px rgba(255, 107, 107, 0.4) !important;
        color: white !important;
    }

    /* Recipe Container Overrides */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: linear-gradient(145deg, #1e1e24, #2b2b36) !important;
        border: 1px solid #3a3a4a !important;
        border-radius: 16px !important;
        box-shadow: 0 8px 32px rgba(0,0,0,0.15) !important;
        transition: transform 0.2s ease !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        transform: translateY(-3px) !important;
        border-color: #FF6B6B !important;
    }

    /* Badges & Tags */
    .coverage-high { color: #00e676; font-weight: 800; text-shadow: 0 0 10px rgba(0,230,118,0.3); }
    .coverage-med { color: #FFB86C; font-weight: 800; }
    .coverage-low { color: #ff5252; font-weight: 800; }
    
    .ing-tag {
        display: inline-block;
        background-color: #2b2b36;
        color: #e0e0e0;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.9em;
        margin: 4px 6px 6px 0;
        border: 1px solid #3a3a4a;
        transition: border-color 0.2s;
    }
    .ing-tag:hover { border-color: #FF6B6B; }
    
    .ing-tag-missing {
        background-color: rgba(255, 107, 107, 0.1);
        color: #FF6B6B;
        border: 1px solid rgba(255, 107, 107, 0.3);
    }
    
    .dashboard-card {
        background: linear-gradient(145deg, #1e1e24, #2b2b36);
        padding: 24px;
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.15);
        text-align: center;
        border: 1px solid #3a3a4a;
        margin-bottom: 24px;
        transition: transform 0.2s ease;
    }
    .dashboard-card:hover {
        transform: translateY(-5px);
    }
    .dashboard-card h3 {
        color: #a0a0b0;
        font-size: 1.1rem;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 12px;
        margin-top: 0;
    }
    .dashboard-card h2 {
        font-size: 3rem;
        font-weight: 800;
        margin: 0;
        background: -webkit-linear-gradient(45deg, #FF6B6B, #FFB86C);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .macro-container {
        background-color: #2b2b36;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 16px;
        border-left: 5px solid #FF6B6B;
    }
    .macro-header {
        display: flex;
        justify-content: space-between;
        margin-bottom: 8px;
        color: #e0e0e0;
        font-weight: 600;
    }
    .macro-bar-bg {
        background-color: #1e1e24;
        border-radius: 8px;
        height: 12px;
        width: 100%;
        overflow: hidden;
    }
    .macro-bar-fill {
        height: 100%;
        background: linear-gradient(90deg, #FF6B6B, #FFB86C);
        border-radius: 8px;
        transition: width 1s ease-in-out;
    }
    .macro-value {
        color: #a0a0b0;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# --- State ---
if 'active_recipe' not in st.session_state:
    st.session_state.active_recipe = None
if 'generated_instructions' not in st.session_state:
    st.session_state.generated_instructions = None

def fetch_pantry():
    try:
        r = requests.get(f"{API_URL}/pantry")
        return r.json() if r.status_code == 200 else []
    except:
        return []

st.markdown('<h1 class="main-header">SmartPantry <span style="-webkit-text-fill-color: initial;">🍳</span></h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Discover delicious recipes tailored to your ingredients and preferences.</p>', unsafe_allow_html=True)


# --- Navigation ---
page = st.sidebar.radio("Navigation", ["Let's Cook", "Pantry", "Dashboard"])

if page == "Let's Cook":
    if st.session_state.active_recipe is None:
        st.header("1. Let's Cook")
        
        # Preferences
        st.subheader("Preferences")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            meal_type = st.selectbox("Meal Type", ["Any", "Breakfast", "Lunch", "Dinner"])
        with c2:
            difficulty = st.selectbox("Difficulty", ["Any", "Easy", "Medium", "Hard"])
        with c3:
            diet = st.selectbox("Health Goal", ["Any", "Healthy", "Indulgent"])
        with c4:
            servings = st.number_input("Servings", min_value=1, max_value=20, value=2)
            
        st.subheader("What are you craving? (Optional)")
        nl_query = st.text_input("Natural Language Query", placeholder="e.g. I want a light indian dinner")
        
        if st.button("🔍 Find Recipes", use_container_width=True, type="primary"):
            with st.spinner("Chef AI is matching your pantry..."):
                payload = {
                    "query": nl_query,
                    "servings": servings,
                    "top_k": 5
                }
                
                if meal_type != "Any": 
                    payload["meal_type"] = meal_type.lower()
                if difficulty != "Any": 
                    payload["difficulty"] = difficulty.lower()
                if diet != "Any": 
                    payload["diet"] = diet.lower()
                try:
                    response = requests.post(f"{API_URL}/recommend", json=payload)
                    response.raise_for_status()
                    recipes = response.json().get("recipes", [])
                    st.session_state.current_results = recipes
                except Exception as e:
                    st.error("Failed to fetch recipes.")

        # Show results if we have them in state
        if 'current_results' in st.session_state and st.session_state.current_results:
            st.markdown("---")
            for r in st.session_state.current_results:
                cov_pct = r.get("coverage_pct", 0)
                cov_class = "coverage-high" if cov_pct > 80 else ("coverage-med" if cov_pct > 50 else "coverage-low")
                nutrition = r.get("nutrition", {})
                time = nutrition.get("cook_time_mins", "?")
                cals = nutrition.get("calories", "?")
                
                with st.container(border=True):
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.subheader(r['title'])
                        
                        difficulty_str = str(r.get('difficulty') or 'N/A').title()
                        
                        rate_warning = " ⚠️ (API Rate Limited)" if nutrition.get("rate_limited") else ""
                        st.caption(f"⏱️ Cook Time: {time} mins | 🔥 {cals} kcal/serving{rate_warning} | Difficulty: {difficulty_str} | Servings: {r.get('servings', 'N/A')}")
                    with col_b:
                        st.markdown(f'<div style="text-align: right; font-size: 1.2em;">Match: <span class="{cov_class}">{cov_pct:.0f}%</span></div>', unsafe_allow_html=True)
                        if st.button("👨‍🍳 Cook", key=f"cook_view_{r['id']}"):
                            st.session_state.active_recipe = r
                            st.session_state.generated_instructions = None
                            st.rerun()
                            
                    # Missing ingredients preview
                    missing_req = r.get("missing_required", [])
                    if missing_req:
                        missing_names = [m.get('name', '') if isinstance(m, dict) else str(m) for m in missing_req]
                        st.markdown(f"**Missing:** {', '.join([name.title() for name in missing_names])}")

    else:
        # --- Cook View ---
        r = st.session_state.active_recipe
        st.header(f"👨‍🍳 Let's Cook: {r['title']}")
        
        if st.button("⬅️ Back to Recommendations"):
            st.session_state.active_recipe = None
            st.rerun()
            
        nutrition = r.get("nutrition", {})
        st.caption(f"⏱️ {nutrition.get('cook_time_mins', '?')} mins | Servings: {r.get('servings')} | "
                   f"🔥 {nutrition.get('calories', '?')} kcal | Pro: {nutrition.get('protein', '?')}g | Carbs: {nutrition.get('carbs', '?')}g | Fat: {nutrition.get('fat', '?')}g")
        
        st.subheader("Ingredients Required")
        for ing in r.get("ingredients", []):
            qty = f"{ing.get('qty', '')}"
            if qty.endswith(".0"): qty = qty[:-2]
            st.write(f"- {qty} {ing.get('unit', '')} **{ing.get('name', '')}**")
            
        st.markdown("---")
        
        st.subheader("Generate Instructions (AI)")
        constraints = st.text_input("Dietary Constraints / Substitutions (optional)", placeholder="e.g. I don't want to use butter")
        if st.button("✨ Generate Recipe"):
            with st.spinner("AI is writing the recipe..."):
                payload = {"recipe": r, "constraints": constraints}
                try:
                    res = requests.post(f"{API_URL}/recipe/generate_instructions", json=payload)
                    if res.status_code == 200:
                        st.session_state.generated_instructions = res.json()
                except Exception as e:
                    st.error("Generation failed.")
                    
        if st.session_state.generated_instructions:
            gen = st.session_state.generated_instructions
            st.success(f"**{gen.get('title', r['title'])}**")
            if gen.get('notes'): st.info(gen['notes'])
            for idx, step in enumerate(gen.get("instructions", [])):
                st.write(f"{idx+1}. {step}")
                
        st.markdown("---")
        st.subheader("Done Cooking? Log it!")
        st.write("How did you like it? Logging will deduct ingredients from your pantry and update your dashboard.")
        
        r1, r2, r3 = st.columns(3)
        def handle_log(review_str):
            payload = {
                "recipe": st.session_state.active_recipe,
                "review": review_str,
                "nutrition": st.session_state.active_recipe.get("nutrition", {})
            }
            res = requests.post(f"{API_URL}/log_recipe", json=payload)
            if res.status_code == 200:
                st.success("Recipe Logged! Pantry updated.")
                st.session_state.active_recipe = None
                st.session_state.generated_instructions = None
            else:
                st.error("Failed to log recipe.")
                
        if r1.button("Love it 👍👍"): handle_log("love")
        if r2.button("Liked it 👍"): handle_log("like")
        if r3.button("Disliked it 👎"): handle_log("dislike")


elif page == "Pantry":
    st.header("📦 Your Pantry")
    pantry_items = fetch_pantry()
    
    st.subheader("Current Stock")
    if pantry_items:
        for item in pantry_items:
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.markdown(f"<div class='pantry-item'>{item['ingredient'].title()}</div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='pantry-item'>{item['quantity']} {item['unit']}</div>", unsafe_allow_html=True)
            if c3.button("❌", key=f"del_{item['ingredient']}", help="Remove"):
                requests.delete(f"{API_URL}/pantry/{item['ingredient']}")
                st.rerun()
    else:
        st.info("Pantry is empty.")
        
    with st.expander("➕ Add Ingredient"):
        with st.form("add_pantry_form"):
            new_ing = st.text_input("Ingredient Name")
            new_qty = st.number_input("Quantity", min_value=0.0, value=1.0)
            new_unit = st.text_input("Unit (e.g. g, ml, pcs)", value="pcs")
            if st.form_submit_button("Add"):
                if new_ing.strip():
                    requests.post(f"{API_URL}/pantry", json={"ingredient": new_ing, "quantity": new_qty, "unit": new_unit})
                    st.rerun()
                    
    st.markdown("---")
    st.subheader("✨ AI Suggested Additions")
    st.write("Based on the recipes you've loved, consider picking these up on your next grocery trip:")
    if st.button("Get Suggestions"):
        with st.spinner("AI is analyzing your taste profile..."):
            try:
                res = requests.get(f"{API_URL}/pantry/suggestions")
                if res.status_code == 200:
                    suggs = res.json().get("suggestions", [])
                    for s in suggs:
                        st.success(f"🛒 {s}")
            except:
                st.error("Failed to load suggestions.")

elif page == "Dashboard":
    st.markdown('<h2 style="margin-bottom: 30px;">📊 Nutritional Dashboard</h2>', unsafe_allow_html=True)
    try:
        res = requests.get(f"{API_URL}/dashboard/metrics")
        if res.status_code == 200:
            data = res.json()
            c1, c2 = st.columns(2)
            c1.markdown(f'<div class="dashboard-card"><h3>Meals Cooked</h3><h2>{data.get("recipes_logged", 0)}</h2></div>', unsafe_allow_html=True)
            c2.markdown(f'<div class="dashboard-card"><h3>Total Calories</h3><h2>{data.get("total_calories", 0)} <span style="font-size:1.2rem;color:#a0a0b0;-webkit-text-fill-color:initial;">kcal</span></h2></div>', unsafe_allow_html=True)
            
            st.markdown('<h3 style="margin-top:20px; margin-bottom: 20px; color:#e0e0e0;">Macro Breakdown</h3>', unsafe_allow_html=True)
            macros = data.get("macros", {})
            
            def render_macro(name, current, target):
                pct = min(current / max(target, 1), 1.0) * 100
                return f'''
                <div class="macro-container">
                    <div class="macro-header">
                        <span>{name}</span>
                        <span class="macro-value">{current}g / {target}g</span>
                    </div>
                    <div class="macro-bar-bg">
                        <div class="macro-bar-fill" style="width: {pct}%;"></div>
                    </div>
                </div>
                '''

            st.markdown(render_macro("Protein", macros.get('protein', 0), 150), unsafe_allow_html=True)
            st.markdown(render_macro("Carbohydrates", macros.get('carbs', 0), 300), unsafe_allow_html=True)
            st.markdown(render_macro("Fats", macros.get('fat', 0), 80), unsafe_allow_html=True)
            
            st.markdown("<hr style='margin: 40px 0; border-color: #333;'>", unsafe_allow_html=True)
            st.markdown('<h3 style="margin-bottom: 20px; color:#e0e0e0;">🧠 AI Nutrition Insights</h3>', unsafe_allow_html=True)
            if st.button("✨ Generate Premium Insights", use_container_width=True):
                with st.spinner("Nutritionist AI is analyzing your intake..."):
                    ires = requests.get(f"{API_URL}/dashboard/insights")
                    if ires.status_code == 200:
                        insights = ires.json().get("insights", [])
                        for i in insights:
                            st.markdown(f"""
                            <div style="background-color: rgba(255, 107, 107, 0.1); border-left: 4px solid #FF6B6B; padding: 16px; border-radius: 0 8px 8px 0; margin-bottom: 12px; color: #e0e0e0; font-size: 1.05em; line-height: 1.5;">
                                💡 {i}
                            </div>
                            """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Could not load dashboard metrics. Ensure backend is running. {e}")
