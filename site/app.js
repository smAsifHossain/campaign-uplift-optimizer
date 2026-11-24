const $ = (selector) => document.querySelector(selector);
const state = { results: null };
const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const oneDecimal = new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const currency2 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const systemTheme = matchMedia("(prefers-color-scheme: dark)");

function savedTheme() {
  try { return localStorage.getItem("campaign-uplift-theme"); } catch (error) { return null; }
}

function themeColor(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function updateThemeControl() {
  const dark = document.documentElement.dataset.theme === "dark";
  const label = dark ? "Use light theme" : "Use dark theme";
  $("#theme-toggle").setAttribute("aria-label", label);
  $("#theme-toggle").setAttribute("title", label);
  $("#theme-toggle").setAttribute("aria-pressed", String(dark));
  $("#theme-toggle-label").textContent = label;
  $("#theme-color").setAttribute("content", dark ? "#0c1210" : "#f4f7f6");
}

function applyTheme(theme, persist = true) {
  document.documentElement.dataset.theme = theme;
  if (persist) {
    try { localStorage.setItem("campaign-uplift-theme", theme); } catch (error) { /* Theme persistence is optional. */ }
  }
  updateThemeControl();
  if (state.results) renderCharts();
}

function signed(value, digits = 1) {
  const formatted = Number(value).toFixed(digits);
  return value > 0 ? `+${formatted}` : formatted;
}

function percent(value, digits = 1) {
  return `${(value * 100).toFixed(digits)}%`;
}

function percentagePoints(value, digits = 3) {
  return `${signed(value * 100, digits)} pp`;
}

function displayName(value) {
  const names = {
    linear_t_learner: "Linear T-Learner",
    boosted_t_learner: "Boosted T-Learner",
    boosted_s_learner: "Boosted S-Learner",
    conversion_propensity: "Propensity",
    random_targeting: "Random",
  };
  return names[value] || value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function linePath(points, x, y) {
  return points.map((point, index) => `${index ? "L" : "M"}${x(point.x).toFixed(2)},${y(point.y).toFixed(2)}`).join(" ");
}

function renderEffectChart() {
  const effect = state.results.experiment;
  const container = $("#effect-chart");
  const width = window.innerWidth <= 520 ? 430 : 670;
  const height = 205;
  const left = window.innerWidth <= 520 ? 88 : 112;
  const right = window.innerWidth <= 520 ? 66 : 82;
  const plotTop = 28;
  const plotBottom = 145;
  const max = Math.max(effect.treated_conversion_rate, effect.control_conversion_rate) * 1.25;
  const x = (value) => left + (value / max) * (width - left - right);
  const ticks = Array.from({ length: 5 }, (_, index) => {
    const value = (max * index) / 4;
    return `<line class="chart-grid" x1="${x(value)}" y1="${plotTop}" x2="${x(value)}" y2="${plotBottom}" />
      <text class="chart-axis" x="${x(value)}" y="171" text-anchor="middle">${percent(value, 2)}</text>`;
  }).join("");
  const rows = [
    { label: "Treatment", value: effect.treated_conversion_rate, color: themeColor("--accent") },
    { label: "Control", value: effect.control_conversion_rate, color: themeColor("--line-strong") },
  ];
  const bars = rows.map((row, index) => {
    const y = 48 + index * 55;
    return `<text class="chart-axis" x="${left - 13}" y="${y + 18}" text-anchor="end">${row.label}</text>
      <rect x="${left}" y="${y}" width="${Math.max(1, x(row.value) - left)}" height="27" rx="2" fill="${row.color}"><title>${row.label}: ${percent(row.value, 3)}</title></rect>
      <text class="chart-label" x="${x(row.value) + 9}" y="${y + 18}">${percent(row.value, 3)}</text>`;
  }).join("");
  container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Treatment conversion rate ${percent(effect.treated_conversion_rate, 3)} versus control ${percent(effect.control_conversion_rate, 3)}">${ticks}${bars}<text class="chart-label" x="${left}" y="198">ATE ${percentagePoints(effect.absolute_effect)} · 95% CI ${percentagePoints(effect.ci_95_low)} to ${percentagePoints(effect.ci_95_high)}</text></svg>`;
}

function renderModelChart() {
  const container = $("#model-chart");
  const rows = state.results.model_comparison.filter((row) => row.validation_auuc_above_random != null);
  const labels = {
    linear_t_learner: "Linear T",
    boosted_t_learner: "Boosted T",
    boosted_s_learner: "Boosted S",
    conversion_propensity: "Propensity",
  };
  const width = window.innerWidth <= 520 ? 430 : 670;
  const height = 205;
  const left = window.innerWidth <= 520 ? 90 : 118;
  const right = window.innerWidth <= 520 ? 50 : 62;
  const max = Math.max(...rows.map((row) => row.validation_auuc_above_random)) * 1.14;
  const x = (value) => left + (value / max) * (width - left - right);
  const ticks = Array.from({ length: 5 }, (_, index) => {
    const value = (max * index) / 4;
    return `<line class="chart-grid" x1="${x(value)}" y1="18" x2="${x(value)}" y2="170" />
      <text class="chart-axis" x="${x(value)}" y="194" text-anchor="middle">${value.toFixed(2)}</text>`;
  }).join("");
  const bars = rows.map((row, index) => {
    const y = 27 + index * 37;
    const color = row.selected ? themeColor("--accent") : row.category === "predictive_baseline" ? themeColor("--orange") : themeColor("--line-strong");
    return `<text class="chart-axis" x="${left - 12}" y="${y + 14}" text-anchor="end">${labels[row.model]}</text>
      <rect x="${left}" y="${y}" width="${Math.max(1, x(row.validation_auuc_above_random) - left)}" height="20" rx="2" fill="${color}"><title>${displayName(row.model)}: ${row.validation_auuc_above_random.toFixed(3)}</title></rect>
      <text class="chart-label" x="${x(row.validation_auuc_above_random) + 8}" y="${y + 14}">${row.validation_auuc_above_random.toFixed(3)}</text>`;
  }).join("");
  container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Validation AUUC comparison for candidate models">${ticks}${bars}</svg>`;
}

function renderPolicyChart() {
  const container = $("#policy-chart");
  const curves = state.results.policy_curves;
  const series = [
    { points: curves.uplift, color: themeColor("--accent"), width: 4 },
    { points: curves.propensity, color: themeColor("--orange"), width: 3 },
    { points: curves.random, color: themeColor("--muted"), width: 2.5 },
  ];
  const width = 1050;
  const height = 300;
  const left = 62;
  const right = 30;
  const top = 25;
  const bottom = 52;
  const all = series.flatMap((item) => item.points.map((point) => point.incremental_per_1000_eligible));
  const min = Math.min(0, ...all);
  const max = Math.max(...all) * 1.12;
  const x = (value) => left + value * (width - left - right);
  const y = (value) => top + ((max - value) / (max - min || 1)) * (height - top - bottom);
  const yTicks = Array.from({ length: 5 }, (_, index) => min + ((max - min) * index) / 4);
  const grid = yTicks.map((value) => `<line class="chart-grid" x1="${left}" y1="${y(value)}" x2="${width - right}" y2="${y(value)}" /><text class="chart-axis" x="${left - 10}" y="${y(value) + 4}" text-anchor="end">${value.toFixed(2)}</text>`).join("");
  const xTicks = [0, 0.2, 0.4, 0.6, 0.8, 1].map((value) => `<text class="chart-axis" x="${x(value)}" y="${height - 22}" text-anchor="middle">${percent(value, 0)}</text>`).join("");
  const paths = series.map((item) => `<path d="${linePath(item.points.map((point) => ({ x: point.fraction, y: point.incremental_per_1000_eligible })), x, y)}" fill="none" stroke="${item.color}" stroke-width="${item.width}" stroke-linecap="round" stroke-linejoin="round" />`).join("");
  const selectedReach = state.results.selection.selected_reach_on_validation;
  container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Uplift, propensity and random targeting policy value by campaign reach">${grid}${xTicks}<line x1="${x(selectedReach)}" y1="${top}" x2="${x(selectedReach)}" y2="${height - bottom}" stroke="${themeColor("--ink")}" stroke-width="1.5" stroke-dasharray="5 5" />${paths}<text class="chart-label" x="${x(selectedReach) + 8}" y="${top + 14}">Selected ${percent(selectedReach, 0)}</text><text class="chart-axis" x="${width / 2}" y="${height - 3}" text-anchor="middle">Campaign reach</text><text class="chart-axis" transform="translate(14 ${height / 2}) rotate(-90)" text-anchor="middle">Incremental conversions / 1,000 eligible</text></svg>`;
}

function scenarioRows() {
  const population = Number($("#population-input").value);
  const maxReach = Number($("#reach-input").value) / 100;
  const contactCost = Number($("#cost-input").value) / 100;
  const conversionValue = Number($("#value-input").value);
  return state.results.policy_curves.uplift
    .filter((point) => point.fraction <= maxReach + 1e-9)
    .map((point) => {
      const targeted = Math.round(population * point.fraction);
      const incremental = population * point.incremental_per_1000_eligible / 1000;
      const low = population * point.ci_95_low / 1000;
      const high = population * point.ci_95_high / 1000;
      const profit = incremental * conversionValue - targeted * contactCost;
      const breakEven = targeted ? incremental * conversionValue / targeted : 0;
      return { fraction: point.fraction, targeted, incremental, low, high, profit, breakEven };
    });
}

function renderOptimizerChart(rows, positive) {
  const container = $("#optimizer-chart");
  const width = 760;
  const height = 210;
  const left = 67;
  const right = 25;
  const top = 18;
  const bottom = 47;
  const xMax = Number($("#reach-input").value) / 100;
  const values = rows.map((row) => row.profit);
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const pad = (max - min || 1) * 0.12;
  const yMin = min - pad;
  const yMax = max + pad;
  const x = (value) => left + (value / xMax) * (width - left - right);
  const y = (value) => top + ((yMax - value) / (yMax - yMin)) * (height - top - bottom);
  const ticks = Array.from({ length: 4 }, (_, index) => yMin + ((yMax - yMin) * index) / 3);
  const grid = ticks.map((value) => `<line class="chart-grid" x1="${left}" y1="${y(value)}" x2="${width - right}" y2="${y(value)}" /><text class="chart-axis" x="${left - 8}" y="${y(value) + 4}" text-anchor="end">${currency.format(value)}</text>`).join("");
  const points = rows.map((row) => ({ x: row.fraction, y: row.profit }));
  container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Estimated scenario profit by campaign reach">${grid}<line x1="${left}" y1="${y(0)}" x2="${width - right}" y2="${y(0)}" stroke="${themeColor("--line-strong")}" stroke-width="1.5" /><path d="${linePath(points, x, y)}" fill="none" stroke="${positive ? themeColor("--accent") : themeColor("--red")}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" /><text class="chart-axis" x="${left}" y="${height - 17}">5%</text><text class="chart-axis" x="${width - right}" y="${height - 17}" text-anchor="end">${percent(xMax, 0)} reach</text></svg>`;
}

function renderOptimizer() {
  if (!state.results) return;
  const population = Number($("#population-input").value);
  const maxReach = Number($("#reach-input").value);
  const contactCost = Number($("#cost-input").value) / 100;
  const conversionValue = Number($("#value-input").value);
  $("#population-output").textContent = number.format(population);
  $("#reach-output").textContent = `${maxReach}%`;
  $("#cost-output").textContent = currency2.format(contactCost);
  $("#value-output").textContent = currency.format(conversionValue);
  const rows = scenarioRows();
  if (!rows.length) return;
  const best = rows.reduce((winner, row) => row.profit > winner.profit ? row : winner, rows[0]);
  $("#optimizer-targeted").textContent = number.format(best.targeted);
  $("#optimizer-fraction").textContent = `${percent(best.fraction, 0)} of eligible customers`;
  $("#optimizer-incremental").textContent = signed(best.incremental, 1);
  $("#optimizer-conversion-ci").textContent = `95% interval ${signed(best.low, 1)} to ${signed(best.high, 1)}`;
  $("#optimizer-profit").textContent = currency.format(best.profit);
  $("#optimizer-break-even").textContent = `Break-even contact cost ${currency2.format(best.breakEven)}`;
  const positive = best.profit > 0;
  $(".output-verdict").classList.toggle("negative", !positive);
  $("#optimizer-decision-title").textContent = positive ? percent(best.fraction, 0) : "Do not launch";
  $("#optimizer-decision-copy").textContent = positive
    ? "Highest estimated profit within the reach limit. Keep a randomized holdout during rollout."
    : "No evaluated reach is profitable under these assumptions.";
  renderOptimizerChart(rows, positive);
}

function renderCharts() {
  renderEffectChart();
  renderModelChart();
  renderPolicyChart();
  renderOptimizer();
}

function renderResults(results) {
  state.results = results;
  if (results.status !== "portfolio_real_data") {
    const banner = $("#status-banner");
    banner.hidden = false;
    banner.textContent = "Development build: these results use labeled synthetic data and are not portfolio findings.";
  }
  const experiment = results.experiment;
  const scenario = results.default_scenario.locked_test_result_at_selected_reach;
  const reach = results.selection.selected_reach_on_validation;
  $("#chart-selected-reach").textContent = percent(reach, 0);
  $("#hero-reach").textContent = percent(reach, 0);
  $("#hero-model").textContent = displayName(results.selection.selected_model);
  $("#hero-profit").textContent = currency.format(scenario.scenario_profit);
  $("#kpi-test-rows").textContent = number.format(results.dataset.test.rows);
  $("#kpi-ate").textContent = percentagePoints(experiment.absolute_effect);
  $("#kpi-ate-ci").textContent = `95% CI ${percentagePoints(experiment.ci_95_low)} to ${percentagePoints(experiment.ci_95_high)}`;
  $("#kpi-incremental").textContent = signed(scenario.incremental_conversions, 1);
  $("#kpi-reach").textContent = percent(reach, 0);
  $("#data-source-rows").textContent = number.format(results.source.rows_scanned);
  $("#data-sample-rows").textContent = number.format(results.dataset.overall.rows);
  $("#data-missing-values").textContent = number.format(results.dataset.overall.missing_values);
  $("#method-sample-rows").textContent = number.format(results.dataset.overall.rows);
  $("#method-missing-values").textContent = number.format(results.dataset.overall.missing_values);
  $("#method-ate").textContent = percentagePoints(experiment.absolute_effect);
  $("#split-train-rows").textContent = number.format(results.dataset.train.rows);
  $("#split-validation-rows").textContent = number.format(results.dataset.validation.rows);
  $("#split-test-rows").textContent = number.format(results.dataset.test.rows);
  const inputs = results.default_scenario.inputs;
  $("#population-input").value = inputs.population;
  $("#reach-input").value = Math.round(inputs.max_reach * 100);
  $("#cost-input").value = Math.round(inputs.contact_cost * 100);
  $("#value-input").value = inputs.conversion_value;
  renderCharts();
}

async function initialize() {
  try {
    const response = await fetch("data/results.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderResults(await response.json());
    $("#loading").hidden = true;
    $("#site-content").hidden = false;
  } catch (error) {
    console.error(error);
    $("#loading").hidden = true;
    $("#load-error").hidden = false;
  }
}

$("#theme-toggle").addEventListener("click", () => {
  applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
});
["population-input", "reach-input", "cost-input", "value-input"].forEach((id) => {
  $(`#${id}`).addEventListener("input", renderOptimizer);
});
systemTheme.addEventListener("change", (event) => {
  if (!savedTheme()) applyTheme(event.matches ? "dark" : "light", false);
});
window.addEventListener("resize", () => {
  if (state.results) renderCharts();
});

updateThemeControl();
initialize();
