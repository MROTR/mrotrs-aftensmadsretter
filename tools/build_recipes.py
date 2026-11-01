#!/usr/bin/env python3
"""
Build & Nutrition Compiler for Aftensmadsretter (v2).

Reads:
- Aftensmadsretter/recipes_yaml/*.yaml (Structured YAML recipes)
- Aftensmadsretter/recipes/*.md (Legacy Markdown recipes not yet migrated to YAML, as fallback for the PWA)
- Aftensmadsretter/tools/nutrition_db.json

Outputs:
- Aftensmadsretter/webapp/recipes_data.js (Bundled JSON data for the mobile PWA)
- Aftensmadsretter/recipes/<id>.md (When --write-md is passed, updates Markdown views from YAML)
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

import yaml

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(TOOLS_DIR)
YAML_DIR = os.path.join(BASE_DIR, "recipes_yaml")
MD_DIR = os.path.join(BASE_DIR, "recipes")
WEBAPP_DIR = os.path.join(BASE_DIR, "webapp")
DB_PATH = os.path.join(TOOLS_DIR, "nutrition_db.json")


def normalize_utf8(text: str) -> str:
    return unicodedata.normalize("NFC", text)


# Cooked weight yield multipliers (raw -> cooked weight in g)
# Dry grains/legumes absorb water (2.2x - 2.6x); cooked meats/mushrooms lose moisture;
# most liquids/sauces are controlled at component level via `evaporation_factor`.
DEFAULT_COOKED_MULTIPLIERS: Dict[str, float] = {
    "ris": 2.5,
    "basmatiris": 2.5,
    "jasminris": 2.5,
    "brune ris": 2.5,
    "grødris": 2.8,
    "pasta": 2.2,
    "spaghetti": 2.2,
    "fuldkornspasta": 2.2,
    "nudler": 2.2,
    "ægnudler": 2.2,
    "risnudler": 2.2,
    "glasnudler": 2.3,
    "quinoa": 2.6,
    "couscous": 2.2,
    "bulgur": 2.4,
    "perlebyg": 2.5,
    "perlespelt": 2.4,
    "linser": 2.5,
    "røde linser": 2.5,
    "grønne linser": 2.4,
    "belugalinser": 2.4,
    "kikærter": 2.3,       # Dry chickpeas
    "kikærter_dåse": 1.0,  # Already hydrated
    "bønner_dåse": 1.0,
    "champignon": 0.75,    # Shrinks when sautéed
    "svampe": 0.75,
    "spinat": 0.85,
}

# Supplemental ingredients if missing in nutrition_db.json
SUPPLEMENTAL_INGREDIENTS: Dict[str, Dict[str, float]] = {
    "spidskommen": {"kcal": 375, "protein": 17.8, "fat": 22.3, "carb": 44.2, "fiber": 10.5},
    "stødt koriander": {"kcal": 298, "protein": 12.4, "fat": 17.8, "carb": 55.0, "fiber": 41.9},
    "kardemomme": {"kcal": 311, "protein": 10.8, "fat": 6.7, "carb": 68.5, "fiber": 28.0},
    "chiliflager": {"kcal": 282, "protein": 13.5, "fat": 14.3, "carb": 50.0, "fiber": 27.2},
    "chili": {"kcal": 40, "protein": 1.9, "fat": 0.4, "carb": 8.8, "fiber": 1.5},
    "gurkemeje": {"kcal": 312, "protein": 9.7, "fat": 3.3, "carb": 67.1, "fiber": 22.7},
    "garam masala": {"kcal": 325, "protein": 14.0, "fat": 14.0, "carb": 45.0, "fiber": 20.0},
    "karrypasta": {"kcal": 125, "protein": 3.5, "fat": 5.5, "carb": 15.0, "fiber": 3.0},
    "mynte": {"kcal": 44, "protein": 3.3, "fat": 0.7, "carb": 8.4, "fiber": 6.8},
    "laurbærblade": {"kcal": 313, "protein": 7.6, "fat": 8.4, "carb": 75.0, "fiber": 26.3},
    "peanuts": {"kcal": 585, "protein": 24.4, "fat": 49.7, "carb": 16.1, "fiber": 8.4},
    "æg": {"kcal": 143, "protein": 12.6, "fat": 9.5, "carb": 0.7, "fiber": 0.0},
}

UNIT_LABELS_DA = {
    "g": ("gram", "gram"),
    "kg": ("kg", "kg"),
    "ml": ("milliliter", "milliliter"),
    "dl": ("deciliter", "deciliter"),
    "l": ("liter", "liter"),
    "tsk": ("teskefuld", "teskefulde"),
    "spsk": ("spiseskefuld", "spiseskefulde"),
    "stk": ("", ""),
    "fed": ("fed", "fed"),
    "dåse": ("dåse", "dåser"),
    "håndfuld": ("håndfuld", "håndfulde"),
    "knivspids": ("knivspids", "knivspidser"),
    "bundt": ("bundt", "bundter"),
    "pakke": ("pakke", "pakker"),
    "": ("", ""),
}


def load_db() -> Dict[str, Any]:
    with open(DB_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    ingredients = {normalize_utf8(k).lower(): v for k, v in raw.get("ingredients", {}).items() if not k.startswith("__")}
    for k, v in SUPPLEMENTAL_INGREDIENTS.items():
        nk = normalize_utf8(k).lower()
        if nk not in ingredients:
            ingredients[nk] = v
    unit_weights = {normalize_utf8(k).lower(): v for k, v in raw.get("unit_weights", {}).items()}
    unit_weights.setdefault("håndfuld", 20)
    unit_weights.setdefault("fed", 4)
    return {"ingredients": ingredients, "unit_weights": unit_weights}


def resolve_raw_grams(ing: Dict[str, Any], db: Dict[str, Any]) -> float:
    if ing.get("grams_override") is not None:
        return float(ing["grams_override"])
    amount = ing.get("amount")
    if amount is None or amount == 0:
        return 0.0
    amount = float(amount)
    unit = (ing.get("unit") or "").lower()
    item = normalize_utf8(ing.get("item", "")).lower()
    db_entry = db["ingredients"].get(item, {})
    density = float(db_entry.get("density_g_per_ml", 1.0))

    if unit == "g":
        return amount
    if unit == "kg":
        return amount * 1000.0
    if unit == "ml":
        return amount * density
    if unit == "dl":
        return amount * 100.0 * density
    if unit == "l":
        return amount * 1000.0 * density
    if unit == "tsk":
        return amount * 5.0 * density
    if unit == "spsk":
        return amount * 15.0 * density
    if unit == "fed":
        return amount * float(db_entry.get("unit_weight_g", 4.0))
    if unit == "dåse":
        return amount * float(db_entry.get("unit_weight_g", 400.0))
    if unit == "håndfuld":
        return amount * float(db_entry.get("unit_weight_g", 15.0))
    if unit == "knivspids":
        return amount * 0.5
    if unit in ("stk", ""):
        if "unit_weight_g" in db_entry:
            return amount * float(db_entry["unit_weight_g"])
        if item in db["unit_weights"]:
            return amount * float(db["unit_weights"][item])
        for k, w in sorted(db["unit_weights"].items(), key=lambda x: len(x[0]), reverse=True):
            if k in item:
                return amount * float(w)
        return amount * 100.0
    return 0.0


def smart_kitchen_convert(amount: float, unit: str, display_unit: Optional[str], db_entry: Dict[str, Any]) -> Tuple[float, str]:
    """
    Converts canonical storage (ml, g, stk) to friendly Danish kitchen units (dl, spsk, tsk, dåse, g, ml)
    with sensible kitchen rounding (e.g., 11.25 ml [0.75 spsk] -> 2 tsk).
    """
    pref = (display_unit or unit or "").lower()
    u = (unit or "").lower()

    # Canned items stored in g or ml with display_unit="dåse"
    if pref == "dåse":
        can_w = float(db_entry.get("unit_weight_g", 400.0))
        cans = amount / can_w if can_w > 0 else amount
        return cans, "dåse"

    # Volume canonical (ml) -> kitchen volume (tsk, spsk, dl, ml)
    if u == "ml":
        ml = amount
        if pref in ("tsk", "spsk", "auto"):
            # Under 15 ml: prefer tsk (5 ml) unless it's an exact 0.5 spsk (7.5 ml) and pref=="spsk"
            if pref == "spsk":
                spsk = ml / 15.0
                # If spsk is close to whole or .5 (e.g. 0.5, 1, 1.5, 2, 2.5, 3), keep spsk;
                # otherwise if it's e.g. 0.75 spsk (11.25 ml) or < 7 ml, step down to tsk!
                nearest_half = round(spsk * 2) / 2.0
                if ml >= 7.0 and abs(spsk - nearest_half) < 0.08:
                    return nearest_half, "spsk"
                tsk = round(ml / 5.0 * 2) / 2.0
                return max(0.25, tsk), "tsk"
            else:
                # pref == "tsk"
                if ml >= 30.0 and abs((ml / 15.0) - round(ml / 15.0)) < 0.1:
                    return round(ml / 15.0), "spsk"
                tsk = round(ml / 5.0 * 2) / 2.0
                return max(0.25, tsk), "tsk"
        if pref == "dl":
            if ml < 45.0:
                # Step down small dl to spsk
                return round((ml / 15.0) * 2) / 2.0, "spsk"
            return ml / 100.0, "dl"
        return ml, "ml"

    return amount, pref or u


def format_number_da(val: float, use_comma: bool = False) -> str:
    if abs(val - round(val)) < 1e-6:
        s = str(int(round(val)))
    elif abs(val * 2 - round(val * 2)) < 1e-6:
        s = f"{val:.1f}"
    else:
        s = f"{val:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",") if use_comma else s


def format_ingredient_line(ing: Dict[str, Any], db_entry: Dict[str, Any], use_long_units: bool = True) -> str:
    label = ing.get("label") or ing.get("item", "")
    amount = ing.get("amount")
    range_text = ing.get("range_text")
    unit = ing.get("unit") or ""
    display_unit = ing.get("display_unit")
    prep = ing.get("prep")
    optional = ing.get("optional", False)

    if amount is None and not range_text:
        base = label
        if prep:
            base += f", {prep}"
        if optional and "valgfrit" not in base.lower():
            base += " (valgfrit)"
        return base

    disp_amt, disp_u = smart_kitchen_convert(float(amount or 0), unit, display_unit, db_entry)
    amt_str = range_text if range_text else format_number_da(disp_amt, use_comma=False)
    is_plural = (disp_amt != 1.0) or bool(range_text)

    if use_long_units and disp_u in UNIT_LABELS_DA:
        u_sing, u_plur = UNIT_LABELS_DA[disp_u]
        unit_str = u_plur if is_plural else u_sing
    else:
        unit_str = "" if disp_u == "stk" else disp_u

    parts = [amt_str]
    if unit_str:
        parts.append(unit_str)
    parts.append(label)
    line = " ".join(parts)
    if prep:
        line += f", {prep}"
    if optional and "valgfrit" not in line.lower():
        line += " (valgfrit)"
    return line


def compile_yaml_recipe(filepath: str, db: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    warnings: List[str] = []
    servings = int(data.get("servings", 4))
    ref_lookup: Dict[str, Dict[str, Any]] = {}

    compiled_components = []
    for comp in data.get("components", []):
        evap = float(comp.get("evaporation_factor", 1.0))
        comp_totals = {
            "raw_weight": 0.0,
            "cooked_weight": 0.0,
            "kcal": 0.0,
            "protein": 0.0,
            "carb": 0.0,
            "fat": 0.0,
            "fiber": 0.0,
        }
        compiled_ings = []

        for ing in comp.get("ingredients", []):
            item_key = normalize_utf8(ing["item"]).lower()
            db_entry = db["ingredients"].get(item_key)
            if not db_entry:
                warnings.append(f"[{data['id']}] Unknown ingredient item '{item_key}' in nutrition_db.json")
                db_entry = {"kcal": 0, "protein": 0, "fat": 0, "carb": 0, "fiber": 0}

            raw_g = resolve_raw_grams(ing, db)
            hydration_mult = float(db_entry.get("hydration_factor", DEFAULT_COOKED_MULTIPLIERS.get(item_key, 1.0)))
            # Apply hydration if dry grain/legume, otherwise apply component evaporation if liquid/sauce
            if hydration_mult != 1.0:
                cooked_g = raw_g * hydration_mult
            else:
                cooked_g = raw_g * evap

            macros = {
                k: (raw_g / 100.0) * float(db_entry.get(k, 0.0))
                for k in ("kcal", "protein", "carb", "fat", "fiber")
            }

            # Ignore trace spice/salt macros when amount is null or negligible (<2g spices can still count accurately)
            comp_totals["raw_weight"] += raw_g
            comp_totals["cooked_weight"] += cooked_g
            for k in macros:
                comp_totals[k] += macros[k]

            compiled_ing = {
                "ref": ing.get("ref"),
                "item": item_key,
                "label": ing.get("label") or ing["item"],
                "amount": ing.get("amount"),
                "range_text": ing.get("range_text"),
                "unit": ing.get("unit") or "",
                "display_unit": ing.get("display_unit") or ing.get("unit") or "",
                "unit_weight_g": float(db_entry.get("unit_weight_g", 400.0 if ing.get("display_unit") == "dåse" else 100.0)),
                "frida_id": db_entry.get("frida_id"),
                "source": db_entry.get("source", "custom"),
                "aisle": db_entry.get("aisle", "kolonial"),
                "prep": ing.get("prep"),
                "optional": bool(ing.get("optional", False)),
                "scaling": ing.get("scaling", "linear"),
                "raw_g": round(raw_g, 1),
                "cooked_g": round(cooked_g, 1),
                "macros": {k: round(v, 1) for k, v in macros.items()},
                "formatted_md": format_ingredient_line(ing, db_entry, use_long_units=True),
            }
            compiled_ings.append(compiled_ing)
            if ing.get("ref"):
                ref_lookup[ing["ref"]] = compiled_ing

        compiled_components.append({
            "id": comp["id"],
            "title": comp["title"],
            "role": comp["role"],
            "default_enabled": bool(comp.get("default_enabled", True)),
            "evaporation_factor": evap,
            "totals": {k: round(v, 1) for k, v in comp_totals.items()},
            "ingredients": compiled_ings,
        })

    # Pre-calculate standard summary variants for Markdown & quick overview
    variants = build_nutrition_variants(compiled_components, servings)

    compiled_recipe = {
        "id": data["id"],
        "title": data["title"],
        "format": "yaml_v2",
        "source": data.get("source", ""),
        "image": data.get("image", ""),
        "servings": servings,
        "standard_kcal_per_portion": int(data.get("standard_kcal_per_portion", 650)),
        "time": data.get("time", {}),
        "tags": data.get("tags", []),
        "notes": data.get("notes", ""),
        "components": compiled_components,
        "steps": data.get("steps", []),
        "ref_lookup": ref_lookup,
        "variants": variants,
    }
    return compiled_recipe, warnings


def sum_component_list(comps: List[Dict[str, Any]]) -> Dict[str, float]:
    res = {"raw_weight": 0.0, "cooked_weight": 0.0, "kcal": 0.0, "protein": 0.0, "carb": 0.0, "fat": 0.0, "fiber": 0.0}
    for c in comps:
        for k in res:
            res[k] += c["totals"][k]
    return res


def build_nutrition_variants(components: List[Dict[str, Any]], servings: int) -> List[Dict[str, Any]]:
    base_comps = [c for c in components if c["role"] == "base"]
    default_comps = [c for c in components if c["default_enabled"]]
    all_comps = components

    variants = []

    def add_variant_rows(label_prefix: str, comps: List[Dict[str, Any]], include_per_100: bool = False):
        t = sum_component_list(comps)
        if t["cooked_weight"] <= 0:
            return
        if include_per_100:
            factor_100 = 100.0 / t["cooked_weight"]
            variants.append({
                "name": f"{label_prefix} (pr. 100 g spiseklar)",
                "raw_weight": round(t["raw_weight"] * factor_100),
                "cooked_weight": 100,
                "kcal": round(t["kcal"] * factor_100, 1),
                "protein": round(t["protein"] * factor_100, 1),
                "carb": round(t["carb"] * factor_100, 1),
                "fat": round(t["fat"] * factor_100, 1),
                "fiber": round(t["fiber"] * factor_100, 1),
            })
        variants.append({
            "name": f"{label_prefix} (pr. portion, 1/{servings})",
            "raw_weight": round(t["raw_weight"] / servings),
            "cooked_weight": round(t["cooked_weight"] / servings),
            "kcal": round(t["kcal"] / servings),
            "protein": round(t["protein"] / servings, 1),
            "carb": round(t["carb"] / servings, 1),
            "fat": round(t["fat"] / servings, 1),
            "fiber": round(t["fiber"] / servings, 1),
        })
        variants.append({
            "name": f"{label_prefix} (hele opskriften)",
            "raw_weight": round(t["raw_weight"]),
            "cooked_weight": round(t["cooked_weight"]),
            "kcal": round(t["kcal"]),
            "protein": round(t["protein"], 1),
            "carb": round(t["carb"], 1),
            "fat": round(t["fat"], 1),
            "fiber": round(t["fiber"], 1),
        })

    # 1. Default meal (Standard serveringsforslag)
    default_titles = " + ".join(c["title"].replace("Til ", "").lower() for c in default_comps)
    add_variant_rows("Standard måltid", default_comps, include_per_100=True)

    # 2. If base differs from default (e.g. without rice/pasta/raita), show "Kun basisret"
    if len(base_comps) != len(default_comps) and base_comps:
        add_variant_rows("Kun basisret (uden tilbehør)", base_comps, include_per_100=True)

    # 3. If there are disabled optional components, show "Med alle tilvalg"
    if len(all_comps) > len(default_comps):
        add_variant_rows("Med alle tilvalg", all_comps, include_per_100=False)

    return variants


def render_step_for_markdown(step_text: str, ref_lookup: Dict[str, Dict[str, Any]]) -> str:
    def repl(match):
        ref = match.group(1)
        ing = ref_lookup.get(ref)
        if not ing:
            return ref
        return ing["label"].lower() if not ing["label"][0].isupper() else ing["label"]
    return re.sub(r"\{([a-z0-9_]+)\}", repl, step_text)


def generate_markdown_from_compiled(recipe: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# {recipe['title']}\n")
    if recipe.get("image"):
        lines.append(f"![{recipe['id']}]({recipe['image']})\n")

    if recipe.get("source"):
        lines.append(f"* Kilde: {recipe['source']}")
    lines.append(f"* Antal: **{recipe['servings']} pers.**")
    t = recipe.get("time", {})
    if t.get("total_min"):
        lines.append(f"* Tid i alt: **{t['total_min']} min.**")
    if t.get("active_min"):
        lines.append(f"* Arbejdstid: **{t['active_min']} min.**")
    lines.append("")

    # Nutrition Section
    lines.append("## Vejledende næringsindhold")
    lines.append("Beregnede tal fra struktureret YAML-opskrift (både råvægt og estimeret spiseklar vægt efter vandoptag/fordampning).\n")

    headers = ["Variant", "Råvægt (g)", "Spiseklar (ca., g)", "kcal", "Protein (g)", "Kulhydrat (g)", "Fedt (g)", "Kostfibre (g)"]
    rows = []
    for v in recipe["variants"]:
        rows.append([
            v["name"],
            str(v["raw_weight"]),
            str(v["cooked_weight"]),
            f"{v['kcal']:.1f}" if isinstance(v["kcal"], float) else str(v["kcal"]),
            f"{v['protein']:.1f}",
            f"{v['carb']:.1f}",
            f"{v['fat']:.1f}",
            f"{v['fiber']:.1f}",
        ])

    col_widths = [max(len(headers[i]), max((len(r[i]) for r in rows), default=0)) + 2 for i in range(len(headers))]
    header_line = "|" + "|".join(
        f" {headers[i]} ".ljust(col_widths[i]) if i == 0 else f" {headers[i]} ".rjust(col_widths[i])
        for i in range(len(headers))
    ) + "|"
    sep_line = "|" + "|".join(
        f" {'-' * (col_widths[i] - 2)} " if i == 0 else f" {'-' * (col_widths[i] - 3)}: "
        for i in range(len(headers))
    ) + "|"
    lines.append(header_line)
    lines.append(sep_line)
    for r in rows:
        lines.append("|" + "|".join(
            f" {r[i]} ".ljust(col_widths[i]) if i == 0 else f" {r[i]} ".rjust(col_widths[i])
            for i in range(len(headers))
        ) + "|")
    lines.append("")
    if recipe.get("notes"):
        lines.append(f"Antagelser (kort): {recipe['notes']}\n")

    # Ingredients Section
    lines.append("## Ingredienser")
    for comp in recipe["components"]:
        lines.append(f"### {comp['title']}")
        for ing in comp["ingredients"]:
            lines.append(f"- [ ] {ing['formatted_md']}")
        lines.append("")

    # Steps Section
    lines.append("## Fremgangsmåde")
    for idx, step_group in enumerate(recipe["steps"]):
        if idx > 0 and step_group.get("section"):
            lines.append(f"### {step_group['section']}")
        for item in step_group.get("items", []):
            rendered = render_step_for_markdown(item, recipe["ref_lookup"])
            lines.append(f"- [ ] {rendered}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def parse_legacy_markdown_recipe(filepath: str) -> Optional[Dict[str, Any]]:
    """Parses not-yet-migrated .md recipes so the PWA displays all dishes in the collection."""
    filename = os.path.basename(filepath)
    if filename in ("liste-af-retter.md", "nutrition-summary.md"):
        return None
    recipe_id = filename[:-3]

    with open(filepath, "r", encoding="utf-8") as f:
        text = normalize_utf8(f.read())

    lines = text.splitlines()
    title = recipe_id.replace("-", " ").capitalize()
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break

    img_match = re.search(r"!\[[^\]]*\]\(([^)]+)\)", text)
    image = img_match.group(1) if img_match else ""

    source_match = re.search(r"\*\s*Kilde:\s*(.+)", text)
    source = source_match.group(1).strip() if source_match else ""

    servings = 4
    serv_match = re.search(r"\*\s*Antal:\s*[^\d]*(\d+)", text)
    if serv_match:
        servings = int(serv_match.group(1))

    time_total = ""
    t_match = re.search(r"\*\s*Tid i alt:\s*\*\*([^*]+)\*\*", text)
    if t_match:
        time_total = t_match.group(1).replace("min.", "").strip()

    # Extract per-100g or per-portion from markdown table if present
    kcal_portion = 600
    protein_portion = 20.0
    carb_portion = 65.0
    fat_portion = 20.0
    fiber_portion = 8.0
    weight_portion = 450

    for line in lines:
        if line.strip().startswith("|") and ("portion" in line.lower() or "1/" in line.lower()):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 7:
                try:
                    weight_portion = float(cells[1])
                    kcal_portion = float(cells[2])
                    protein_portion = float(cells[3])
                    carb_portion = float(cells[4])
                    fat_portion = float(cells[5])
                    fiber_portion = float(cells[6])
                    break
                except ValueError:
                    pass

    # Extract ingredient sections
    components = []
    in_ing = False
    in_steps = False
    current_comp = {"id": "main_base", "title": "Ingredienser", "role": "base", "default_enabled": True, "ingredients": []}
    steps_groups = []
    current_steps = {"section": "Fremgangsmåde", "items": []}

    for line in lines:
        if line.startswith("## Ingredienser"):
            in_ing = True
            in_steps = False
            continue
        elif line.startswith("## Fremgangsmåde"):
            if current_comp["ingredients"]:
                components.append(current_comp)
            in_ing = False
            in_steps = True
            continue
        elif line.startswith("## "):
            in_ing = False
            in_steps = False
            continue

        if in_ing:
            if line.startswith("### "):
                if current_comp["ingredients"]:
                    components.append(current_comp)
                sec_title = line[4:].strip()
                role = "carb" if "servering" in sec_title.lower() else ("side" if "raita" in sec_title.lower() else "base")
                current_comp = {
                    "id": re.sub(r"[^a-z0-9]+", "_", sec_title.lower()).strip("_"),
                    "title": sec_title,
                    "role": role,
                    "default_enabled": True,
                    "ingredients": [],
                }
            else:
                m = re.match(r"-\s*\[[ x]\]\s*(.+)", line.strip())
                if m:
                    raw = m.group(1).strip()
                    num_m = re.match(r"^(\d+(?:[.,]\d+)?)\s+(\S+)\s+(.+)$", raw)
                    if num_m:
                        amt = float(num_m.group(1).replace(",", "."))
                        unit = num_m.group(2)
                        lbl = num_m.group(3)
                    else:
                        amt = None
                        unit = ""
                        lbl = raw
                    current_comp["ingredients"].append({
                        "ref": None,
                        "item": lbl,
                        "label": lbl,
                        "amount": amt,
                        "range_text": None,
                        "unit": unit,
                        "prep": None,
                        "optional": "valgfrit" in raw.lower(),
                        "scaling": "linear",
                        "raw_g": 0,
                        "cooked_g": 0,
                        "macros": {"kcal": 0, "protein": 0, "carb": 0, "fat": 0, "fiber": 0},
                        "formatted_md": raw,
                    })

        if in_steps:
            if line.startswith("### "):
                if current_steps["items"]:
                    steps_groups.append(current_steps)
                current_steps = {"section": line[4:].strip(), "items": []}
            else:
                m = re.match(r"-\s*\[[ x]\]\s*(.+)", line.strip())
                if m:
                    current_steps["items"].append(m.group(1).strip())

    if current_steps["items"]:
        steps_groups.append(current_steps)

    if not components:
        return None

    # Assign estimated totals to first component for legacy recipes
    for idx, c in enumerate(components):
        if idx == 0:
            c["totals"] = {
                "raw_weight": round(weight_portion * servings),
                "cooked_weight": round(weight_portion * servings),
                "kcal": round(kcal_portion * servings),
                "protein": round(protein_portion * servings, 1),
                "carb": round(carb_portion * servings, 1),
                "fat": round(fat_portion * servings, 1),
                "fiber": round(fiber_portion * servings, 1),
            }
        else:
            c["totals"] = {"raw_weight": 0, "cooked_weight": 0, "kcal": 0, "protein": 0, "carb": 0, "fat": 0, "fiber": 0}

    return {
        "id": recipe_id,
        "title": title,
        "format": "legacy_md",
        "source": source,
        "image": image,
        "servings": servings,
        "standard_kcal_per_portion": 650,
        "time": {"total_min": time_total, "active_min": ""},
        "tags": ["markdown"],
        "notes": "Endnu ikke migreret til YAML v2 (viser eksisterende næringsdata fra Markdown).",
        "components": components,
        "steps": steps_groups,
        "ref_lookup": {},
        "variants": build_nutrition_variants(components, servings),
    }


def update_liste_af_retter(recipes: List[Dict[str, Any]]) -> None:
    lines = ["# Liste af retter\n"]
    for r in sorted(recipes, key=lambda x: x["title"].lower()):
        lines.append(f"- [{r['title']}]({r['id']}.md)")
    path = os.path.join(MD_DIR, "liste-af-retter.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("Updated Markdown: recipes/liste-af-retter.md")


def update_readme_recipe_list(recipes: List[Dict[str, Any]], yaml_count: int) -> None:
    readme_path = os.path.join(BASE_DIR, "README.md")
    if not os.path.exists(readme_path):
        return
    with open(readme_path, "r", encoding="utf-8") as f:
        text = f.read()

    # Update tree count
    text = re.sub(
        r"(├── recipes_yaml/\s+# ★ KILDEDATA \(Source of Truth\): )\d+( strukturerede YAML v2-opskrifter)",
        rf"\g<1>{yaml_count}\g<2>",
        text
    )

    # Update Opskrifter section
    sorted_recipes = sorted(recipes, key=lambda x: x["title"].lower())
    recipe_bullets = []
    for r in sorted_recipes:
        recipe_bullets.append(f"* [{r['title']}](recipes/{r['id']}.md) ([YAML](recipes_yaml/{r['id']}.yaml))")
    new_bullets = "\n".join(recipe_bullets)

    new_text = re.sub(
        r"(## Opskrifter \()\d+( retter\)\n\n).*?(?=\n\nSe også|\Z)",
        rf"\g<1>{len(recipes)}\g<2>{new_bullets}",
        text,
        flags=re.DOTALL
    )
    if new_text != text:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(new_text)
        print("Updated README: Aftensmadsretter/README.md")


def main():
    parser = argparse.ArgumentParser(description="Build Aftensmadsretter YAML -> PWA + Markdown")
    parser.add_argument("--write-md", action="store_true", help="Also write generated Markdown files for YAML recipes")
    parser.add_argument("--skip-image-sync", action="store_true", help="Skip auto-syncing external image URLs to Files/images/")
    args = parser.parse_args()

    # 0. Automatically sync and localize external images if present
    if not args.skip_image_sync:
        try:
            import sync_images
            sync_images.main()
        except Exception as e:
            print(f"Warning: sync_images failed: {e}")

    db = load_db()
    recipes: List[Dict[str, Any]] = []
    yaml_ids = set()
    all_warnings: List[str] = []

    if os.path.exists(YAML_DIR):
        for fname in sorted(os.listdir(YAML_DIR)):
            if not fname.endswith((".yaml", ".yml")):
                continue
            fpath = os.path.join(YAML_DIR, fname)
            compiled, warnings = compile_yaml_recipe(fpath, db)
            recipes.append(compiled)
            yaml_ids.add(compiled["id"])
            all_warnings.extend(warnings)

            if args.write_md:
                md_out = generate_markdown_from_compiled(compiled)
                md_path = os.path.join(MD_DIR, f"{compiled['id']}.md")
                with open(md_path, "w", encoding="utf-8") as mf:
                    mf.write(md_out)
                print(f"Updated Markdown: recipes/{compiled['id']}.md")

    # Include legacy Markdown recipes that haven't been migrated yet so the PWA has all dishes
    if os.path.exists(MD_DIR):
        for fname in sorted(os.listdir(MD_DIR)):
            if not fname.endswith(".md"):
                continue
            rid = fname[:-3]
            if rid in yaml_ids:
                continue
            legacy = parse_legacy_markdown_recipe(os.path.join(MD_DIR, fname))
            if legacy:
                recipes.append(legacy)

    # Sort: YAML v2 recipes first (alphabetical), then legacy recipes
    recipes.sort(key=lambda r: (0 if r["format"] == "yaml_v2" else 1, r["title"].lower()))

    if args.write_md:
        summary_lines = [
            "# Næringsindhold på tværs af retter (Standard måltid)\n",
            "Auto-genereret fra `recipes_yaml/*.yaml` med DTU Frida / custom næringsdata.\n",
            "| Ret | Fil | Pr. portion (kcal) | Spiseklar portion (g) | Pr. 100 g spiseklar (kcal) | Protein / portion (g) | Kulhydrat / portion (g) | Fedt / portion (g) | Kostfibre / portion (g) |",
            "| --- | --- | -----------------: | --------------------: | -------------------------: | --------------------: | ----------------------: | -----------------: | ----------------------: |",
        ]
        for r in sorted(recipes, key=lambda x: x["title"].lower()):
            v100 = r["variants"][0] if r.get("variants") else {}
            vport = r["variants"][1] if len(r.get("variants", [])) > 1 else v100
            summary_lines.append(
                f"| [{r['title']}]({r['id']}.md) | `{r['id']}.yaml` | "
                f"{vport.get('kcal', 0)} | {vport.get('cooked_weight', 0)} | {v100.get('kcal', 0)} | "
                f"{vport.get('protein', 0)} | {vport.get('carb', 0)} | {vport.get('fat', 0)} | {vport.get('fiber', 0)} |"
            )
        summary_path = os.path.join(MD_DIR, "nutrition-summary.md")
        with open(summary_path, "w", encoding="utf-8") as sf:
            sf.write("\n".join(summary_lines) + "\n")
        print("Updated Markdown: recipes/nutrition-summary.md")

        update_liste_af_retter(recipes)
        update_readme_recipe_list(recipes, len(yaml_ids))

    os.makedirs(WEBAPP_DIR, exist_ok=True)
    out_js_path = os.path.join(WEBAPP_DIR, "recipes_data.js")
    payload = {
        "generated_by": "tools/build_recipes.py",
        "yaml_count": len(yaml_ids),
        "total_count": len(recipes),
        "recipes": recipes,
    }
    with open(out_js_path, "w", encoding="utf-8") as f:
        f.write("window.AFTENSMAD_DATA = ")
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write(";\n")

    print(f"Built {len(recipes)} recipes ({len(yaml_ids)} YAML v2, {len(recipes) - len(yaml_ids)} legacy MD) -> {out_js_path}")
    if all_warnings:
        print("\nWarnings:")
        for w in all_warnings:
            print("  !", w)
        sys.exit(1)


if __name__ == "__main__":
    main()
