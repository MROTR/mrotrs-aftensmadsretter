---
name: add-aftensmadsret
description: 'Add or update a Danish dinner recipe in recipes_yaml/ with DTU Frida / custom ingredients, canonical units, localized images, and compiled Markdown + PWA outputs. Use when adding a new recipe from a URL, text, or photo, editing existing recipes, or adding ingredients to nutrition_db.json.'
argument-hint: 'Indsæt opskrifts-URL, ingrediensliste eller beskrivelse af retten...'
user-invocable: true
---

# Add or Update an Aftensmadsret (YAML v2 Recipe Workflow)

Use this skill whenever the user wants to add a new recipe (from a URL, photo, notes, or description), update an existing recipe in ``, or add new ingredients to `nutrition_db.json`.

## End-to-End Procedure

### Step 0: Handling Rough Notes, Brain-Dumps, Photos, or URLs
The user may provide any of the following as input:
- **Roughly described notes / brain-dumps** (e.g. *"Lav en opskrift på rød linsesuppe med lidt olie, 2 løg, hvidløg, gulerødder, 1 dåse kokosmælk, 1 dåse hakkede tomater, røde linser og bouillon — svits løg og krydderier og kog 25 min"*).
- **Incomplete quantities** (e.g. *"lidt olivenolie"*, *"ris til 4 personer"*, *"en sjat fløde"*, *"krydderier efter smag"*).
- **A URL** (use `web_fetch` to read the recipe page and extract title, image, servings, ingredients, and steps).
- **A photo/screenshot** of a cookbook or handwritten note.

When the input is rough or incomplete:
1. **Ask the user first (`ask_user`) about any important or basic missing information instead of guessing:**
   - **Always stop and ask** if any of the following are missing or unclear:
     - **Number of servings (`servings`)** if not stated.
     - **Quantities for calorie-dense or primary ingredients** (e.g. meat/plantefars, paneer/cheese, dry lentils/beans/chickpeas, rice/pasta/noodles/potatoes, coconut milk/cream, or oil/butter when it significantly impacts nutrition).
     - **Which accompaniment/carb belongs with the dish** (e.g. rice vs. pasta vs. bread, and whether it should be enabled by default).
     - **Core cooking method or missing steps** (e.g. oven temperature/time, simmering time, or how a sub-component like a sauce or topping is prepared).
     - **Nutrition values for a brand-new custom product** if it's a specific supermarket item whose macros aren't obvious.
   - Group all questions into a single, concise `ask_user` form (with sensible suggested defaults pre-filled in the form fields so the user can either accept with one click or adjust).
2. **Convert confirmed quantities into canonical units:**
   - `1 tsk` = `5 ml` (`display_unit: tsk`), `1 spsk` = `15 ml` (`display_unit: spsk`), `1 dl` = `100 ml` (`display_unit: dl`).
   - `1 dåse hakkede tomater / kokosmælk` = `400 g` / `400 ml` (`display_unit: dåse`, `scaling: whole_unit`).
   - `1 dåse drænede kikærter/bønner` = `240 g` (`display_unit: dåse`, `scaling: whole_unit`).
3. **Expand shorthand steps into clear, chronological Danish cooking steps:**
   - Include heat levels (*middel varme*), cooking times using en-dashes (`5–7 minutter`), sensory cues (*til løgene er bløde og klare*), and inline `{ref}` tokens for every ingredient (`Varm {olie} op i en gryde...`).

### Step 1: Determine the Recipe ID & Metadata
1. Choose a lowercase kebab-case `id` with Danish characters transliterated (`æ` -> `ae`, `ø` -> `oe`, `å` -> `aa`), e.g. `vegetar-korma-med-blomkaal-og-kikaerter`.
2. Target file path: `recipes_yaml/<id>.yaml`.

### Step 2: Check All Ingredients Against `nutrition_db.json`
Every ingredient `item` in the YAML file **must** match an exact key in `tools/nutrition_db.json` (otherwise `build_recipes.py` will fail with exit code 1).

1. Search existing ingredients:
   ```bash
   python3 tools/frida_lookup.py --search "<søgeord>"
   ```
2. If an ingredient is missing, add it using `frida_lookup.py --add` (prefer official DTU Frida values when it's a standard whole food, or `custom` when it's a specific supermarket product):
   ```bash
   python3 tools/frida_lookup.py \
     --add "<item_id>" \
     --frida-id <optional_frida_id> \
     --frida-name "<Beskrivende navn>" \
     --kcal <kcal_pr_100g> \
     --protein <g> --carb <g> --fat <g> --fiber <g> \
     --density <g_pr_ml_default_1.0> \
     --hydration <cooked_weight_mult_default_1.0> \
     --aisle <frugt_og_groent|broed|koed_og_fisk|mejeri_og_aeg|kolonial|frost|basis_og_krydderier>
   ```
   * **Common hydration factors:** Dry rice/red lentils = `2.5`, dry pasta/noodles = `2.2`, quinoa = `2.6`, raw mushrooms = `0.75`, raw spinach = `0.85`.
   * **Common densities (`g/ml`):** Water/milk/cream/coconut milk/canned tomatoes = `1.0`, olive/cooking oil = `0.92`, dry rice/lentils = `0.85`, wheat flour = `0.60`, ground spices = `0.45`.

### Step 3: Structure the YAML v2 Recipe (`recipes_yaml/<id>.yaml`)
1. Always include the schema header on line 1:
   ```yaml
   # yaml-language-server: $schema=../schemas/recipe.schema.json
   ```
2. **Split the dish into modular `components`:**
   - `role: base` (`default_enabled: true`, `evaporation_factor: 0.85–0.92` for simmering sauces/stews)
   - `role: carb` (`default_enabled: true` or `false` for rice, pasta, noodles, bread)
   - `role: side` (raita, salad, roasted chickpeas, fried eggs)
   - `role: optional` (`default_enabled: false` for optional cream, extra cheese/paneer)
   - `role: topping` (peanuts, sesame seeds, parmesan, herbs)
3. **Use canonical units (`g`, `ml`, `stk`) + `display_unit`:**
   - `1 tsk` -> `amount: 5, unit: ml, display_unit: tsk`
   - `0.5 spsk` -> `amount: 7.5, unit: ml, display_unit: spsk`
   - `2 spsk` -> `amount: 30, unit: ml, display_unit: spsk`
   - `3 dl` -> `amount: 300, unit: ml, display_unit: dl`
   - `2 dåser hakkede tomater` -> `amount: 800, unit: g, display_unit: dåse, scaling: whole_unit`
   - `1 dåse drænede kikærter/bønner` -> `amount: 240, unit: g, display_unit: dåse, scaling: whole_unit`
   - Set `scaling: sublinear` on frying oils and pungent spices so doubling a batch scales them gently (`ratio^0.8`).
4. **Use `{ref}` tokens in `steps`:**
   - Assign a short `ref` to ingredients (`ref: olie`, `ref: loeg`, `ref: hvidloeg`) and write `{olie}`, `{loeg}` inside step strings so the PWA shows live scaled quantities inline.

#### Complete Example Template
```yaml
# yaml-language-server: $schema=../schemas/recipe.schema.json
id: eksempel-karry
title: Eksempel karry
source: https://eksempel.dk/opskrift
image: https://eksempel.dk/billede.jpg
servings: 4
standard_kcal_per_portion: 650
time:
  total_min: 30
  active_min: 15
tags:
  - vegetar
  - karry
  - hurtig
notes: "Kort note om retten og dens moduler."

components:
  - id: karry_base
    title: Til karryen
    role: base
    default_enabled: true
    evaporation_factor: 0.90
    ingredients:
      - ref: olie
        item: olivenolie
        amount: 30
        unit: ml
        display_unit: spsk
        scaling: sublinear
      - ref: loeg
        item: løg
        amount: 2
        unit: stk
        prep: finthakkede
      - ref: tomater
        item: hakkede tomater
        amount: 400
        unit: g
        display_unit: dåse
        scaling: whole_unit
      - item: salt
        label: Salt
        amount: null

  - id: ris_carb
    title: Til servering (ris)
    role: carb
    default_enabled: true
    ingredients:
      - ref: ris
        item: basmatiris
        amount: 300
        unit: ml
        display_unit: dl

steps:
  - section: Karry
    component_id: karry_base
    items:
      - "Kog {ris} efter anvisning på pakken."
      - "Varm {olie} op i en gryde og sautér {loeg} i 5 minutter."
      - "Tilsæt {tomater} og lad simre i 15 minutter. Smag til med salt og servér med {ris}."
```

### Step 4: Localize Image & Compile Outputs
1. If `image` is an `http(s)://` URL, localize and compress it:
   ```bash
   python3 tools/sync_images.py
   ```
2. Compile the YAML recipe into Markdown (`recipes/<id>.md`, `nutrition-summary.md`, and `webapp/recipes_data.js`):
   ```bash
   python3 tools/build_recipes.py --write-md
   ```
3. Add the recipe link to `README.md` (and `recipes/liste-af-retter.md` if applicable) in alphabetical order.
