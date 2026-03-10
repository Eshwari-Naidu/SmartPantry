import json
from pathlib import Path
from typing import Dict, Any

from sqlalchemy.orm import Session

from backend.app.db import Base, engine, SessionLocal
from backend.app.models import Recipe, Ingredient, RecipeIngredient

BASE_DIR = Path(__file__).resolve().parents[2]
RECIPES_JSON = BASE_DIR / "data" / "recipes.json"

def norm_list(val):
    # store lists as comma-separated strings (MVP)
    if isinstance(val, list):
        return ",".join([str(x).strip().lower() for x in val])
    if val is None:
        return None
    return str(val).strip().lower()

def norm_name(name: str) -> str:
    return str(name).strip().lower()

def create_tables():
    Base.metadata.create_all(bind=engine)

def seed():
    create_tables()

    with open(RECIPES_JSON, "r", encoding="utf-8") as f:
        recipes = json.load(f)

    db: Session = SessionLocal()
    try:
        # wipe existing data (safe for MVP)
        db.query(RecipeIngredient).delete()
        db.query(Ingredient).delete()
        db.query(Recipe).delete()
        db.commit()

        for r in recipes:
            recipe = Recipe(
                id=str(r["id"]),
                title=r["title"],
                difficulty=r.get("difficulty"),
                servings=r.get("servings"),
                cuisine=norm_list(r.get("cuisine")),
                meal_type=norm_list(r.get("meal_type")),
                diet=norm_list(r.get("diet")),
            )
            db.add(recipe)
            db.flush()  # ensures recipe exists

            # Merge duplicate ingredients (same normalized name) within a recipe
            merged_ings: Dict[str, Dict[str, Any]] = {}
            for ing in r.get("ingredients", []):
                ing_name = norm_name(ing["name"])
                if ing_name not in merged_ings:
                    merged_ings[ing_name] = {
                        "qty": float(ing.get("qty", 0)),
                        "unit": str(ing.get("unit", "")).strip().lower(),
                        "optional": bool(ing.get("optional", False)),
                    }
                else:
                    merged_ings[ing_name]["qty"] += float(ing.get("qty", 0))
                    merged_ings[ing_name]["optional"] = bool(
                        merged_ings[ing_name]["optional"]
                        and bool(ing.get("optional", False))
                    )

            for ing_name, ing_data in merged_ings.items():
                ingredient = db.query(Ingredient).filter_by(name=ing_name).first()
                if not ingredient:
                    ingredient = Ingredient(name=ing_name)
                    db.add(ingredient)
                    db.flush()

                ri = RecipeIngredient(
                    recipe_id=recipe.id,
                    ingredient_id=ingredient.id,
                    qty=float(ing_data.get("qty", 0)),
                    unit=str(ing_data.get("unit", "")).strip().lower(),
                    optional=bool(ing_data.get("optional", False)),
                )
                db.add(ri)

        db.commit()
        print("✅ Seeded recipes into SQLite:", engine.url)
    finally:
        db.close()

if __name__ == "__main__":
    seed()
