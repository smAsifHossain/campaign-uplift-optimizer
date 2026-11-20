const state = { results: null, currentView: "overview" };

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat("en-US", { maximumFractionDigits: 3 });
const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const currency2 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const percent = (value, digits = 2) => `${(100 * value).toFixed(digits)}%`;
const signed = (value, digits = 3) => `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
const titleCase = (value) => value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

function themeColor(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function showView(name, updateHash = true) {
  state.currentView = name;
  $$(".view").forEach((view) => { view.hidden = view.dataset.page !== name; });
  $$(".nav-link").forEach((button) => button.classList.toggle("active", button.dataset.view === name));
  if (updateHash) history.replaceState(null, "", `#${name}`);
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (state.results) renderChartsForView(name);
}

function svgLineChart(container, series, options = {}) {
  const width = 720;
  const height = options.compact ? 220 : 300;
  const margin = { top: 24, right: 24, bottom: 42, left: 64 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const allPoints = series.flatMap((item) => item.points);
  const xMin = options.xMin ?? Math.min(...allPoints.map((point) => point.x));
  const xMax = options.xMax ?? Math.max(...allPoints.map((point) => point.x));
  let yMin = options.yMin ?? Math.min(0, ...allPoints.map((point) => point.y));
  let yMax = options.yMax ?? Math.max(0, ...allPoints.map((point) => point.y));
  if (yMin === yMax) { yMin -= 1; yMax += 1; }
  const yPadding = (yMax - yMin) * 0.12;
  yMin -= yPadding;
  yMax += yPadding;
  const x = (value) => margin.left + ((value - xMin) / (xMax - xMin || 1)) * plotWidth;
  const y = (value) => margin.top + (1 - (value - yMin) / (yMax - yMin || 1)) * plotHeight;
  const xTicks = options.xTicks ?? 5;
  const yTicks = options.yTicks ?? 4;
  const grid = [];
  for (let index = 0; index <= yTicks; index += 1) {
    const value = yMin + ((yMax - yMin) * index) / yTicks;
    const yPos = y(value);
    grid.push(`<line class="chart-grid" x1="${margin.left}" y1="${yPos}" x2="${width - margin.right}" y2="${yPos}" />`);
    grid.push(`<text class="chart-axis" x="${margin.left - 10}" y="${yPos + 4}" text-anchor="end">${options.yFormat ? options.yFormat(value) : decimal.format(value)}</text>`);
  }
  for (let index = 0; index <= xTicks; index += 1) {
    const value = xMin + ((xMax - xMin) * index) / xTicks;
    grid.push(`<text class="chart-axis" x="${x(value)}" y="${height - 14}" text-anchor="middle">${options.xFormat ? options.xFormat(value) : decimal.format(value)}</text>`);
  }
  const paths = series.map((item) => {
    const path = item.points.map((point, index) => `${index === 0 ? "M" : "L"}${x(point.x).toFixed(2)} ${y(point.y).toFixed(2)}`).join(" ");
    return `<path d="${path}" fill="none" stroke="${item.color}" stroke-width="${item.width ?? 2.5}" ${item.dash ? `stroke-dasharray="${item.dash}"` : ""} stroke-linecap="round" stroke-linejoin="round"><title>${item.label}</title></path>`;
  }).join("");
  container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${options.label ?? "Line chart"}">${grid.join("")}<line class="chart-grid" x1="${margin.left}" y1="${y(0)}" x2="${width - margin.right}" y2="${y(0)}" />${paths}<text class="chart-axis" x="${width / 2}" y="${height - 1}" text-anchor="middle">${options.xLabel ?? ""}</text></svg>`;
}

function svgBarChart(container, rows) {
  const width = 700;
  const rowHeight = 44;
  const height = Math.max(210, rows.length * rowHeight + 58);
  const left = 190;
  const right = 36;
  const values = rows.flatMap((row) => [row.validation ?? 0, row.test ?? 0]);
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const span = max - min || 1;
  const x = (value) => left + ((value - min) / span) * (width - left - right);
  const zero = x(0);
  const content = rows.map((row, index) => {
    const y = 28 + index * rowHeight;
    const validationX = x(row.validation ?? 0);
    const testX = x(row.test ?? 0);
    const validationWidth = Math.abs(validationX - zero);
    const testWidth = Math.abs(testX - zero);
    return `<text class="chart-axis" x="${left - 12}" y="${y + 16}" text-anchor="end">${row.label}</text>
      <rect x="${Math.min(zero, validationX)}" y="${y}" width="${validationWidth}" height="11" rx="3" fill="${themeColor("--muted")}"><title>Validation: ${decimal.format(row.validation ?? 0)}</title></rect>
      <rect x="${Math.min(zero, testX)}" y="${y + 16}" width="${testWidth}" height="11" rx="3" fill="${row.selected ? themeColor("--accent") : themeColor("--orange")}"><title>Test: ${decimal.format(row.test ?? 0)}</title></rect>`;
  }).join("");
  container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Validation and test AUUC comparison"><line class="chart-grid" x1="${zero}" y1="12" x2="${zero}" y2="${height - 28}" />${content}<text class="chart-axis" x="${left}" y="${height - 5}">Gray = validation · Color = test</text></svg>`;
}

function renderPolicyChart(containerId) {
  const curves = state.results.policy_curves;
  const convert = (curve, key) => curve.map((point) => ({ x: point.fraction, y: point[key] }));
  svgLineChart($(containerId), [
    { label: "Uplift", points: convert(curves.uplift, "incremental_per_1000_eligible"), color: themeColor("--accent"), width: 3 },
    { label: "Propensity", points: convert(curves.propensity, "incremental_per_1000_eligible"), color: themeColor("--orange") },
    { label: "Random", points: convert(curves.random, "random_policy_per_1000_eligible"), color: themeColor("--muted"), dash: "6 5", width: 1.5 },
  ], { xMin: 0, xMax: 1, xFormat: (value) => `${Math.round(value * 100)}%`, xLabel: "Campaign reach", yFormat: (value) => decimal.format(value), label: "Incremental conversions per 1,000 eligible customers by campaign reach" });
}

function renderExperimentChart() {
  const effect = state.results.experiment;
  const container = $("#experiment-effect-chart");
  const width = 700;
  const height = 220;
  const left = 80;
  const right = 50;
  const low = Math.min(0, effect.ci_95_low) * 1.35;
  const high = Math.max(0, effect.ci_95_high) * 1.35;
  const x = (value) => left + ((value - low) / (high - low || 1)) * (width - left - right);
  const zero = x(0);
  container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Average treatment effect with 95 percent confidence interval">
    <line class="chart-grid" x1="${zero}" y1="35" x2="${zero}" y2="172" />
    <line x1="${x(effect.ci_95_low)}" y1="105" x2="${x(effect.ci_95_high)}" y2="105" stroke="${themeColor("--accent")}" stroke-width="5" stroke-linecap="round" />
    <circle cx="${x(effect.absolute_effect)}" cy="105" r="8" fill="${themeColor("--surface")}" stroke="${themeColor("--accent")}" stroke-width="4" />
    <text class="chart-title" x="${x(effect.absolute_effect)}" y="78" text-anchor="middle">ATE ${percent(effect.absolute_effect, 3)}</text>
    <text class="chart-axis" x="${x(effect.ci_95_low)}" y="133" text-anchor="middle">${percent(effect.ci_95_low, 3)}</text>
    <text class="chart-axis" x="${x(effect.ci_95_high)}" y="133" text-anchor="middle">${percent(effect.ci_95_high, 3)}</text>
    <text class="chart-axis" x="${zero}" y="193" text-anchor="middle">No effect</text>
  </svg>`;
}

function renderModelCharts() {
  const rows = state.results.model_comparison.map((row) => ({
    label: titleCase(row.model),
    validation: row.validation_auuc_above_random,
    test: row.test_auuc_above_random,
    selected: row.selected,
  }));
  svgBarChart($("#model-comparison-chart"), rows);
  const calibration = state.results.calibration;
  svgLineChart($("#calibration-chart"), [
    { label: "Predicted", points: calibration.map((row) => ({ x: row.rank, y: row.predicted_uplift })), color: themeColor("--accent"), width: 3 },
    { label: "Realized", points: calibration.map((row) => ({ x: row.rank, y: row.realized_uplift })), color: themeColor("--green") },
  ], { xMin: 1, xMax: calibration.length, xTicks: Math.min(5, calibration.length - 1), xFormat: (value) => `${Math.round(value)}`, xLabel: "Uplift rank group (highest first)", yFormat: (value) => percent(value, 2), label: "Predicted and realized uplift by rank group" });
}

function scenarioRows() {
  const population = Number($("#population-input").value);
  const maxReach = Number($("#reach-input").value) / 100;
  const contactCost = Number($("#cost-input").value) / 100;
  const conversionValue = Number($("#value-input").value);
  return state.results.policy_curves.uplift.filter((point) => point.fraction <= maxReach + 1e-9).map((point) => {
    const targeted = Math.round(population * point.fraction);
    const incremental = population * point.incremental_per_1000_eligible / 1000;
    const low = population * point.ci_95_low / 1000;
    const high = population * point.ci_95_high / 1000;
    const cost = targeted * contactCost;
    const profit = incremental * conversionValue - cost;
    return { fraction: point.fraction, targeted, incremental, low, high, profit, breakEven: targeted ? incremental * conversionValue / targeted : 0 };
  });
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
  $("#optimizer-fraction").textContent = `${Math.round(best.fraction * 100)}% of eligible customers`;
  $("#optimizer-incremental").textContent = signed(best.incremental, 1);
  $("#optimizer-conversion-ci").textContent = `95% interval: ${signed(best.low, 1)} to ${signed(best.high, 1)}`;
  $("#optimizer-profit").textContent = currency.format(best.profit);
  $("#optimizer-break-even").textContent = `Break-even contact cost: ${currency2.format(best.breakEven)}`;
  const positive = best.profit > 0;
  const decision = $("#optimizer-decision");
  decision.classList.toggle("negative", !positive);
  $("#optimizer-decision-title").textContent = positive ? "Run a controlled rollout" : "Do not launch at this cost";
  $("#optimizer-decision-copy").textContent = positive
    ? "The scenario is positive at the selected reach. Preserve a randomized holdout to verify the policy online."
    : "No evaluated reach is profitable under these assumptions. Reduce contact cost or revise campaign value.";
  svgLineChart($("#optimizer-chart"), [
    { label: "Scenario profit", points: rows.map((row) => ({ x: row.fraction, y: row.profit })), color: positive ? themeColor("--green") : themeColor("--red"), width: 3 },
  ], { xMin: 0, xMax: maxReach / 100, xFormat: (value) => `${Math.round(value * 100)}%`, xLabel: "Campaign reach", yFormat: (value) => currency.format(value), label: "Scenario profit by campaign reach" });
}

function renderChartsForView(name) {
  if (name === "overview") renderPolicyChart("#overview-policy-chart");
  if (name === "experiment") renderExperimentChart();
  if (name === "models") renderModelCharts();
  if (name === "optimizer") renderOptimizer();
}

function renderResults(results) {
  state.results = results;
  if (results.status !== "portfolio_real_data") {
    const banner = $("#status-banner");
    banner.hidden = false;
    banner.textContent = "Development build: these results use explicitly labeled synthetic data and are not portfolio findings.";
  }
  const experiment = results.experiment;
  const selected = results.model_comparison.find((row) => row.selected);
  const scenario = results.default_scenario.locked_test_result_at_selected_reach;
  const comparison = results.policy_comparison_at_selected_reach;
  const paired = comparison.uplift_vs_propensity;
  $("#overview-model").textContent = titleCase(results.selection.selected_model);
  $("#overview-reach").textContent = percent(results.selection.selected_reach_on_validation, 0);
  $("#overview-profit").textContent = currency.format(scenario.scenario_profit);
  $("#overview-decision-title").textContent = scenario.scenario_profit > 0 ? "Controlled rollout" : "Do not launch";
  $("#overview-decision-copy").textContent = scenario.scenario_profit > 0
    ? "Offline value is positive under the default assumptions. Uplift did not clearly beat propensity, so validate both policies head-to-head."
    : "The selected policy is not profitable under the default assumptions.";
  $("#metric-test-rows").textContent = number.format(results.dataset.test.rows);
  $("#metric-ate").textContent = percent(experiment.absolute_effect, 3);
  $("#metric-ate-ci").textContent = `95% CI ${percent(experiment.ci_95_low, 3)} to ${percent(experiment.ci_95_high, 3)}`;
  $("#metric-incremental").textContent = signed(scenario.incremental_conversions, 1);
  $("#metric-auuc").textContent = decimal.format(selected.test_auuc_above_random);

  $("#experiment-control-rate").textContent = percent(experiment.control_conversion_rate, 3);
  $("#experiment-treatment-rate").textContent = percent(experiment.treated_conversion_rate, 3);
  $("#experiment-relative-lift").textContent = percent(experiment.relative_lift, 1);
  $("#experiment-control-n").textContent = `${number.format(experiment.control_rows)} control observations`;
  $("#experiment-treatment-n").textContent = `${number.format(experiment.treated_rows)} treated observations`;
  $("#experiment-pvalue").textContent = `Two-sided p = ${experiment.p_value_two_sided.toPrecision(3)}`;

  $("#model-table-body").innerHTML = results.model_comparison.map((row) => `<tr>
    <td>${titleCase(row.model)}</td><td>${titleCase(row.category)}</td>
    <td class="numeric">${row.validation_auuc_above_random == null ? "—" : decimal.format(row.validation_auuc_above_random)}</td>
    <td class="numeric">${decimal.format(row.test_auuc_above_random)}</td>
    <td>${row.selected ? '<span class="selected-chip">Selected on validation</span>' : "Baseline / candidate"}</td>
  </tr>`).join("");
  $("#policy-comparison-note").innerHTML = `<strong>Equal-reach paired comparison:</strong> uplift minus propensity is ${signed(paired.difference_per_1000_eligible, 3)} incremental conversions per 1,000 eligible (95% CI ${signed(paired.ci_95_low, 3)} to ${signed(paired.ci_95_high, 3)}). <strong>Conclusion:</strong> ${titleCase(comparison.conclusion)}.`;
  $("#limitations-list").innerHTML = results.limitations.map((item) => `<li>${item}</li>`).join("");

  const inputs = results.default_scenario.inputs;
  $("#population-input").value = inputs.population;
  $("#reach-input").value = Math.round(inputs.max_reach * 100);
  $("#cost-input").value = Math.round(inputs.contact_cost * 100);
  $("#value-input").value = inputs.conversion_value;
  renderChartsForView(state.currentView);
}

async function initialize() {
  try {
    const response = await fetch("data/results.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const results = await response.json();
    $("#loading").hidden = true;
    renderResults(results);
    const requested = location.hash.slice(1);
    const valid = ["overview", "experiment", "models", "optimizer", "methodology"];
    showView(valid.includes(requested) ? requested : "overview", false);
  } catch (error) {
    console.error(error);
    $("#loading").hidden = true;
    $("#load-error").hidden = false;
  }
}

$$('.nav-link').forEach((button) => button.addEventListener("click", () => showView(button.dataset.view)));
$$('[data-go]').forEach((button) => button.addEventListener("click", () => showView(button.dataset.go)));
['population-input', 'reach-input', 'cost-input', 'value-input'].forEach((id) => {
  $(`#${id}`).addEventListener("input", renderOptimizer);
});
window.addEventListener("hashchange", () => {
  const requested = location.hash.slice(1);
  if (requested && requested !== state.currentView) showView(requested, false);
});
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => renderChartsForView(state.currentView));

initialize();
