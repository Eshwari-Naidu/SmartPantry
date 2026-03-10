# 🍳 SmartPantry

SmartPantry is an intelligent, full-stack recipe recommendation and pantry management engine. It completely reinvents how you figure out what to cook by analyzing the exact ingredients you currently have in your kitchen, predicting missing nutritional statistics using local Machine Learning, and utilizing Generative AI to act as your personal dietitian and sous-chef.

## ✨ Key Features
- **Dynamic Recipe Recommendation Engine:** Ranks thousands of recipes based on what ingredients you currently own, automatically calculating a "Coverage Percentage" to minimize your grocery trips.
- **Natural Language Filtering:** Tell the app "I want a light healthy dinner with no meat." The app translates this to structured JSON filters and uses **Semantic Concept Mapping** to automatically expand "meat" into specific exclusions like "venison", "bacon", and "duck."
- **Fuzzy Pantry Deductions:** Logs your meals and automatically deducts ingredients from your virtual pantry. Employs advanced token-intersection fuzzy matching so if a recipe calls for `"waxy potatoes"` but you only have `"potatoes"`, the system flawlessly handles the math.
- **AI-Powered "Sous-Chef":** Dynamically generates step-by-step cooking instructions on the fly and customizes them based on your strict dietary constraints (e.g. substituting butter for olive oil).
- **Premium Analytics Dashboard:** A gorgeous, glassmorphism-styled dashboard that tracks your session calories, visualizes your macronutrient breakdowns, and provides highly specific, personalized AI nutritional insights based on what you actually ate.

---

## 🧠 Data Science & Machine Learning Highlights
This project heavily leverages offline Machine Learning and NLP to provide instantaneous, offline results without relying entirely on expensive, rate-limited cloud APIs.

*   **Offline Nutritional Prediction (Random Forest):** 
    Not all scraped recipes contain calorie or macro data. Instead of constantly pinging an LLM API to guess missing data, this project features a custom Machine Learning pipeline (`ml_pipeline.py`). We trained a `scikit-learn` **Random Forest Regressor** on a dataset of 20,000+ Epicurious recipes. The model utilizes a **TF-IDF Vectorizer** to biologically map the `ingredients` and `title` text strings into mathematical weights, allowing the offline model to predict the Calorie, Protein, and Fat outputs in milliseconds with high accuracy.
*   **Semantic Concept Expansion:** 
    A robust NLP abstraction layer that translates broad human dietary constraints ("no nuts") into highly specific database filtering tokens ("almond", "walnut", "pecan").
*   **Fuzzy Token-Intersection Matching:** 
    A custom algorithm designed to overcome the brittle nature of string matching. It calculates the intersection of ingredient name tokens to map complex recipe requirements (e.g., *“3 pieces of sweet eating apple”*) to simple pantry inventory objects (*“Apple”*), ignoring adjectives and unit-mismatches.

---

## 🛠️ Technology Stack

### Frontend Architecture
The frontend is built for rapid data deployment while overriding basic elements with a custom injected **Dark Mode Glassmorphism CSS** theme for a premium, vibrant aesthetic.
*   `Streamlit` (Core UI framework)
*   `Requests` (REST API communication)
*   `Pandas` (Dataframe rendering)

### Backend Architecture
A decoupled, lightning-fast RESTful API structure that handles all heavy lifting, ML inference, and database management.
*   `FastAPI` (High-performance API framework)
*   `Uvicorn` (ASGI web server)
*   `Python 3.x`

### Database & Data Engineering
*   `SQLite` (Local file-based SQL database)
*   `SQLAlchemy` (Object-Relational Mapping to interact with the DB via pure Python)
*   `Pandas` (Heavy data sanitation and feature extraction for the pantry and ingredients)
*   `Numpy` (Vector math processing)

### Machine Learning & AI
*   `Scikit-Learn` (`RandomForestRegressor`, `TfidfVectorizer`, `Pipeline`, `MultiOutputRegressor`)
*   `Joblib` (For serializing and caching the trained ML `.pkl` model into RAM)
*   `Google Generative AI SDK` (Gemini Flash latest—used strictly for NL query intent parsing and dynamic recipe instruction generation).

---

## 🚀 How to Run Locally

Because the application uses a decoupled architecture, you must run the backend and frontend simultaneously in two separate terminals.

**1. Start the Backend server:**
```bash
# From the root directory, start the FastAPI server on port 8000
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

**2. Start the Frontend UI:**
```bash
# In a second terminal window, start the Streamlit application
streamlit run frontend/app.py
```
*The app will instantly open in your default browser at `http://localhost:8501`.*
