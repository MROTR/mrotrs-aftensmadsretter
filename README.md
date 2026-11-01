# Aftensmadsretter (YAML v2 + Mobile PWA + Markdown)

Dette katalog indeholder hele opskriftssamlingen, næringsdatabasen (baseret på **DTU Fødevaredatabanken (Frida)** kombineret med egne råvarer), Python-kompileren samt den mobilvenlige **Progressive Web App (PWA)**.

---

## Overblik over arkitekturen

```text
Aftensmadsretter/
├── recipes_yaml/            # ★ KILDEDATA (Source of Truth): 32 strukturerede YAML v2-opskrifter
├── schemas/
│   └── recipe.schema.json   # JSON Schema til VS Code auto-complete og validering af YAML-filer
├── tools/
│   ├── build_recipes.py     # Kompilerer YAML -> Markdown-tabeller + webapp/recipes_data.js
│   ├── frida_lookup.py      # Søg og tilføj ingredienser (DTU Frida + custom varer) i nutrition_db.json
│   ├── sync_images.py       # Henter, skalerer (max 900px) og komprimerer billeder til Files/images/
│   └── nutrition_db.json    # Ingrediensdatabase (makroer pr. 100g, massefylde, vandoptag, supermarkedsafdeling)
├── webapp/                  # Mobil-PWA (kan åbnes direkte eller udgives via GitHub Pages)
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   ├── recipes_data.js      # Auto-genereret bundle fra build_recipes.py
│   ├── manifest.json
│   └── sw.js                # Offline Service Worker
├── recipes/                 # Auto-genererede Markdown-visninger (*.md) + nutrition-summary.md
└── Files/
    └── images/              # Lokalt gemte og optimerede opskriftsbilleder (*.jpg)
```

---

## Hurtig kommandoguide (CLI)

Kør altid kommandoerne fra repo-roden:

### 1. Byg alt automatisk (Markdown-filer, billeder, oversigter og mobil-webapp)
```bash
python3 Aftensmadsretter/tools/build_recipes.py --write-md
```
Dette er **hovedkommandoen**, som automatisk:
* Henter, optimerer og lokaliserer eksterne opskriftsbilleder (`image: https://...` i YAML) direkte til `Files/images/<id>.jpg` og opdaterer YAML-stien.
* Validerer at **alle** ingrediens-ID'er (`item`) findes i `nutrition_db.json`. Hvis en ingrediens mangler, fejler scriptet med exit-kode `1` og viser præcis hvilket ID der mangler.
* Genererer/opdaterer alle Markdown-filer i `Aftensmadsretter/recipes/` samt `nutrition-summary.md`.
* Auto-opdaterer oversigterne i både `Aftensmadsretter/README.md` (antal og alfabetisk liste) og `recipes/liste-af-retter.md`.
* Bundler mobil-webapp'en til `Aftensmadsretter/webapp/recipes_data.js`.

### 2. Søg i ingrediensdatabasen (`nutrition_db.json`)
```bash
python3 Aftensmadsretter/tools/frida_lookup.py --search "kokos"
```

### 3. Tilføj en ny ingrediens (enten fra DTU Frida eller en custom supermarkedsvare)
```bash
# Eksempel A: Tilføj en vare med reference til DTU Frida FoodID
python3 Aftensmadsretter/tools/frida_lookup.py \
  --add "røde linser" \
  --frida-id 144 \
  --frida-name "Linser, tørrede, rå" \
  --kcal 338 --protein 25.4 --carb 50.8 --fat 1.1 --fiber 10.7 \
  --density 0.85 --hydration 2.5 --aisle kolonial

# Eksempel B: Tilføj en custom vare (f.eks. fra varedeklaration i Rema 1000 / Netto)
python3 Aftensmadsretter/tools/frida_lookup.py \
  --add "plantefars" \
  --frida-name "Plantefars (Rema 1000)" \
  --kcal 165 --protein 18.0 --carb 3.0 --fat 8.0 --fiber 6.0 \
  --aisle koed_og_fisk
```

Gyldige værdier for `--aisle` (bruges til at sortere indkøbslisten i butiksrækkefølge):
* `frugt_og_groent` (🥬 Frugt & Grønt)
* `broed` (🍞 Brød)
* `koed_og_fisk` (🥩 Kød, Fisk & Plantefars)
* `mejeri_og_aeg` (🧀 Mejeri & Æg)
* `kolonial` (🥫 Kolonial & Konserves)
* `frost` (❄️ Frost)
* `basis_og_krydderier` (🧂 Krydderier, Olie & Basisvarer)

### 4. Standalone billed-optimering (valgfrit)
`build_recipes.py --write-md` klarer automatisk billederne, men værktøjet kan også køres isoleret:
```bash
python3 Aftensmadsretter/tools/sync_images.py
```
Dette downloader billedet, skalerer det til maks. 900px bredde i JPEG (`Files/images/<id>.jpg`) og opdaterer `image:`-feltet i YAML-filen.

### 5. Åbn eller test PWA'en lokalt
Du kan åbne `Aftensmadsretter/webapp/index.html` direkte i din browser, eller starte en lokal webserver:
```bash
python3 -m http.server 8000 --directory Aftensmadsretter/webapp
```

### 6. Eksport til Microsoft To Do (iPhone Genvej & Web) og Deling
I **🛒 Indkøbsliste**-visningen i PWA'en er der direkte understøttelse af **Microsoft To Do** og mobildeling:
* **📲 Tilføj til To Do (iPhone Genvej):**
  * Kopierer alle uafkrydsede varer (i supermarkeds-rækkefølge, ekskl. krydderier medmindre tilvalgt) og starter automatisk iPhone-genvejen `Tilføj Til To-do` (*Get clipboard* → *Split Text by New Lines* → *Repeat with each* → *Microsoft To Do: Add Repeat Item to List*), som opretter hver vare som sin egen opgave i Microsoft To Do.
* **☑️ Kopiér til To Do & 📤 Del liste… (Web Share API):**
  * Kopierer rene varelinjer (til indsættelse i `to-do.office.com` på PC/Mac) eller åbner telefonens indbyggede Del-menu.

---

## Sådan opbygges en YAML v2-opskrift (`recipes_yaml/<id>.yaml`)

Hver fil i `recipes_yaml/` starter med schema-kommentaren `# yaml-language-server: $schema=../schemas/recipe.schema.json`, som giver auto-complete i VS Code.

### Nøgleprincipper:
1. **Kanoniske mængder (`g`, `ml`, `stk`) + `display_unit` (`spsk`, `tsk`, `dl`, `dåse`):**
   * Lagring i `ml` eller `g` gør skalering og indkøbsliste-sammenlægning eksakt.
   * `1 tsk = 5 ml`, `1 spsk = 15 ml`, `1 dl = 100 ml`, `1 dåse = 400 g` (eller `240 g` drænet for kikærter/bønner).
   * Ved skalering afrunder appen automatisk til nærmeste naturlige danske køkkenmål (f.eks. bliver `0.75 spsk` [`11.25 ml`] automatisk vist som `2 tsk`).
2. **Modulopdelte `components` (`role`):**
   * `base`: Selve hovedretten/saucen/gryderetten (`default_enabled: true`).
   * `carb`: Ris, pasta, nudler, brød (`default_enabled: true` eller `false`).
   * `side`: Tilbehør som raita, salat, ristede kikærter, spejlæg.
   * `optional`: Valgfrie tilføjelser som fløde eller ekstra paneer (`default_enabled: false`).
   * `topping`: Peanuts, sesam, parmesan, kanelsukker.
3. **Inline `{ref}`-tokens i `steps`:**
   * Giv ingredienser et kort `ref: olie`, `ref: loeg` osv., og skriv `{olie}` og `{loeg}` i fremgangsmåden. Så vises de skalerede mængder direkte inde i hvert trin i webapp'en!

---

## Opskrifter (32 retter)

* [Bagt ratatouille](recipes/bagt-ratatouille.md) ([YAML](recipes_yaml/bagt-ratatouille.yaml))
* [Beluga Bolognese](recipes/beluga-bolognese.md) ([YAML](recipes_yaml/beluga-bolognese.yaml))
* [Bolognese m. fake kød](recipes/bolognese-m-fake-koed.md) ([YAML](recipes_yaml/bolognese-m-fake-koed.yaml))
* [Chana masala](recipes/chana-masala.md) ([YAML](recipes_yaml/chana-masala.yaml))
* [Chili sin carne](recipes/chili-sin-carne.md) ([YAML](recipes_yaml/chili-sin-carne.yaml))
* [Cremede kartofler](recipes/cremede-kartofler.md) ([YAML](recipes_yaml/cremede-kartofler.yaml))
* [Dhal](recipes/dhal.md) ([YAML](recipes_yaml/dhal.yaml))
* [Falafler](recipes/falafler.md) ([YAML](recipes_yaml/falafler.yaml))
* [Gryderet (Solsikkepige special)](recipes/gryderet-solsikkepige-special.md) ([YAML](recipes_yaml/gryderet-solsikkepige-special.yaml))
* [Harira](recipes/harira.md) ([YAML](recipes_yaml/harira.yaml))
* [Hvidkålssuppe](recipes/hvidkaalssuppe.md) ([YAML](recipes_yaml/hvidkaalssuppe.yaml))
* [Indiske ris](recipes/indiske-ris.md) ([YAML](recipes_yaml/indiske-ris.yaml))
* [Kogt quinoa (basis)](recipes/kogt-quinoa.md) ([YAML](recipes_yaml/kogt-quinoa.yaml))
* [Kokosmælk Wok karry](recipes/kokosmaelk-wok-karry.md) ([YAML](recipes_yaml/kokosmaelk-wok-karry.yaml))
* [Linsekarry med ris](recipes/linsekarry-med-ris.md) ([YAML](recipes_yaml/linsekarry-med-ris.yaml))
* [Mexikansk risret](recipes/mexikansk-risret.md) ([YAML](recipes_yaml/mexikansk-risret.yaml))
* [Peanutbutter wok med nudler](recipes/peanutbutter-wok-med-nudler.md) ([YAML](recipes_yaml/peanutbutter-wok-med-nudler.yaml))
* [Quinoa i én pande med krydret paneer og grøntsager](recipes/one-pan-quinoa-with-spiced-paneer-and-vegetables.md) ([YAML](recipes_yaml/one-pan-quinoa-with-spiced-paneer-and-vegetables.yaml))
* [Red thai curry](recipes/red-thai-curry.md) ([YAML](recipes_yaml/red-thai-curry.yaml))
* [Risengrød](recipes/risengroed.md) ([YAML](recipes_yaml/risengroed.yaml))
* [Råstegte kartofler](recipes/raastegte-kartofler.md) ([YAML](recipes_yaml/raastegte-kartofler.yaml))
* [Stenalderbrød](recipes/stenalderbroed.md) ([YAML](recipes_yaml/stenalderbroed.yaml))
* [Svampe stroganoff](recipes/svampe-stroganoff.md) ([YAML](recipes_yaml/svampe-stroganoff.yaml))
* [Svampelasagne](recipes/svampelasagne.md) ([YAML](recipes_yaml/svampelasagne.yaml))
* [Thai rød karry med kylling](recipes/thai-red-curry-with-chicken.md) ([YAML](recipes_yaml/thai-red-curry-with-chicken.yaml))
* [Thai rød karrypasta](recipes/thai-roed-karrypasta.md) ([YAML](recipes_yaml/thai-roed-karrypasta.yaml))
* [Valdemarsro-style Pommes frites](recipes/valdemarsro-style-pommes-frites.md) ([YAML](recipes_yaml/valdemarsro-style-pommes-frites.yaml))
* [Vegetar fyldte peberfrugter med svampe](recipes/vegetar-fyldte-peberfrugter-med-svampe.md) ([YAML](recipes_yaml/vegetar-fyldte-peberfrugter-med-svampe.yaml))
* [Vegetar Korma med blomkål og kikærter](recipes/vegetar-korma-med-blomkaal-og-kikaerter.md) ([YAML](recipes_yaml/vegetar-korma-med-blomkaal-og-kikaerter.yaml))
* [Vegetar panang karry](recipes/vegetar-panang-karry.md) ([YAML](recipes_yaml/vegetar-panang-karry.yaml))
* [Vegetar ristaffel med grøntsager](recipes/vegetar-ristaffel-med-groentsager.md) ([YAML](recipes_yaml/vegetar-ristaffel-med-groentsager.yaml))
* [Vegetarisk omelet](recipes/vegetarisk-omelet.md) ([YAML](recipes_yaml/vegetarisk-omelet.yaml))

Se også [Samlet næringsoversigt (nutrition-summary.md)](recipes/nutrition-summary.md).
