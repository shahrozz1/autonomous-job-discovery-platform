// Roleful dashboard. Reads the two files written by "python -m roleful export" and draws
// everything in the browser: no build step, no libraries, no tracking.

const $ = (id) => document.getElementById(id);
const PAGE = 40;
const YEARS = ["None", "1+", "2+", "3+", "4+", "5+", "Not stated"];
let roles = [];
let info = {};
let shown = PAGE;

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "style") for (const [k, v] of Object.entries(value)) node.style.setProperty(k, v);
    else if (key in node) node[key] = value;
    else node.setAttribute(key, value);
  }
  node.append(...children.filter((c) => c !== null && c !== undefined));
  return node;
}

const num = (n) => Number(n).toLocaleString("en-US");
const money = (n) => `$${Math.round(n / 1000)}K`;
const pct = (n, of) => (of ? Math.round((100 * n) / of) : 0);
const day = (iso) => new Date(`${iso}T12:00:00`);
const daysAgo = (iso) => Math.max(0, Math.round((day(info.summary.runDate) - day(iso)) / 86400000));
const yearsText = (y) => (y === null ? "Experience not stated" : y === 0 ? "No experience asked" : `${y}+ years`);
const countBy = (list, key) => {
  const out = new Map();
  for (const item of list) for (const k of [key(item)].flat()) out.set(k, (out.get(k) || 0) + 1);
  return [...out].sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])));
};

// --- start ----------------------------------------------------------------------------------------

Promise.all(["roles", "insights"].map((name) => fetch(`data/${name}.json`).then((r) => r.json())))
  .then(([list, insights]) => {
    roles = list;
    info = insights;
    start();
  })
  .catch(() => {
    $("count").textContent = "The data files didn't load. Run “python -m roleful export”, then serve this folder.";
  });

function start() {
  const s = info.summary;
  $("updated").textContent = `Updated ${day(s.runDate).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}`;
  const tiles = [
    ["Postings read", num(s.listed), `${num(s.inUs)} of them in the US`],
    ["Company boards", num(s.boards), "on Greenhouse, Lever and Ashby"],
    ["Matching jobs", num(s.roles), `from ${num(s.postings)} listings`],
    ["Ask for 2 years or less", num(s.entry), `${pct(s.entry, s.roles)}% of matching jobs`],
    ["Posted this week", num(s.newThisWeek), `${num(s.strong)} jobs score 80 or higher`],
  ];
  $("tiles").append(...tiles.map(([label, value, more]) =>
    el("div", {}, el("dt", { textContent: label }), el("dd", {}, value, el("small", { textContent: more })))));

  fill("f-family", "All families", countBy(roles, (r) => r.family));
  fill("f-market", "All markets", countBy(roles, (r) => r.markets));
  fill("f-skill", "Any skill", countBy(roles, (r) => r.skills.map(([name]) => name)));
  for (const id of ["f-search", "f-family", "f-market", "f-years", "f-skill", "f-sort"]) {
    $(id).addEventListener("input", () => { shown = PAGE; draw(); });
  }
  $("more").addEventListener("click", () => { shown += PAGE; drawJobs(filtered(true)); });

  const p = info.profile;
  $("profile-note").textContent =
    `Fit is scored against a sample profile (${p.skills.join(", ")}; up to ${p.maxYears} years of experience): ` +
    Object.entries(p.points).map(([part, points]) => `${part} ${points}`).join(", ") +
    " points. Change config/profile.toml to score for someone else.";

  const tabs = [$("tab-jobs"), $("tab-data")];
  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => select(i));
    tab.addEventListener("keydown", (e) => {
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") { select(1 - i); tabs[1 - i].focus(); }
    });
  });
  function select(which) {
    tabs.forEach((tab, i) => {
      tab.setAttribute("aria-selected", i === which);
      tab.tabIndex = i === which ? 0 : -1;
      $(tab.getAttribute("aria-controls")).hidden = i !== which;
    });
    for (const label of document.querySelectorAll(".jobs-only")) label.hidden = which === 1;
    location.replace(which ? "#data" : "#jobs");
  }
  if (location.hash === "#data") select(1);
  draw();
}

function fill(id, all, counted) {
  $(id).append(el("option", { value: "", textContent: all }),
    ...counted.map(([name, n]) => el("option", { value: name, textContent: `${name} (${n})` })));
}

function filtered(useYears) {
  const words = $("f-search").value.trim().toLowerCase();
  const [family, market, skill, years] = ["f-family", "f-market", "f-skill", "f-years"].map((id) => $(id).value);
  return roles.filter((r) =>
    (!words || `${r.title} ${r.company}`.toLowerCase().includes(words)) &&
    (!family || r.family === family) &&
    (!market || r.markets.includes(market)) &&
    (!skill || r.skills.some(([name]) => name === skill)) &&
    (!useYears || years === "" || (r.years ?? 0) <= Number(years)));
}

function draw() {
  drawJobs(filtered(true));
  drawCharts(filtered(false));
}

// --- jobs -----------------------------------------------------------------------------------------

function drawJobs(list) {
  const by = {
    score: (a, b) => b.score - a.score,
    posted: (a, b) => (b.posted || "").localeCompare(a.posted || ""),
    pay: (a, b) => (b.pay?.[1] || 0) - (a.pay?.[1] || 0),
  }[$("f-sort").value];
  const sorted = [...list].sort(by);
  $("count").textContent = list.length ? `${num(list.length)} of ${num(roles.length)} jobs` : "No jobs match these filters.";
  $("jobs").replaceChildren(...sorted.slice(0, shown).map(card));
  $("more").hidden = sorted.length <= shown;
}

function card(r) {
  const have = new Set(info.profile.skills);
  const where = r.locations.length > 2 ? `${r.locations[0]} and ${r.locations.length - 1} more places` : r.locations.join("; ");
  const age = r.posted ? daysAgo(r.posted) : null;
  const when = age === null ? null : age === 0 ? "today" : age === 1 ? "yesterday" : `${age} days ago`;
  return el("li", { className: "job" },
    el("div", { className: "fit" }, el("b", { textContent: r.score }), el("span", { textContent: "fit" }),
      el("i", { style: { "--fit": `${r.score}%` }, "aria-hidden": "true" })),
    el("h3", {}, el("a", { href: r.url, target: "_blank", rel: "noopener", textContent: r.title })),
    el("div", { className: "terms" },
      el("b", { textContent: r.pay ? (r.pay[0] === r.pay[1] ? money(r.pay[0]) : `${money(r.pay[0])} to ${money(r.pay[1])}`) : "Pay not listed" }),
      el("span", { textContent: yearsText(r.years) })),
    el("p", { className: "where", textContent: [r.company, where, when && `posted ${when}`].filter(Boolean).join(" · ") }),
    el("div", { className: "chips" },
      ...r.skills.slice(0, 9).map(([name, required]) =>
        el("span", { className: `chip${have.has(name) ? " have" : ""}${required ? "" : " soft"}`, textContent: name,
          title: `${required ? "Required or part of the job" : "Nice to have"}${have.has(name) ? ", in the profile" : ""}` })),
      el("details", { className: "why" }, el("summary", { textContent: "Why this score" }),
        el("ul", {}, ...r.reasons.map((text) => el("li", { textContent: text }))))));
}

// --- charts ---------------------------------------------------------------------------------------

function drawCharts(list) {
  $("data-count").textContent = `Based on ${num(list.length)} open jobs. The filters above change every chart.`;
  $("charts").replaceChildren(...[skillChart, experienceChart, payChart, ageChart, marketChart].map((chart) => chart(list)));
}

function figure(title, subtitle, body, head, rows, full = false) {
  const numeric = (i) => i > 0;
  return el("figure", { className: `chart${full ? " full" : ""}` },
    el("figcaption", {}, el("h2", { textContent: title }), el("p", { textContent: subtitle })),
    ...[body].flat(),
    el("details", {}, el("summary", { textContent: "Show as a table" }), el("div", { className: "scroll" },
      el("table", {},
        el("thead", {}, el("tr", {}, ...head.map((h, i) => el("th", { textContent: h, className: numeric(i) ? "n" : "" })))),
        el("tbody", {}, ...rows.map((row) => el("tr", {},
          ...row.map((v, i) => el("td", { textContent: v, className: numeric(i) ? "n" : "" })))))))));
}

function tip(node, strong, text) {
  node.tabIndex = 0;
  node.setAttribute("aria-label", `${strong} ${text}`);
  const show = (x, y) => {
    $("tip").replaceChildren(el("b", { textContent: strong }), text);
    $("tip").hidden = false;
    const box = $("tip").getBoundingClientRect();
    $("tip").style.left = `${Math.max(8, Math.min(x + 14, innerWidth - box.width - 8))}px`;
    $("tip").style.top = `${y + box.height + 24 > innerHeight ? y - box.height - 10 : y + 16}px`;
  };
  const hide = () => { $("tip").hidden = true; };
  node.addEventListener("pointermove", (e) => show(e.clientX, e.clientY));
  node.addEventListener("pointerleave", hide);
  node.addEventListener("focus", () => { const b = node.getBoundingClientRect(); show(b.left, b.bottom); });
  node.addEventListener("blur", hide);
  return node;
}

function skillChart(list) {
  const total = new Map(), must = new Map();
  for (const r of list) for (const [name, required] of r.skills) {
    total.set(name, (total.get(name) || 0) + 1);
    if (required) must.set(name, (must.get(name) || 0) + 1);
  }
  const top = [...total].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 18);
  const max = top[0]?.[1] || 1;
  const body = el("div", { className: "bars" }, ...top.map(([name, n]) => {
    const req = must.get(name) || 0;
    const track = el("div", { className: "track" },
      req ? el("div", { className: "bar", style: { width: `${(86 * req) / max}%` } }) : null,
      n - req ? el("div", { className: "bar", style: { width: `${(86 * (n - req)) / max}%`, "--fill": "var(--series-light)" } }) : null,
      el("span", { className: "val", textContent: `${pct(n, list.length)}%` }));
    tip(track, `${name}: ${n} jobs`, `${req} require it or use it on the job, ${n - req} list it as a plus`);
    return el("div", { className: "row" }, el("span", { className: "name", textContent: name }), track);
  }));
  const legend = el("div", { className: "legend" },
    el("span", { textContent: "Required or part of the job", style: { "--key": "var(--series)" } }),
    el("span", { textContent: "Nice to have", style: { "--key": "var(--series-light)" } }));
  return figure("Which skills do these jobs ask for?", "Share of open jobs that mention each skill", [legend, body],
    ["Skill", "Jobs", "Share", "Required or on the job"], top.map(([name, n]) => [name, n, `${pct(n, list.length)}%`, must.get(name) || 0]), true);
}

const yearSlot = (r) => (r.years === null ? 6 : Math.min(r.years, 5));

function columns(rows, highlight, describe) {
  const max = Math.max(...rows.map(([, n]) => n), 1);
  const total = rows.reduce((sum, [, n]) => sum + n, 0);
  return [
    el("div", { className: "columns" }, ...rows.map(([name, n], i) => tip(
      el("div", {}, el("b", { textContent: `${pct(n, total)}%` }),
        el("i", { style: { height: `${(82 * n) / max}%`, "--fill": highlight(i) ? "var(--series)" : "var(--rest)" } })),
      `${n} jobs`, describe(name)))),
    el("div", { className: "ticks" }, ...rows.map(([name]) => el("span", { textContent: name }))),
  ];
}

function experienceChart(list) {
  const counts = YEARS.map((name, i) => [name, list.filter((r) => yearSlot(r) === i).length]);
  const within = counts.slice(0, 3).reduce((sum, [, n]) => sum + n, 0);
  return figure("How much experience do they ask for?",
    `${pct(within, list.length)}% ask for two years or less. None of the titles say “senior”.`,
    columns(counts, (i) => i < 3, (name) => (name === "Not stated" ? "experience not stated" : `ask for ${name === "None" ? "none" : `${name} years`}`)),
    ["Experience", "Jobs", "Share"], counts.map(([name, n]) => [name, n, `${pct(n, list.length)}%`]));
}

function quantile(sorted, q) {
  const at = (sorted.length - 1) * q, low = Math.floor(at);
  return sorted[low] + (sorted[Math.min(low + 1, sorted.length - 1)] - sorted[low]) * (at - low);
}

function payChart(list) {
  const groups = YEARS.map((name, i) => [name, list.filter((r) => r.pay && yearSlot(r) === i)
    .map((r) => (r.pay[0] + r.pay[1]) / 2).sort((a, b) => a - b)]).filter(([, pay]) => pay.length >= 5)
    .map(([name, pay]) => ({ name, n: pay.length, low: quantile(pay, 0.25), mid: quantile(pay, 0.5), high: quantile(pay, 0.75) }));
  const top = Math.ceil(Math.max(...groups.map((g) => g.high), 100000) / 50000) * 50000;
  const at = (v) => `${(100 * v) / top}%`;
  const body = el("div", { className: "ranges" },
    ...groups.flatMap((g) => [
      el("span", { className: "name", textContent: g.name === "None" || g.name === "Not stated" ? g.name : `${g.name} years` }),
      tip(el("div", { className: "lane" },
        el("div", { className: "span", style: { left: at(g.low), width: at(g.high - g.low) } }),
        el("div", { className: "dot", style: { left: at(g.mid) } }),
        el("span", { className: "val", textContent: money(g.mid), style: { left: `calc(${at(g.high)} + 6px)` } })),
      `${money(g.mid)} in the middle`, `half pay ${money(g.low)} to ${money(g.high)} (${g.n} jobs that list pay)`),
    ]),
    el("span"), el("div", { className: "scale" }, ...[0, 0.5, 1].map((f) => el("span", { textContent: f ? money(top * f) : "$0" }))));
  return figure("What does each step up in experience pay?",
    "Midpoint of the listed range. Dot: median. Bar: the middle half of jobs.", body,
    ["Experience", "Jobs", "25th", "Median", "75th"], groups.map((g) => [g.name, g.n, money(g.low), money(g.mid), money(g.high)]));
}

function ageChart(list) {
  const steps = [["1 week", 7], ["1 month", 30], ["3 months", 90], ["6 months", 180], ["Older", Infinity]];
  const ages = list.filter((r) => r.posted).map((r) => daysAgo(r.posted));
  const counts = steps.map(([name, limit], i) => [name, ages.filter((d) => d <= limit && d > (i ? steps[i - 1][1] : -1)).length]);
  const old = counts.slice(3).reduce((sum, [, n]) => sum + n, 0);
  return figure("How long have these jobs been up?",
    `${pct(old, ages.length)}% have been listed for more than three months.`,
    columns(counts, (i) => i > 2, (name) => (name === "Older" ? "over six months old" : `listed up to ${name} ago`)),
    ["Age", "Jobs", "Share"], counts.map(([name, n]) => [name, n, `${pct(n, ages.length)}%`]));
}

function marketChart(list) {
  const rows = countBy(list, (r) => r.markets);
  const max = rows[0]?.[1] || 1;
  const body = el("div", { className: "bars" }, ...rows.map(([name, n]) => {
    const track = el("div", { className: "track" }, el("div", { className: "bar", style: { width: `${(86 * n) / max}%` } }),
      el("span", { className: "val", textContent: n }));
    tip(track, `${n} jobs`, `${name}; ${list.filter((r) => r.pay && r.markets.includes(name)).length} of them list pay`);
    return el("div", { className: "row" }, el("span", { className: "name", textContent: name }), track);
  }));
  return figure("Where are they?", "Jobs listed in several places count in each one", body,
    ["Market", "Jobs", "List pay"], rows.map(([name, n]) => [name, n, list.filter((r) => r.pay && r.markets.includes(name)).length]));
}
