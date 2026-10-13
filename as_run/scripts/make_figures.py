"""Manuscript figures from sealed packages (read-only); PDF and PNG in docs/manuscript/figures.

F1 endpoint calibration (lenient proximity vs D06), F2 methods by team size, F3 certificate
validity, F4 junction blockability, F5 KAN capture law, F6 learning vs rule. TEST results (A-110)
are added when `experiments/20261003_test_confirmation_r01/summary.json` exists.
"""

from __future__ import annotations

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "experiments")
OUT = os.path.join(ROOT, "docs", "manuscript", "figures")
REAL = [
    "adelaide_cbd",
    "toronto_downtown",
    "washington_downtown",
    "seattle_downtown",
    "phoenix_downtown",
    "portland_downtown",
    "sapporo_grid",
]
TEST = ["chicago_loop", "melbourne_cbd", "salt_lake_city", "minneapolis_downtown"]
COL = {"plus_opt": "#1b6ca8", "ambush_a95": "#7fb3d5", "pursuit": "#b03a2e", "mappo_kan": "#6c3483"}
NAME = {
    "plus_opt": "Predictive lane blocking (optimised)",
    "ambush_a95": "Junction ambush",
    "pursuit": "Pursuit",
    "mappo_kan": "MAPPO-KAN (imitation)",
}


def load(*parts):
    path = os.path.join(EXP, *parts)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as h:
        return json.load(h)


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"), dpi=200, bbox_inches="tight")
    plt.close(fig)


def err(v):
    return [[v[0] - v[1]], [v[2] - v[0]]]


def f1_endpoints(test):
    rob = load("20261001_robustness_study_r01", "summary.json")
    cells = [c for k, c in rob["cells"].items() if k.startswith("F_")]
    mean = lambda xs: sum(xs) / len(xs)  # noqa: E731
    groups = [
        (
            "Real downtowns\n(7 cities)",
            mean([c["pursuit_prox5"][0] for c in cells]),
            None,
            mean([c["pursuit_team_d06"][0] for c in cells]),
        ),
        (
            "Literature-like\ngrids",
            rob["L_literature_like"]["pursuit_prox_5m"][0],
            rob["L_literature_like"]["pursuit_prox_5m_centre"][0],
            rob["L_literature_like"]["pursuit_d06"][0],
        ),
    ]
    add = load("20261004_audit_addendum_r01", "ADDENDUM_SUMMARY.json")
    if add:
        nt = add["replays"]["B3_null_team"]
        groups.append(
            (
                "Null team\n(no pursuit)",
                nt["prox_5m"][2],
                nt["prox_5m_centre"][2],
                nt["d06"][2],
            )
        )
    if test:
        r = test["H2"]["rates"]
        groups.append(
            (
                "TEST cities\n(unseen)",
                r["prox_5m"][0],
                r["prox_5m_centre"][0],
                r["d06"][0],
            )
        )
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    w = 0.26
    for g, (_label, body, centre, d06) in enumerate(groups):
        ax.bar(g - w, body, w, color="#d5a6bd", label="Within 5 m (body gap)" if g == 0 else None)
        if centre is not None:
            ax.bar(g, centre, w, color="#f5cba7", label="Within 5 m (centre)" if g == 1 else None)
        ax.bar(g + w, d06, w, color="#1b6ca8", label="Operational capture (OC)" if g == 0 else None)
    ax.set_xticks(range(len(groups)), [g[0] for g in groups])
    ax.set_ylabel("Success rate")
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "F1_endpoint_calibration")


def f2_methods(test):
    a99 = load("20261002_ambush_optimization_r01", "summary.json")
    panels = [("Fresh scenarios, 7 cities", a99["cells"], ("AVOIDANT", "RANDOM"))]
    if test:
        panels.append(
            ("Held-out TEST cities", test["TX"], ("AVOIDANT", "RANDOM", "OPTIMAL_ESCAPE"))
        )
    n = sum(len(p[2]) for p in panels)
    fig, axes = plt.subplots(1, n, figsize=(2.6 * n, 3.2), sharey=True)
    k = 0
    for title, cells, levels in panels:
        for level in levels:
            ax = axes[k]
            k += 1
            for j, m in enumerate(("plus_opt", "ambush_a95", "pursuit")):
                xs, ys, es = [], [], []
                for team in (3, 5, 7):
                    c = cells.get(f"{level}_team{team}")
                    if c and c.get(m):
                        xs.append(team + (j - 1) * 0.25)
                        ys.append(c[m][0])
                        es.append(c[m])
                if ys:
                    ax.errorbar(
                        xs,
                        ys,
                        yerr=[
                            [y - e[1] for y, e in zip(ys, es, strict=True)],
                            [e[2] - y for y, e in zip(ys, es, strict=True)],
                        ],
                        fmt="o-",
                        color=COL[m],
                        label=NAME[m] if k == 1 else None,
                        ms=4,
                        capsize=2,
                    )
            ax.set_title(f"{title}\n{level.replace('_', ' ').lower()}", fontsize=8)
            ax.set_xticks([3, 5, 7])
            ax.set_xlabel("Pursuers")
            ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Capture rate (OC)")
    fig.legend(frameon=False, fontsize=8, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.16))
    save(fig, "F2_methods_by_team")


def f3_certificates(test):
    add = load("20261004_audit_addendum_r02", "ADDENDUM_R02_SUMMARY.json")
    if add:
        r = add["N_I"]
        f = lambda x: [x["observed"], *x["family_95"]]  # noqa: E731
        bars = [
            ("Junction\n7 cities", f(r["B2F_junction_joint"])),
            ("Junction\nTEST", f(r["B2T_junction_joint"])),
            ("Lane\n7 cities", f(r["B2F_lane_nv_joint"])),
            ("Lane\nTEST", f(r["B2T_lane_nv_joint"])),
        ]
        # A-133 (F4-6): the indicator audits and the OC hold audit use different escape
        # definitions and different pursuer behaviour, so they are drawn in separate panels.
        fig, (ax, ax2) = plt.subplots(
            1, 2, figsize=(6.6, 3.0), gridspec_kw={"width_ratios": [4, 2.1], "wspace": 0.45}
        )
        for i, (_label, v) in enumerate(bars):
            ax.bar(i, v[0], color="#b03a2e" if v[0] > 0.2 else "#1b6ca8")
            ax.errorbar(i, v[0], yerr=err(v), color="k", capsize=3)
        ax.set_xticks(range(len(bars)), [b[0] for b in bars], fontsize=7)
        ax.set_ylabel("Gate or network exit within 60 s", fontsize=8)
        title_a = "(a) Containment indicators, by level\npursuers keep their last orders"
        ax.set_title(title_a, fontsize=8)
        ax.set_ylim(0, 1)
        ax.spines[["top", "right"]].set_visible(False)
        ae = load("20261004_audit_addendum_r03", "ADDENDUM_R03_SUMMARY.json")["AE"]
        n, probe = ae["captures"], ae["escapes"]
        held = [("Scripted\nevader", 0), ("Active\nlane-change\nprobe", probe)]
        for i, (_label, k) in enumerate(held):
            ax2.bar(i, k / n, color="#1b6ca8")
            ax2.text(i, k / n + 0.03, f"{k} / {n:,}", ha="center", fontsize=7)
        ax2.set_xticks(range(len(held)), [h[0] for h in held], fontsize=7)
        ax2.set_ylabel("Moved more than 10 m within 60 s", fontsize=8)
        ax2.set_title("(b) OC captures\npursuers held", fontsize=8)
        ax2.set_ylim(0, 1)
        ax2.spines[["top", "right"]].set_visible(False)
        save(fig, "F3_certificate_validity")
        return
    fin = load("20261001_final_study_r01", "summary.json")["descriptive"]
    d06 = load("20261003_d06_persistence_audit_r01", "summary.json")["per_method"]["pursuit"]
    bars = [
        ("Junction-level\ncertificate", fin["audit_junction"]["escape"]),
        ("Lane-level\ncertificate", fin["audit_lane_nv"]["escape"]),
        ("OC capture\n(pursuers held)", d06["frozen_escape_60s"][:3]),
    ]
    if test:
        s5 = test["S"]["S5_certificates"]
        if s5["junction"]["escape"]:
            bars.insert(1, ("Junction-level\n(TEST)", s5["junction"]["escape"]))
        if s5["lane_nv"]["escape"]:
            bars.insert(3, ("Lane-level\n(TEST)", s5["lane_nv"]["escape"]))
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    for i, (_label, v) in enumerate(bars):
        ax.bar(i, v[0], color="#b03a2e" if v[0] > 0.1 else "#1b6ca8")
        ax.errorbar(i, v[0], yerr=err(v), color="k", capsize=3)
    ax.axhline(0.10, ls="--", lw=0.8, color="grey")
    ax.set_xticks(range(len(bars)), [b[0] for b in bars], fontsize=8)
    ax.set_ylabel("Evader escape within 60 s")
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "F3_certificate_validity")


def f4_blockability():
    with open(os.path.join(ROOT, "docs", "manuscript", "junction_blockability.json")) as h:
        b = json.load(h)
    extra = os.path.join(ROOT, "docs", "manuscript", "junction_blockability_test.json")
    if os.path.exists(extra):
        with open(extra) as h:
            b.update(json.load(h))
    names = [m for m in REAL + TEST + ["C2_grid6x6", "C3_grid9x9"] if m in b]
    fig, ax = plt.subplots(figsize=(6.8, 3.0))
    for k, (team, col) in enumerate(((3, "#7fb3d5"), (5, "#1b6ca8"))):
        ax.bar(
            [i + (k - 0.5) * 0.38 for i in range(len(names))],
            [b[m][f"closable_by_{team}"] for m in names],
            0.38,
            color=col,
            label=f"{team} pursuers",
        )
    ax.set_xticks(range(len(names)), [m.split("_")[0] for m in names], rotation=45, fontsize=7)
    ax.set_ylabel("Junctions closable")
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "F4_junction_blockability")


def f5_capture_law():
    c = load("20261002_kan_capture_law_r01", "CAPTURE_LAW.json")["models"]["kan"]["effect_curves"]
    fig, ax = plt.subplots(figsize=(3.6, 2.8))
    ax.plot(c["lanes_first"]["x"], c["lanes_first"]["p"], "o-", color="#6c3483")
    ax.set_xlabel("Lanes to close at the first junction")
    ax.set_ylabel("Predicted capture (KAN)")
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "F5_kan_capture_law")


def f6_learning():
    amb = load("20261001_ambush_learning_r01", "summary.json")["rates"]
    mp = load("20261002_mappo_r01", "summary.json")["rates"]
    bars = [
        ("Rule\n(ambush)", amb["rule"], "#1b6ca8"),
        ("PPO-MLP", amb["mlp_s1_best"], "#a569bd"),
        ("PPO-KAN", amb["kan_s1_best"], "#6c3483"),
        ("Planner\n(c2_15)", mp["planner_c215"], "#1b6ca8"),
        ("Teacher\n(3-s hold)", mp["teacher_mode"], "#5499c7"),
        ("MAPPO-MLP", mp["mappo_mlp_s1"], "#a569bd"),
        ("MAPPO-KAN", mp["mappo_kan_s1"], "#6c3483"),
        ("Random\nslot", mp["random_slot"], "#aab7b8"),
    ]
    fig, ax = plt.subplots(figsize=(6.8, 3.0))
    for i, (_label, v, col) in enumerate(bars):
        ax.bar(i + (0.6 if i >= 3 else 0), v[0], color=col)
        ax.errorbar(i + (0.6 if i >= 3 else 0), v[0], yerr=err(v), color="k", capsize=2)
    ax.set_xticks(
        [i + (0.6 if i >= 3 else 0) for i in range(len(bars))], [b[0] for b in bars], fontsize=7
    )
    ax.set_ylabel("Capture rate (OC)")
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, "F6_learning_vs_rule")


def f7_interpretability():
    add = load("20261004_audit_addendum_r01", "ADDENDUM_SUMMARY.json")
    if add:
        me = add["B5"]["matched_estimand"]["lanes_first"]
        fig, ax = plt.subplots(figsize=(3.6, 2.8))
        x = list(range(1, len(me["observed"]) + 1))
        ax.plot(x, me["observed"], "ks", ms=4, label="Observed (held out)")
        for name, col, lab in (
            ("kan", "#6c3483", "KAN"),
            ("spline_gam", "#28b463", "Spline-additive"),
            ("mlp", "#a569bd", "MLP"),
            ("logistic", "#1b6ca8", "Logistic"),
        ):
            m = me["models"][name]
            ax.plot(x, m["pred"], "-", color=col, label=f"{lab} (r={m['r']}, MAE={m['mae']})")
        ax.set_xlabel("Bin of lanes to close (held-out rows)", fontsize=8)
        ax.set_ylabel("Capture probability")
        ax.legend(frameon=False, fontsize=6)
        ax.spines[["top", "right"]].set_visible(False)
        save(fig, "F7_kan_mlp_logistic_shapes")
        return
    r = load("20261003_interpretability_r01", "INTERPRETABILITY_CAPTURE_LAW.json")
    if r is None:
        return
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9))
    for ax, f, label in (
        (axes[0], "lanes_first", "Lanes to close at the first junction"),
        (axes[1], "t_mean", "Mean pursuer travel time to the evader (s)"),
    ):
        x = r["models"]["kan"]["pd"][f]["x"]
        obs = r["observed_heldout_by_bin"][f]
        ax.plot(
            [a for a, o in zip(x, obs, strict=True) if o is not None],
            [o for o in obs if o is not None],
            "ks",
            ms=4,
            label="Observed (held out)",
        )
        for name, col in (("kan", "#6c3483"), ("mlp", "#a569bd"), ("logistic", "#1b6ca8")):
            rr = r["models"][name]["pd_faithfulness_r"][f]
            ax.plot(
                x, r["models"][name]["pd"][f]["p"], "-", color=col, label=f"{name.upper()} (r={rr})"
            )
        ax.set_xlabel(label, fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Capture probability")
    axes[0].legend(frameon=False, fontsize=7)
    axes[1].legend(frameon=False, fontsize=7)
    save(fig, "F7_kan_mlp_logistic_shapes")


def main() -> int:
    test = load("20261003_test_confirmation_r01", "summary.json")
    f1_endpoints(test)
    f2_methods(test)
    f3_certificates(test)
    f4_blockability()
    f5_capture_law()
    f6_learning()
    f7_interpretability()
    print(sorted(os.listdir(OUT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
