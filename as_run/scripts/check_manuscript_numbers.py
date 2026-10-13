"""Check that key numbers in the article and its supplement match the sealed summaries (A-121).

Each check formats a value from a summary JSON and looks for it in the normalised LaTeX source
("$-$" -> "-", math and spacing commands removed). Prints a table and exits non-zero on a mismatch.
"""

from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "experiments")


def load(*p):
    path = os.path.join(EXP, *p)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as h:
        return json.load(h)


def norm(tex):
    tex = (
        tex.replace("$-$", "-")
        .replace("\\%", "%")
        .replace("\\,", "")
        .replace("$", "")
        .replace("{", "")
        .replace("}", "")
    )
    tex = re.sub(r"\s+", " ", tex)
    return tex


def f3(x):
    return f"{x:.3f}"


def half_up(x, nd=3):
    """Round a stored decimal half up (0.0775 -> 0.078), as the sealed decision documents do."""
    from decimal import ROUND_HALF_UP, Decimal

    return str(Decimal(str(x)).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP))


def iv(lo, hi, nd=3):
    return f"[{lo:.{nd}f}, {hi:.{nd}f}]"


def pct(x, nd=1):
    return f"{100 * x:.{nd}f}"


def piv(b):
    return f"[{pct(b[0])}, {pct(b[1])}]"


def main() -> int:
    # The article and its supplement are checked together: detail moved to the supplement must
    # still match the sealed summaries.
    # Optional argument: the folder of the manuscript to check (default: the IEEE-template one).
    folder = sys.argv[1] if len(sys.argv) > 1 else os.path.join("docs", "manuscript", "ieee")
    tex = raw = ""
    for name in ("main.tex", "supplement.tex"):
        path = os.path.join(ROOT, folder, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as h:
                text = h.read()
            raw += text
            tex += " " + norm(text)
    checks = []
    a1 = load("20261004_audit_addendum_r01", "ADDENDUM_SUMMARY.json")
    if a1:
        b4 = a1["B4"]
        h1 = b4["TEST_H1_plb_minus_pursuit"]
        checks += [
            ("H1 estimate", f3(h1["family_97.5"][0])),
            ("H1 family 97.5", iv(*h1["family_97.5"][1:])),
            ("H1 city-family 95", iv(*h1["city_family_95"][1:])),
            ("H2 estimate", f3(b4["TEST_H2_prox5_minus_pc_pursuit"]["family_97.5"][0])),
            ("H2 family 97.5", iv(*b4["TEST_H2_prox5_minus_pc_pursuit"]["family_97.5"][1:])),
            ("S2 optimal TEST", iv(*b4["TEST_S2_optimal_plb_minus_pursuit"]["family_95"][1:])),
            ("OX optimal", iv(*b4["OX_optimal_plb_minus_pursuit"]["family_95"][1:])),
            ("Goal family", iv(*b4["GOAL_plb_minus_pursuit"]["family_95"][1:])),
            (
                "A-99 primary city-family",
                iv(*b4["A99_plb_minus_a95 (A-99 primary)"]["city_family_95"][1:]),
            ),
        ]
    a2 = load("20261004_audit_addendum_r02", "ADDENDUM_R02_SUMMARY.json")
    if a2:
        ni = a2["N_I"]
        nd = ni["null_d06"]
        checks += [
            (
                "Null OC",
                f"{pct(nd['observed'])}% [{pct(nd['family_95'][0])}, {pct(nd['family_95'][1])}]",
            ),
            ("Lane TEST joint", piv(ni["B2T_lane_nv_joint"]["family_95"])),
            ("Junction A-91 joint", piv(ni["B2F_junction_joint"]["family_95"])),
            ("Persistence families", str(a2["P"]["families_scenario_evader"])),
            ("KAN TEST AUC", f"{a2['K']['splits']['TEST']['observed_auc']['kan']:.3f}"),
        ]
    mv = load("20261004_mappo_v2_r01", "summary.json")
    if mv:
        for head in ("mlp", "kan"):
            d = mv["primary"][head]["minus_planner_97.5"]
            checks.append((f"MAPPO-v2 {head}", iv(d[1], d[2])))
    a3 = load("20261004_audit_addendum_r03", "ADDENDUM_R03_SUMMARY.json")
    if a3:
        p = a3["AB"]["primary_pooled"]
        checks.append(("AB primary", iv(p[1], p[2])))
    pe = load("20261005_published_env_audit_r01", "summary.json")
    if pe:
        for cell, label in (
            ("3x3Traffic_4_2|null", "Published env null 4v2"),
            ("3x3Traffic_4_2|greedy", "Published env chaser 4v2"),
            ("3x3Traffic_7_4|null", "Published env null 7v4"),
            ("3x3Traffic_7_4|greedy", "Published env chaser 7v4"),
        ):
            b = pe["cells"][cell]
            sc = b["published"]["success"]
            checks.append((label, f"{pct(sc[0])}% {piv(sc[1:])}"))
        r02 = load("20261005_published_env_audit_r02", "ANALYSIS.json")
        if r02:
            # follow-up marks come from the addendum that completed the 12 censored cases (A-133)
            for cell, label in (
                ("3x3Traffic_4_2|null", "Published env null 4v2"),
                ("3x3Traffic_4_2|greedy", "Published env chaser 4v2"),
                ("3x3Traffic_7_4|null", "Published env null 7v4"),
                ("3x3Traffic_7_4|greedy", "Published env chaser 7v4"),
            ):
                far = r02["marks"][cell]["+10s"]["over_50m_from_every_pursuer"]
                checks.append((label + " +10 s", f"{pct(far[0])}% {piv(far[1:3])}"))
                stop = r02["stop_analogue"][cell]["share_stopped_2s"]
                checks.append((label + " stop 2 s", f"{pct(stop)}%"))
        n_events = sum(b["published"]["capture_events"] for b in pe["cells"].values())
        checks.append(("Published env events", f"{n_events} over both"))
    mp_ = load("20261005_mappo_prox_r01", "summary.json")
    if mp_:
        g = mp_["primary"]["gap_prox_minus_oc__prox_trained_minus_oc_trained"]
        checks.append(("Prox-trained primary", iv(g[1], g[2])))
        d = mp_["secondary"]["d06:prox_trained_minus_oc_trained"]
        checks.append(("Prox-trained OC loss", f"{d[0]:.3f} {iv(d[1], d[2])}"))
        for name, key in (
            ("PLB-pursuit OC (PE19)", "d06:plb_minus_pursuit"),
            ("PLB-pursuit 5 m", "prox_5m:plb_minus_pursuit"),
        ):
            d = mp_["secondary"][key]
            checks.append((name, iv(d[1], d[2])))
    ks = load("20261005_kinematic_sensitivity_r01", "summary.json")
    if ks:
        for variant in ("K0", "K1", "K2"):
            d = ks["variants"][variant]["plb_minus_pursuit_family_95"]
            checks.append((f"Kinematics {variant}", f"+{d[0]:.3f} {iv(d[1], d[2])}"))
    ti = load("20261005_traffic_interaction_posthoc_r01", "POSTHOC.json")
    if ti:
        d = ti["family_95"]
        checks.append(("Traffic interaction", iv(d[1], d[2])))
    tr = load("20261005_traffic_sensitivity_r01", "summary.json")
    if tr:
        d = tr["primary_plb_minus_pursuit_traffic_family_95"]
        checks.append(("Traffic primary", f"+{d[0]:.3f} {iv(d[1], d[2])}"))
        d = tr["traffic_minus_no_traffic_plb_family_95"]
        checks.append(("Traffic effect on PLB", f"{d[0]:.3f} {iv(d[1], d[2])}"))
    te = load("20261005_tuned_evader_r01", "summary.json")
    if te:
        d = te["primary_plb_minus_pursuit_vs_tuned_family_95"]
        checks.append(("Tuned evader primary", f"+{d[0]:.3f} {iv(d[1], d[2])}"))
        d = te["primary_city_family_95"]
        checks.append(("Tuned evader city-family", iv(d[1], d[2])))
        d = te["plb_tuned_minus_reference_family_95"]
        checks.append(("Tuned minus reference", iv(d[1], d[2])))
    m3 = load("20261005_mappo_v3_r01", "summary.json")
    if m3:
        d = m3["primary_2_gap_P_final_minus_start"]["family_95"]
        checks.append(("MAPPO-v3 primary 2", f"{d[0]:.3f} {iv(d[1], d[2])}"))
        sec = m3["secondary"]
        for label, key in (
            ("MAPPO-v3 final W - start", "d06:final_W_mlp_minus_start"),
            ("MAPPO-v3 final F mlp - start", "d06:final_F_mlp_minus_start"),
            ("MAPPO-v3 final F kan - start", "d06:final_F_kan_minus_start"),
            ("MAPPO-v3 final P - start", "d06:final_P_mlp_minus_start"),
            ("MAPPO-v3 start - PLB", "d06:start_mlp_minus_plb"),
            ("PLB-pursuit OC (PE23)", "d06:plb_minus_pursuit"),
            ("PLB-pursuit 5 m (PE23)", "prox_5m:plb_minus_pursuit"),
            ("PLB-pursuit centre (PE23)", "prox_5m_centre:plb_minus_pursuit"),
        ):
            d = sec[key]
            checks.append((label, iv(d[1], d[2])))
    # A-143 / A-144: the learning block repeated with the corrected training loop.
    m4 = load("20261006_mappo_v4_r01", "ANALYSIS.json")
    if m4:
        t, tr = m4["test"], m4["training"]
        d = t["primary_2"]["family_95"]
        checks.append(("MAPPO-v4 primary 2", f"+{d[0]:.3f} {iv(d[1], d[2])}"))
        for label, key in (
            ("MAPPO-v4 final W - start", "d06:final_W_mlp_minus_start"),
            ("MAPPO-v4 final F mlp - start", "d06:final_F_mlp_minus_start"),
            ("MAPPO-v4 final F kan - start", "d06:final_F_kan_minus_start"),
            ("MAPPO-v4 final P - start", "d06:final_P_mlp_minus_start"),
            ("MAPPO-v4 W - F", "d06:final_W_mlp_minus_final_F_mlp"),
            ("MAPPO-v4 start - PLB", "d06:start_mlp_minus_plb"),
            ("PLB-pursuit OC (PE24)", "d06:plb_minus_pursuit"),
            ("PLB-pursuit 5 m (PE24)", "prox_5m:plb_minus_pursuit"),
            ("PLB-pursuit centre (PE24)", "prox_5m_centre:plb_minus_pursuit"),
        ):
            d = t["secondary"][key]
            checks.append((label, iv(d[1], d[2])))
        runs = [v for k, v in tr["runs"].items() if k.endswith("|train")]
        oc = [v for k, v in tr["runs"].items() if not k.startswith("P_")]
        a = tr["all"]
        checks += [
            ("MAPPO-v4 test completed", f"leaving {t['completed']}"),
            ("MAPPO-v4 training valid", f"{sum(v['valid'] for v in runs)} were valid"),
            ("MAPPO-v4 transitions", f"{sum(v['transitions'] for v in runs)} transitions"),
            ("MAPPO-v4 sampled valid", f"{a['valid']} valid"),
            (
                "MAPPO-v4 earlier contract",
                f"{a['earlier_contract_decisions']} decisions, of which "
                f"{a['earlier_contract_decisions_without_future']}",
            ),
            (
                "MAPPO-v4 captures on a tick",
                f"{sum(v['captures_on_a_decision_tick'] for v in oc)} of "
                f"{sum(v['captures'] for v in oc)} captures",
            ),
            ("MAPPO-v4 collisions", str(a["episodes_with_a_collision"])),
        ]
    # A-139 (fifth review): scan of capture instants, reconstruction and offline delimitation.
    sc = load("20261005_capture_instant_scan_r01", "summary.json")
    if sc:
        n = sc["replays"]
        checks += [
            ("Scan: instants confirmed", f"agree in all {sc['same_instant_all_four']} captures"),
            ("Scan: inner gaps", f"in {sc['traces_with_an_inner_gap']} of the {n} traces"),
            ("Scan: frames", f"{sc['frames_scanned'] / 1e6:.2f} million"),
        ]
    rc = load("20261005_v3_first_batch_reconstruction_r01", "summary.json")
    if rc:
        a = rc["all_runs"]
        dec, nof = a["decisions_trained_by_the_earlier_contract"], a["of_which_without_a_future"]
        checks += [
            ("Reconstruction: runs", f"{rc['reproduced_runs']} of 8 batches reproduced"),
            ("Reconstruction: decisions", f"trained {dec} decisions, of which {nof}"),
            ("Reconstruction: episodes", f"{a['valid']} valid episodes"),
            ("Reconstruction: horizon", f"{a['episodes_ending_at_the_horizon']} at the horizon"),
        ]
    dl = load("20261005_fifth_review_delimitation_r01", "DELIMITATION.json")
    if dl:
        t = dl["v3_training_from_the_sealed_log"]["all_runs"]
        tick = dl["capture_on_a_decision_tick_v2_test"]["learned (3 s decisions)"]
        checks += [
            ("Delimitation: valid range", f"between {t['valid_min']} and {t['valid_max']}"),
            (
                "Delimitation: no objective",
                f"between {t['without_objective_min']} and {t['without_objective_max']}",
            ),
            ("Delimitation: on a tick", f"{tick['on_a_tick']} of {tick['captures']} captures"),
        ]
    # A-138 / A-141: second held-out set, and its post hoc comparison with TEST.
    hb = load("20261005_heldout_b_r01", "summary.json")
    if hb:
        b1, b2 = hb["B1_plb_minus_pursuit_family_97.5"], hb["B2_prox5_minus_oc_pursuit_family_97.5"]
        checks += [
            ("Held-out B primary 1", f"+{b1[0]:.3f} [{b1[1]:.3f}, {b1[2]:.3f}]"),
            ("Held-out B city-family", iv(*hb["B1_city_family_95"][1:])),
            ("Held-out B primary 2", f"+{b2[0]:.3f} [{b2[1]:.3f}, {b2[2]:.3f}]"),
            ("Held-out B optimal", iv(*hb["optimal_plb_minus_pursuit_family_95"][1:])),
            ("Held-out B PLB-ambush", iv(*hb["plb_minus_ambush_family_95"][1:])),
            ("Held-out B under body gap", iv(*hb["plb_minus_pursuit_under_body_gap_5m"][1:])),
            ("Held-out B under centre", iv(*hb["plb_minus_pursuit_under_centre_5m"][1:])),
            ("Held-out B null OC", f"{pct(hb['null_team']['d06'])}%"),
            ("Held-out B null body gap", f"{pct(hb['null_team']['prox_5m'])}%"),
            ("Held-out B null centre", f"{pct(hb['null_team']['prox_5m_centre'])}%"),
            ("Held-out B valid", f"{hb['episodes'] - hb['failed']} valid"),
        ]
    ph = load("20261006_heldout_sets_posthoc_r01", "summary.json")
    if ph:
        for label, key in (
            ("Held-out sets: PLB-pursuit", "plb_minus_pursuit_oc"),
            ("Held-out sets: PLB-ambush", "plb_minus_ambush_oc"),
            ("Held-out sets: gap", "body_gap_5m_minus_oc_pursuit"),
        ):
            d = ph["contrasts"][key]["TEST_minus_HELDOUT_B_95"]
            checks.append((label, f"+{half_up(d[0])} [{half_up(d[1])}, {half_up(d[2])}]"))
    # A-137 / A-140: second published environment.
    pp = load("20261005_published_env_pepcrl_r01", "summary.json")
    if pp:
        for scenario in ("RealMap_6_3", "RealMap_7_4", "RealMap_8_5"):
            sn = pp["cells"][f"{scenario}|null"]["published"]["success"]
            checks.append((f"PEPCRL null {scenario[-3:]}", f"{pct(sn[0])}% {piv(sn[1:])}"))
            sg = pp["cells"][f"{scenario}|greedy"]["published"]["success"]
            checks.append((f"PEPCRL chaser {scenario[-3:]}", f"{pct(sg[0])}%"))
            checks.append((f"PEPCRL chaser {scenario[-3:]} interval", piv(sg[1:])))
        events = sum(b["published"]["capture_events"] for b in pp["cells"].values())
        same = sum(b["published"]["relation_counts"]["same_lane"] for b in pp["cells"].values())
        checks.append(("PEPCRL events", f"none of the {events} capture events"))
        checks.append(("PEPCRL same lane", str(same)))
        aborted = sum(
            b["published"]["capture_events_from_aborted_episodes"] for b in pp["cells"].values()
        )
        done_pub = sum(b["published"]["episodes"] for b in pp["cells"].values())
        checks.append(
            (
                "PEPCRL completed",
                f"{pp['rows']} scheduled episodes, {pp['rows'] - pp['failed']} completed",
            )
        )
        checks.append(("PEPCRL published mode", f"{done_pub} in published mode"))
        checks.append(
            (
                "PEPCRL events before an abort",
                f"{events - aborted} from completed episodes and {aborted} recorded",
            )
        )
        if pe:
            both = events + sum(b["published"]["capture_events"] for b in pe["cells"].values())
            checks.append(("Published events, both environments", f"none of {both} captures"))
    counts_path = os.path.join(ROOT, "provenance", "EPISODE_COUNTS.json")
    if os.path.exists(counts_path):
        with open(counts_path, encoding="utf-8") as h:
            counts = json.load(h)
        own = counts["own_setting"]["total"]
        for label, key in (
            ("Count evaluation", "evaluation"),
            ("Count selection", "selection"),
            ("Count replay", "replay"),
            ("Count failed", "failed"),
        ):
            checks.append((label, str(own[key])))
        third = counts["third_party_environment"]["total"]
        checks.append(("Count third-party replays", f"{third['replay']} replays"))
    bad = 0
    for name, s in checks:
        ok = s in tex
        bad += not ok
        print(f"{'OK ' if ok else 'MISSING'}  {name:28s} {s}")
    body = "\n".join(x for x in raw.splitlines() if not x.lstrip().startswith("%"))
    pending = len(re.findall(r"\\pending\{", body))
    if pending:
        print(f"PENDING markers still in the manuscript: {pending} (remove them before submission)")
    print(f"{len(checks) - bad}/{len(checks)} found")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
