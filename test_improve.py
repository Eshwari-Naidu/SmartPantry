import os
import sys

sys.path.insert(0, os.path.abspath('.'))

from backend.app.main import improve_recipe_endpoint, ImproveRequest

# Let's test with a recipe ID that should exist based on seed_recipes
# Usually they are like 'jo_1' or similar, let's find one first or just use jo_001 if we don't know
# Actually let's query the DB to get the first recipe id
from backend.app.db import SessionLocal
from backend.app.models import Recipe

def run_test():
    db = SessionLocal()
    first_recipe = db.query(Recipe).first()
    db.close()
    
    if not first_recipe:
        print("No recipes in the database.")
        sys.exit(1)
        
    recipe_id = first_recipe.id
    print(f"Testing improvement on recipe: {recipe_id} - {first_recipe.title}")
    
    req = ImproveRequest(feedback="Make it a spicy Indian style recipe without any eggs.")
    
    response = improve_recipe_endpoint(recipe_id, req)
    
    import json
    print(json.dumps(response.body.decode('utf-8'), indent=2))
    
if __name__ == "__main__":
    run_test()
