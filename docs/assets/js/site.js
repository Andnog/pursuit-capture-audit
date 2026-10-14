/*
 * The page: charts and numbers from assets/data/charts.json, which tools/build_site_data.py
 * writes from the sealed evidence. No number of the study is typed in the page or in this file.
 */
(function () {
  "use strict";

  const { bars, forest, strip, percent, signed, fixed } = window.Charts;
  const THIN = " ";

  const ENDPOINTS = [
    { key: "oc", name: "Operational capture", tone: "oc" },
    { key: "body", name: "Within 5 m, between bodies", tone: "prox" },
    { key: "centre", name: "Within 5 m, between centres", tone: "prox2" },
  ];
  const METHODS = [
    { key: "plus_opt", name: "Predictive lane blocking", tone: "ink" },
    { key: "ambush_a95", name: "Junction ambush", tone: "mid" },
    { key: "pursuit", name: "Pursuit", tone: "ink", shape: "ring" },
  ];

  function thousands(value) {
    return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, THIN);
  }

  function points(entry) {
    return { ...entry, v: entry.v * 100, lo: entry.lo * 100, hi: entry.hi * 100 };
  }

  function plain(values) {
    const out = {};
    Object.keys(values).forEach((key) => {
      out[key] = typeof values[key] === "number" ? { v: values[key] } : values[key];
    });
    return out;
  }

  function charts(data) {
    const development = data.null_team.development;
    return {
      "null-team": () => ({
        kind: bars,
        series: ENDPOINTS,
        max: 60,
        ticks: [0, 20, 40, 60],
        caption: "Success of a team that does not pursue, by capture rule",
        rows: [
          {
            label: "Seven cities",
            note: thousands(development.oc.n) + " episodes",
            values: { oc: development.oc, body: development.body, centre: development.centre },
          },
          { label: "Four held-out cities", note: "second held-out set", values: plain(data.null_team.heldout_b) },
        ],
      }),
      "same-episodes": () => ({
        kind: bars,
        series: ENDPOINTS,
        max: 100,
        ticks: [0, 25, 50, 75, 100],
        caption: "Success of the pursuit team on the held-out cities, by capture rule",
        rows: [
          { label: "TEST cities", note: "every evader", values: plain(data.pursuit.test) },
          { label: "HELD-OUT B cities", note: "avoidant and random evaders", values: plain(data.pursuit.heldout_b) },
        ],
      }),
      published: () => ({
        kind: bars,
        series: [
          { key: "random", name: "Team that turns at random", tone: "ink" },
          { key: "chase", name: "Team that chases", tone: "mid" },
        ],
        max: 80,
        ticks: [0, 20, 40, 60, 80],
        caption: "Episodes that meet the published success criterion, by team",
        rows: data.published.map((entry) => ({
          label: entry.name,
          note: entry.detail,
          values: { random: entry.random, chase: entry.chase },
        })),
      }),
      reversal: () => {
        const rows = [];
        ENDPOINTS.forEach((endpoint) => {
          rows.push({ heading: "Scored by: " + endpoint.name.toLowerCase() });
          data.reversal.forEach((set) => {
            rows.push({ label: set.set, tone: endpoint.tone, ...points(set[endpoint.key]) });
          });
        });
        return {
          kind: forest,
          rows,
          domain: [-8, 20],
          ticks: [-5, 0, 5, 10, 15, 20],
          unit: "points",
          caption: "Predictive lane blocking minus pursuit, by capture rule and set of scenarios",
        };
      },
      containment: () => ({
        kind: bars,
        series: [{ key: "escape", name: "Certified evaders that escape", tone: "ink" }],
        max: 100,
        ticks: [0, 25, 50, 75, 100],
        caption: "Evaders certified as enclosed that escape within 60 s",
        rows: data.containment.map((entry) => ({
          label: entry.level,
          note: entry.cities + ", " + thousands(entry.n) + " certificates",
          values: { escape: entry },
        })),
      }),
      advantage: () => ({
        kind: forest,
        rows: data.advantage.map((entry) => ({ ...points(entry), label: entry.label, note: entry.note, tone: "oc", strong: entry.primary })),
        domain: [-5, 30],
        ticks: [0, 10, 20, 30],
        unit: "points",
        caption: "Predictive lane blocking minus pursuit, in operational capture",
      }),
      "by-team-test": () => teamStrip(data.by_team.test, "TEST cities"),
      "by-team-b": () => teamStrip(data.by_team.heldout_b, "HELD-OUT B cities"),
      ablation: () => ({
        kind: forest,
        rows: [{ ...points(data.ablation.all), label: "All scenarios", tone: "oc", strong: true }].concat(
          data.ablation.rows.map((entry) => ({ ...points(entry), label: entry.label, tone: "oc" }))
        ),
        domain: [0, 14],
        ticks: [0, 5, 10],
        unit: "points",
        caption: "Coordinated minus independent lane blocking, in operational capture",
      }),
      learning: () => ({
        kind: forest,
        rows: data.learning.map((entry) => ({ ...points(entry), label: entry.label, note: entry.note, tone: "oc" })),
        domain: [-3, 6],
        ticks: [-2, 0, 2, 4, 6],
        unit: "points",
        caption: "Learned controllers: change in operational capture",
      }),
    };
  }

  function teamStrip(rows, title) {
    const out = [];
    let evader = null;
    rows.forEach((row) => {
      if (row.evader !== evader) {
        evader = row.evader;
        out.push({ heading: evader + " evader" });
      }
      const values = {};
      METHODS.forEach((method) => {
        values[method.key] = row[method.key] * 100;
      });
      out.push({ label: row.team + " pursuers", values });
    });
    return {
      kind: strip,
      series: METHODS,
      rows: out,
      domain: [0, 45],
      ticks: [0, 10, 20, 30, 40],
      caption: "Operational capture rate by evader and team size, " + title,
    };
  }

  function fills(data) {
    const development = data.null_team.development;
    const primary = data.advantage.filter((entry) => entry.primary).map(points);
    const junction = data.containment.filter((entry) => entry.level.startsWith("Junction")).map((entry) => entry.v);
    const lane = data.containment.filter((entry) => entry.level.startsWith("Lane")).map((entry) => entry.v);
    const random = data.published.map((entry) => entry.random.v);
    const chase = data.published.map((entry) => entry.chase.v);
    const span = (values) => {
      const low = fixed(Math.min(...values), 0);
      const high = fixed(Math.max(...values), 0);
      return low === high ? "About " + low : low + "–" + high;
    };
    const interval = (entry) => "[" + fixed(entry.lo, 1) + ", " + fixed(entry.hi, 1) + "]";
    return {
      "null-oc": percent(development.oc.v),
      "null-body": percent(development.body.v),
      "null-centre": percent(development.centre.v),
      "null-body10": percent(development.body10.v),
      "null-range": span([development.centre.v, development.body10.v, data.null_team.heldout_b.centre]) + " %",
      "published-events": thousands(data.published_events),
      "published-random": span(random) + " %",
      "published-chase": span(chase) + " %",
      "test-oc": percent(data.pursuit.test.oc, 0),
      "test-body": percent(data.pursuit.test.body, 0),
      "ratio-test": fixed(data.pursuit.test.body / data.pursuit.test.oc, 1),
      "ratio-b": fixed(data.pursuit.heldout_b.body / data.pursuit.heldout_b.oc, 1),
      "junction-range": span(junction) + " %",
      "lane-range": span(lane) + " %",
      "adv-test": signed(primary[0].v, 1),
      "adv-test-ci": interval(primary[0]),
      "adv-b": signed(primary[1].v, 1),
      "adv-b-ci": interval(primary[1]),
      ablation: fixed(data.ablation.all.v * 100, 1),
      "hold-captures": thousands(data.hold.captures),
      "hold-held": String(data.hold.escapes_held),
      "hold-probe": String(data.hold.escapes_probe),
      "count-evaluation": thousands(data.counts.evaluation),
      "count-studies": String(data.counts.studies),
      "count-numbers": String(data.counts.article_numbers),
      "count-recomputed": String(data.counts.headline_recomputed),
    };
  }

  function render(data) {
    const specs = charts(data);
    document.querySelectorAll("[data-chart]").forEach((root) => {
      const build = specs[root.dataset.chart];
      if (!build) return;
      const spec = build();
      spec.kind(root, spec);
    });
    const values = fills(data);
    document.querySelectorAll("[data-fill]").forEach((target) => {
      if (values[target.dataset.fill] !== undefined) target.textContent = values[target.dataset.fill];
    });
  }

  function navigation() {
    const links = Array.from(document.querySelectorAll(".site-nav a[href^='#']"));
    const byId = new Map(links.map((link) => [link.getAttribute("href").slice(1), link]));
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          links.forEach((link) => link.removeAttribute("aria-current"));
          const link = byId.get(entry.target.id);
          if (link) link.setAttribute("aria-current", "true");
        });
      },
      { rootMargin: "-35% 0px -60% 0px" }
    );
    byId.forEach((_link, id) => {
      const section = document.getElementById(id);
      if (section) observer.observe(section);
    });
  }

  function copyButtons() {
    document.querySelectorAll("pre").forEach((block) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "copy";
      button.textContent = "Copy";
      button.addEventListener("click", () => {
        navigator.clipboard.writeText(block.querySelector("code").textContent).then(() => {
          button.textContent = "Copied";
          setTimeout(() => (button.textContent = "Copy"), 1600);
        });
      });
      block.appendChild(button);
    });
  }

  function start() {
    navigation();
    copyButtons();
    fetch(new URL("assets/data/charts.json", document.baseURI))
      .then((response) => response.json())
      .then(render)
      .catch(() => {
        document.querySelectorAll("[data-chart]").forEach((root) => {
          root.textContent = "The figures could not be loaded.";
        });
      });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
