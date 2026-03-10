from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]  # goes to project root: smartpantry/
PANTRY_PATH = BASE_DIR / "data" / "pantry.csv"

def save_pantry(pantry_df):
    pantry_df.to_csv(PANTRY_PATH, index=False)

def load_pantry():
    return pd.read_csv(BASE_DIR / "data" / "pantry.csv")

def load_recipes():
    data = {
        "recipe": ["Veg Omelette", "Paneer Butter Masala", "Chicken Stir Fry"],
        "meal": ["breakfast", "lunch", "dinner"],
        "difficulty": ["easy", "medium", "easy"],
        "type": ["healthy", "indulgent", "healthy"]
    }
    return pd.DataFrame(data)

if __name__ == "__main__":
    print(load_pantry())
    print(load_recipes())
