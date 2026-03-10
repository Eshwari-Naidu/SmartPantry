import json
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.multioutput import MultiOutputRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import joblib
import os

def load_data(json_path: str) -> pd.DataFrame:
    print(f"Loading dataset from {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    records = []
    for recipe in data:
        title = recipe.get('title', '')
        ingredients = " ".join(recipe.get('ingredients', []))
        
        # Combine title and ingredients into a single text block for the NLP model
        text_features = title + " " + ingredients
        
        calories = recipe.get('calories')
        protein = recipe.get('protein')
        fat = recipe.get('fat')
        
        # Only keep rows that have valid, non-null nutritional info
        if pd.notna(calories) and pd.notna(protein) and pd.notna(fat):
            # Basic outlier filtering (removing logically impossible data points)
            if calories < 5000 and protein < 300 and fat < 300: 
                records.append({
                    'text': text_features,
                    'calories': float(calories),
                    'protein': float(protein),
                    'fat': float(fat)
                })
                
    df = pd.DataFrame(records)
    print(f"Loaded {len(df)} valid recipes for training.")
    return df

def train_model():
    df = load_data('archive_extracted/full_format_recipes.json')
    
    # Target Variables: We want to predict these 3 things simultaneously
    X = df['text']
    y = df[['calories', 'protein', 'fat']]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.1, random_state=42)
    
    print("Building NLP Pipeline (TF-IDF + Random Forest)...")
    # TF-IDF converts words like "chicken" into mathematical importance weights
    # RandomForest learns the relationships between those weights and the calories
    # We limit max_features to 2000 and trees to 50 to keep the model fast and lightweight (<100MB)
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(stop_words='english', max_features=2000)),
        ('regressor', MultiOutputRegressor(RandomForestRegressor(n_estimators=50, max_depth=15, n_jobs=-1, random_state=42)))
    ])
    
    print("Training model... this may take 1-2 minutes...")
    pipeline.fit(X_train, y_train)
    
    print("Evaluating model...")
    y_pred = pipeline.predict(X_test)
    
    mae_calories = mean_absolute_error(y_test['calories'], y_pred[:, 0])
    mae_protein = mean_absolute_error(y_test['protein'], y_pred[:, 1])
    mae_fat = mean_absolute_error(y_test['fat'], y_pred[:, 2])
    
    print(f"Mean Absolute Error - Calories: {mae_calories:.1f} kcal")
    print(f"Mean Absolute Error - Protein: {mae_protein:.1f} g")
    print(f"Mean Absolute Error - Fat: {mae_fat:.1f} g")
    
    model_path = os.path.join('backend', 'app', 'services', 'nutrition_model.pkl')
    print(f"Saving trained model to {model_path}...")
    
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump(pipeline, model_path)
    
    print("Model successfully built and saved! You can now delete the extraction folder.")

if __name__ == "__main__":
    train_model()
