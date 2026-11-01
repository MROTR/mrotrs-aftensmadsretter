# Copilot instructions (mrotrs-aftensmadsretter)

## What this repo is
- Dedicated repository for Danish dinner recipes (`recipes_yaml/`), nutrition calculation (DTU Frida + custom items), generated Markdown (`recipes/`), and a zero-dependency Mobile PWA (`webapp/`).

## Repository structure
- `recipes_yaml/*.yaml` – **Source of truth** for all recipes (structured YAML v2, kebab-case filenames)
- `schemas/recipe.schema.json` – JSON Schema for YAML v2 recipes
- `recipes/*.md` – Auto-generated Markdown recipe files + `nutrition-summary.md`
- `Files/images/` – Local optimized recipe images (`<id>.jpg`)
- `tools/` – Python compiler (`build_recipes.py`), DTU Frida + custom ingredient CLI (`frida_lookup.py`), image optimizer (`sync_images.py`), and `nutrition_db.json`
- `webapp/` – Zero-dependency Progressive Web App (PWA) deployed to GitHub Pages (`https://mrotr.github.io/mrotrs-aftensmadsretter/`)

## Recipe Workflow
1. **Always create or edit recipes in `recipes_yaml/<id>.yaml`** (never hand-edit generated tables in `recipes/<id>.md`).
2. **Filename & `id`**: lowercase kebab-case, transliterate Danish (`æ`->`ae`, `ø`->`oe`, `å`->`aa`, e.g. `risengroed.yaml`).
3. **Modular Components (`components`)**:
   - Separate the main dish (`role: base`) from accompaniments (`role: carb` for rice/pasta/noodles, `role: side` for raita/salad, `role: optional` for cream/extras, `role: topping` for nuts/cheese).
4. **Canonical Units + Smart Display Units**:
   - Store ingredient amounts canonically in `ml`, `g`, or `stk`/`fed`/`håndfuld`, and set `display_unit` (`spsk`, `tsk`, `dl`, `dåse`) when a kitchen volume/container unit is preferred (`1 tsk = 5 ml`, `1 spsk = 15 ml`, `1 dl = 100 ml`, `1 dåse tomat/kokosmælk = 400 g/ml`, `1 dåse drænede kikærter/bønner = 240 g`).
5. **Inline Step Tokens (`{ref}`)**:
   - Give ingredients a short `ref` (e.g. `ref: olie`, `ref: loeg`) and reference them in `steps` as `{olie}`, `{loeg}` so the PWA renders live scaled quantities inline.
6. **Ingredients & DTU Frida (`tools/nutrition_db.json`)**:
   - Every ingredient `item` must match an exact key in `tools/nutrition_db.json`.
   - Use `python3 tools/frida_lookup.py --search "<query>"` to find existing ingredient IDs, or `--add "<id>"` to add missing DTU Frida or custom products before compiling.
7. **Localize Images & Compile**:
   - Run `python3 tools/sync_images.py` if the recipe uses an external `https://...` image URL.
   - Run `python3 tools/build_recipes.py --write-md` to validate all ingredients, regenerate `recipes/*.md` + `nutrition-summary.md`, and bundle `webapp/recipes_data.js`.
   - Add new recipes to `README.md` under `## Opskrifter`.
