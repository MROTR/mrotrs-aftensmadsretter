(function () {
  const DATA = window.AFTENSMAD_DATA || { recipes: [] };
  const recipes = DATA.recipes || [];

  const catalogView = document.getElementById("catalogView");
  const detailView = document.getElementById("detailView");
  const shoppingView = document.getElementById("shoppingView");
  const shoppingContent = document.getElementById("shoppingContent");
  const shoppingNavBtn = document.getElementById("shoppingNavBtn");
  const shoppingNavText = document.getElementById("shoppingNavText");
  const addToPlanDetailBtn = document.getElementById("addToPlanDetailBtn");
  const backFromShoppingBtn = document.getElementById("backFromShoppingBtn");
  const todoExportBtn = document.getElementById("todoExportBtn");
  const shareShoppingBtn = document.getElementById("shareShoppingBtn");
  const copyShoppingBtn = document.getElementById("copyShoppingBtn");
  const clearShoppingBtn = document.getElementById("clearShoppingBtn");
  const recipeGrid = document.getElementById("recipeGrid");
  const searchInput = document.getElementById("searchInput");
  const tagFilters = document.getElementById("tagFilters");
  const headerSubtitle = document.getElementById("headerSubtitle");
  const recipeDetailContent = document.getElementById("recipeDetailContent");
  const backBtn = document.getElementById("backBtn");
  const brandHome = document.getElementById("brandHome");
  const resetChecksBtn = document.getElementById("resetChecksBtn");
  const wakeLockBtn = document.getElementById("wakeLockBtn");
  const wakeText = document.getElementById("wakeText");

  let activeTag = "alle";
  let searchQuery = "";
  let currentRecipe = null;
  let currentServings = 4;
  let targetKcal = 650;
  let enabledComponents = {};
  let wakeLockSentinel = null;

  headerSubtitle.textContent = `${DATA.total_count || recipes.length} retter (${DATA.yaml_count || 0} interaktive YAML v2)`;

  // Register Service Worker for offline mobile PWA support
  if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  }

  // Screen Wake Lock (Kitchen Mode)
  wakeLockBtn.addEventListener("click", async () => {
    if (wakeLockSentinel) {
      await wakeLockSentinel.release();
      wakeLockSentinel = null;
      wakeLockBtn.classList.remove("active");
      wakeText.textContent = "Skærmlås: Normal";
      return;
    }
    if ("wakeLock" in navigator) {
      try {
        wakeLockSentinel = await navigator.wakeLock.request("screen");
        wakeLockBtn.classList.add("active");
        wakeText.textContent = "Køkkentilstand: Skærm tændt";
        wakeLockSentinel.addEventListener("release", () => {
          wakeLockSentinel = null;
          wakeLockBtn.classList.remove("active");
          wakeText.textContent = "Skærmlås: Normal";
        });
      } catch (e) {
        alert("Din browser tillod ikke skærmlås i dette vindue.");
      }
    } else {
      alert("Skærmlås (Wake Lock API) understøttes ikke i denne browser.");
    }
  });

  function formatNumDa(val) {
    if (val === null || val === undefined || isNaN(val)) return "";
    if (Math.abs(val - Math.round(val)) < 0.05) return String(Math.round(val));
    if (Math.abs(val * 4 - Math.round(val * 4)) < 0.06) {
      const q = Math.round(val * 4) / 4;
      return q.toString().replace(".", ",");
    }
    return val.toFixed(1).replace(".", ",");
  }

  // Converts canonical amounts (ml, g, stk) into Danish kitchen units (dl, spsk, tsk, dåse)
  // with sensible kitchen rounding (e.g. 0.75 spsk [11.25 ml] -> 2 tsk).
  function smartKitchenConvert(amount, unit, displayUnit, unitWeightG) {
    const pref = (displayUnit || unit || "").toLowerCase();
    const u = (unit || "").toLowerCase();

    if (pref === "dåse" && (u === "g" || u === "ml")) {
      const canW = unitWeightG || 400;
      const cans = amount / canW;
      return { amount: Math.round(cans * 2) / 2, unit: "dåse" };
    }

    if (u === "ml") {
      const ml = amount;
      if (pref === "spsk" || pref === "tsk" || pref === "auto") {
        if (pref === "spsk") {
          const spsk = ml / 15.0;
          const nearestHalf = Math.round(spsk * 2) / 2;
          // If it's >= 7 ml and close to a clean .0 or .5 spsk, show spsk; otherwise step down to tsk (e.g. 11.25 ml = 0.75 spsk -> 2 tsk)
          if (ml >= 7.0 && Math.abs(spsk - nearestHalf) < 0.08) {
            return { amount: nearestHalf, unit: "spsk" };
          }
          const tsk = Math.max(0.25, Math.round((ml / 5.0) * 2) / 2);
          return { amount: tsk, unit: "tsk" };
        } else {
          // pref === "tsk" -> step up to spsk if >= 30 ml (2 spsk) and clean
          if (ml >= 30.0 && Math.abs(ml / 15.0 - Math.round(ml / 15.0)) < 0.1) {
            return { amount: Math.round(ml / 15.0), unit: "spsk" };
          }
          const tsk = Math.max(0.25, Math.round((ml / 5.0) * 2) / 2);
          return { amount: tsk, unit: "tsk" };
        }
      }
      if (pref === "dl") {
        if (ml < 45.0) {
          return { amount: Math.round((ml / 15.0) * 2) / 2, unit: "spsk" };
        }
        return { amount: Math.round((ml / 100.0) * 4) / 4, unit: "dl" };
      }
      return { amount: Math.round(ml), unit: "ml" };
    }

    return { amount: amount, unit: pref === "stk" ? "" : (pref || u) };
  }

  function scaleIngredientAmount(ing, ratio) {
    if (ing.amount === null || ing.amount === undefined) return null;
    if (ing.scaling === "fixed") return ing.amount;
    if (ing.scaling === "sublinear") {
      // Spices and frying fats scale gently when making large batches
      return ing.amount * Math.pow(ratio, 0.8);
    }
    return ing.amount * ratio;
  }

  function formatScaledIngredient(ing, ratio) {
    const scaledCanonical = scaleIngredientAmount(ing, ratio);
    const prep = ing.prep ? `, ${ing.prep}` : "";
    if (scaledCanonical === null) {
      return `${ing.label}${prep}`;
    }
    const conv = smartKitchenConvert(scaledCanonical, ing.unit, ing.display_unit, ing.unit_weight_g);
    const amtStr = formatNumDa(conv.amount);
    const uStr = conv.unit === "stk" ? "" : conv.unit;
    return `${amtStr}${uStr ? " " + uStr : ""} ${ing.label}${prep}`;
  }

  function renderInlineStepText(stepText, recipe, ratio) {
    const lookup = recipe.ref_lookup || {};
    return stepText.replace(/\{([a-z0-9_]+)\}/g, (_, refKey) => {
      const ing = lookup[refKey];
      if (!ing) return refKey;
      const scaledCanonical = scaleIngredientAmount(ing, ratio);
      if (scaledCanonical === null) {
        return `<span class="inline-ing">${ing.label.toLowerCase()}</span>`;
      }
      const conv = smartKitchenConvert(scaledCanonical, ing.unit, ing.display_unit, ing.unit_weight_g);
      const uStr = conv.unit === "stk" ? "" : conv.unit;
      const amtBadge = ` (${formatNumDa(conv.amount)}${uStr ? " " + uStr : ""})`;
      return `<span class="inline-ing">${ing.label.toLowerCase()}${amtBadge}</span>`;
    });
  }

  function collectTags() {
    const tagSet = new Set(["alle", "yaml_v2"]);
    recipes.forEach((r) => (r.tags || []).forEach((t) => tagSet.add(t)));
    tagFilters.innerHTML = "";
    Array.from(tagSet).forEach((tag) => {
      const btn = document.createElement("button");
      btn.className = "tag-pill" + (tag === activeTag ? " active" : "");
      btn.textContent = tag === "alle" ? "Alle retter" : (tag === "yaml_v2" ? "✨ Interaktive (YAML v2)" : `#${tag}`);
      btn.addEventListener("click", () => {
        activeTag = tag;
        collectTags();
        renderCatalog();
      });
      tagFilters.appendChild(btn);
    });
  }

  function getDefaultMealPerPortion(recipe) {
    const v = (recipe.variants || [])[1] || (recipe.variants || [])[0];
    if (v) return v;
    return { kcal: 0, protein: 0, carb: 0, fat: 0, cooked_weight: 0 };
  }

  function renderCatalog() {
    const q = searchQuery.trim().toLowerCase();
    const filtered = recipes.filter((r) => {
      if (activeTag === "yaml_v2" && r.format !== "yaml_v2") return false;
      if (activeTag !== "alle" && activeTag !== "yaml_v2" && !(r.tags || []).includes(activeTag)) return false;
      if (!q) return true;
      const inTitle = r.title.toLowerCase().includes(q);
      const inTags = (r.tags || []).some((t) => t.toLowerCase().includes(q));
      const inIngs = (r.components || []).some((c) =>
        (c.ingredients || []).some((i) => (i.label || "").toLowerCase().includes(q))
      );
      return inTitle || inTags || inIngs;
    });

    recipeGrid.innerHTML = "";
    filtered.forEach((r) => {
      const card = document.createElement("article");
      card.className = "recipe-card";
      const portion = getDefaultMealPerPortion(r);
      const isYaml = r.format === "yaml_v2";
      const imgSrc = (r.image || "").replace(/^\.\.\/Files\//, "./Files/");

      card.innerHTML = `
        <div class="card-img-wrap">
          ${imgSrc ? `<img src="${imgSrc}" alt="${r.title}" loading="lazy" onerror="this.style.display='none'" />` : ""}
          <span class="format-badge ${isYaml ? "yaml" : "legacy"}">${isYaml ? "YAML v2 • Skalérbar" : "Markdown"}</span>
        </div>
        <div class="card-body">
          <h2 class="card-title">${r.title}</h2>
          <div class="card-meta">
            <span>👥 ${r.servings} pers.</span>
            ${r.time && r.time.total_min ? `<span>⏱ ${r.time.total_min} min.</span>` : ""}
          </div>
          <div class="card-macros">
            <span>Pr. portion: <strong>${Math.round(portion.kcal)} kcal</strong></span>
            <span>P: ${portion.protein}g • K: ${portion.carb}g • F: ${portion.fat}g</span>
          </div>
        </div>
      `;
      card.addEventListener("click", () => openRecipe(r.id));
      recipeGrid.appendChild(card);
    });
  }

  function getCheckState(recipeId, key) {
    try {
      const raw = localStorage.getItem(`checks_${recipeId}`);
      const map = raw ? JSON.parse(raw) : {};
      return !!map[key];
    } catch (e) {
      return false;
    }
  }

  function setCheckState(recipeId, key, val) {
    try {
      const raw = localStorage.getItem(`checks_${recipeId}`);
      const map = raw ? JSON.parse(raw) : {};
      map[key] = val;
      localStorage.setItem(`checks_${recipeId}`, JSON.stringify(map));
    } catch (e) {}
  }

  function openRecipe(recipeId) {
    const r = recipes.find((x) => x.id === recipeId);
    if (!r) return;
    currentRecipe = r;
    currentServings = r.servings || 4;
    targetKcal = r.standard_kcal_per_portion || 650;
    enabledComponents = {};
    (r.components || []).forEach((c) => {
      enabledComponents[c.id] = c.default_enabled !== false;
    });

    catalogView.classList.add("hidden");
    detailView.classList.remove("hidden");
    location.hash = `#${r.id}`;
    window.scrollTo({ top: 0, behavior: "smooth" });
    renderRecipeDetail();
  }

  function computeActiveNutrition(recipe, ratio) {
    let rawWeight = 0;
    let cookedWeight = 0;
    let kcal = 0;
    let protein = 0;
    let carb = 0;
    let fat = 0;
    let fiber = 0;

    (recipe.components || []).forEach((c) => {
      if (!enabledComponents[c.id]) return;
      const t = c.totals || {};
      rawWeight += (t.raw_weight || 0) * ratio;
      cookedWeight += (t.cooked_weight || 0) * ratio;
      kcal += (t.kcal || 0) * ratio;
      protein += (t.protein || 0) * ratio;
      carb += (t.carb || 0) * ratio;
      fat += (t.fat || 0) * ratio;
      fiber += (t.fiber || 0) * ratio;
    });

    return { rawWeight, cookedWeight, kcal, protein, carb, fat, fiber };
  }

  function renderRecipeDetail() {
    if (!currentRecipe) return;
    const r = currentRecipe;
    const ratio = currentServings / (r.servings || 4);
    const activeTotals = computeActiveNutrition(r, ratio);

    const perPortionKcal = currentServings > 0 ? activeTotals.kcal / currentServings : 0;
    const perPortionCookedG = currentServings > 0 ? activeTotals.cookedWeight / currentServings : 0;
    const perPortionRawG = currentServings > 0 ? activeTotals.rawWeight / currentServings : 0;
    const perPortionProtein = currentServings > 0 ? activeTotals.protein / currentServings : 0;
    const perPortionCarb = currentServings > 0 ? activeTotals.carb / currentServings : 0;
    const perPortionFat = currentServings > 0 ? activeTotals.fat / currentServings : 0;
    const perPortionFiber = currentServings > 0 ? activeTotals.fiber / currentServings : 0;

    const per100CookedKcal = activeTotals.cookedWeight > 0 ? (activeTotals.kcal / activeTotals.cookedWeight) * 100 : 0;
    const per100CookedProtein = activeTotals.cookedWeight > 0 ? (activeTotals.protein / activeTotals.cookedWeight) * 100 : 0;
    const per100CookedCarb = activeTotals.cookedWeight > 0 ? (activeTotals.carb / activeTotals.cookedWeight) * 100 : 0;
    const per100CookedFat = activeTotals.cookedWeight > 0 ? (activeTotals.fat / activeTotals.cookedWeight) * 100 : 0;
    const per100CookedFiber = activeTotals.cookedWeight > 0 ? (activeTotals.fiber / activeTotals.cookedWeight) * 100 : 0;

    // Target kcal plate weight calculation (how many grams of cooked dish to put on plate for targetKcal)
    const targetPlateGrams = per100CookedKcal > 0 ? Math.round((targetKcal / per100CookedKcal) * 100) : 0;
    const totalTargetPortionsInPot = targetKcal > 0 ? (activeTotals.kcal / targetKcal).toFixed(1).replace(".", ",") : "0";

    const roleLabels = {
      base: "Basisret",
      carb: "Kulhydrat / Tilbehør",
      side: "Tilbehør",
      optional: "Tilvalg",
      topping: "Topping"
    };

    recipeDetailContent.innerHTML = `
      <div class="hero-card">
        <div class="hero-header">
          <h2>${r.title}</h2>
          <div class="hero-meta">
            <span>👥 Standard: <strong>${r.servings} pers.</strong></span>
            ${r.time && r.time.total_min ? `<span>⏱ Tid i alt: <strong>${r.time.total_min} min.</strong></span>` : ""}
            ${r.time && r.time.active_min ? `<span>🔪 Arbejdstid: <strong>${r.time.active_min} min.</strong></span>` : ""}
            ${r.source && r.source.startsWith("http") ? `<a href="${r.source}" target="_blank" rel="noopener">🔗 Original opskrift</a>` : ""}
          </div>
          ${r.notes ? `<p style="margin:10px 0 0 0; font-size:0.86rem; color:var(--text-muted);">${r.notes}</p>` : ""}
        </div>
      </div>

      <div class="interactive-panel">
        <div class="panel-row">
          <div>
            <div class="panel-label">1. Skalér antal portioner</div>
            <div style="font-size:0.82rem; color:var(--text-muted);">Alle mængder (også inde i fremgangsmåden) opdateres automatisk</div>
          </div>
          <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
            <div class="stepper">
              <button id="decServBtn" aria-label="Færre portioner">−</button>
              <span id="servDisplay">${currentServings} pers.</span>
              <button id="incServBtn" aria-label="Flere portioner">+</button>
            </div>
            <button id="resetServBtn" class="snap-btn" title="Gendan opskriftens oprindelige antal (${r.servings} pers., passer til hele dåser)">
              Hele dåser (${r.servings} pers.)
            </button>
          </div>
        </div>

        <div>
          <div class="panel-label" style="margin-bottom:8px;">2. Til/fravælg moduler i næringsberegningen</div>
          <div class="component-toggles" id="compToggleContainer"></div>
        </div>

        <div>
          <div class="panel-label" style="margin-bottom:8px;">3. Næringsindhold (valgte moduler)</div>
          <div class="nutrition-grid">
            <div class="stat-card highlight">
              <div class="stat-title">Pr. portion (1/${currentServings})</div>
              <div class="stat-value">${Math.round(perPortionKcal)} kcal</div>
              <div class="stat-sub">Spiseklar: ~${Math.round(perPortionCookedG)} g (rå: ${Math.round(perPortionRawG)} g)</div>
            </div>
            <div class="stat-card">
              <div class="stat-title">Makroer pr. portion</div>
              <div class="stat-value" style="font-size:1.02rem;">P: ${formatNumDa(perPortionProtein)}g • K: ${formatNumDa(perPortionCarb)}g</div>
              <div class="stat-sub">Fedt: ${formatNumDa(perPortionFat)}g • Fibre: ${formatNumDa(perPortionFiber)}g</div>
            </div>
            <div class="stat-card">
              <div class="stat-title">Pr. 100 g spiseklar ret</div>
              <div class="stat-value">${formatNumDa(per100CookedKcal)} kcal</div>
              <div class="stat-sub">P: ${formatNumDa(per100CookedProtein)}g • K: ${formatNumDa(per100CookedCarb)}g</div>
              <div class="stat-sub">Fedt: ${formatNumDa(per100CookedFat)}g • Fibre: ${formatNumDa(per100CookedFiber)}g</div>
            </div>
            <div class="stat-card">
              <div class="stat-title">Hele gryden (${currentServings} pers.)</div>
              <div class="stat-value">${Math.round(activeTotals.kcal)} kcal</div>
              <div class="stat-sub">Samlet spiseklar: ~${Math.round(activeTotals.cookedWeight)} g</div>
            </div>
          </div>
        </div>

        <div class="target-kcal-bar">
          <div>
            🎯 <strong>Standardiseret portion:</strong> Ønsker du en portion på præcis
            <input type="number" id="targetKcalInput" value="${targetKcal}" step="50" min="200" max="1500" />
            <strong>kcal</strong>?
          </div>
          <div>
            Øs <strong>~${targetPlateGrams} g spiseklar mad</strong> op på tallerkenen
            <span style="color:var(--text-muted);">(${totalTargetPortionsInPot} std.-portioner i gryden)</span>
          </div>
        </div>
      </div>

      <div class="two-col">
        <div class="content-card">
          <h3>Ingredienser (${currentServings} pers.)</h3>
          <div id="ingredientsContainer"></div>
        </div>
        <div class="content-card">
          <h3>Fremgangsmåde</h3>
          <div id="stepsContainer"></div>
        </div>
      </div>
    `;

    // Bind stepper buttons
    document.getElementById("decServBtn").addEventListener("click", () => {
      if (currentServings > 1) {
        currentServings -= 1;
        renderRecipeDetail();
      }
    });
    document.getElementById("incServBtn").addEventListener("click", () => {
      currentServings += 1;
      renderRecipeDetail();
    });
    document.getElementById("resetServBtn").addEventListener("click", () => {
      currentServings = r.servings || 4;
      renderRecipeDetail();
    });

    const kcalInput = document.getElementById("targetKcalInput");
    kcalInput.addEventListener("change", (e) => {
      const val = parseInt(e.target.value, 10);
      if (val >= 100 && val <= 2500) {
        targetKcal = val;
        renderRecipeDetail();
      }
    });

    // Render component toggle chips
    const compToggleContainer = document.getElementById("compToggleContainer");
    (r.components || []).forEach((c) => {
      const btn = document.createElement("button");
      const isOn = !!enabledComponents[c.id];
      const compKcalPerPortion = Math.round(((c.totals?.kcal || 0) * ratio) / currentServings);
      btn.className = "comp-toggle" + (isOn ? " active" : "");
      btn.innerHTML = `
        <span>${isOn ? "☑" : "☐"} ${c.title}</span>
        <span class="comp-role-tag">${roleLabels[c.role] || c.role} • ${compKcalPerPortion} kcal/pers</span>
      `;
      btn.addEventListener("click", () => {
        enabledComponents[c.id] = !enabledComponents[c.id];
        renderRecipeDetail();
      });
      compToggleContainer.appendChild(btn);
    });

    // Render ingredients
    const ingContainer = document.getElementById("ingredientsContainer");
    (r.components || []).forEach((c) => {
      const sec = document.createElement("div");
      const isOn = !!enabledComponents[c.id];
      sec.className = "comp-section" + (isOn ? "" : " disabled");
      const compRawG = Math.round((c.totals?.raw_weight || 0) * ratio);
      sec.innerHTML = `<h4><span>${c.title}</span> <span>${compRawG > 0 ? compRawG + " g rå" : ""}</span></h4>`;
      const ul = document.createElement("ul");
      ul.className = "check-list";

      (c.ingredients || []).forEach((ing, idx) => {
        const checkKey = `ing_${c.id}_${idx}`;
        const checked = getCheckState(r.id, checkKey);
        const li = document.createElement("li");
        li.className = "check-item" + (checked ? " checked" : "");
        const text = formatScaledIngredient(ing, ratio);
        const scaledRawG = Math.round((ing.raw_g || 0) * ratio);
        const weightNote = scaledRawG > 0 && ing.display_unit !== "g" ? `<span class="ing-weight-pill">(~${scaledRawG} g)</span>` : "";
        const fridaBadge = ing.frida_id ? `<span class="frida-badge" title="DTU Fødevaredatabanken (Frida #${ing.frida_id})">Frida</span>` : "";

        li.innerHTML = `
          <input type="checkbox" ${checked ? "checked" : ""} />
          <span>${text}${weightNote}${fridaBadge}</span>
        `;
        li.addEventListener("click", () => {
          const nextVal = !li.classList.contains("checked");
          li.classList.toggle("checked", nextVal);
          li.querySelector("input").checked = nextVal;
          setCheckState(r.id, checkKey, nextVal);
        });
        ul.appendChild(li);
      });
      sec.appendChild(ul);
      ingContainer.appendChild(sec);
    });

    // Render steps with inline scaled quantities
    const stepsContainer = document.getElementById("stepsContainer");
    (r.steps || []).forEach((sg, sIdx) => {
      const sec = document.createElement("div");
      const isDimmed = sg.component_id && enabledComponents[sg.component_id] === false;
      sec.className = "comp-section" + (isDimmed ? " disabled" : "");
      if (sg.section) {
        sec.innerHTML = `<h4>${sg.section}</h4>`;
      }
      const ul = document.createElement("ul");
      ul.className = "check-list";
      (sg.items || []).forEach((stepText, itemIdx) => {
        const checkKey = `step_${sIdx}_${itemIdx}`;
        const checked = getCheckState(r.id, checkKey);
        const li = document.createElement("li");
        li.className = "check-item" + (checked ? " checked" : "");
        const renderedHtml = renderInlineStepText(stepText, r, ratio);
        li.innerHTML = `
          <input type="checkbox" ${checked ? "checked" : ""} />
          <span>${renderedHtml}</span>
        `;
        li.addEventListener("click", () => {
          const nextVal = !li.classList.contains("checked");
          li.classList.toggle("checked", nextVal);
          li.querySelector("input").checked = nextVal;
          setCheckState(r.id, checkKey, nextVal);
        });
        ul.appendChild(li);
      });
      sec.appendChild(ul);
      stepsContainer.appendChild(sec);
    });
  }

  // --- MEAL PLANNER & SUPERMARKET SHOPPING LIST ---
  const AISLE_ORDER = [
    { key: "frugt_og_groent", title: "🥬 Frugt & Grønt" },
    { key: "broed", title: "🍞 Brød" },
    { key: "koed_og_fisk", title: "🥩 Kød, Fisk & Plantefars" },
    { key: "mejeri_og_aeg", title: "🧀 Mejeri & Æg" },
    { key: "kolonial", title: "🥫 Kolonial & Konserves" },
    { key: "frost", title: "❄️ Frost" },
    { key: "basis_og_krydderier", title: "🧂 Krydderier, Olie & Basisvarer (tjek lager hjemme)" }
  ];

  function loadMealPlan() {
    try {
      const raw = localStorage.getItem("aftensmad_meal_plan");
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  }

  function saveMealPlan(plan) {
    try {
      localStorage.setItem("aftensmad_meal_plan", JSON.stringify(plan));
    } catch (e) {}
    updateShoppingBadge();
  }

  function updateShoppingBadge() {
    const plan = loadMealPlan();
    shoppingNavText.textContent = `Indkøbsliste (${plan.length})`;
    if (plan.length > 0) {
      shoppingNavBtn.classList.add("active");
    } else {
      shoppingNavBtn.classList.remove("active");
    }
  }

  function addCurrentRecipeToPlan() {
    if (!currentRecipe) return;
    const plan = loadMealPlan();
    const enabledCompIds = Object.keys(enabledComponents).filter((k) => enabledComponents[k]);
    const existingIdx = plan.findIndex((p) => p.recipeId === currentRecipe.id);
    const entry = {
      recipeId: currentRecipe.id,
      title: currentRecipe.title,
      servings: currentServings,
      enabledCompIds
    };
    if (existingIdx >= 0) {
      plan[existingIdx] = entry;
    } else {
      plan.push(entry);
    }
    saveMealPlan(plan);
    addToPlanDetailBtn.textContent = `✓ Tilføjet (${currentServings} pers.) — Se liste`;
  }

  function aggregateShoppingList() {
    const plan = loadMealPlan();
    const byItem = {};

    plan.forEach((planEntry) => {
      const r = recipes.find((x) => x.id === planEntry.recipeId);
      if (!r) return;
      const ratio = (planEntry.servings || r.servings || 4) / (r.servings || 4);
      const activeSet = new Set(planEntry.enabledCompIds || (r.components || []).map((c) => c.id));

      (r.components || []).forEach((c) => {
        if (!activeSet.has(c.id)) return;
        (c.ingredients || []).forEach((ing) => {
          const itemKey = (ing.item || ing.label || "").toLowerCase();
          if (!itemKey || itemKey === "vand") return;
          const groupKey = `${itemKey}__${ing.unit || ""}__${ing.display_unit || ""}`;
          if (!byItem[groupKey]) {
            byItem[groupKey] = {
              item: itemKey,
              label: ing.label || ing.item,
              unit: ing.unit || "",
              display_unit: ing.display_unit || ing.unit || "",
              unit_weight_g: ing.unit_weight_g || 400,
              aisle: ing.aisle || "kolonial",
              totalAmount: 0,
              hasAmount: false,
              totalRawG: 0,
              recipes: new Set()
            };
          }
          const scaledAmt = scaleIngredientAmount(ing, ratio);
          if (scaledAmt !== null && scaledAmt !== undefined) {
            byItem[groupKey].totalAmount += scaledAmt;
            byItem[groupKey].hasAmount = true;
          }
          byItem[groupKey].totalRawG += (ing.raw_g || 0) * ratio;
          byItem[groupKey].recipes.add(r.title);
        });
      });
    });

    return Object.values(byItem);
  }

  function renderShoppingView() {
    const plan = loadMealPlan();
    if (plan.length === 0) {
      shoppingContent.innerHTML = `
        <div class="content-card" style="text-align:center; padding:36px 16px;">
          <h3>Din ugeplan / indkøbsliste er tom</h3>
          <p style="color:var(--text-muted);">Åbn en opskrift, vælg antal personer, og tryk på <strong>"🛒 + Tilføj til indkøbsliste"</strong> for at samle ingredienser sorteret efter supermarkedets afdelinger.</p>
        </div>
      `;
      return;
    }

    const aggregated = aggregateShoppingList();
    const byAisle = {};
    AISLE_ORDER.forEach((a) => { byAisle[a.key] = []; });
    aggregated.forEach((entry) => {
      const k = byAisle[entry.aisle] ? entry.aisle : "kolonial";
      byAisle[k].push(entry);
    });

    const includePantryInExport = localStorage.getItem("todo_include_pantry") === "true";

    let html = `
      <div class="todo-banner">
        <div>
          <strong>☑️ Microsoft To Do & Deling:</strong>
          <span style="color:var(--text-muted);">
            "Kopiér til Microsoft To Do" kopierer alle ikke-afkrydsede varer som rene linjer (i butiksrækkefølge). Når du sætter ind i en delt liste i Microsoft To Do, spørger To Do om den skal oprette hver linje som sit eget punkt!
          </span>
        </div>
        <div class="todo-banner-actions">
          <label style="display:inline-flex; align-items:center; gap:6px; cursor:pointer; font-size:0.83rem;">
            <input type="checkbox" id="includePantryToggle" ${includePantryInExport ? "checked" : ""} />
            <span>Medtag krydderier/basisvarer ved eksport</span>
          </label>
          <a href="https://to-do.office.com/tasks/" target="_blank" rel="noopener" style="color:var(--blue); font-weight:600; text-decoration:none; font-size:0.83rem;">
            Åbn Microsoft To Do ↗
          </a>
        </div>
      </div>
      <div class="content-card" style="margin-bottom:16px;">
        <h3>Valgte retter i ugeplanen (${plan.length})</h3>
        <div class="plan-card-list" id="planChipsContainer"></div>
      </div>
      <div class="aisle-grid" id="aisleGridContainer"></div>
    `;
    shoppingContent.innerHTML = html;

    const pantryToggle = document.getElementById("includePantryToggle");
    if (pantryToggle) {
      pantryToggle.addEventListener("change", (e) => {
        localStorage.setItem("todo_include_pantry", e.target.checked ? "true" : "false");
      });
    }

    const chipsContainer = document.getElementById("planChipsContainer");
    plan.forEach((p, idx) => {
      const chip = document.createElement("div");
      chip.className = "plan-chip";
      chip.innerHTML = `
        <span><strong>${p.title}</strong> (${p.servings} pers.)</span>
        <button title="Fjern fra ugeplan" data-idx="${idx}">✕</button>
      `;
      chip.querySelector("button").addEventListener("click", () => {
        const nextPlan = loadMealPlan();
        nextPlan.splice(idx, 1);
        saveMealPlan(nextPlan);
        renderShoppingView();
      });
      chipsContainer.appendChild(chip);
    });

    const aisleGrid = document.getElementById("aisleGridContainer");
    AISLE_ORDER.forEach((aisleInfo) => {
      const items = byAisle[aisleInfo.key] || [];
      if (items.length === 0) return;

      const card = document.createElement("div");
      card.className = "aisle-card";
      card.innerHTML = `<h4>${aisleInfo.title}</h4>`;
      const ul = document.createElement("ul");
      ul.className = "check-list";

      items.forEach((entry, iIdx) => {
        const checkKey = `shop_${aisleInfo.key}_${entry.item}_${iIdx}`;
        const checked = getCheckState("shopping_list", checkKey);
        const li = document.createElement("li");
        li.className = "check-item" + (checked ? " checked" : "");

        let qtyText = entry.label;
        if (entry.hasAmount) {
          const conv = smartKitchenConvert(entry.totalAmount, entry.unit, entry.display_unit, entry.unit_weight_g);
          const uStr = conv.unit === "stk" ? "" : conv.unit;
          qtyText = `<strong>${formatNumDa(conv.amount)}${uStr ? " " + uStr : ""}</strong> ${entry.label}`;
        }
        const rawG = Math.round(entry.totalRawG);
        const gNote = rawG > 0 && entry.display_unit !== "g" ? `<span class="ing-weight-pill">(~${rawG} g)</span>` : "";
        const fromList = Array.from(entry.recipes).join(", ");

        li.innerHTML = `
          <input type="checkbox" ${checked ? "checked" : ""} />
          <span>${qtyText}${gNote}<span class="recipe-from-tag">[${fromList}]</span></span>
        `;
        li.addEventListener("click", () => {
          const nextVal = !li.classList.contains("checked");
          li.classList.toggle("checked", nextVal);
          li.querySelector("input").checked = nextVal;
          setCheckState("shopping_list", checkKey, nextVal);
        });
        ul.appendChild(li);
      });
      card.appendChild(ul);
      aisleGrid.appendChild(card);
    });
  }

  function showShoppingView() {
    catalogView.classList.add("hidden");
    detailView.classList.add("hidden");
    shoppingView.classList.remove("hidden");
    location.hash = "#indkoebsliste";
    renderShoppingView();
  }

  function showCatalog() {
    currentRecipe = null;
    detailView.classList.add("hidden");
    shoppingView.classList.add("hidden");
    catalogView.classList.remove("hidden");
    history.pushState("", document.title, window.location.pathname + window.location.search);
  }

  backBtn.addEventListener("click", showCatalog);
  backFromShoppingBtn.addEventListener("click", showCatalog);
  brandHome.addEventListener("click", showCatalog);
  shoppingNavBtn.addEventListener("click", showShoppingView);
  addToPlanDetailBtn.addEventListener("click", () => {
    if (addToPlanDetailBtn.textContent.startsWith("✓")) {
      showShoppingView();
    } else {
      addCurrentRecipeToPlan();
    }
  });

  clearShoppingBtn.addEventListener("click", () => {
    saveMealPlan([]);
    localStorage.removeItem("checks_shopping_list");
    renderShoppingView();
  });

  function formatShoppingEntryPlain(entry) {
    let text = entry.label;
    if (entry.hasAmount) {
      const conv = smartKitchenConvert(entry.totalAmount, entry.unit, entry.display_unit, entry.unit_weight_g);
      const uStr = conv.unit === "stk" ? "" : conv.unit;
      text = `${formatNumDa(conv.amount)}${uStr ? " " + uStr : ""} ${entry.label}`;
    }
    const rawG = Math.round(entry.totalRawG);
    if (rawG > 0 && entry.display_unit !== "g" && entry.unit !== "g" && entry.unit !== "ml") {
      text += ` (~${rawG} g)`;
    }
    return text;
  }

  // Builds plain newline-separated tasks specifically for Microsoft To Do multi-task paste
  // (excludes already-checked items, and excludes pantry spices unless toggled on)
  function buildMicrosoftToDoLines() {
    const aggregated = aggregateShoppingList();
    const byAisle = {};
    AISLE_ORDER.forEach((a) => { byAisle[a.key] = []; });
    aggregated.forEach((entry) => {
      const k = byAisle[entry.aisle] ? entry.aisle : "kolonial";
      byAisle[k].push(entry);
    });

    const includePantry = localStorage.getItem("todo_include_pantry") === "true";
    const lines = [];

    AISLE_ORDER.forEach((a) => {
      if (a.key === "basis_og_krydderier" && !includePantry) return;
      const items = byAisle[a.key] || [];
      items.forEach((entry, iIdx) => {
        const checkKey = `shop_${a.key}_${entry.item}_${iIdx}`;
        const isChecked = getCheckState("shopping_list", checkKey);
        if (isChecked) return; // Skip items already checked off at home
        lines.push(formatShoppingEntryPlain(entry));
      });
    });
    return lines;
  }

  function buildFullFormattedShoppingText(excludeCheckedAndPantry) {
    const plan = loadMealPlan();
    const aggregated = aggregateShoppingList();
    const byAisle = {};
    AISLE_ORDER.forEach((a) => { byAisle[a.key] = []; });
    aggregated.forEach((entry) => {
      const k = byAisle[entry.aisle] ? entry.aisle : "kolonial";
      byAisle[k].push(entry);
    });

    const includePantry = localStorage.getItem("todo_include_pantry") === "true";
    const dishTitles = plan.map((p) => `${p.title} (${p.servings} pers.)`).join(", ");
    const lines = [`🛒 INDKØBSLISTE: ${dishTitles}`];

    AISLE_ORDER.forEach((a) => {
      if (excludeCheckedAndPantry && a.key === "basis_og_krydderier" && !includePantry) return;
      const items = byAisle[a.key] || [];
      const activeItems = [];
      items.forEach((entry, iIdx) => {
        const checkKey = `shop_${a.key}_${entry.item}_${iIdx}`;
        const isChecked = getCheckState("shopping_list", checkKey);
        if (excludeCheckedAndPantry && isChecked) return;
        activeItems.push(formatShoppingEntryPlain(entry));
      });
      if (!activeItems.length) return;
      lines.push(`\n${a.title}:`);
      activeItems.forEach((txt) => lines.push(`• ${txt}`));
    });
    return lines.join("\n");
  }

  todoExportBtn.addEventListener("click", async () => {
    const todoLines = buildMicrosoftToDoLines();
    if (!todoLines.length) {
      alert("Ingen uafkrydsede varer at eksportere.");
      return;
    }
    const payload = todoLines.join("\n");
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(payload);
    }
    todoExportBtn.textContent = `✓ ${todoLines.length} varer kopieret til To Do!`;
    setTimeout(() => {
      todoExportBtn.textContent = "☑️ Kopiér til Microsoft To Do";
    }, 3500);
  });

  shareShoppingBtn.addEventListener("click", async () => {
    const shareText = buildFullFormattedShoppingText(true);
    if (navigator.share) {
      try {
        await navigator.share({
          title: "Indkøbsliste",
          text: shareText
        });
        return;
      } catch (e) {
        if (e && e.name === "AbortError") return;
      }
    }
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(shareText);
      shareShoppingBtn.textContent = "✓ Kopieret (klar til deling)!";
      setTimeout(() => {
        shareShoppingBtn.textContent = "📤 Del liste…";
      }, 2500);
    }
  });

  copyShoppingBtn.addEventListener("click", () => {
    const text = buildFullFormattedShoppingText(false);
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text);
      copyShoppingBtn.textContent = "✓ Kopieret!";
      setTimeout(() => { copyShoppingBtn.textContent = "📋 Kopiér alt"; }, 2000);
    }
  });

  resetChecksBtn.addEventListener("click", () => {
    if (!currentRecipe) return;
    localStorage.removeItem(`checks_${currentRecipe.id}`);
    renderRecipeDetail();
  });

  searchInput.addEventListener("input", (e) => {
    searchQuery = e.target.value || "";
    renderCatalog();
  });

  // Initial render & deep-link support (#dhal or #indkoebsliste)
  updateShoppingBadge();
  collectTags();
  renderCatalog();
  function handleHashNavigation() {
    if (location.hash === "#indkoebsliste") {
      showShoppingView();
      return;
    }
    if (location.hash && location.hash.length > 1) {
      const targetId = location.hash.slice(1);
      if (recipes.some((r) => r.id === targetId)) {
        shoppingView.classList.add("hidden");
        addToPlanDetailBtn.textContent = "🛒 + Tilføj til indkøbsliste";
        openRecipe(targetId);
      }
    } else if (currentRecipe || !shoppingView.classList.contains("hidden")) {
      showCatalog();
    }
  }
  window.addEventListener("hashchange", handleHashNavigation);
  handleHashNavigation();
})();
