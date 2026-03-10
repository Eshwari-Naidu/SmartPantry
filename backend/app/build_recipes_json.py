import argparse
import ast
import csv
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

try:
    # New official Gemini SDK
    from google import genai
except Exception:  # pragma: no cover
    genai = None

BASE_DIR = Path(__file__).resolve().parents[2]  # smartpantry/
DEFAULT_INPUT = BASE_DIR / "JamieOliver_full.csv"
DEFAULT_OUTPUT = BASE_DIR / "data" / "recipes.json"
DEFAULT_CACHE = BASE_DIR / "data" / "jo_cuisine_cache.json"

if load_dotenv is not None:
    # Allow running this script without manually exporting env vars.
    load_dotenv(BASE_DIR / ".env")

# Keep these aligned with how you plan to filter cuisines in the app.
ALLOWED_CUISINES: List[str] = [
    "indian",
    "italian",
    "mexican",
    "chinese",
    "japanese",
    "thai",
    "korean",
    "vietnamese",
    "french",
    "greek",
    "spanish",
    "middle eastern",
    "mediterranean",
    "american",
    "british",
    "asian",
    "other",
]


FRACTIONS = {
    "½": 0.5,
    "¼": 0.25,
    "¾": 0.75,
    "⅓": 1 / 3,
    "⅔": 2 / 3,
    "⅛": 0.125,
    # replacement char sometimes appears from bad encodings; best-effort: treat as 1/2
    "�": 0.5,
}


UNIT_ALIASES = {
    # weight
    "g": ("g", 1.0),
    "gram": ("g", 1.0),
    "grams": ("g", 1.0),
    "kg": ("g", 1000.0),
    "kgs": ("g", 1000.0),
    "kilogram": ("g", 1000.0),
    "kilograms": ("g", 1000.0),
    "oz": ("g", 28.3495),
    "ounce": ("g", 28.3495),
    "ounces": ("g", 28.3495),
    "lb": ("g", 453.592),
    "lbs": ("g", 453.592),
    "pound": ("g", 453.592),
    "pounds": ("g", 453.592),
    # volume
    "ml": ("ml", 1.0),
    "millilitre": ("ml", 1.0),
    "millilitres": ("ml", 1.0),
    "l": ("ml", 1000.0),
    "litre": ("ml", 1000.0),
    "litres": ("ml", 1000.0),
    "cl": ("ml", 10.0),
    # spoons/cups (convert to ml)
    "tsp": ("ml", 5.0),
    "teaspoon": ("ml", 5.0),
    "teaspoons": ("ml", 5.0),
    "tbsp": ("ml", 15.0),
    "tablespoon": ("ml", 15.0),
    "tablespoons": ("ml", 15.0),
    "cup": ("ml", 240.0),
    "cups": ("ml", 240.0),
}


STOPWORDS = {
    "fresh",
    "organic",
    "higher-welfare",
    "free-range",
    "unsalted",
    "salted",
    "small",
    "medium",
    "large",
    "heaped",
    "level",
    "finely",
    "roughly",
    "thinly",
    "thickly",
    "chopped",
    "sliced",
    "diced",
    "grated",
    "crushed",
    "peeled",
    "optional",
}


def _safe_int_from_text(text: str, default: int = 2) -> int:
    m = re.search(r"\d+", str(text))
    if not m:
        return default
    try:
        return int(m.group(0))
    except Exception:
        return default


def normalize_difficulty(raw: str) -> Optional[str]:
    s = str(raw or "").strip().lower()
    if not s:
        return None
    if "super easy" in s or s == "easy":
        return "easy"
    if "not too tricky" in s or "not too difficult" in s or s == "medium":
        return "medium"
    if "challenge" in s or "a bit of a challenge" in s or s == "hard":
        return "hard"
    # fallback: keep only known values
    if s in {"easy", "medium", "hard"}:
        return s
    return None


def _qty_token_to_float(token: str) -> Optional[float]:
    token = token.strip()
    if not token:
        return None
    if token in FRACTIONS:
        return FRACTIONS[token]

    # handle forms like "1½" or "1�" (digit(s) followed by a fraction char)
    for ch, val in FRACTIONS.items():
        if token.endswith(ch):
            prefix = token[: -len(ch)].strip()
            if re.fullmatch(r"\d+(?:\.\d+)?", prefix or ""):
                return float(prefix) + float(val)

    # normalize unicode fractions inside token (e.g. "1½")
    for ch, val in FRACTIONS.items():
        if ch in token:
            token = token.replace(ch, f" {val} ")
    token = token.strip()

    # "1 1/2"
    m = re.match(r"^(\d+)\s+(\d+)\s*/\s*(\d+)$", token)
    if m:
        return float(m.group(1)) + float(m.group(2)) / float(m.group(3))

    # "1/2"
    m = re.match(r"^(\d+)\s*/\s*(\d+)$", token)
    if m:
        return float(m.group(1)) / float(m.group(2))

    # "1-2" or "1–2" -> take the first number (lower bound)
    m = re.match(r"^(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)$", token)
    if m:
        return float(m.group(1))

    # "1.6"
    m = re.match(r"^\d+(?:\.\d+)?$", token)
    if m:
        return float(token)

    return None


def _standardize_unit(unit: str) -> Optional[Tuple[str, float]]:
    u = str(unit or "").strip().lower().rstrip(".")
    if not u:
        return None
    return UNIT_ALIASES.get(u)


def _cleanup_ingredient_name(name: str) -> str:
    s = str(name or "").strip().lower()
    if not s:
        return ""

    # drop parentheticals (prep notes, weights, etc.)
    s = re.sub(r"\([^)]*\)", " ", s)
    # keep only the part before commas (prep often after commas)
    s = s.split(",")[0]

    # remove common leading fillers
    s = re.sub(r"^\s*(a|an)\s+", "", s)
    s = re.sub(r"^\s*of\s+", "", s)

    tokens = [t for t in re.split(r"\s+", s) if t]
    tokens = [t for t in tokens if t not in STOPWORDS]

    s = " ".join(tokens).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def parse_ingredients(raw: str) -> List[Dict[str, Any]]:
    """
    Parse JamieOliver_full ingredient items into SmartPantry schema:
    [{name, qty, unit, optional}]
    Units standardized to g/ml/pcs where possible.
    """
    try:
        items = ast.literal_eval(raw) if isinstance(raw, str) else []
    except Exception:
        items = []

    if not isinstance(items, list):
        return []

    out: List[Dict[str, Any]] = []
    for item in items:
        s = str(item or "").strip()
        if not s:
            continue

        # section headers like "GRAVY", "SALAD", etc.
        if re.fullmatch(r"[A-Z][A-Z\s\-]{2,}", s) or s.endswith(":"):
            continue

        s = s.replace("\u00a0", " ").strip()

        # If we have an explicit weight in parentheses, prefer it.
        paren_qty = None
        paren_unit = None
        m_paren = re.search(r"\(\s*(\d+(?:\.\d+)?)\s*(g|kg|ml|l)\s*\)", s.lower())
        if m_paren:
            paren_qty = float(m_paren.group(1))
            paren_unit = m_paren.group(2)

        optional = bool(re.search(r"\b(optional|to serve|to taste)\b", s.lower()))

        s_norm = s
        # normalize the replacement char at start (often 1/2)
        if s_norm.startswith("�"):
            s_norm = "1/2 " + s_norm[1:].lstrip()

        # pattern: "1 x 1.6kg whole duck"
        m_x = re.match(
            r"^\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*(kg|g|ml|l)\b(.*)$",
            s_norm.strip().lower(),
        )
        if m_x:
            mult = float(m_x.group(1))
            qty = float(m_x.group(2)) * mult
            unit = m_x.group(3)
            rest = m_x.group(4).strip()
            std = _standardize_unit(unit)
            if std:
                base_unit, factor = std
                qty = qty * factor
                name = _cleanup_ingredient_name(rest)
                if name:
                    out.append({"name": name, "qty": round(qty, 3), "unit": base_unit, "optional": optional})
                continue

        # tokenize for leading quantity/unit patterns
        tokens = re.split(r"\s+", s_norm.strip())
        qty: Optional[float] = None
        unit: Optional[str] = None
        name_tokens: List[str] = tokens[:]

        # quantity can be "1", "1/2", "½", "1 1/2"
        if tokens:
            # try "1 1/2" using first 3 tokens
            if len(tokens) >= 3:
                q3 = _qty_token_to_float(" ".join(tokens[:3]))
                if q3 is not None:
                    qty = q3
                    name_tokens = tokens[3:]
                else:
                    q1 = _qty_token_to_float(tokens[0])
                    if q1 is not None:
                        qty = q1
                        name_tokens = tokens[1:]
            else:
                q1 = _qty_token_to_float(tokens[0])
                if q1 is not None:
                    qty = q1
                    name_tokens = tokens[1:]

        # if a parenthetical weight exists, override qty/unit with that
        if paren_qty is not None and paren_unit is not None:
            qty = paren_qty
            unit = paren_unit
        else:
            # parse unit after qty
            if name_tokens:
                # skip qualifiers before the unit (e.g. "heaped teaspoons", "level tablespoons")
                while name_tokens and name_tokens[0].strip().lower().rstrip(".") in STOPWORDS:
                    name_tokens = name_tokens[1:]

                if name_tokens:
                    u = name_tokens[0].strip().lower().rstrip(".")
                    # support plural forms we already include in aliases
                    if u in UNIT_ALIASES:
                        unit = u
                        name_tokens = name_tokens[1:]
                    elif u.endswith("s") and u[:-1] in UNIT_ALIASES:
                        unit = u[:-1]
                        name_tokens = name_tokens[1:]

        # If no qty parsed, treat as 1 pcs (e.g. "1 onion" is parsed, but "onion" alone)
        if qty is None:
            qty = 1.0
            unit = unit or "pcs"

        std = _standardize_unit(unit) if unit else None
        base_unit = "pcs"
        if std:
            base_unit, factor = std
            qty = qty * factor
        else:
            # unknown unit: default to pcs
            base_unit = "pcs"

        name = _cleanup_ingredient_name(" ".join(name_tokens))
        if not name:
            continue

        out.append({"name": name, "qty": round(float(qty), 3), "unit": base_unit, "optional": optional})

    # merge duplicates (same name+unit) by summing qty
    merged: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for ing in out:
        key = (ing["name"], ing["unit"])
        if key not in merged:
            merged[key] = dict(ing)
        else:
            merged[key]["qty"] = round(float(merged[key]["qty"]) + float(ing["qty"]), 3)
            merged[key]["optional"] = bool(merged[key]["optional"] and ing["optional"])
    return list(merged.values())


def heuristic_cuisine(title: str, ingredients: Iterable[str]) -> Optional[str]:
    t = str(title or "").lower()
    joined = " ".join([t] + [str(x).lower() for x in ingredients])

    rules: List[Tuple[str, List[str]]] = [
        ("indian", ["tikka", "masala", "korma", "dal", "chana", "paneer", "garam masala", "naan", "chapati", "curry"]),
        ("italian", ["pasta", "risotto", "gnocchi", "parmig", "parmesan", "mozzarella", "pesto", "marinara", "prosciutto"]),
        ("mexican", ["taco", "quesadilla", "enchilada", "salsa", "tortilla", "guacamole", "chipotle"]),
        ("chinese", ["five-spice", "hoisin", "bok choy", "shaoxing", "szechuan", "schezwan"]),
        ("japanese", ["miso", "mirin", "dashi", "udon", "soba", "teriyaki", "wasabi"]),
        ("thai", ["lemongrass", "galangal", "kaffir", "pad thai", "thai basil", "fish sauce"]),
        ("korean", ["gochujang", "kimchi", "bulgogi", "gochugaru"]),
        ("vietnamese", ["pho", "nuoc mam", "rice paper", "banh mi"]),
        ("greek", ["feta", "oregano", "tzatziki", "halloumi"]),
        ("middle eastern", ["hummus", "tahini", "sumac", "za'atar", "falafel", "harissa"]),
        ("french", ["dijon", "béchamel", "bechamel", "confit", "bouillabaisse"]),
        ("spanish", ["paella", "chorizo", "smoked paprika", "pimenton"]),
    ]

    for cuisine, kws in rules:
        if any(kw in joined for kw in kws):
            return cuisine
    return None


def heuristic_meal_type(title: str, ingredients: Iterable[str]) -> str:
    """
    Guess meal_type ("breakfast", "lunch", "dinner") using simple rules.
    This is intentionally lightweight and avoids extra Gemini calls.
    """
    t = str(title or "").lower()
    joined = " ".join([t] + [str(x).lower() for x in ingredients])

    breakfast_kw = [
        "breakfast",
        "omelette",
        "fried eggs",
        "scrambled eggs",
        "granola",
        "porridge",
        "muesli",
        "pancake",
        "waffle",
        "toast",
        "smoothie",
        "overnight oats",
    ]

    lunch_kw = [
        "salad",
        "sandwich",
        "wrap",
        "burrito",
        "quesadilla",
        "soup",
        "burger",
        "toastie",
        "frittata",
    ]

    if any(kw in joined for kw in breakfast_kw):
        return "breakfast"
    if any(kw in joined for kw in lunch_kw):
        return "lunch"

    # Default bucket
    return "dinner"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_json(text: str) -> Any:
    """
    Best-effort extraction of JSON from model output.
    """
    if not text:
        raise ValueError("Empty model response")
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try to find a JSON array/object inside.
    m = re.search(r"(\[.*\]|\{.*\})", text, flags=re.DOTALL)
    if not m:
        raise ValueError("No JSON found in model response")
    return json.loads(m.group(1))


def gemini_classify_cuisines(
    items: List[Dict[str, Any]],
    model_name: str,
) -> Dict[str, str]:
    if genai is None:
        raise RuntimeError("google-genai is not installed or importable")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in environment/.env")

    client = genai.Client(api_key=api_key)

    prompt_obj = {
        "allowed_cuisines": ALLOWED_CUISINES,
        "task": (
            "Classify each recipe into ONE cuisine from allowed_cuisines. "
            "Return JSON only: an object mapping recipe_id -> cuisine. "
            "If unsure, use 'other'."
        ),
        "recipes": [
            {
                "recipe_id": it["recipe_id"],
                "title": it["title"],
                "ingredient_keywords": it["ingredient_keywords"],
            }
            for it in items
        ],
    }

    resp = client.models.generate_content(
        model=model_name,
        contents=json.dumps(prompt_obj, ensure_ascii=False),
    )
    data = _extract_json((resp.text or "").strip())
    if not isinstance(data, dict):
        raise ValueError("Model did not return a JSON object")

    out: Dict[str, str] = {}
    allowed = set(ALLOWED_CUISINES)
    for k, v in data.items():
        cuisine = str(v or "other").strip().lower()
        if cuisine not in allowed:
            cuisine = "other"
        out[str(k)] = cuisine
    return out


def stable_jo_id(url: str, title: str) -> str:
    # deterministic so reruns don't create new IDs
    seed = (str(url or "").strip() + "||" + str(title or "").strip()).encode("utf-8", errors="ignore")
    h = hashlib.sha1(seed).hexdigest()[:16]
    return f"jo_{h}"


def read_jo_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def build_recipes(
    rows: List[Dict[str, str]],
    cuisine_cache: Dict[str, str],
    use_gemini: bool,
    batch_size: int,
    model_name: str,
    max_gemini_calls: Optional[int],
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    recipes: List[Dict[str, Any]] = []
    to_classify: List[Dict[str, Any]] = []

    for row in rows:
        url = (row.get("recipe_urls") or "").strip()
        title = (row.get("recipe_name") or "").strip()
        recipe_id = stable_jo_id(url, title)

        raw_ingredients = row.get("ingredients") or ""
        ingredients_struct = parse_ingredients(raw_ingredients)
        ingredient_names = [i["name"] for i in ingredients_struct]

        cuisine = cuisine_cache.get(recipe_id)
        if not cuisine:
            cuisine = heuristic_cuisine(title, ingredient_names)

        if not cuisine:
            cuisine = "other"
            if use_gemini:
                # keep the prompt small: title + top few ingredient names
                to_classify.append(
                    {
                        "recipe_id": recipe_id,
                        "title": title,
                        "ingredient_keywords": ingredient_names[:10],
                    }
                )

        serves = _safe_int_from_text(row.get("serves", ""), default=2)
        difficulty = normalize_difficulty(row.get("difficulty", ""))
        meal_type = heuristic_meal_type(title, ingredient_names)

        recipes.append(
            {
                "id": recipe_id,
                "title": title,
                "difficulty": difficulty,
                "servings": serves,
                "cuisine": cuisine,
                "meal_type": meal_type,
                "diet": None,
                "ingredients": ingredients_struct,
            }
        )

    if use_gemini and to_classify:
        new_labels: Dict[str, str] = {}
        calls = 0
        for i in range(0, len(to_classify), batch_size):
            if max_gemini_calls is not None and calls >= max_gemini_calls:
                break
            batch = to_classify[i : i + batch_size]
            labels = gemini_classify_cuisines(batch, model_name=model_name)
            new_labels.update(labels)
            calls += 1

        # apply labels
        for r in recipes:
            rid = r["id"]
            if rid in new_labels:
                r["cuisine"] = new_labels[rid]
                cuisine_cache[rid] = new_labels[rid]

    return recipes, cuisine_cache


def merge_recipes(existing: List[Dict[str, Any]], new: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for r in existing:
        if isinstance(r, dict) and r.get("id"):
            by_id[str(r["id"])] = r
    for r in new:
        rid = str(r.get("id"))
        if not rid:
            continue
        # For Jamie Oliver imports (jo_* ids), always refresh the record on rebuild.
        if rid.startswith("jo_") or rid not in by_id:
            by_id[rid] = r
    # stable-ish ordering: keep existing first, then new
    out: List[Dict[str, Any]] = []
    seen = set()
    for r in existing:
        rid = str(r.get("id")) if isinstance(r, dict) else None
        if rid and rid in by_id and rid not in seen:
            out.append(by_id[rid])
            seen.add(rid)
    for r in new:
        rid = str(r.get("id"))
        if rid and rid in by_id and rid not in seen:
            out.append(by_id[rid])
            seen.add(rid)
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build/merge recipes.json from JamieOliver_full.csv with minimal Gemini calls.")
    parser.add_argument("--input", type=str, default=str(DEFAULT_INPUT), help="Path to JamieOliver_full.csv")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT), help="Path to data/recipes.json")
    parser.add_argument("--cache", type=str, default=str(DEFAULT_CACHE), help="Cuisine cache JSON path")
    parser.add_argument("--no-gemini", action="store_true", help="Do not call Gemini; unknown cuisines become 'other'")
    parser.add_argument("--batch-size", type=int, default=50, help="Gemini batch size (recipes per call)")
    parser.add_argument("--max-gemini-calls", type=int, default=None, help="Cap Gemini calls for a run")
    parser.add_argument("--model", type=str, default=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"), help="Gemini model name")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    output_path = Path(args.output)
    cache_path = Path(args.cache)

    if not input_path.exists():
        print(f"ERROR: input not found: {input_path}", file=sys.stderr)
        return 2

    existing = load_json(output_path, default=[])
    if not isinstance(existing, list):
        existing = []

    cache_payload = load_json(cache_path, default={"version": 1, "cuisines": {}})
    if not isinstance(cache_payload, dict):
        cache_payload = {"version": 1, "cuisines": {}}
    cuisine_cache = cache_payload.get("cuisines") or {}
    if not isinstance(cuisine_cache, dict):
        cuisine_cache = {}

    rows = read_jo_csv(input_path)

    new_recipes, cuisine_cache = build_recipes(
        rows=rows,
        cuisine_cache=cuisine_cache,
        use_gemini=not args.no_gemini,
        batch_size=max(1, int(args.batch_size)),
        model_name=str(args.model),
        max_gemini_calls=args.max_gemini_calls,
    )

    merged = merge_recipes(existing, new_recipes)
    save_json(output_path, merged)

    cache_payload["cuisines"] = cuisine_cache
    save_json(cache_path, cache_payload)

    print(f"Wrote {len(merged)} recipes to {output_path}")
    print(f"Cuisine cache size: {len(cuisine_cache)} ({cache_path})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())