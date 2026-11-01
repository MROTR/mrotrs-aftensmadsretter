#!/usr/bin/env python3
"""
DTU Fødevaredatabanken (Frida) & Custom Ingredient Manager (`tools/frida_lookup.py`).

Provides:
1. Official DTU Frida (frida.fooddata.dk) reference mappings, macros, densities,
   cooked hydration factors, and supermarket aisle categorization.
2. CLI commands to:
   - `--upgrade-db`: Enrich `nutrition_db.json` with Frida FoodIDs, `source` ("dtu_frida" vs "custom"),
     `density_g_per_ml`, `hydration_factor`, and `aisle` categories while preserving custom items.
   - `--search <query>`: Search ingredients in the database (shows Frida ID / source / aisle / density).
   - `--add-custom`: Add or update a custom product (e.g. Rema 1000 / Netto product not in Frida).
"""

import argparse
import json
import os
import unicodedata
from typing import Any, Dict

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(TOOLS_DIR, "nutrition_db.json")


def norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip().lower()


# Official DTU Fødevaredatabanken (Frida) curated reference values (per 100g edible part)
# + density (g/ml), cooked hydration/yield factor, default piece weight (g), and supermarket aisle.
# Aisles:
#   1. frugt_og_groent (Frugt & Grønt)
#   2. broed (Brød)
#   3. koed_og_fisk (Kød, Fisk & Plantefars)
#   4. mejeri_og_aeg (Mejeri & Æg)
#   5. kolonial (Kolonial & Konserves)
#   6. frost (Frost)
#   7. basis_og_krydderier (Krydderier, Olie & Basisvarer)
FRIDA_AND_CURATED_META: Dict[str, Dict[str, Any]] = {
    # Vegetables (Frugt & Grønt)
    "løg": {
        "frida_id": 146, "frida_name": "Løg, rå", "source": "dtu_frida",
        "kcal": 40, "protein": 1.2, "fat": 0.1, "carb": 7.9, "fiber": 1.9,
        "unit_weight_g": 100, "hydration_factor": 0.90, "aisle": "frugt_og_groent"
    },
    "rødløg": {
        "frida_id": 146, "frida_name": "Løg, rå (rødløg)", "source": "dtu_frida",
        "kcal": 40, "protein": 1.2, "fat": 0.1, "carb": 7.9, "fiber": 1.9,
        "unit_weight_g": 100, "hydration_factor": 0.90, "aisle": "frugt_og_groent"
    },
    "forårsløg": {
        "frida_id": 147, "frida_name": "Forårsløg, rå", "source": "dtu_frida",
        "kcal": 32, "protein": 1.8, "fat": 0.2, "carb": 5.3, "fiber": 2.6,
        "unit_weight_g": 20, "hydration_factor": 0.95, "aisle": "frugt_og_groent"
    },
    "hvidløg": {
        "frida_id": 122, "frida_name": "Hvidløg, rå", "source": "dtu_frida",
        "kcal": 149, "protein": 6.4, "fat": 0.5, "carb": 31.0, "fiber": 2.1,
        "unit_weight_g": 4, "hydration_factor": 1.0, "aisle": "frugt_og_groent"
    },
    "ingefær": {
        "frida_id": 725, "frida_name": "Ingefær, rod, rå", "source": "dtu_frida",
        "kcal": 80, "protein": 1.8, "fat": 0.8, "carb": 15.8, "fiber": 2.0,
        "density_g_per_ml": 0.65, "hydration_factor": 1.0, "aisle": "frugt_og_groent"
    },
    "gulerod": {
        "frida_id": 105, "frida_name": "Gulerod, rå", "source": "dtu_frida",
        "kcal": 36, "protein": 0.7, "fat": 0.2, "carb": 6.7, "fiber": 2.9,
        "unit_weight_g": 80, "hydration_factor": 0.92, "aisle": "frugt_og_groent"
    },
    "gulerødder": {
        "frida_id": 105, "frida_name": "Gulerod, rå", "source": "dtu_frida",
        "kcal": 36, "protein": 0.7, "fat": 0.2, "carb": 6.7, "fiber": 2.9,
        "unit_weight_g": 80, "hydration_factor": 0.92, "aisle": "frugt_og_groent"
    },
    "kartoffel": {
        "frida_id": 132, "frida_name": "Kartoffel, rå", "source": "dtu_frida",
        "kcal": 77, "protein": 2.0, "fat": 0.1, "carb": 15.9, "fiber": 1.4,
        "unit_weight_g": 80, "hydration_factor": 0.95, "aisle": "frugt_og_groent"
    },
    "kartofler": {
        "frida_id": 132, "frida_name": "Kartoffel, rå", "source": "dtu_frida",
        "kcal": 77, "protein": 2.0, "fat": 0.1, "carb": 15.9, "fiber": 1.4,
        "unit_weight_g": 80, "hydration_factor": 0.95, "aisle": "frugt_og_groent"
    },
    "broccoli": {
        "frida_id": 54, "frida_name": "Broccoli, rå", "source": "dtu_frida",
        "kcal": 35, "protein": 3.5, "fat": 0.4, "carb": 3.1, "fiber": 3.0,
        "unit_weight_g": 300, "hydration_factor": 0.95, "aisle": "frugt_og_groent"
    },
    "blomkål": {
        "frida_id": 47, "frida_name": "Blomkål, rå", "source": "dtu_frida",
        "kcal": 25, "protein": 2.0, "fat": 0.3, "carb": 2.9, "fiber": 2.2,
        "unit_weight_g": 500, "hydration_factor": 0.95, "aisle": "frugt_og_groent"
    },
    "squash": {
        "frida_id": 299, "frida_name": "Squash (courgette), rå", "source": "dtu_frida",
        "kcal": 17, "protein": 1.2, "fat": 0.2, "carb": 2.2, "fiber": 1.0,
        "unit_weight_g": 250, "hydration_factor": 0.90, "aisle": "frugt_og_groent"
    },
    "agurk": {
        "frida_id": 3, "frida_name": "Agurk, rå", "source": "dtu_frida",
        "kcal": 14, "protein": 0.7, "fat": 0.1, "carb": 2.2, "fiber": 0.7,
        "unit_weight_g": 300, "hydration_factor": 1.0, "aisle": "frugt_og_groent"
    },
    "spinat": {
        "frida_id": 296, "frida_name": "Spinat, rå", "source": "dtu_frida",
        "kcal": 23, "protein": 2.6, "fat": 0.4, "carb": 1.1, "fiber": 2.2,
        "hydration_factor": 0.85, "aisle": "frugt_og_groent"
    },
    "champignon": {
        "frida_id": 62, "frida_name": "Champignon, rå", "source": "dtu_frida",
        "kcal": 22, "protein": 3.1, "fat": 0.3, "carb": 0.9, "fiber": 2.1,
        "hydration_factor": 0.75, "aisle": "frugt_og_groent"
    },
    "svampe": {
        "frida_id": 62, "frida_name": "Svampe, blandede, rå", "source": "dtu_frida",
        "kcal": 22, "protein": 3.1, "fat": 0.3, "carb": 0.9, "fiber": 2.1,
        "hydration_factor": 0.75, "aisle": "frugt_og_groent"
    },
    "lime": {
        "frida_id": 572, "frida_name": "Lime, rå", "source": "dtu_frida",
        "kcal": 30, "protein": 0.7, "fat": 0.2, "carb": 7.7, "fiber": 2.8,
        "unit_weight_g": 60, "hydration_factor": 1.0, "aisle": "frugt_og_groent"
    },
    "limesaft": {
        "frida_id": 573, "frida_name": "Limesaft, friskpresset", "source": "dtu_frida",
        "kcal": 25, "protein": 0.4, "fat": 0.1, "carb": 6.5, "fiber": 0.4,
        "density_g_per_ml": 1.0, "unit_weight_g": 25, "hydration_factor": 1.0, "aisle": "frugt_og_groent"
    },
    "citron": {
        "frida_id": 64, "frida_name": "Citron, rå", "source": "dtu_frida",
        "kcal": 29, "protein": 1.1, "fat": 0.3, "carb": 6.5, "fiber": 2.8,
        "unit_weight_g": 80, "hydration_factor": 1.0, "aisle": "frugt_og_groent"
    },
    "chili": {
        "frida_id": 220, "frida_name": "Chilipeber, rød, rå", "source": "dtu_frida",
        "kcal": 40, "protein": 1.9, "fat": 0.4, "carb": 7.3, "fiber": 1.5,
        "unit_weight_g": 15, "hydration_factor": 1.0, "aisle": "frugt_og_groent"
    },
    "koriander": {
        "frida_id": 732, "frida_name": "Koriander, frisk", "source": "dtu_frida",
        "kcal": 23, "protein": 2.1, "fat": 0.5, "carb": 0.9, "fiber": 2.8,
        "unit_weight_g": 15, "hydration_factor": 1.0, "aisle": "frugt_og_groent"
    },
    "persille": {
        "frida_id": 224, "frida_name": "Persille, frisk", "source": "dtu_frida",
        "kcal": 36, "protein": 3.0, "fat": 0.8, "carb": 3.0, "fiber": 3.3,
        "unit_weight_g": 15, "hydration_factor": 1.0, "aisle": "frugt_og_groent"
    },
    "mynte": {
        "frida_id": 741, "frida_name": "Mynte, frisk", "source": "dtu_frida",
        "kcal": 44, "protein": 3.3, "fat": 0.7, "carb": 5.3, "fiber": 6.8,
        "unit_weight_g": 15, "hydration_factor": 1.0, "aisle": "frugt_og_groent"
    },
    "timian": {
        "frida_id": 755, "frida_name": "Timian, frisk", "source": "dtu_frida",
        "kcal": 101, "protein": 5.6, "fat": 1.7, "carb": 10.5, "fiber": 14.0,
        "density_g_per_ml": 0.35, "hydration_factor": 1.0, "aisle": "frugt_og_groent"
    },

    # Legumes & Canned (Kolonial & Konserves)
    "røde linser": {
        "frida_id": 144, "frida_name": "Linser, tørrede, rå", "source": "dtu_frida",
        "kcal": 338, "protein": 25.4, "fat": 1.1, "carb": 50.8, "fiber": 10.7,
        "density_g_per_ml": 0.85, "hydration_factor": 2.5, "aisle": "kolonial"
    },
    "belugalinser": {
        "frida_id": 144, "frida_name": "Linser, tørrede, rå (beluga)", "source": "dtu_frida",
        "kcal": 338, "protein": 25.4, "fat": 1.1, "carb": 48.0, "fiber": 15.0,
        "density_g_per_ml": 0.85, "hydration_factor": 2.4, "aisle": "kolonial"
    },
    "kikærter_dåse": {
        "frida_id": 1112, "frida_name": "Kikærter, kogte/konserves, drænede", "source": "dtu_frida",
        "kcal": 128, "protein": 7.2, "fat": 2.4, "carb": 16.2, "fiber": 6.4,
        "unit_weight_g": 240, "hydration_factor": 1.0, "aisle": "kolonial"
    },
    "hakkede tomater": {
        "frida_id": 342, "frida_name": "Tomat, flået/hakket, på dåse", "source": "dtu_frida",
        "kcal": 21, "protein": 1.1, "fat": 0.1, "carb": 3.2, "fiber": 1.0,
        "density_g_per_ml": 1.0, "unit_weight_g": 400, "hydration_factor": 1.0, "aisle": "kolonial"
    },
    "passata": {
        "frida_id": 342, "frida_name": "Passata / mosede tomater", "source": "dtu_frida",
        "kcal": 24, "protein": 1.3, "fat": 0.2, "carb": 4.0, "fiber": 1.2,
        "density_g_per_ml": 1.0, "unit_weight_g": 400, "hydration_factor": 1.0, "aisle": "kolonial"
    },
    "tomatpuré": {
        "frida_id": 343, "frida_name": "Tomatpuré, koncentreret", "source": "dtu_frida",
        "kcal": 85, "protein": 4.5, "fat": 0.4, "carb": 14.5, "fiber": 2.8,
        "density_g_per_ml": 1.05, "hydration_factor": 1.0, "aisle": "kolonial"
    },
    "kokosmælk": {
        "frida_id": 1034, "frida_name": "Kokosmælk, konserves (~17-18% fedt)", "source": "dtu_frida",
        "kcal": 187, "protein": 1.6, "fat": 18.0, "carb": 2.7, "fiber": 0.8,
        "density_g_per_ml": 1.0, "unit_weight_g": 400, "hydration_factor": 1.0, "aisle": "kolonial"
    },
    "basmatiris": {
        "frida_id": 245, "frida_name": "Ris, hvide/basmati, rå", "source": "dtu_frida",
        "kcal": 356, "protein": 7.1, "fat": 0.7, "carb": 78.8, "fiber": 1.3,
        "density_g_per_ml": 0.85, "hydration_factor": 2.5, "aisle": "kolonial"
    },
    "brune ris": {
        "frida_id": 244, "frida_name": "Ris, brune (fuldkorn), rå", "source": "dtu_frida",
        "kcal": 357, "protein": 7.5, "fat": 2.7, "carb": 73.5, "fiber": 3.6,
        "density_g_per_ml": 0.85, "hydration_factor": 2.5, "aisle": "kolonial"
    },
    "spaghetti": {
        "frida_id": 219, "frida_name": "Pasta, spaghetti, rå", "source": "dtu_frida",
        "kcal": 355, "protein": 12.5, "fat": 1.5, "carb": 71.0, "fiber": 3.2,
        "hydration_factor": 2.2, "aisle": "kolonial"
    },
    "nudler": {
        "frida_id": 219, "frida_name": "Nudler, hvede/æg, tørrede, rå", "source": "dtu_frida",
        "kcal": 360, "protein": 12.0, "fat": 2.0, "carb": 71.5, "fiber": 3.0,
        "hydration_factor": 2.2, "aisle": "kolonial"
    },
    "peanutbutter": {
        "frida_id": 654, "frida_name": "Jordnøddesmør (peanutbutter)", "source": "dtu_frida",
        "kcal": 612, "protein": 23.6, "fat": 50.0, "carb": 12.0, "fiber": 6.8,
        "density_g_per_ml": 1.06, "hydration_factor": 1.0, "aisle": "kolonial"
    },
    "peanuts": {
        "frida_id": 126, "frida_name": "Jordnødder (peanuts), ristede, saltede", "source": "dtu_frida",
        "kcal": 598, "protein": 24.4, "fat": 51.0, "carb": 11.5, "fiber": 8.0,
        "density_g_per_ml": 0.60, "hydration_factor": 1.0, "aisle": "kolonial"
    },
    "sesamfrø": {
        "frida_id": 269, "frida_name": "Sesamfrø, afskallede", "source": "dtu_frida",
        "kcal": 595, "protein": 18.0, "fat": 52.0, "carb": 10.0, "fiber": 11.6,
        "density_g_per_ml": 0.62, "hydration_factor": 1.0, "aisle": "kolonial"
    },
    "rødvin": {
        "frida_id": 258, "frida_name": "Rødvin", "source": "dtu_frida",
        "kcal": 73, "protein": 0.1, "fat": 0.0, "carb": 0.3, "fiber": 0.0,
        "density_g_per_ml": 1.0, "hydration_factor": 1.0, "aisle": "kolonial"
    },

    # Frost
    "edamame": {
        "frida_id": 1150, "frida_name": "Sojabønner, grønne (edamame), frosne", "source": "dtu_frida",
        "kcal": 121, "protein": 11.9, "fat": 5.2, "carb": 5.0, "fiber": 5.2,
        "hydration_factor": 1.0, "aisle": "frost"
    },

    # Dairy & Eggs (Mejeri & Æg)
    "piskefløde": {
        "frida_id": 85, "frida_name": "Piskefløde 38%", "source": "dtu_frida",
        "kcal": 364, "protein": 2.0, "fat": 38.0, "carb": 3.0, "fiber": 0.0,
        "density_g_per_ml": 1.0, "hydration_factor": 1.0, "aisle": "mejeri_og_aeg"
    },
    "smør": {
        "frida_id": 286, "frida_name": "Smør, saltet", "source": "dtu_frida",
        "kcal": 742, "protein": 0.6, "fat": 82.0, "carb": 0.6, "fiber": 0.0,
        "density_g_per_ml": 0.95, "hydration_factor": 1.0, "aisle": "mejeri_og_aeg"
    },
    "græsk yoghurt 10": {
        "frida_id": 1088, "frida_name": "Yoghurt, græsk type, 10% fedt", "source": "dtu_frida",
        "kcal": 126, "protein": 5.2, "fat": 10.0, "carb": 3.8, "fiber": 0.0,
        "density_g_per_ml": 1.0, "hydration_factor": 1.0, "aisle": "mejeri_og_aeg"
    },
    "parmesan": {
        "frida_id": 212, "frida_name": "Parmesan, fast modnet ost", "source": "dtu_frida",
        "kcal": 402, "protein": 36.0, "fat": 28.0, "carb": 0.0, "fiber": 0.0,
        "hydration_factor": 1.0, "aisle": "mejeri_og_aeg"
    },
    "paneer": {
        "frida_id": None, "frida_name": "Paneer (indisk fast ost, ~23% fedt)", "source": "custom",
        "kcal": 296, "protein": 18.0, "fat": 23.0, "carb": 3.0, "fiber": 0.0,
        "hydration_factor": 1.0, "aisle": "mejeri_og_aeg"
    },
    "æg": {
        "frida_id": 362, "frida_name": "Æg, hønse-, helt, rå", "source": "dtu_frida",
        "kcal": 137, "protein": 12.3, "fat": 9.3, "carb": 1.1, "fiber": 0.0,
        "unit_weight_g": 55, "hydration_factor": 1.0, "aisle": "mejeri_og_aeg"
    },

    # Pantry, Oils & Spices (Krydderier, Olie & Basisvarer)
    "olivenolie": {
        "frida_id": 203, "frida_name": "Olivenolie", "source": "dtu_frida",
        "kcal": 900, "protein": 0.0, "fat": 100.0, "carb": 0.0, "fiber": 0.0,
        "density_g_per_ml": 0.92, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "hvedemel": {
        "frida_id": 118, "frida_name": "Hvedemel, almindeligt", "source": "dtu_frida",
        "kcal": 348, "protein": 10.3, "fat": 1.3, "carb": 71.9, "fiber": 3.2,
        "density_g_per_ml": 0.60, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "sukker": {
        "frida_id": 307, "frida_name": "Sukker, stødt melis", "source": "dtu_frida",
        "kcal": 400, "protein": 0.0, "fat": 0.0, "carb": 100.0, "fiber": 0.0,
        "density_g_per_ml": 0.85, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "brun farin": {
        "frida_id": 58, "frida_name": "Brun farin", "source": "dtu_frida",
        "kcal": 380, "protein": 0.1, "fat": 0.0, "carb": 95.0, "fiber": 0.0,
        "density_g_per_ml": 0.80, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "sojasauce": {
        "frida_id": 291, "frida_name": "Sojasauce", "source": "dtu_frida",
        "kcal": 61, "protein": 7.5, "fat": 0.1, "carb": 7.6, "fiber": 0.5,
        "density_g_per_ml": 1.15, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "fiskesauce": {
        "frida_id": None, "frida_name": "Fiskesauce (Thai fish sauce)", "source": "custom",
        "kcal": 35, "protein": 5.0, "fat": 0.0, "carb": 3.5, "fiber": 0.0,
        "density_g_per_ml": 1.15, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "eddike": {
        "frida_id": 74, "frida_name": "Eddike, lagereddike/vineddike", "source": "dtu_frida",
        "kcal": 21, "protein": 0.0, "fat": 0.0, "carb": 0.6, "fiber": 0.0,
        "density_g_per_ml": 1.0, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "karry": {
        "frida_id": 730, "frida_name": "Karry, pulver", "source": "dtu_frida",
        "kcal": 325, "protein": 14.3, "fat": 14.0, "carb": 25.0, "fiber": 33.2,
        "density_g_per_ml": 0.45, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "paprika": {
        "frida_id": 746, "frida_name": "Paprika, stødt", "source": "dtu_frida",
        "kcal": 282, "protein": 14.1, "fat": 12.9, "carb": 19.0, "fiber": 34.9,
        "density_g_per_ml": 0.45, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "spidskommen": {
        "frida_id": 753, "frida_name": "Spidskommen, stødt", "source": "dtu_frida",
        "kcal": 375, "protein": 17.8, "fat": 22.3, "carb": 33.7, "fiber": 10.5,
        "density_g_per_ml": 0.45, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "stødt koriander": {
        "frida_id": 733, "frida_name": "Korianderfrø, stødt", "source": "dtu_frida",
        "kcal": 298, "protein": 12.4, "fat": 17.8, "carb": 13.0, "fiber": 41.9,
        "density_g_per_ml": 0.40, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "kardemomme": {
        "frida_id": 729, "frida_name": "Kardemomme, stødt", "source": "dtu_frida",
        "kcal": 311, "protein": 10.8, "fat": 6.7, "carb": 40.5, "fiber": 28.0,
        "density_g_per_ml": 0.45, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "gurkemeje": {
        "frida_id": 723, "frida_name": "Gurkemeje, stødt", "source": "dtu_frida",
        "kcal": 312, "protein": 9.7, "fat": 3.3, "carb": 44.4, "fiber": 22.7,
        "density_g_per_ml": 0.50, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "chiliflager": {
        "frida_id": 718, "frida_name": "Chili, tørret (flager/pulver)", "source": "dtu_frida",
        "kcal": 282, "protein": 13.5, "fat": 14.3, "carb": 22.8, "fiber": 27.2,
        "density_g_per_ml": 0.40, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "garam masala": {
        "frida_id": None, "frida_name": "Garam masala (krydderiblanding)", "source": "custom",
        "kcal": 325, "protein": 14.0, "fat": 14.0, "carb": 30.0, "fiber": 20.0,
        "density_g_per_ml": 0.45, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "karrypasta": {
        "frida_id": None, "frida_name": "Thai karrypasta (rød/grøn)", "source": "custom",
        "kcal": 125, "protein": 3.5, "fat": 5.5, "carb": 15.0, "fiber": 3.0,
        "density_g_per_ml": 1.05, "hydration_factor": 1.0, "aisle": "kolonial"
    },
    "laurbærblade": {
        "frida_id": 737, "frida_name": "Laurbærblade, tørrede", "source": "dtu_frida",
        "kcal": 313, "protein": 7.6, "fat": 8.4, "carb": 48.7, "fiber": 26.3,
        "unit_weight_g": 0.5, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "bouillonterning": {
        "frida_id": 51, "frida_name": "Bouillonterning, grøntsags/okse", "source": "dtu_frida",
        "kcal": 250, "protein": 15.0, "fat": 18.0, "carb": 6.0, "fiber": 0.0,
        "unit_weight_g": 10, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "grøntsagsbouillon": {
        "frida_id": 52, "frida_name": "Grøntsagsbouillon, spiseklar", "source": "dtu_frida",
        "kcal": 3, "protein": 0.3, "fat": 0.1, "carb": 0.2, "fiber": 0.0,
        "density_g_per_ml": 1.0, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "salt": {
        "frida_id": 265, "frida_name": "Salt, bordsalt", "source": "dtu_frida",
        "kcal": 0, "protein": 0.0, "fat": 0.0, "carb": 0.0, "fiber": 0.0,
        "density_g_per_ml": 1.2, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "peber": {
        "frida_id": 747, "frida_name": "Peber, sort", "source": "dtu_frida",
        "kcal": 251, "protein": 10.4, "fat": 3.3, "carb": 38.3, "fiber": 25.3,
        "density_g_per_ml": 0.50, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "vand": {
        "frida_id": 351, "frida_name": "Vand, postevand", "source": "dtu_frida",
        "kcal": 0, "protein": 0.0, "fat": 0.0, "carb": 0.0, "fiber": 0.0,
        "density_g_per_ml": 1.0, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "oregano": {
        "frida_id": 745, "frida_name": "Oregano, tørret/frisk", "source": "dtu_frida",
        "kcal": 265, "protein": 9.0, "fat": 4.3, "carb": 26.0, "fiber": 42.5,
        "density_g_per_ml": 0.35, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "muskatnød": {
        "frida_id": 740, "frida_name": "Muskatnød, stødt", "source": "dtu_frida",
        "kcal": 525, "protein": 5.8, "fat": 36.3, "carb": 28.5, "fiber": 20.8,
        "density_g_per_ml": 0.45, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "dijonsennep": {
        "frida_id": 268, "frida_name": "Sennep, færdiglavet (dijon)", "source": "dtu_frida",
        "kcal": 140, "protein": 7.0, "fat": 8.0, "carb": 8.0, "fiber": 3.5,
        "density_g_per_ml": 1.05, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "dild": {
        "frida_id": 72, "frida_name": "Dild, frisk", "source": "dtu_frida",
        "kcal": 43, "protein": 3.5, "fat": 1.1, "carb": 4.9, "fiber": 2.1,
        "unit_weight_g": 30, "hydration_factor": 1.0, "aisle": "frugt_og_groent"
    },
    "purløg": {
        "frida_id": 236, "frida_name": "Purløg, rå", "source": "dtu_frida",
        "kcal": 30, "protein": 3.3, "fat": 0.7, "carb": 1.9, "fiber": 2.5,
        "unit_weight_g": 15, "hydration_factor": 1.0, "aisle": "frugt_og_groent"
    },
    "sild": {
        "frida_id": 274, "frida_name": "Sild, stegt/paneret", "source": "dtu_frida",
        "kcal": 215, "protein": 17.5, "fat": 14.5, "carb": 3.5, "fiber": 0.3,
        "unit_weight_g": 75, "hydration_factor": 1.0, "aisle": "koed_og_fisk"
    },
    "safran": {
        "frida_id": 750, "frida_name": "Safran, tørret", "source": "dtu_frida",
        "kcal": 310, "protein": 11.4, "fat": 5.9, "carb": 61.5, "fiber": 3.9,
        "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "fennikelfrø": {
        "frida_id": 721, "frida_name": "Fennikelfrø, tørrede", "source": "dtu_frida",
        "kcal": 345, "protein": 15.8, "fat": 14.9, "carb": 12.5, "fiber": 39.8,
        "density_g_per_ml": 0.45, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "sorte ris": {
        "frida_id": 244, "frida_name": "Ris, sorte/fuldkorn, rå", "source": "dtu_frida",
        "kcal": 356, "protein": 8.5, "fat": 2.8, "carb": 72.0, "fiber": 4.5,
        "density_g_per_ml": 0.85, "hydration_factor": 2.5, "aisle": "kolonial"
    },
    "stødt nellike": {
        "frida_id": 742, "frida_name": "Nelliker, stødt", "source": "dtu_frida",
        "kcal": 274, "protein": 6.0, "fat": 13.0, "carb": 31.6, "fiber": 33.9,
        "density_g_per_ml": 0.45, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "sriracha": {
        "frida_id": None, "frida_name": "Sriracha chilisauce", "source": "custom",
        "kcal": 93, "protein": 2.0, "fat": 1.0, "carb": 19.0, "fiber": 1.5,
        "density_g_per_ml": 1.1, "hydration_factor": 1.0, "aisle": "basis_og_krydderier"
    },
    "tørrede svampe": {
        "frida_id": 1062, "frida_name": "Svampe, tørrede (f.eks. Karl Johan)", "source": "dtu_frida",
        "kcal": 286, "protein": 30.0, "fat": 3.0, "carb": 25.0, "fiber": 20.0,
        "hydration_factor": 3.5, "aisle": "kolonial"
    },
    "blandet salat": {
        "frida_id": 124, "frida_name": "Salat, blandet grøn, rå", "source": "dtu_frida",
        "kcal": 15, "protein": 1.3, "fat": 0.2, "carb": 1.5, "fiber": 1.5,
        "hydration_factor": 1.0, "aisle": "frugt_og_groent"
    },
    "kaffir-limeblade": {
        "frida_id": None, "frida_name": "Kaffir-limeblade", "source": "custom",
        "kcal": 30, "protein": 1.0, "fat": 0.2, "carb": 5.0, "fiber": 2.0,
        "unit_weight_g": 0.5, "hydration_factor": 1.0, "aisle": "frugt_og_groent"
    },
    "citrongræs": {
        "frida_id": 719, "frida_name": "Citrongræs, frisk", "source": "dtu_frida",
        "kcal": 99, "protein": 1.8, "fat": 0.5, "carb": 21.0, "fiber": 4.2,
        "density_g_per_ml": 0.50, "hydration_factor": 1.0, "aisle": "frugt_og_groent"
    },
    "rejepasta": {
        "frida_id": None, "frida_name": "Thai rejepasta (shrimp paste)", "source": "custom",
        "kcal": 155, "protein": 22.0, "fat": 6.0, "carb": 3.0, "fiber": 0.0,
        "density_g_per_ml": 1.1, "hydration_factor": 1.0, "aisle": "kolonial"
    },
    "skalotteløg": {
        "frida_id": 276, "frida_name": "Skalotteløg, rå", "source": "dtu_frida",
        "kcal": 72, "protein": 2.5, "fat": 0.1, "carb": 13.6, "fiber": 3.2,
        "unit_weight_g": 25, "hydration_factor": 0.90, "aisle": "frugt_og_groent"
    },
    "bagekartoffel": {
        "frida_id": 132, "frida_name": "Kartoffel, bagekartoffel, rå", "source": "dtu_frida",
        "kcal": 77, "protein": 2.0, "fat": 0.1, "carb": 15.9, "fiber": 1.4,
        "unit_weight_g": 200, "hydration_factor": 0.90, "aisle": "frugt_og_groent"
    },
    "kokosmel": {
        "frida_id": 138, "frida_name": "Kokosmel / tørret kokos (kokosflager)", "source": "dtu_frida",
        "kcal": 660, "protein": 6.9, "fat": 64.5, "carb": 7.4, "fiber": 16.3,
        "density_g_per_ml": 0.45, "hydration_factor": 1.0, "aisle": "kolonial"
    },
}


def infer_aisle(key: str, current_section: str) -> str:
    if any(x in key for x in ("olie", "smør", "eddike", "soja", "salt", "peber", "karry", "paprika", "kanel", "sukker", "farin", "honning", "sirup", "bouillon", "mel", "gær")):
        if "smør" in key:
            return "mejeri_og_aeg"
        return "basis_og_krydderier"
    if "VEGETABLES" in current_section or "FRUITS" in current_section:
        return "frugt_og_groent"
    if "DAIRY" in current_section or key in ("æg",):
        return "mejeri_og_aeg"
    if "MEAT" in current_section or "plantefars" in key or "tofu" in key:
        return "koed_og_fisk"
    if any(x in key for x in ("brød", "bolle", "pitabrød", "tortilla", "naan")):
        return "broed"
    if "edamame" in key or "ærter" in key:
        return "frost"
    return "kolonial"


def upgrade_db():
    with open(DB_PATH, "r", encoding="utf-8") as f:
        db = json.load(f)

    ingredients = db.get("ingredients", {})
    unit_weights = {norm(k): v for k, v in db.get("unit_weights", {}).items()}

    current_section = ""
    upgraded_ingredients = {}

    for raw_k, val in ingredients.items():
        if raw_k.startswith("__"):
            current_section = raw_k
            upgraded_ingredients[raw_k] = val
            continue

        k = norm(raw_k)
        if k in FRIDA_AND_CURATED_META:
            meta = dict(FRIDA_AND_CURATED_META[k])
            meta.setdefault("density_g_per_ml", 1.0)
            meta.setdefault("hydration_factor", 1.0)
            if "unit_weight_g" not in meta and k in unit_weights:
                meta["unit_weight_g"] = unit_weights[k]
            upgraded_ingredients[raw_k] = meta
        else:
            entry = dict(val)
            entry.setdefault("frida_id", None)
            entry.setdefault("source", "custom")
            entry.setdefault("density_g_per_ml", 1.0)
            entry.setdefault("hydration_factor", 1.0)
            entry.setdefault("aisle", infer_aisle(k, current_section))
            if "unit_weight_g" not in entry and k in unit_weights:
                entry["unit_weight_g"] = unit_weights[k]
            upgraded_ingredients[raw_k] = entry

    # Ensure all curated items exist in upgraded_ingredients
    existing_norm = {norm(k) for k in upgraded_ingredients if not k.startswith("__")}
    for k, meta in FRIDA_AND_CURATED_META.items():
        if k not in existing_norm:
            m = dict(meta)
            m.setdefault("density_g_per_ml", 1.0)
            m.setdefault("hydration_factor", 1.0)
            upgraded_ingredients[k] = m

    db["schema_version"] = "2.0-dtu-frida-hybrid"
    db["ingredients"] = upgraded_ingredients

    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

    frida_count = sum(
        1 for k, v in upgraded_ingredients.items()
        if isinstance(v, dict) and v.get("source") == "dtu_frida"
    )
    custom_count = sum(
        1 for k, v in upgraded_ingredients.items()
        if isinstance(v, dict) and v.get("source") != "dtu_frida"
    )
    print(f"Upgraded {DB_PATH}: {frida_count} DTU Frida items, {custom_count} custom/curated items.")


def search_db(query: str):
    with open(DB_PATH, "r", encoding="utf-8") as f:
        db = json.load(f)
    q = norm(query)
    print(f"{'ID':<22} | {'Kilde (Frida ID)':<20} | {'kcal':<5} | {'P':<4} | {'K':<4} | {'F':<4} | {'Afdeling':<20}")
    print("-" * 92)
    for k, v in db.get("ingredients", {}).items():
        if k.startswith("__") or not isinstance(v, dict):
            continue
        if q in norm(k) or q in norm(v.get("frida_name", "")):
            src = f"Frida #{v['frida_id']}" if v.get("frida_id") else "Custom"
            print(f"{k:<22} | {src:<20} | {v.get('kcal', 0):<5.0f} | {v.get('protein', 0):<4.1f} | {v.get('carb', 0):<4.1f} | {v.get('fat', 0):<4.1f} | {v.get('aisle', '-')}")


def add_ingredient(
    item_id: str,
    kcal: float,
    protein: float,
    carb: float,
    fat: float,
    fiber: float,
    aisle: str,
    frida_id: int = None,
    frida_name: str = None,
    density: float = 1.0,
    hydration: float = 1.0,
    unit_weight_g: float = None,
):
    with open(DB_PATH, "r", encoding="utf-8") as f:
        db = json.load(f)
    key = norm(item_id)
    entry = {
        "frida_id": frida_id,
        "frida_name": frida_name or item_id,
        "source": "dtu_frida" if frida_id else "custom",
        "kcal": kcal,
        "protein": protein,
        "fat": fat,
        "carb": carb,
        "fiber": fiber,
        "density_g_per_ml": density,
        "hydration_factor": hydration,
        "aisle": aisle,
    }
    if unit_weight_g is not None:
        entry["unit_weight_g"] = unit_weight_g
        db.setdefault("unit_weights", {})[key] = unit_weight_g

    db.setdefault("ingredients", {})[key] = entry
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=4)
    print(f"Added/updated ingredient '{key}' ({entry['source']}) in {DB_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DTU Frida & Custom Ingredient DB Tool")
    parser.add_argument("--upgrade-db", action="store_true", help="Upgrade nutrition_db.json with Frida metadata, densities, and aisles")
    parser.add_argument("--search", type=str, help="Search ingredients in nutrition_db.json")
    parser.add_argument("--add", type=str, metavar="ID", help="Add or update an ingredient ID in nutrition_db.json")
    parser.add_argument("--kcal", type=float, default=0.0, help="kcal per 100g")
    parser.add_argument("--protein", type=float, default=0.0, help="Protein (g) per 100g")
    parser.add_argument("--carb", type=float, default=0.0, help="Available carbohydrate (g) per 100g")
    parser.add_argument("--fat", type=float, default=0.0, help="Fat (g) per 100g")
    parser.add_argument("--fiber", type=float, default=0.0, help="Dietary fiber (g) per 100g")
    parser.add_argument(
        "--aisle",
        type=str,
        default="kolonial",
        choices=[
            "frugt_og_groent",
            "broed",
            "koed_og_fisk",
            "mejeri_og_aeg",
            "kolonial",
            "frost",
            "basis_og_krydderier",
        ],
        help="Supermarket aisle category",
    )
    parser.add_argument("--frida-id", type=int, default=None, help="Optional DTU Frida FoodID")
    parser.add_argument("--frida-name", type=str, default=None, help="Optional official Frida or product name")
    parser.add_argument("--density", type=float, default=1.0, help="Density in g/ml (default 1.0)")
    parser.add_argument("--hydration", type=float, default=1.0, help="Cooked weight multiplier (e.g. 2.5 for dry rice)")
    parser.add_argument("--unit-weight", type=float, default=None, help="Weight in grams per 1 stk/fed/dåse")
    args = parser.parse_args()

    if args.upgrade_db:
        upgrade_db()
    elif args.search:
        search_db(args.search)
    elif args.add:
        add_ingredient(
            item_id=args.add,
            kcal=args.kcal,
            protein=args.protein,
            carb=args.carb,
            fat=args.fat,
            fiber=args.fiber,
            aisle=args.aisle,
            frida_id=args.frida_id,
            frida_name=args.frida_name,
            density=args.density,
            hydration=args.hydration,
            unit_weight_g=args.unit_weight,
        )
    else:
        parser.print_help()
