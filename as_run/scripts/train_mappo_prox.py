"""MAPPO fine-tuned on the literature's proximity endpoint (A-125, pre-registered).

Same design as `train_mappo_v2.py` (A-116), with one change: the training reward, validation and
checkpoint selection use "any pursuer within 5 m (body gap) of the evader", and the episode is
truncated at the first such instant. Imitation starts from the A-116 demonstrations with the same
seeds. Test: every method is scored under OC, body-gap <= 5 m and centre <= 5 m. Resumable chunks.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import multiprocessing as mp
import os
import pickle
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import train_mappo_v2 as v2  # noqa: E402
from run_endpoint_validation import DEVELOPMENT, TRAINING  # noqa: E402

SEEDS = [1, 2]
V2 = os.path.join(ROOT, "experiments", "20261004_mappo_v2_r01", "state.pkl")
CFG = dict(v2.CFG)
# Fixed budget, as in the literature: no early stop; the final policy is the primary object.
CFG.update(max_episodes=2048, min_episodes=2048, patience=99)


def first_proximity(ep, threshold=5.0):
    """(time of the first frame with a body gap <= threshold, centre<=5 ever, body<=5 ever)."""
    from joint_interception.domain.geometry import body_separation_m

    t_first, centre5 = None, False
    for f in ep.trace:
        e = f.vehicles.get("e1")
        if e is None:
            continue
        for v, p in f.vehicles.items():
            if v == "e1":
                continue
            c = math.dist((e.x, e.y), (p.x, p.y))
            centre5 = centre5 or c <= 5.0
            near = t_first is None and c <= 16.0
            if near and body_separation_m(e.rectangle(), p.rectangle()) <= threshold:
                t_first = f.time_s
        if t_first is not None and centre5:
            break
    return t_first, centre5


def episode(args):
    from audit_cage_certificate import replay

    key, m, i, seed, salt, level, team, kind, head, weights, mode, rseed, keep_ticks = args
    learner = None
    if kind in ("mappo", "mappo_v2"):
        learner = {
            "params": v2._params(),
            "head": head,
            "weights": weights,
            "mode": mode,
            "seed": rseed,
        }
    elif kind == "ambush_plus":
        learner = {"params": v2._params()}
    try:
        ep, _ = replay(
            m, i, seed, salt, "T", None, "policy", 300.0, kind=kind, speed=1.0, level=level,
            team=team, learner=learner, reward_mode="certificate",
        )  # fmt: skip
    except Exception as error:  # noqa: BLE001
        return {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
    t_p, centre5 = first_proximity(ep)
    ticks = v2.truncate_ticks(getattr(ep, "mappo_ticks", []), t_p) if keep_ticks else []
    return {
        "key": key,
        "success": t_p is not None,  # the training / selection endpoint of this study
        "prox_5m": t_p is not None,
        "prox_5m_centre": bool(centre5),
        "d06": bool(ep.contact_capture),
        "collided": ep.collided,
        "ticks": ticks,
    }


def val_tasks(head, weights, tag):
    n = 16 * CFG["val_per_combo"]
    return [
        v2.task(f"{tag}|{k}", k, 9500 + k, "PV19", "mappo_v2", head, weights, "greedy", False)
        for k in range(n)
    ]


def test_tasks(pols):
    out = []
    for m in TRAINING + DEVELOPMENT:
        for i in range(CFG["test_scenarios"]):
            for rep in range(CFG["test_reps"]):
                seed = 9500 + i + 100000 * rep
                for level in ("AVOIDANT", "RANDOM"):
                    for team in CFG["test_teams"]:
                        for pname, kind, head, w, mode in pols:
                            out.append(
                                (f"test|{pname}|{m}|{i}|{seed}|{level}|{team}", m, i, seed, "PE19")
                                + (level, team, kind, head, w, mode, i, False)
                            )
    return out


def summarise(package, store, st):
    rows = [r for k, r in store.rows.items() if k.startswith("test|") and "failed" not in r]
    cell = {}
    for r in rows:
        _, p, m, i, _seed, level, team = r["key"].split("|")
        for f in ("d06", "prox_5m", "prox_5m_centre"):
            cell.setdefault((f, p, m, int(i), level, int(team)), []).append(float(r[f]))
    mean = {k: sum(v) / len(v) for k, v in cell.items()}
    # "prox_final": the final proximity-trained policy, averaged over the two seeds, per cell.
    finals = [f"proxlast_mlp_s{s}" for s in SEEDS]
    for k in [k for k in mean if k[1] == finals[0]]:
        vals = [mean.get((k[0], f) + k[2:]) for f in finals]
        if all(v is not None for v in vals):
            mean[(k[0], "prox_final") + k[2:]] = sum(vals) / len(vals)
    names = sorted({k[1] for k in mean})

    def rate(f, p):
        xs = [v for k, v in mean.items() if k[0] == f and k[1] == p]
        return round(sum(xs) / max(1, len(xs)), 4)

    def fam(fn):
        """fn(key_without_field_and_method) -> value or None; grouped by family."""
        out = {}
        keys = {k[2:] for k in mean}
        for k in keys:
            v = fn(k)
            if v is not None:
                out.setdefault(k[:3], []).append(v)
        return out

    def get(f, p, k):
        return mean.get((f, p) + k)

    def diff(f, a, b):
        def fn(k):
            x, y = get(f, a, k), get(f, b, k)
            return None if x is None or y is None else x - y

        return v2.family_bootstrap(fam(fn))

    def gap_diff(a, b):
        def fn(k):
            vals = [get("prox_5m", a, k), get("d06", a, k), get("prox_5m", b, k), get("d06", b, k)]
            return (
                None if any(v is None for v in vals) else (vals[0] - vals[1]) - (vals[2] - vals[3])
            )

        return v2.family_bootstrap(fam(fn))

    out = {
        "rates": {p: {f: rate(f, p) for f in ("d06", "prox_5m", "prox_5m_centre")} for p in names},
        "runs": {
            n: {k: r.get(k) for k in ("best", "bc_val", "episodes", "stop_reason", "vals")}
            for n, r in st["runs"].items()
        },
        "selected": st.get("selected"),
        "failed": sum(1 for k, r in store.rows.items() if k.startswith("test|") and "failed" in r),
        "collisions": sum(r.get("collided", False) for r in rows),
        "primary": {},
        "secondary": {},
    }
    sel = "prox_final"
    out["primary"] = {
        "checkpoint": "final policies of both proximity runs, averaged per cell",
        "gap_prox_minus_oc__prox_trained_minus_oc_trained": gap_diff(sel, "mappo_oc"),
    }
    out["secondary"]["best_validation_checkpoint_gap"] = gap_diff(
        f"prox_{st['selected']}", "mappo_oc"
    )
    g = out["primary"]["gap_prox_minus_oc__prox_trained_minus_oc_trained"]
    out["primary"]["passes"] = bool(g and g[1] > 0)
    for f in ("d06", "prox_5m", "prox_5m_centre"):
        out["secondary"][f"{f}:prox_trained_minus_oc_trained"] = diff(f, sel, "mappo_oc")
        out["secondary"][f"{f}:prox_trained_minus_plb"] = diff(f, sel, "planner_c215")
        out["secondary"][f"{f}:plb_minus_pursuit"] = diff(f, "planner_c215", "pursuit")
        for s in SEEDS:
            out["secondary"][f"{f}:final_s{s}_minus_oc_trained"] = diff(
                f, f"proxlast_mlp_s{s}", "mappo_oc"
            )
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    return out


def main() -> int:
    import torch

    from joint_interception.rl.mappo_policy import MappoActorCritic

    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--budget-min", type=float, default=25.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if args.smoke:
        CFG.update(
            bc_epochs=1, max_episodes=32, batch=16, val_every=1, val_per_combo=1, min_episodes=16,
            patience=1, test_scenarios=1, test_reps=1, test_teams=[3],
        )  # fmt: skip
        SEEDS[:] = [1]
    v2.CFG.update(CFG)
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    deadline = time.time() + 60 * args.budget_min
    spath = os.path.join(package, "state.pkl")
    with open(V2, "rb") as h:
        v2st = pickle.load(h)
    if os.path.exists(spath):
        with open(spath, "rb") as h:
            st = pickle.load(h)
    else:
        st = {"phase": "runs", "runs": {}, "order": [f"mlp_s{s}" for s in SEEDS]}

    def save():
        with open(spath + ".tmp", "wb") as h:
            pickle.dump(st, h)
        os.replace(spath + ".tmp", spath)

    def log(e):
        e["wall"] = round(time.time(), 1)
        with open(os.path.join(package, "train_log.jsonl"), "a", encoding="utf-8") as h:
            h.write(json.dumps(e) + "\n")
        print(json.dumps(e), flush=True)

    left = lambda: deadline - time.time()  # noqa: E731
    demos = v2st["demos"]
    if args.smoke:
        demos = demos[:2000]
    with mp.get_context("spawn").Pool(args.workers, initializer=v2._init) as pool:
        while st["phase"] == "runs" and left() > 150:
            pending = [r for r in st["order"] if not st["runs"].get(r, {}).get("done")]
            if not pending:
                st["selected"] = max(st["runs"], key=lambda n: (st["runs"][n]["best"], n))
                st["phase"] = "test"
                log({"stage": "selected", "run": st["selected"]})
                save()
                break
            name = pending[0]
            seed = int(name.split("_s")[1])
            run = st["runs"].setdefault(name, {})
            rng = random.Random(seed)
            if "rng_state" in run:
                rng.setstate(run["rng_state"])
            if "model" not in run:
                torch.manual_seed(seed)
                model = MappoActorCritic("mlp")
                data = list(demos)
                rng.shuffle(data)
                train = data[len(data) // 10 :]
                v2.bc_train(model, train, CFG["bc_epochs"], rng)
                v = v2.rate(
                    pool.map(episode, val_tasks("mlp", v2._bytes(model), f"v{name}0"), chunksize=2)
                )
                opt = torch.optim.Adam(model.parameters(), lr=CFG["lr"])
                run.update(
                    model=v2._bytes(model), opt=opt.state_dict(), episodes=0, iteration=0, vals=[v],
                    best=v, best_model=v2._bytes(model), bc_val=v, stale=0,
                    rng_state=rng.getstate(),
                )  # fmt: skip
                log({"stage": "bc", "run": name, "val_prox": v})
                save()
            model = MappoActorCritic("mlp")
            model.load_state_dict(torch.load(io.BytesIO(run["model"]), weights_only=True))
            opt = torch.optim.Adam(model.parameters(), lr=CFG["lr"])
            opt.load_state_dict(run["opt"])
            stop = False
            while run["episodes"] < CFG["max_episodes"] and left() > 150 and not stop:
                base = 100000 * seed + run["episodes"]
                w = v2._bytes(model)
                tasks = [
                    v2.task(
                        f"t{base + j}",
                        base + j,
                        300000 + base + j,
                        f"PT19{seed}",
                        "mappo_v2",
                        "mlp",
                        w,
                        "sample",
                        True,
                    )  # fmt: skip
                    for j in range(CFG["batch"])
                ]
                eps = pool.map(episode, tasks, chunksize=2)
                stats = v2.mappo_update(model, opt, eps, rng)
                run["episodes"] += CFG["batch"]
                run["iteration"] += 1
                log(
                    {
                        "stage": "mappo",
                        "run": name,
                        "iteration": run["iteration"],
                        "episodes": run["episodes"],
                        "prox_success": round(v2.rate(eps), 3),
                        "oc": round(sum(e.get("d06", False) for e in eps) / max(1, len(eps)), 3),
                        **{k: round(x, 4) for k, x in stats.items()},
                    }  # fmt: skip
                )
                if run["iteration"] % CFG["val_every"] == 0:
                    v = v2.rate(
                        pool.map(
                            episode,
                            val_tasks("mlp", v2._bytes(model), f"v{name}{run['iteration']}"),
                            chunksize=2,
                        )
                    )
                    run["vals"].append(v)
                    sm = sum(run["vals"][-2:]) / len(run["vals"][-2:])
                    if sm >= run["best"] + CFG["min_delta"]:
                        run["best"], run["best_model"], run["stale"] = sm, v2._bytes(model), 0
                    else:
                        run["stale"] += 1
                    log(
                        {
                            "stage": "validation",
                            "run": name,
                            "episodes": run["episodes"],
                            "val_prox": v,
                            "smoothed": round(sm, 3),
                            "best": round(run["best"], 3),
                            "stale": run["stale"],
                        }  # fmt: skip
                    )
                    if run["episodes"] >= CFG["min_episodes"] and run["stale"] >= CFG["patience"]:
                        run["stop_reason"] = "breaker"
                        stop = True
                run["model"], run["opt"] = v2._bytes(model), opt.state_dict()
                run["last_model"] = v2._bytes(model)
                run["rng_state"] = rng.getstate()
                save()
            if stop or run["episodes"] >= CFG["max_episodes"]:
                run["done"] = True
                run.setdefault("stop_reason", "max_episodes")
                log(
                    {
                        "stage": "run_end",
                        "run": name,
                        "episodes": run["episodes"],
                        "best": run["best"],
                    }
                )
                save()
        if st["phase"] == "test" and left() > 150:
            from run_ambush_optimization import Store

            sel_v2 = v2st["selected"]["mlp"]
            pols = [
                ("planner_c215", "ambush_plus", None, None, None),
                ("pursuit", "pursuit", None, None, None),
                ("mappo_oc", "mappo_v2", "mlp", v2st["runs"][sel_v2]["best_model"], "greedy"),
            ]
            for name, run in sorted(st["runs"].items()):
                pols.append((f"prox_{name}", "mappo_v2", "mlp", run["best_model"], "greedy"))
                pols.append((f"proxlast_{name}", "mappo_v2", "mlp", run["last_model"], "greedy"))
            store = Store(package)
            if store.run(pool, test_tasks(pols), deadline - 60, episode):
                st["phase"] = "summary"
            save()
            log({"stage": "test_chunk", "done": len(store.rows)})
        if st["phase"] == "summary":
            from run_ambush_optimization import Store

            out = summarise(package, Store(package), st)
            st["phase"] = "done"
            save()
            log({"stage": "done", "primary": out["primary"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
