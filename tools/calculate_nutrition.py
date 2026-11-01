
import json
import os
import re
import argparse
import unicodedata

# Path config
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Aftensmadsretter root
RECIPES_DIR = os.path.join(BASE_DIR, "recipes")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nutrition_db.json")

def normalize_utf8(text):
    return unicodedata.normalize('NFC', text)

# Load DB
try:
    with open(DB_PATH, 'r', encoding='utf-8') as f:
        DB = json.load(f)
        # Normalize DB keys
        DB["ingredients"] = {normalize_utf8(k): v for k, v in DB["ingredients"].items()}
        DB["unit_weights"] = {normalize_utf8(k): v for k, v in DB["unit_weights"].items()}
except FileNotFoundError:
    print(f"Error: {DB_PATH} not found.")
    DB = {"unit_weights": {}, "ingredients": {}}

# Helper to normalize text
def normalize_key(name):
    name = normalize_utf8(name)
    name = name.lower().strip()
    return name

def get_ingredient_data(name):
    name = normalize_utf8(name)
    # Try exact match
    if name in DB["ingredients"]:
        return DB["ingredients"][name]
    
    # Try fuzzy / substring
    # E.g. "zittauerløg" should match "løg" if exact missing?
    # Or "rødløg" matches "løg" in my previous logic.
    
    best_match = None
    longest_len = 0
    
    # Pre-process name for matching
    name_norm = " " + name + " "
    
    for key in DB["ingredients"]:
        # Exact match or word boundary match
        # Simple check: is key inside name?
        # But we want to avoid "ris" matching "frisk"
        # So we check if key is in name surrounded by non-alphanumeric?
        # Or just use regex boundaries
        if re.search(r'\b' + re.escape(key) + r'\b', name):
            if len(key) > longest_len:
                longest_len = len(key)
                best_match = key
    
    if best_match:
        return DB["ingredients"][best_match]
    
    return None

def get_unit_weight(unit_name, item_name):
    unit_name = normalize_utf8(unit_name)
    item_name = normalize_utf8(item_name)
    
    # 1. Specialized handling for 'stk' (piece) or empty unit which depends on the item's specific weight
    if unit_name == "stk" or unit_name == "":
        keys = sorted(DB["unit_weights"].keys(), key=len, reverse=True)
        for k in keys:
            # Skip keys that are clearly units if they end up in this dict (though structure is shared)
            if k in ["stk", "dåse", "tsk", "spsk"]: continue
            
            if k in item_name:
                return DB["unit_weights"][k]

    # 2. Generic unit lookup (e.g. "dåse" -> 400g, "tsk" -> 5g)
    if unit_name in DB["unit_weights"]:
        return DB["unit_weights"][unit_name]
                
    return 0 # Unknown unit weight

def parse_amount(text):
    text = text.replace(',', '.')
    if '/' in text:
        try:
            n, d = text.split('/')
            return float(n)/float(d)
        except: pass
    if '-' in text or '–' in text:
        text = text.replace('–', '-')
        try:
            p = [float(x) for x in text.split('-') if x.strip()]
            if p: return sum(p)/len(p)
        except: pass
    
    try:
        return float(re.findall(r"[\d\.]+", text)[0])
    except:
        return 1.0

def parse_recipe(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    ingredients = []
    in_section = False
    
    for line in lines:
        line = normalize_utf8(line)
        if line.startswith("## Ingredienser"):
            in_section = True
            continue
        if line.startswith("## ") and in_section:
            in_section = False
            continue
            
        if in_section:
            m = re.match(r'- \[[ x]\] (.*)', line.strip())
            if m:
                raw = m.group(1).strip()
                # Simple parse
                parts = raw.split(' ')
                amount = 0
                if re.match(r'^\d', parts[0]):
                    amount = parse_amount(parts[0])
                    rest = parts[1:]
                else:
                    amount = 0 # Trace
                    rest = parts
                
                unit = ""
                name = ""
                
                if rest:
                    potential_unit = rest[0].lower().rstrip('.,s')
                    # Standardize unit
                    std_units = {
                        "g": "g", "gram": "g", "kg": "kg", 
                        "dl": "dl", "deciliter": "dl", "l": "l", "ml": "ml", "milliliter": "ml",
                        "tsk": "tsk", "teske": "tsk", "teskefuld": "tsk", "teskefulde": "tsk",
                        "spsk": "spsk", "spiseske": "spsk", "spiseskefuld": "spsk", "spiseskefulde": "spsk",
                        "dåse": "dåse", "dåser": "dåse", 
                        "stk": "stk", "fed": "fed"
                    }
                    if potential_unit in std_units:
                        unit = std_units[potential_unit]
                        name = " ".join(rest[1:])
                    else:
                        unit = "stk" # Implicit
                        name = " ".join(rest)
                
                name = name.strip(',. ')
                ingredients.append({"name": name, "amount": amount, "unit": unit, "raw": raw})

    # Calculate
    total_macros = {"kcal": 0, "protein": 0, "fat": 0, "carb": 0, "fiber": 0, "weight": 0}
    
    details = []
    
    for ing in ingredients:
        name = normalize_key(ing['name'])
        amount = ing['amount']
        unit = ing['unit']
        
        weight_g = 0
        
        if unit == 'g': weight_g = amount
        elif unit == 'kg': weight_g = amount * 1000
        elif unit == 'dl': weight_g = amount * 100
        elif unit == 'l': weight_g = amount * 1000
        elif unit == 'ml': weight_g = amount
        elif unit == 'tsk': weight_g = amount * 5
        elif unit == 'spsk': weight_g = amount * 15
        elif unit == 'fed': weight_g = amount * 5 # Garlic clove
        elif unit == 'dåse': weight_g = amount * 400 # Default can
        elif unit == 'stk':
            unit_w = get_unit_weight("stk", name)
            weight_g = amount * unit_w
            
        data = get_ingredient_data(name)
        
        if data and weight_g > 0:
            macros = {}
            for k in ["kcal", "protein", "fat", "carb", "fiber"]:
                val = (weight_g / 100.0) * data.get(k, 0)
                total_macros[k] += val
                macros[k] = val
            total_macros["weight"] += weight_g
            details.append({"name": name, "weight": weight_g, "macros": macros, "source": "DB"})
        else:
            details.append({"name": name, "weight": weight_g, "macros": {}, "source": "MISSING"})

    return total_macros, details

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate Nutrition for a recipe")
    parser.add_argument("file", help="Filename in recipes folder (e.g. dhal.md)")
    args = parser.parse_args()
    
    target_file = os.path.join(RECIPES_DIR, args.file)
    if not os.path.exists(target_file):
        print(f"File not found: {target_file}")
    else:
        totals, det = parse_recipe(target_file)
        print(f"--- Analysis for {args.file} ---")
        print(f"{'Ingredient':<30} | {'Weight':<8} | {'kcal':<6} | {'P':<5} | {'C':<5} | {'F':<5} | {'Fib':<5}")
        print("-" * 80)
        for d in det:
            w = f"{d['weight']:.0f}"
            if d['source'] == 'MISSING':
                 print(f"{d['name']:<30} | {w:<8} |   -    |   -   |   -   |   -   |   -   (MISSING)")
            else:
                 m = d['macros']
                 print(f"{d['name']:<30} | {w:<8} | {m['kcal']:<6.0f} | {m['protein']:<5.1f} | {m['carb']:<5.1f} | {m['fat']:<5.1f} | {m['fiber']:<5.1f}")
        
        print("-" * 80)
        t = totals
        print(f"{'TOTAL':<30} | {t['weight']:<8.0f} | {t['kcal']:<6.0f} | {t['protein']:<5.1f} | {t['carb']:<5.1f} | {t['fat']:<5.1f} | {t['fiber']:<5.1f}")
        
        if t['weight'] > 0:
            per_100 = {k: (v / t['weight']) * 100 for k,v in t.items()}
            print(f"{'Per 100g':<30} | {'100':<8} | {per_100['kcal']:<6.1f} | {per_100['protein']:<5.1f} | {per_100['carb']:<5.1f} | {per_100['fat']:<5.1f} | {per_100['fiber']:<5.1f}")

