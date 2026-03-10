from pydantic import BaseModel
import pandas as pd
from backend.app.services.constraints_gemini import interpret_constraints
from backend.app.services.improve_gemini import improve_recipe_gemini
from fastapi import FastAPI, Query
from typing import List, Optional
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import joinedload

from backend.app.db import SessionLocal
from backend.app.models import Recipe, RecipeIngredient
from backend.app.data_loader import load_pantry
from backend.app.services.recommend import recommend_recipes, recommend_from_constraints

from fastapi import HTTPException
from backend.app.data_loader import save_pantry
from backend.app.services.serializers import recipe_to_dict
from backend.app.services.pantry_update import deduct_ingredients
from backend.app.session_store import log_recipe, get_session_logs, get_liked_recipes
from backend.app.services.ai_helpers import (
    generate_full_recipe,
    generate_nutritional_insights,
    suggest_pantry_additions
)

app = FastAPI(title="SmartPantry API")

@app.get("/")
def read_root():
    return {"message": "Welcome to SmartPantry API"}

@app.get("/pantry")
def get_pantry():
    pantry = load_pantry()
    # Convert to list of dicts
    return JSONResponse(content=jsonable_encoder(pantry.to_dict(orient="records")))

class PantryItem(BaseModel):
    ingredient: str
    quantity: float
    unit: str

@app.post("/pantry")
def add_pantry_item(item: PantryItem):
    pantry = load_pantry()
    item_name = item.ingredient.strip().lower()
    
    # Check if exists
    if item_name in pantry['ingredient'].values:
        pantry.loc[pantry['ingredient'] == item_name, 'quantity'] += item.quantity
        # Optional: handle unit mismatch nicely, here we just update qty for simplicity
    else:
        new_row = pd.DataFrame([{"ingredient": item_name, "quantity": item.quantity, "unit": item.unit.strip().lower()}])
        pantry = pd.concat([pantry, new_row], ignore_index=True)
    
    save_pantry(pantry)
    return JSONResponse(content={"message": f"Added {item_name} to pantry."})

@app.delete("/pantry/{ingredient}")
def remove_pantry_item(ingredient: str):
    pantry = load_pantry()
    item_name = ingredient.strip().lower()
    
    if item_name in pantry['ingredient'].values:
        pantry = pantry[pantry['ingredient'] != item_name]
        save_pantry(pantry)
        return JSONResponse(content={"message": f"Removed {item_name} from pantry."})
    else:
        raise HTTPException(status_code=404, detail="Ingredient not found in pantry.")

@app.get("/recommend")
def get_recommendations(
    exclude: Optional[List[str]] = Query(default=None),
    cuisine: Optional[List[str]] = Query(default=None),
    meal_type: Optional[str] = None,
    top_k: int = 5
):
    pantry = load_pantry()

    db = SessionLocal()
    try:
        recipes = (
            db.query(Recipe)
            .options(joinedload(Recipe.ingredients).joinedload(RecipeIngredient.ingredient))
            .all()
        )

        results = recommend_recipes(
            pantry_df=pantry,
            recipes=recipes,
            db=db,
            top_k=top_k,
            exclude_ingredients=exclude,
            preferred_cuisine=cuisine,
            meal_type=meal_type,
        )
    finally:
        db.close()

    return JSONResponse(content=jsonable_encoder({"recommendations": results}))

@app.post("/cook/{recipe_id}")
def cook_recipe(recipe_id: str):
    pantry = load_pantry()

    db = SessionLocal()
    recipe = (
        db.query(Recipe)
        .options(joinedload(Recipe.ingredients).joinedload(RecipeIngredient.ingredient))
        .filter(Recipe.id == recipe_id)
        .first()
    )
    db.close()

    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    rd = recipe_to_dict(recipe)

    try:
        updated = deduct_ingredients(pantry, rd)
        save_pantry(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return JSONResponse(content=jsonable_encoder({
        "message": f"Cooked {rd['title']}. Pantry updated.",
        "pantry_rows": len(updated)
    }))

class ImproveRequest(BaseModel):
    feedback: str

@app.post("/recipe/{recipe_id}/improve")
def improve_recipe_endpoint(recipe_id: str, req: ImproveRequest):
    db = SessionLocal()
    recipe = (
        db.query(Recipe)
        .options(joinedload(Recipe.ingredients).joinedload(RecipeIngredient.ingredient))
        .filter(Recipe.id == recipe_id)
        .first()
    )
    db.close()

    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    rd = recipe_to_dict(recipe)
    improved_recipe = improve_recipe_gemini(rd, req.feedback)
    
    return JSONResponse(content=jsonable_encoder({
        "original_recipe": rd,
        "improved_recipe": improved_recipe,
        "feedback": req.feedback
    }))


class LogRecipeRequest(BaseModel):
    recipe: dict
    review: str # love, like, dislike
    nutrition: dict

@app.post("/log_recipe")
def log_recipe_endpoint(req: LogRecipeRequest):
    pantry = load_pantry()
    
    # 1. Deduct from pantry
    try:
        updated = deduct_ingredients(pantry, req.recipe)
        save_pantry(updated)
    except Exception as e:
        # We might fail if quantities are wonky, just ignore for logging purposes in portfolio
        pass
        
    # 2. Log to session
    log_recipe(req.recipe, req.review, req.nutrition)
    return {"message": "Logged successfully"}


@app.get("/dashboard/metrics")
def get_dashboard_metrics():
    logs = get_session_logs()
    total_cals = sum(l.get("nutrition", {}).get("calories", 0) for l in logs)
    total_pro = sum(l.get("nutrition", {}).get("protein", 0) for l in logs)
    total_carbs = sum(l.get("nutrition", {}).get("carbs", 0) for l in logs)
    total_fat = sum(l.get("nutrition", {}).get("fat", 0) for l in logs)
    
    return {
        "recipes_logged": len(logs),
        "total_calories": total_cals,
        "macros": {
            "protein": total_pro,
            "carbs": total_carbs,
            "fat": total_fat
        },
        "logs": logs
    }


@app.get("/dashboard/insights")
def get_dashboard_insights():
    logs = get_session_logs()
    total_cals = sum(l.get("nutrition", {}).get("calories", 0) for l in logs)
    total_macros = {
        "protein": sum(l.get("nutrition", {}).get("protein", 0) for l in logs),
        "carbs": sum(l.get("nutrition", {}).get("carbs", 0) for l in logs),
        "fat": sum(l.get("nutrition", {}).get("fat", 0) for l in logs)
    }
    insights = generate_nutritional_insights(total_cals, total_macros)
    return {"insights": insights}


@app.get("/pantry/suggestions")
def get_pantry_suggestions():
    pantry = load_pantry()
    pantry_list = pantry['ingredient'].tolist()
    liked = get_liked_recipes()
    return {"suggestions": suggest_pantry_additions(pantry_list, liked)}


class GenerateRecipeRequest(BaseModel):
    recipe: dict
    constraints: str = ""

@app.post("/recipe/generate_instructions")
def generate_instructions_endpoint(req: GenerateRecipeRequest):
    rd = req.recipe
    title = rd.get("title", "Unknown")
    ingredients = rd.get("ingredients", [])
    result = generate_full_recipe(title, ingredients, req.constraints)
    return JSONResponse(content=jsonable_encoder(result))


class InterpretRequest(BaseModel):
    text: str

@app.post("/interpret")
def interpret(req: InterpretRequest):
    return JSONResponse(content=jsonable_encoder(interpret_constraints(req.text)))


class RecommendRequest(BaseModel):
    query: str
    servings: Optional[int] = None
    meal_type: Optional[str] = None
    difficulty: Optional[str] = None
    diet: Optional[str] = None
    top_k: int = 5


@app.post("/recommend")
def recommend_from_nl(req: RecommendRequest):
    """
    Main NL → recommendations endpoint.

    Flow:
      text -> interpret_constraints (Gemini) -> structured filters
           -> DB query + pantry matching + ranking -> top recipes.
    """
    # 1) Interpret natural language into structured constraints
    constraints = interpret_constraints(req.query) or {}

    # Override/augment with explicit API inputs
    if req.servings is not None:
        constraints["servings"] = req.servings
    if req.meal_type is not None:
        constraints["meal_type"] = req.meal_type
    if req.difficulty is not None:
        constraints["difficulty"] = req.difficulty
    if req.diet is not None:
        constraints["diet"] = req.diet
    constraints["top_k"] = int(req.top_k or constraints.get("top_k") or 5)

    # 2) Load pantry + DB session
    pantry = load_pantry()
    db = SessionLocal()
    try:
        recommendations = recommend_from_constraints(
            pantry_df=pantry,
            db=db,
            constraints=constraints,
        )
    finally:
        db.close()

    return JSONResponse(
        content=jsonable_encoder(
            {
                "constraints": constraints,
                "recipes": recommendations,
            }
        )
    )