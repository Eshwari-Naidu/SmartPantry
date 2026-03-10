# backend/app/session_store.py

from typing import List, Dict, Any

# In-memory session store (resets when the backend restarts)
# This serves as a mock database for the user session logs

session_logs: List[Dict[str, Any]] = []

def log_recipe(recipe: Dict[str, Any], review: str, nutrition: Dict[str, float]):
    """
    Logs a recipe to the session history.
    Includes the recipe data, user's review rating, and the macro breakdown.
    """
    # Create an entry
    log_entry = {
         # "id": recipe.get("id"),
         "title": recipe.get("title", "Unknown"),
         "review": review, # 'love', 'like', 'dislike'
         "nutrition": nutrition, # {'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0}
         "servings": recipe.get("servings", 1)
    }
    session_logs.append(log_entry)
    
def get_session_logs() -> List[Dict[str, Any]]:
    return session_logs

def get_liked_recipes() -> List[str]:
    """Returns titles of all recipes marked as 'love' or 'like'."""
    return [
         log['title'] for log in session_logs 
         if log['review'] in ('love', 'like')
    ]
