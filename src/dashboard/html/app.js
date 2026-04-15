/* ================================================================== */
/* jobDB Dashboard — Client Application                                */
/* SPA routing, API client, Chart.js rendering, 6 page builders        */
/* ================================================================== */

(() => {
"use strict";

// ------------------------------------------------------------------ //
// CONFIG                                                              //
// ------------------------------------------------------------------ //

const API = "";  // same origin
const CHART_COLORS = [
    "#6366f1", "#8b5cf6", "#a78bfa", "#c4b5fd", "#818cf8",
    "#4f46e5", "#7c3aed", "#5b21b6", "#4338ca", "#312e81",
    "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#f43f5e",
];
const DONUT_COLORS = ["#6366f1", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#f43f5e"];

const SENIORITY_NAMES = {
    intern: "Stażysta", junior: "Junior", mid: "Mid", senior: "Senior",
    lead: "Lead", manager: "Manager", unknown: "Nieokreślony",
};
const WORK_MODE_NAMES = {
    remote: "Zdalna", hybrid: "Hybrydowa", onsite: "Stacjonarna", unknown: "Nieokreślony",
};

// ------------------------------------------------------------------ //
// STATE                                                               //
// ------------------------------------------------------------------ //

let currentPage = "executive";
const filters = { source: [], city: [], work_mode: [], seniority: [], active_only: false };
const charts = {}; // track Chart.js instances for cleanup

// ------------------------------------------------------------------ //
// ICONS (inline SVG strings)                                          //
// ------------------------------------------------------------------ //

const ICO = {
    briefcase:  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg>`,
    dollar:     `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>`,
    building:   `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`,
    mapPin:     `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>`,
    users:      `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>`,
    trending:   `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>`,
    trendDown:  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/></svg>`,
    eye:        `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`,
    percent:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="5" x2="5" y2="19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/></svg>`,
    shield:     `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
    activity:   `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>`,
    clock:      `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
    check:      `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
    alert:      `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
    layers:     `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>`,
    zap:        `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
    globe:      `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>`,
    barChart:   `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/></svg>`,
    target:     `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>`,
};


// ------------------------------------------------------------------ //
// UTILITIES                                                           //
// ------------------------------------------------------------------ //

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function fmt(n) {
    if (n == null) return "—";
    return Number(n).toLocaleString("pl-PL");
}

function fmtPLN(n) {
    if (n == null || n === 0) return "—";
    return Number(n).toLocaleString("pl-PL") + " PLN";
}

function fmtPct(n) {
    if (n == null) return "—";
    return n.toFixed(1) + "%";
}

function trendHtml(value, suffix = "%") {
    if (value == null) return "";
    const cls = value > 0 ? "trend-up" : value < 0 ? "trend-down" : "trend-flat";
    const arrow = value > 0 ? "↑" : value < 0 ? "↓" : "→";
    return `<span class="${cls}">${arrow} ${Math.abs(value).toFixed(1)}${suffix}</span>`;
}

async function api(path, extraParams = {}) {
    const params = new URLSearchParams();
    if (filters.source.length) filters.source.forEach(s => params.append("source", s));
    if (filters.city.length) filters.city.forEach(c => params.append("city", c));
    if (filters.work_mode.length) filters.work_mode.forEach(w => params.append("work_mode", w));
    if (filters.seniority.length) filters.seniority.forEach(s => params.append("seniority", s));
    if (filters.active_only) params.set("active_only", "true");
    Object.entries(extraParams).forEach(([k, v]) => {
        if (v != null) params.set(k, String(v));
    });
    const qs = params.toString();
    const url = `${API}/api/${path}${qs ? "?" + qs : ""}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`API ${path}: ${res.status}`);
    return res.json();
}

function destroyChart(id) {
    if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}

function createChart(canvasId, config) {
    destroyChart(canvasId);
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    const c = new Chart(ctx, config);
    charts[canvasId] = c;
    return c;
}

function kpiCard(icon, colorClass, label, value, sub = "") {
    return `
    <div class="kpi-card">
        <div class="kpi-icon ${colorClass}">${icon}</div>
        <div class="kpi-body">
            <div class="kpi-label">${label}</div>
            <div class="kpi-value">${value}</div>
            ${sub ? `<div class="kpi-sub">${sub}</div>` : ""}
        </div>
    </div>`;
}

function badge(text, color = "indigo") {
    return `<span class="badge badge-${color}">${text}</span>`;
}

const defaultTooltip = {
    backgroundColor: "rgba(255,255,255,0.95)",
    titleColor: "#1a1d23",
    bodyColor: "#6b7280",
    borderColor: "rgba(0,0,0,0.08)",
    borderWidth: 1,
    cornerRadius: 8,
    padding: 10,
    titleFont: { family: "Inter", weight: "600" },
    bodyFont: { family: "Inter" },
    displayColors: true,
    boxPadding: 4,
};

const defaultScales = {
    x: {
        grid: { display: false },
        ticks: { font: { family: "Inter", size: 11 }, color: "#9ca3af" },
    },
    y: {
        grid: { color: "rgba(0,0,0,0.04)" },
        ticks: { font: { family: "Inter", size: 11 }, color: "#9ca3af" },
        border: { display: false },
    },
};

Chart.defaults.font.family = "Inter";
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.pointStyle = "circle";
Chart.defaults.plugins.legend.labels.padding = 16;
Chart.defaults.plugins.legend.labels.font = { family: "Inter", size: 12 };


// ------------------------------------------------------------------ //
// NAVIGATION                                                          //
// ------------------------------------------------------------------ //

function navigateTo(page) {
    currentPage = page;
    $$(".nav-item").forEach(el => el.classList.toggle("active", el.dataset.page === page));
    $$(".page").forEach(el => el.classList.toggle("hidden", el.id !== `page-${page}`));
    loadPage(page);
}

$$(".nav-item").forEach(el => {
    el.addEventListener("click", () => navigateTo(el.dataset.page));
});


// ------------------------------------------------------------------ //
// FILTER PANEL                                                        //
// ------------------------------------------------------------------ //

const filterPanel = $("#filterPanel");
const filterToggle = $("#filterToggle");
const filterClose = $("#filterClose");

filterToggle.addEventListener("click", () => filterPanel.classList.toggle("open"));
filterClose.addEventListener("click", () => filterPanel.classList.remove("open"));

$("#applyFilters").addEventListener("click", () => {
    // Read source checkboxes
    filters.source = [...$$("#filterSource input:checked")].map(i => i.value);
    // Read city multi-select
    filters.city = [...$("#filterCity").selectedOptions].map(o => o.value);
    // Read work mode
    filters.work_mode = [...$$("#filterWorkMode input:checked")].map(i => i.value);
    // Read seniority
    filters.seniority = [...$$("#filterSeniority input:checked")].map(i => i.value);
    // Active only
    filters.active_only = $("#filterActiveOnly").checked;

    filterPanel.classList.remove("open");
    loadPage(currentPage);
});

$("#clearFilters").addEventListener("click", () => {
    filters.source = []; filters.city = []; filters.work_mode = []; filters.seniority = [];
    filters.active_only = false;
    $$("#filterSource input, #filterWorkMode input, #filterSeniority input").forEach(i => i.checked = false);
    $("#filterCity").selectedIndex = -1;
    $("#filterActiveOnly").checked = false;
    filterPanel.classList.remove("open");
    loadPage(currentPage);
});


// ------------------------------------------------------------------ //
// INIT FILTERS                                                        //
// ------------------------------------------------------------------ //

async function initFilters() {
    try {
        const f = await api("filters");
        const sourceNames = {
            pracapl: "Praca.pl", justjoinit: "JustJoin.it",
            pracuj: "Pracuj.pl", rocketjobs: "RocketJobs.pl", jooble: "Jooble",
        };
        $("#filterSource").innerHTML = f.sources.map(s =>
            `<label><input type="checkbox" value="${s}"> ${sourceNames[s] || s}</label>`
        ).join("");

        $("#filterCity").innerHTML = f.cities.map(c =>
            `<option value="${c}">${c}</option>`
        ).join("");

        $("#filterWorkMode").innerHTML = f.work_modes.map(w =>
            `<label><input type="checkbox" value="${w}"> ${WORK_MODE_NAMES[w] || w}</label>`
        ).join("");

        $("#filterSeniority").innerHTML = f.seniorities.map(s =>
            `<label><input type="checkbox" value="${s}"> ${SENIORITY_NAMES[s] || s}</label>`
        ).join("");
    } catch (e) {
        console.error("Failed to load filters:", e);
    }
}


// ------------------------------------------------------------------ //
// PAGE LOADERS                                                        //
// ------------------------------------------------------------------ //

async function loadPage(page) {
    showLoading();
    try {
        switch (page) {
            case "executive": await loadExecutive(); break;
            case "salary":    await loadSalary();    break;
            case "geography": await loadGeography(); break;
            case "employers": await loadEmployers(); break;
            case "trends":    await loadTrends();    break;
            case "quality":   await loadQuality();   break;
        }
    } catch (e) {
        console.error(`Error loading page ${page}:`, e);
    }
    hideLoading();
}

function showLoading() { $("#loadingOverlay").classList.remove("hidden"); }
function hideLoading() { $("#loadingOverlay").classList.add("hidden"); }


// ------------------------------------------------------------------ //
// PAGE 1: EXECUTIVE DASHBOARD                                         //
// ------------------------------------------------------------------ //

async function loadExecutive() {
    const [kpi, sources, workModes, cities, seniority] = await Promise.all([
        api("kpi"),
        api("charts/source-distribution"),
        api("charts/workmode-distribution"),
        api("charts/top-cities"),
        api("charts/seniority-distribution"),
    ]);

    // KPIs
    const freshBadge = kpi.data_freshness_status === "Świeże" ? badge("🟢 " + kpi.data_freshness_status, "green")
        : kpi.data_freshness_status === "Do odświeżenia" ? badge("🟡 " + kpi.data_freshness_status, "amber")
        : badge("🔴 " + kpi.data_freshness_status, "red");

    $("#executiveKpis").innerHTML = [
        kpiCard(ICO.briefcase, "indigo", "Aktywne oferty", fmt(kpi.active_offers), `z ${fmt(kpi.total_offers)} łącznie`),
        kpiCard(ICO.dollar, "green", "Z wynagrodzeniem", fmt(kpi.offers_with_salary), fmtPct(kpi.salary_transparency_pct) + " transparentność"),
        kpiCard(ICO.building, "violet", "Firmy", fmt(kpi.unique_companies), "unikalnych pracodawców"),
        kpiCard(ICO.mapPin, "cyan", "Miasta", fmt(kpi.unique_cities), "lokalizacji"),
        kpiCard(ICO.dollar, "amber", "Śr. wynagrodzenie", fmtPLN(kpi.avg_salary_midpoint), "midpoint widełek"),
        kpiCard(ICO.clock, "blue", "Dane", freshBadge, kpi.last_scrape_time ? `Ostatni scrape: ${kpi.last_scrape_time.substring(0,16)}` : ""),
    ].join("");

    $("#lastScrapeInfo").textContent = kpi.last_scrape_time
        ? `Stan na: ${kpi.last_scrape_time.substring(0, 16)}`
        : "";

    // Source donut
    createChart("chartSourceDonut", {
        type: "doughnut",
        data: {
            labels: sources.map(s => s.label),
            datasets: [{
                data: sources.map(s => s.value),
                backgroundColor: DONUT_COLORS,
                borderWidth: 0,
                hoverOffset: 8,
            }],
        },
        options: {
            cutout: "65%",
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "right" },
                tooltip: defaultTooltip,
            },
        },
    });

    // Work mode donut
    createChart("chartWorkModeDonut", {
        type: "doughnut",
        data: {
            labels: workModes.map(w => w.label),
            datasets: [{
                data: workModes.map(w => w.value),
                backgroundColor: ["#10b981", "#f59e0b", "#6366f1", "#9ca3af"],
                borderWidth: 0,
                hoverOffset: 8,
            }],
        },
        options: {
            cutout: "65%",
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "right" },
                tooltip: defaultTooltip,
            },
        },
    });

    // Top cities bar
    createChart("chartTopCities", {
        type: "bar",
        data: {
            labels: cities.map(c => c.label),
            datasets: [{
                data: cities.map(c => c.value),
                backgroundColor: cities.map((_, i) => {
                    const alpha = 1 - (i / cities.length) * 0.6;
                    return `rgba(99, 102, 241, ${alpha})`;
                }),
                borderRadius: 6,
                borderSkipped: false,
            }],
        },
        options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: defaultTooltip },
            scales: {
                x: { grid: { color: "rgba(0,0,0,0.04)" }, ticks: { font: { family: "Inter", size: 11 }, color: "#9ca3af" }, border: { display: false } },
                y: { grid: { display: false }, ticks: { font: { family: "Inter", size: 11 }, color: "#6b7280" } },
            },
        },
    });

    // Seniority bar
    createChart("chartSeniority", {
        type: "bar",
        data: {
            labels: seniority.map(s => s.label),
            datasets: [{
                data: seniority.map(s => s.value),
                backgroundColor: seniority.map((_, i) => CHART_COLORS[i % CHART_COLORS.length]),
                borderRadius: 6,
                borderSkipped: false,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: defaultTooltip },
            scales: defaultScales,
        },
    });

    // Source table
    const srcData = await api("sources");
    let html = `<table class="data-table"><thead><tr>
        <th>Źródło</th><th class="num">Oferty</th><th class="num">Z salary</th>
        <th class="num">Transparentność</th><th class="num">Udział</th><th class="num">Jakość danych</th>
    </tr></thead><tbody>`;
    srcData.forEach(s => {
        const qColor = s.avg_data_quality >= 70 ? "green" : s.avg_data_quality >= 50 ? "amber" : "red";
        html += `<tr>
            <td><strong>${s.source_name}</strong></td>
            <td class="num">${fmt(s.total)}</td>
            <td class="num">${fmt(s.with_salary)}</td>
            <td class="num">${badge(fmtPct(s.salary_transparency_pct), s.salary_transparency_pct >= 40 ? "green" : "amber")}</td>
            <td class="num">${fmtPct(s.source_share_pct)}</td>
            <td class="num">${badge(fmtPct(s.avg_data_quality), qColor)}</td>
        </tr>`;
    });
    html += "</tbody></table>";
    $("#sourceTable").innerHTML = html;
}


// ------------------------------------------------------------------ //
// PAGE 2: SALARY INTELLIGENCE                                         //
// ------------------------------------------------------------------ //

async function loadSalary() {
    const [sal, bySen, byCity, byWm, bands, heatmap] = await Promise.all([
        api("salary"),
        api("salary/by-seniority"),
        api("salary/by-city", { limit: 10 }),
        api("salary/by-workmode"),
        api("salary/bands"),
        api("salary/heatmap"),
    ]);

    // KPIs
    const senGap = await api("seniority");
    $("#salaryKpis").innerHTML = [
        kpiCard(ICO.dollar, "indigo", "Mediana salary", fmtPLN(sal.median_salary_midpoint), "midpoint widełek"),
        kpiCard(ICO.layers, "violet", "Przedział P25–P75", `${fmt(sal.salary_p25)} – ${fmt(sal.salary_p75)}`, "PLN"),
        kpiCard(ICO.dollar, "green", "Śr. miesięczne PLN", fmtPLN(sal.avg_monthly_salary_pln), "znormalizowane"),
        kpiCard(ICO.trending, "cyan", "Remote premium", senGap.junior_senior_salary_gap == null ? "—" : (senGap.junior_senior_salary_gap > 0 ? "+" : "") + fmt(senGap.junior_senior_salary_gap) + " PLN", "Senior vs Junior gap"),
        kpiCard(ICO.target, "amber", "Mnożnik Sr/Jr", senGap.senior_junior_multiplier != null ? senGap.senior_junior_multiplier + "×" : "—", ""),
        kpiCard(ICO.percent, "blue", "Rozrzut widełek", fmtPLN(sal.avg_salary_spread), "średni spread"),
    ].join("");

    // Salary by seniority (grouped bar: P25, Median, P75)
    const senLabels = bySen.map(s => SENIORITY_NAMES[s.seniority] || s.seniority);
    createChart("chartSalaryBySeniority", {
        type: "bar",
        data: {
            labels: senLabels,
            datasets: [
                { label: "P10", data: bySen.map(s => s.p10), backgroundColor: "rgba(99,102,241,0.15)", borderRadius: 4, borderSkipped: false },
                { label: "P25", data: bySen.map(s => s.p25), backgroundColor: "rgba(99,102,241,0.35)", borderRadius: 4, borderSkipped: false },
                { label: "Mediana", data: bySen.map(s => s.median), backgroundColor: "rgba(99,102,241,0.7)", borderRadius: 4, borderSkipped: false },
                { label: "P75", data: bySen.map(s => s.p75), backgroundColor: "rgba(139,92,246,0.55)", borderRadius: 4, borderSkipped: false },
                { label: "P90", data: bySen.map(s => s.p90), backgroundColor: "rgba(139,92,246,0.25)", borderRadius: 4, borderSkipped: false },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "top" }, tooltip: { ...defaultTooltip, callbacks: { label: ctx => ` ${ctx.dataset.label}: ${fmt(ctx.raw)} PLN` } } },
            scales: {
                ...defaultScales,
                y: { ...defaultScales.y, ticks: { ...defaultScales.y.ticks, callback: v => fmt(v) } },
            },
        },
    });

    // Salary by city
    createChart("chartSalaryByCity", {
        type: "bar",
        data: {
            labels: byCity.map(c => c.city),
            datasets: [
                { label: "Śr. min", data: byCity.map(c => c.avg_min), backgroundColor: "rgba(99,102,241,0.4)", borderRadius: 4, borderSkipped: false },
                { label: "Śr. max", data: byCity.map(c => c.avg_max), backgroundColor: "rgba(99,102,241,0.8)", borderRadius: 4, borderSkipped: false },
            ],
        },
        options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: "top" }, tooltip: { ...defaultTooltip, callbacks: { label: ctx => ` ${ctx.dataset.label}: ${fmt(ctx.raw)} PLN` } } },
            scales: {
                x: { grid: { color: "rgba(0,0,0,0.04)" }, ticks: { font: { family: "Inter", size: 11 }, color: "#9ca3af", callback: v => fmt(v) }, border: { display: false } },
                y: { grid: { display: false }, ticks: { font: { family: "Inter", size: 11 }, color: "#6b7280" } },
            },
        },
    });

    // Salary by work mode
    createChart("chartSalaryByWorkMode", {
        type: "bar",
        data: {
            labels: byWm.map(w => WORK_MODE_NAMES[w.work_mode] || w.work_mode),
            datasets: [{
                data: byWm.map(w => w.avg_midpoint),
                backgroundColor: ["#10b981", "#f59e0b", "#6366f1", "#9ca3af"],
                borderRadius: 6,
                borderSkipped: false,
            }],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { ...defaultTooltip, callbacks: { label: ctx => ` ${fmt(ctx.raw)} PLN` } } },
            scales: { ...defaultScales, y: { ...defaultScales.y, ticks: { ...defaultScales.y.ticks, callback: v => fmt(v) } } },
        },
    });

    // Salary bands
    const bandData = bands.filter(b => b.band !== "Brak danych");
    createChart("chartSalaryBands", {
        type: "bar",
        data: {
            labels: bandData.map(b => b.band),
            datasets: [{
                data: bandData.map(b => b.count),
                backgroundColor: bandData.map((_, i) => {
                    const colors = ["#e0e7ff", "#c7d2fe", "#a5b4fc", "#818cf8", "#6366f1", "#4f46e5", "#4338ca"];
                    return colors[i % colors.length];
                }),
                borderRadius: 6,
                borderSkipped: false,
            }],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: defaultTooltip },
            scales: defaultScales,
        },
    });

    // Heatmap table
    if (heatmap.cities.length) {
        const senNames = { intern: "Stażysta", junior: "Junior", mid: "Mid", senior: "Senior", lead: "Lead", manager: "Manager" };
        let hhtml = `<table class="data-table"><thead><tr><th>Miasto</th>`;
        heatmap.seniorities.forEach(s => { hhtml += `<th class="num">${senNames[s] || s}</th>`; });
        hhtml += `</tr></thead><tbody>`;
        // Find min/max for color scale
        let allVals = [];
        heatmap.cities.forEach(c => {
            heatmap.seniorities.forEach(s => {
                const v = (heatmap.matrix[c] || {})[s];
                if (v) allVals.push(v);
            });
        });
        const minVal = Math.min(...allVals);
        const maxVal = Math.max(...allVals);

        heatmap.cities.forEach(c => {
            hhtml += `<tr><td><strong>${c}</strong></td>`;
            heatmap.seniorities.forEach(s => {
                const v = (heatmap.matrix[c] || {})[s];
                if (v) {
                    const pct = (v - minVal) / (maxVal - minVal || 1);
                    const r = Math.round(224 - pct * 125);
                    const g = Math.round(231 - pct * 80);
                    const b = Math.round(254 - pct * 10);
                    hhtml += `<td class="heatmap-cell num" style="background:rgb(${r},${g},${b})">${fmt(v)}</td>`;
                } else {
                    hhtml += `<td class="heatmap-cell num" style="color:#ccc">—</td>`;
                }
            });
            hhtml += `</tr>`;
        });
        hhtml += `</tbody></table>`;
        $("#salaryHeatmap").innerHTML = hhtml;
    } else {
        $("#salaryHeatmap").innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:20px">Brak danych do wyświetlenia heatmapy</p>`;
    }
}


// ------------------------------------------------------------------ //
// PAGE 3: GEOGRAPHIC MARKET                                           //
// ------------------------------------------------------------------ //

async function loadGeography() {
    const [loc, cities, regions, wmCity, cityTable] = await Promise.all([
        api("location"),
        api("charts/top-cities", { limit: 20 }),
        api("location/by-region"),
        api("location/workmode-by-city", { limit: 10 }),
        api("location/cities", { limit: 20 }),
    ]);

    // KPIs
    const hhiLabel = loc.city_concentration_hhi < 0.15 ? badge("Rozproszony", "green")
        : loc.city_concentration_hhi < 0.25 ? badge("Umiarkowany", "amber")
        : badge("Skoncentrowany", "red");

    $("#geoKpis").innerHTML = [
        kpiCard(ICO.mapPin, "indigo", "Top miasto", loc.top_city, `${fmt(loc.top_city_count)} ofert`),
        kpiCard(ICO.globe, "amber", "Udział Warszawy", fmtPct(loc.warsaw_share_pct), "w total ofert"),
        kpiCard(ICO.target, "cyan", "Koncentracja HHI", loc.city_concentration_hhi.toFixed(3), hhiLabel),
        kpiCard(ICO.building, "green", "Praca zdalna", fmtPct(loc.remote_share_pct), loc.remote_salary_premium_pct != null ? `Premium: ${loc.remote_salary_premium_pct > 0 ? "+" : ""}${loc.remote_salary_premium_pct}%` : ""),
    ].join("");

    // Top 20 cities bar
    createChart("chartGeoCities", {
        type: "bar",
        data: {
            labels: cities.map(c => c.label),
            datasets: [{
                data: cities.map(c => c.value),
                backgroundColor: cities.map((_, i) => `rgba(99, 102, 241, ${1 - (i / cities.length) * 0.6})`),
                borderRadius: 6, borderSkipped: false,
            }],
        },
        options: {
            indexAxis: "y", responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: defaultTooltip },
            scales: {
                x: { grid: { color: "rgba(0,0,0,0.04)" }, ticks: { font: { family: "Inter", size: 11 }, color: "#9ca3af" }, border: { display: false } },
                y: { grid: { display: false }, ticks: { font: { family: "Inter", size: 10 }, color: "#6b7280" } },
            },
        },
    });

    // Regions bar
    if (regions.length) {
        createChart("chartGeoRegions", {
            type: "bar",
            data: {
                labels: regions.map(r => r.region),
                datasets: [{
                    data: regions.map(r => r.count),
                    backgroundColor: "rgba(99,102,241,0.6)",
                    borderRadius: 6, borderSkipped: false,
                }],
            },
            options: {
                indexAxis: "y", responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: defaultTooltip },
                scales: {
                    x: { grid: { color: "rgba(0,0,0,0.04)" }, ticks: { font: { family: "Inter", size: 11 }, color: "#9ca3af" }, border: { display: false } },
                    y: { grid: { display: false }, ticks: { font: { family: "Inter", size: 10 }, color: "#6b7280" } },
                },
            },
        });
    }

    // Work mode by city — 100% stacked
    if (wmCity.cities.length) {
        const modeColors = { remote: "#10b981", hybrid: "#f59e0b", onsite: "#6366f1", unknown: "#d1d5db" };
        const datasets = wmCity.modes.map(m => ({
            label: WORK_MODE_NAMES[m] || m,
            data: wmCity.cities.map(c => {
                const total = Object.values(wmCity.data[c] || {}).reduce((a, b) => a + b, 0);
                return total ? Math.round(((wmCity.data[c] || {})[m] || 0) / total * 100) : 0;
            }),
            backgroundColor: modeColors[m] || "#9ca3af",
            borderRadius: 0,
            borderSkipped: false,
        }));
        createChart("chartWorkModeByCity", {
            type: "bar",
            data: { labels: wmCity.cities, datasets },
            options: {
                indexAxis: "y", responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { position: "top" },
                    tooltip: { ...defaultTooltip, callbacks: { label: ctx => ` ${ctx.dataset.label}: ${ctx.raw}%` } },
                },
                scales: {
                    x: { stacked: true, max: 100, grid: { color: "rgba(0,0,0,0.04)" }, ticks: { callback: v => v + "%", font: { family: "Inter", size: 11 }, color: "#9ca3af" }, border: { display: false } },
                    y: { stacked: true, grid: { display: false }, ticks: { font: { family: "Inter", size: 11 }, color: "#6b7280" } },
                },
            },
        });
    }

    // City detail table
    let thtml = `<table class="data-table"><thead><tr>
        <th>Miasto</th><th>Województwo</th><th class="num">Oferty</th>
        <th class="num">Śr. salary</th><th class="num">Transparentność</th><th class="num">Remote %</th>
    </tr></thead><tbody>`;
    cityTable.forEach(c => {
        thtml += `<tr>
            <td><strong>${c.city}</strong></td>
            <td>${c.region || "—"}</td>
            <td class="num">${fmt(c.total)}</td>
            <td class="num">${c.avg_salary_midpoint ? fmtPLN(c.avg_salary_midpoint) : "—"}</td>
            <td class="num">${badge(fmtPct(c.salary_transparency_pct), c.salary_transparency_pct >= 40 ? "green" : "amber")}</td>
            <td class="num">${fmtPct(c.remote_share_pct)}</td>
        </tr>`;
    });
    thtml += `</tbody></table>`;
    $("#cityTable").innerHTML = thtml;
}


// ------------------------------------------------------------------ //
// PAGE 4: EMPLOYER ANALYTICS                                          //
// ------------------------------------------------------------------ //

async function loadEmployers() {
    const data = await api("employers");

    // KPIs
    $("#employerKpis").innerHTML = [
        kpiCard(ICO.building, "indigo", "Firmy", fmt(data.unique_companies), "unikalnych pracodawców"),
        kpiCard(ICO.barChart, "violet", "Śr. ofert/firma", data.avg_offers_per_company, ""),
        kpiCard(ICO.users, "green", "Duzi pracodawcy", fmt(data.large_employers_count), "≥5 ofert"),
        kpiCard(ICO.percent, "amber", "Top 10 udział", fmtPct(data.top10_share_pct), "koncentracja rynku"),
    ].join("");

    const emps = data.employers || [];

    // Chart: by offers
    const top20byOffers = emps.slice(0, 20);
    createChart("chartEmployersByOffers", {
        type: "bar",
        data: {
            labels: top20byOffers.map(e => e.company.length > 25 ? e.company.substring(0, 25) + "…" : e.company),
            datasets: [{
                data: top20byOffers.map(e => e.offers),
                backgroundColor: "rgba(99,102,241,0.65)",
                borderRadius: 6, borderSkipped: false,
            }],
        },
        options: {
            indexAxis: "y", responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: defaultTooltip },
            scales: {
                x: { grid: { color: "rgba(0,0,0,0.04)" }, ticks: { font: { family: "Inter", size: 11 }, color: "#9ca3af" }, border: { display: false } },
                y: { grid: { display: false }, ticks: { font: { family: "Inter", size: 10 }, color: "#6b7280" } },
            },
        },
    });

    // Chart: by salary
    const withSalary = emps.filter(e => e.avg_salary).sort((a, b) => b.avg_salary - a.avg_salary).slice(0, 20);
    createChart("chartEmployersBySalary", {
        type: "bar",
        data: {
            labels: withSalary.map(e => e.company.length > 25 ? e.company.substring(0, 25) + "…" : e.company),
            datasets: [{
                data: withSalary.map(e => e.avg_salary),
                backgroundColor: withSalary.map(e =>
                    e.competitiveness_index > 100 ? "rgba(16,185,129,0.65)" : "rgba(99,102,241,0.65)"
                ),
                borderRadius: 6, borderSkipped: false,
            }],
        },
        options: {
            indexAxis: "y", responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { ...defaultTooltip, callbacks: { label: ctx => ` ${fmt(ctx.raw)} PLN` } },
            },
            scales: {
                x: { grid: { color: "rgba(0,0,0,0.04)" }, ticks: { font: { family: "Inter", size: 11 }, color: "#9ca3af", callback: v => fmt(v) }, border: { display: false } },
                y: { grid: { display: false }, ticks: { font: { family: "Inter", size: 10 }, color: "#6b7280" } },
            },
        },
    });

    // Employer table
    let html = `<table class="data-table"><thead><tr>
        <th>Firma</th><th class="num">Oferty</th><th class="num">Śr. wynagrodzenie</th>
        <th class="num">Indeks konkurencyjności</th><th>Remote</th><th>Miasta</th>
    </tr></thead><tbody>`;
    emps.forEach(e => {
        const ciColor = e.competitiveness_index == null ? "" :
            e.competitiveness_index >= 110 ? "green" : e.competitiveness_index >= 90 ? "blue" : "red";
        const ciLabel = e.competitiveness_index != null ? badge(e.competitiveness_index.toFixed(0), ciColor) : "—";
        html += `<tr>
            <td><strong>${e.company}</strong></td>
            <td class="num">${fmt(e.offers)}</td>
            <td class="num">${e.avg_salary ? fmtPLN(e.avg_salary) : "—"}</td>
            <td class="num">${ciLabel}</td>
            <td>${e.has_remote ? badge("✓ Tak", "green") : badge("✗ Nie", "red")}</td>
            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${e.cities || ""}">${e.cities || "—"}</td>
        </tr>`;
    });
    html += `</tbody></table>`;
    $("#employerTable").innerHTML = html;
}


// ------------------------------------------------------------------ //
// PAGE 5: TRENDS & DYNAMICS                                           //
// ------------------------------------------------------------------ //

async function loadTrends() {
    const data = await api("trends");

    // KPIs
    const momColor = data.offers_mom_change > 0 ? "green" : data.offers_mom_change < 0 ? "red" : "blue";
    $("#trendKpis").innerHTML = [
        kpiCard(ICO.zap, "indigo", "Velocity", data.offer_velocity + " ofert/dzień", "tempo napływu"),
        kpiCard(ICO.trending, momColor, "Zmiana MoM", data.offers_mom_change != null ? (data.offers_mom_change > 0 ? "+" : "") + data.offers_mom_change.toFixed(1) + "%" : "—", data.offers_mom_trend_icon),
        kpiCard(ICO.activity, "violet", "Nowe dziś", fmt(data.new_today), ""),
        kpiCard(ICO.clock, "cyan", "Nowe w tygodniu", fmt(data.new_this_week), "ostatnie 7 dni"),
        kpiCard(ICO.percent, "amber", "Churn rate", fmtPct(data.offer_churn_rate), "% wygasłych ofert"),
        kpiCard(ICO.barChart, "blue", "YTD", fmt(data.offers_ytd), "od początku roku"),
    ].join("");

    // Daily trend line + 7D rolling avg
    const series = data.daily_series || [];
    if (series.length) {
        // Compute 7D and 30D rolling averages
        const counts = series.map(s => s.count);
        const rolling7 = counts.map((_, i) => {
            const start = Math.max(0, i - 6);
            const slice = counts.slice(start, i + 1);
            return Math.round(slice.reduce((a, b) => a + b, 0) / slice.length);
        });

        createChart("chartDailyTrend", {
            type: "line",
            data: {
                labels: series.map(s => s.date.substring(5)),
                datasets: [
                    {
                        label: "Oferty / dzień",
                        data: counts,
                        borderColor: "rgba(99,102,241,0.4)",
                        backgroundColor: "rgba(99,102,241,0.05)",
                        fill: true,
                        tension: 0.3,
                        pointRadius: 0,
                        borderWidth: 1.5,
                    },
                    {
                        label: "Średnia 7-dniowa",
                        data: rolling7,
                        borderColor: "#6366f1",
                        borderWidth: 2.5,
                        tension: 0.4,
                        pointRadius: 0,
                        fill: false,
                    },
                ],
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: { legend: { position: "top" }, tooltip: defaultTooltip },
                scales: {
                    x: { grid: { display: false }, ticks: { font: { family: "Inter", size: 10 }, color: "#9ca3af", maxTicksLimit: 15 } },
                    y: { grid: { color: "rgba(0,0,0,0.04)" }, ticks: { font: { family: "Inter", size: 11 }, color: "#9ca3af" }, border: { display: false } },
                },
            },
        });
    }

    // Seasonality (day of week)
    const season = data.seasonality || [];
    if (season.length) {
        createChart("chartSeasonality", {
            type: "bar",
            data: {
                labels: season.map(s => s.day),
                datasets: [{
                    data: season.map(s => s.count),
                    backgroundColor: season.map((s) => {
                        const d = s.day;
                        return (d === "Sob" || d === "Nie") ? "rgba(239,68,68,0.5)" : "rgba(99,102,241,0.6)";
                    }),
                    borderRadius: 6, borderSkipped: false,
                }],
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: defaultTooltip },
                scales: defaultScales,
            },
        });
    }

    // Churn — simple gauge-like display using a doughnut
    createChart("chartChurn", {
        type: "doughnut",
        data: {
            labels: ["Wygasłe", "Aktywne"],
            datasets: [{
                data: [data.offer_churn_rate, 100 - data.offer_churn_rate],
                backgroundColor: ["#ef4444", "#e0e7ff"],
                borderWidth: 0,
                hoverOffset: 4,
            }],
        },
        options: {
            cutout: "75%",
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: defaultTooltip,
            },
        },
    });
}


// ------------------------------------------------------------------ //
// PAGE 6: DATA QUALITY & PIPELINE                                     //
// ------------------------------------------------------------------ //

async function loadQuality() {
    const [q, log] = await Promise.all([
        api("quality"),
        api("quality/scrape-log"),
    ]);

    // KPIs
    const freshColor = q.data_freshness_status === "Świeże" ? "green"
        : q.data_freshness_status === "Do odświeżenia" ? "amber" : "red";
    const freshBadge = badge(q.data_freshness_status || "—", freshColor);

    $("#qualityKpis").innerHTML = [
        kpiCard(ICO.shield, freshColor, "Świeżość danych", freshBadge, q.data_freshness_hours != null ? `${q.data_freshness_hours}h od scrape` : ""),
        kpiCard(ICO.check, "green", "Success rate", fmtPct(q.scrape_success_rate_pct), "scrapowań"),
        kpiCard(ICO.clock, "blue", "Śr. czas scrape", q.avg_scrape_duration_sec + "s", ""),
        kpiCard(ICO.alert, "red", "Błędy łącznie", fmt(q.total_scrape_errors), "ze wszystkich runów"),
        kpiCard(ICO.layers, "indigo", "Śr. jakość danych", fmtPct(q.avg_data_completeness_pct), "completeness score"),
    ].join("");

    // Completeness per field — horizontal bar
    const fields = [
        { label: "Firma", value: q.completeness_company_pct },
        { label: "Miasto", value: q.completeness_city_pct },
        { label: "Wynagrodzenie", value: q.completeness_salary_pct },
        { label: "Seniority", value: q.completeness_seniority_pct },
        { label: "Tryb pracy", value: q.completeness_workmode_pct },
    ];
    createChart("chartCompleteness", {
        type: "bar",
        data: {
            labels: fields.map(f => f.label),
            datasets: [{
                data: fields.map(f => f.value),
                backgroundColor: fields.map(f =>
                    f.value >= 70 ? "rgba(16,185,129,0.65)" : f.value >= 40 ? "rgba(245,158,11,0.65)" : "rgba(239,68,68,0.65)"
                ),
                borderRadius: 6, borderSkipped: false,
            }],
        },
        options: {
            indexAxis: "y", responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { ...defaultTooltip, callbacks: { label: ctx => ` ${ctx.raw.toFixed(1)}%` } },
            },
            scales: {
                x: { max: 100, grid: { color: "rgba(0,0,0,0.04)" }, ticks: { callback: v => v + "%", font: { family: "Inter", size: 11 }, color: "#9ca3af" }, border: { display: false } },
                y: { grid: { display: false }, ticks: { font: { family: "Inter", size: 12 }, color: "#6b7280" } },
            },
        },
    });

    // Quality per source
    const qps = q.quality_per_source || [];
    if (qps.length) {
        createChart("chartQualityBySource", {
            type: "bar",
            data: {
                labels: qps.map(s => s.source),
                datasets: [{
                    data: qps.map(s => s.avg_quality_pct),
                    backgroundColor: qps.map(s =>
                        s.avg_quality_pct >= 70 ? "rgba(16,185,129,0.65)" : s.avg_quality_pct >= 50 ? "rgba(245,158,11,0.65)" : "rgba(239,68,68,0.65)"
                    ),
                    borderRadius: 6, borderSkipped: false,
                }],
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { ...defaultTooltip, callbacks: { label: ctx => ` ${ctx.raw.toFixed(1)}%` } },
                },
                scales: {
                    ...defaultScales,
                    y: { ...defaultScales.y, max: 100, ticks: { ...defaultScales.y.ticks, callback: v => v + "%" } },
                },
            },
        });
    }

    // Scrape log table
    let html = `<table class="data-table"><thead><tr>
        <th>Data</th><th>Źródło</th><th>Status</th>
        <th class="num">Scraped</th><th class="num">Nowe</th><th class="num">Zaktualizowane</th>
        <th class="num">Błędy</th><th class="num">Czas (s)</th>
    </tr></thead><tbody>`;
    log.forEach(r => {
        const statusBadge = r.status === "success" ? badge("✓ Sukces", "green")
            : r.status === "partial" ? badge("⚠ Częściowy", "amber")
            : badge("✗ Błąd", "red");
        html += `<tr>
            <td>${r.started_at ? r.started_at.substring(0, 16) : "—"}</td>
            <td>${r.source}</td>
            <td>${statusBadge}</td>
            <td class="num">${fmt(r.offers_scraped)}</td>
            <td class="num">${fmt(r.offers_new)}</td>
            <td class="num">${fmt(r.offers_updated)}</td>
            <td class="num">${r.errors > 0 ? `<span style="color:var(--red);font-weight:600">${r.errors}</span>` : "0"}</td>
            <td class="num">${r.duration_sec != null ? r.duration_sec : "—"}</td>
        </tr>`;
    });
    html += `</tbody></table>`;
    $("#scrapeLogTable").innerHTML = html;
}


// ------------------------------------------------------------------ //
// BOOT                                                                //
// ------------------------------------------------------------------ //

async function boot() {
    await initFilters();
    navigateTo("executive");
}

boot();

})();
