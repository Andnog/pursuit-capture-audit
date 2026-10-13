"""Sensitivity study (A-101): parameters tuned for 7 pursuers, and faster pursuers.

Part A (tuning for 7): one generation of the A-98 search (24 random configurations + the A-99
optimum c2_15 + the defaults), successive halving 48 -> 144 -> 384 episodes on TRAINING cities with
teams of 7 (AVOIDANT / RANDOM), then fresh validation. Breaker: if the best does not beat both c2_15
and the defaults by >= 0.02 on round 3, the better of those two is kept.
Part B (test, fresh scenarios, 7 cities, full 300 s, D06):
- team 7: tuned, c2_15, defaults, pursuit;
- pursuer speed factor 1.0 / 1.1 / 1.2 (evader 1.0), teams 3 and 5: c2_15 and pursuit.
Resumable chunks (--budget-min).
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import pickle
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from run_ambush_optimization import ROUNDS, Store, _init, sample  # noqa: E402
from run_endpoint_validation import DEVELOPMENT, TRAINING  # noqa: E402
from run_robustness_study import bootstrap  # noqa: E402

LEVELS = ["AVOIDANT", "RANDOM"]
MIN_DELTA = 0.02
SPEEDS = [1.0, 1.1, 1.2]


def episode(args):
    from audit_cage_certificate import replay

    key, m, i, seed, salt, level, team, kind, params, psf, full = args
    assert isinstance(psf, float) and 0.5 <= psf <= 2.0, "pursuer speed factor"
    try:
        ep, _ = replay(
            m,
            i,
            seed,
            salt,
            "T",
            None,
            "policy",
            300.0,
            kind=kind,
            speed=1.0,
            level=level,
            team=team,
            learner={"params": params} if params is not None else None,
            reward_mode="certificate" if full else "trap",
            pursuer_speed=psf,
        )
    except Exception as error:  # noqa: BLE001
        return {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
    return {
        "key": key,
        "success": bool(
            ep.contact_capture if full else (ep.trapped_at is not None or ep.contact_capture)
        ),
        "d06": bool(ep.contact_capture),
        "collided": ep.collided,
    }


def search_tasks(rnd, configs):
    n = ROUNDS[rnd][0]
    out = []
    for cname, params in configs.items():
        for m in TRAINING:
            for level in LEVELS:
                for i in range(2 * n):
                    idx = 1000 * rnd + i
                    out.append(
                        (
                            f"s7r{rnd}|{cname}|{m}|{level}|7|{idx}",
                            m,
                            idx,
                            9500 + idx,
                            "PO7",
                            level,
                            7,
                            "ambush_plus",
                            params,
                            1.0,
                            False,
                        )
                    )
    return out


def val_tasks(configs):
    out = []
    for cname, params in configs.items():
        for m in TRAINING:
            for level in LEVELS:
                for i in range(24):
                    out.append(
                        (
                            f"v7|{cname}|{m}|{level}|7|{i}",
                            m,
                            i,
                            9500 + i,
                            "PV12",
                            level,
                            7,
                            "ambush_plus",
                            params,
                            1.0,
                            False,
                        )
                    )
    return out


def test_tasks(tuned, c215, default):
    out = []
    for m in TRAINING + DEVELOPMENT:
        for i in range(20):
            for rep in range(2):
                seed = 9500 + i + 100000 * rep
                for level in LEVELS:
                    base = f"{m}|{i}|{seed}|{level}"
                    for pname, kind, params in (
                        ("tuned7", "ambush_plus", tuned),
                        ("c215", "ambush_plus", c215),
                        ("default", "ambush_plus", default),
                        ("pursuit", "pursuit", None),
                    ):
                        out.append(
                            (
                                f"T7|{pname}|{base}|7|1.0",
                                m,
                                i,
                                seed,
                                "PE12",
                                level,
                                7,
                                kind,
                                params,
                                1.0,
                                True,
                            )
                        )
                    for team in (3, 5):
                        for psf in SPEEDS:
                            for pname, kind, params in (
                                ("c215", "ambush_plus", c215),
                                ("pursuit", "pursuit", None),
                            ):
                                out.append(
                                    (
                                        f"SP|{pname}|{base}|{team}|{psf}",
                                        m,
                                        i,
                                        seed,
                                        "PE12",
                                        level,
                                        team,
                                        kind,
                                        params,
                                        psf,
                                        True,
                                    )
                                )
    return out


def main() -> int:
    from joint_interception.native.ambush_plus import DEFAULTS

    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--budget-min", type=float, default=25.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    deadline = time.time() + 60 * args.budget_min
    spath = os.path.join(package, "state.pkl")
    st = pickle.load(open(spath, "rb")) if os.path.exists(spath) else {"phase": "search"}  # noqa: SIM115
    store = Store(package)
    c215_path = os.path.join(
        ROOT, "experiments", "20261002_ambush_optimization_r01", "summary.json"
    )
    with open(c215_path, encoding="utf-8") as h:
        c215 = json.load(h)["final_params"]
    log = open(os.path.join(package, "log.jsonl"), "a", encoding="utf-8")  # noqa: SIM115

    def note(e):
        e["wall"] = round(time.time(), 1)
        log.write(json.dumps(e) + "\n")
        log.flush()
        print(json.dumps(e), flush=True)

    def save():
        with open(spath + ".tmp", "wb") as h:
            pickle.dump(st, h)
        os.replace(spath + ".tmp", spath)

    with mp.get_context("spawn").Pool(args.workers, initializer=_init) as pool:
        if st["phase"] == "search":
            if "configs" not in st:
                rng = random.Random(707)
                cfgs = {"default": dict(DEFAULTS), "c215": dict(c215)}
                for k in range(24):
                    cfgs[f"t7_{k}"] = sample(rng)
                st.update(configs=cfgs, alive=list(cfgs), round=0)
                save()
            cfgs = st["configs"]
            while st["round"] < len(ROUNDS):
                rnd = st["round"]
                alive = {c: cfgs[c] for c in st["alive"]}
                if not store.run(pool, search_tasks(rnd, alive), deadline, episode):
                    save()
                    note({"stage": "chunk_done", "phase": "search", "round": rnd})
                    return 0
                prefixes = [f"s7r{r}" for r in range(rnd + 1)]
                ranked = sorted(
                    [c for c in alive if c not in ("default", "c215")],
                    key=lambda c: -store.score(prefixes, c)[0],
                )
                keep = ranked[: ROUNDS[rnd][1]]
                note(
                    {
                        "stage": "round",
                        "round": rnd,
                        "default": store.score(prefixes, "default"),
                        "c215": store.score(prefixes, "c215"),
                        "top": [(c, store.score(prefixes, c)) for c in ranked[:4]],
                    }
                )
                st["alive"] = ["default", "c215", *keep]
                st["round"] += 1
                save()
            best = st["alive"][2]
            r3 = [f"s7r{len(ROUNDS) - 1}"]
            sb, sd, sc = (store.score(r3, c)[0] for c in (best, "default", "c215"))
            if sb >= max(sd, sc) + MIN_DELTA:
                st["tuned"], st["tuned_name"] = cfgs[best], best
            else:
                st["tuned"], st["tuned_name"] = (
                    (cfgs["c215"], "c215") if sc >= sd else (cfgs["default"], "default")
                )
                st["breaker"] = (
                    "tuned configuration did not beat c2_15/defaults by 0.02; kept the better"
                )
            note(
                {
                    "stage": "search_end",
                    "best": best,
                    "r3": {"best": sb, "default": sd, "c215": sc},
                    "chosen": st["tuned_name"],
                    "params": st["tuned"],
                }
            )
            st["phase"] = "val"
            save()
        if st["phase"] == "val":
            cfgs = {"tuned": st["tuned"], "c215": c215, "default": dict(DEFAULTS)}
            if not store.run(pool, val_tasks(cfgs), deadline, episode):
                save()
                note({"stage": "chunk_done", "phase": "val"})
                return 0
            st["val"] = {c: store.score(["v7"], c)[0] for c in cfgs}
            note({"stage": "validation", **st["val"]})
            st["phase"] = "test"
            save()
        if st["phase"] == "test":
            tasks = test_tasks(st["tuned"], c215, dict(DEFAULTS))
            if not store.run(pool, tasks, deadline, episode):
                save()
                note(
                    {
                        "stage": "chunk_done",
                        "phase": "test",
                        "done": sum(1 for t in tasks if t[0] in store.rows),
                        "of": len(tasks),
                    }
                )
                return 0
            st["phase"] = "summary"
            save()
        if st["phase"] == "summary":
            summarise(package, store, st)
            st["phase"] = "done"
            save()
            note({"stage": "done"})
    return 0


def summarise(package, store, st):
    rows = [r for k, r in store.rows.items() if k.startswith(("T7|", "SP|")) and "failed" not in r]
    by = {}
    for r in rows:
        block, pname, m, i, seed, level, team, psf = r["key"].split("|")
        by.setdefault((block, pname, level, int(team), float(psf), m, int(i)), []).append(
            float(r["d06"])
        )
    mean = {k: sum(v) / len(v) for k, v in by.items()}

    def per(block, pname, level, team, psf):
        return {k[5:]: v for k, v in mean.items() if k[:5] == (block, pname, level, team, psf)}

    out = {
        "tuned_name": st.get("tuned_name"),
        "tuned_params": st.get("tuned"),
        "breaker": st.get("breaker"),
        "val": st.get("val"),
        "team7": {},
        "speed": {},
        "failed": sum(
            1 for k, r in store.rows.items() if k.startswith(("T7|", "SP|")) and "failed" in r
        ),
        "collisions": sum(r.get("collided", False) for r in rows),
    }
    for level in LEVELS:
        t, c, d, p = (per("T7", n, level, 7, 1.0) for n in ("tuned7", "c215", "default", "pursuit"))
        ks = sorted(set(t).intersection(c, d, p))
        out["team7"][level] = {
            "n": len(ks),
            **{
                n: bootstrap([x[k] for k in ks])
                for n, x in (("tuned7", t), ("c215", c), ("default", d), ("pursuit", p))
            },
            "tuned_minus_c215": bootstrap([t[k] - c[k] for k in ks]),
            "tuned_minus_default": bootstrap([t[k] - d[k] for k in ks]),
            "tuned_minus_pursuit": bootstrap([t[k] - p[k] for k in ks]),
        }
        for team in (3, 5):
            base = per("SP", "c215", level, team, 1.0)
            for psf in SPEEDS:
                c, p = per("SP", "c215", level, team, psf), per("SP", "pursuit", level, team, psf)
                ks = sorted(set(c).intersection(p, base))
                out["speed"][f"{level}_team{team}_x{psf}"] = {
                    "n": len(ks),
                    "c215": bootstrap([c[k] for k in ks]),
                    "pursuit": bootstrap([p[k] for k in ks]),
                    "c215_minus_pursuit": bootstrap([c[k] - p[k] for k in ks]),
                    "c215_gain_vs_x1.0": bootstrap([c[k] - base[k] for k in ks]),
                }
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
