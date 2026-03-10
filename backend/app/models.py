from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.app.db import Base

class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(String, primary_key=True)  # e.g. "poha_001"
    title = Column(String, nullable=False)
    difficulty = Column(String, nullable=True)   # easy/medium/complex
    servings = Column(Integer, nullable=True)

    cuisine = Column(String, nullable=True)      # store comma-separated for MVP
    meal_type = Column(String, nullable=True)    # comma-separated
    diet = Column(String, nullable=True)         # comma-separated
    
    # AI Estimation Cache
    cook_time_mins = Column(Integer, nullable=True)
    calories = Column(Integer, nullable=True)
    protein = Column(Integer, nullable=True)
    carbs = Column(Integer, nullable=True)
    fat = Column(Integer, nullable=True)

    ingredients = relationship("RecipeIngredient", back_populates="recipe", cascade="all, delete-orphan")


class Ingredient(Base):
    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)  # normalized lowercase singular

    recipes = relationship("RecipeIngredient", back_populates="ingredient", cascade="all, delete-orphan")


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recipe_id = Column(String, ForeignKey("recipes.id"), nullable=False)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"), nullable=False)

    qty = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    optional = Column(Boolean, default=False)

    recipe = relationship("Recipe", back_populates="ingredients")
    ingredient = relationship("Ingredient", back_populates="recipes")

    __table_args__ = (
        UniqueConstraint("recipe_id", "ingredient_id", name="uq_recipe_ingredient"),
    )
