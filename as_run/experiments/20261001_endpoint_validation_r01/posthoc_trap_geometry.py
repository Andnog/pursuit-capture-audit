"""POST-HOC (A-88): what kind of trap? For every trapped episode of the endpoint phase, replay it
and classify the immobilisation window: SANDWICH (a pursuer also behind the evader within 30 m),
DEAD_END (the evader's edge leads only back on itself), or FRONT_ONLY (blocked ahead, free behind:
trapped only because a SUMO vehicle cannot turn around mid-block)."""

import json, multiprocessing as mp, os, sys, collections
ROOT = "/Volumes/SSD Mac/PHD/Union/doctoral_joint_interception"
sys.path.insert(0, ROOT + "/src"); sys.path.insert(0, ROOT + "/scripts")
HERE = os.path.dirname(os.path.abspath(__file__))


def one(row):
    import sumolib
    from audit_cage_certificate import PURSUERS, replay
    from run_endpoint_validation import immobilised_at
    from train_caging_pilot import _paths
    ep, recs = replay(row["map_id"], row["index"], 9500 + row["index"], "PE6", "T", None, "policy", 300.0, kind=row["policy"])
    compact = [{"t": r["t"], "v": r["v_e"], "leader": r["leader"], "signal": r["signal"]} for r in recs]
    t0 = immobilised_at(compact, 10.0, 15.0, 30.0)
    if t0 is None:
        return row | {"kind": "CONTACT_ONLY"}
    win = [r for r in recs if t0 - 1e-6 <= r["t"] <= t0 + 10.0 + 1e-6]
    sandwich = any(r["follower"] and r["follower"][0] in PURSUERS and r["follower"][1] <= 30.0 for r in win)
    snet = sumolib.net.readNet(_paths()[row["map_id"]])
    edge = win[0]["edge"]
    dead = False
    if not edge.startswith(":"):
        e = snet.getEdge(edge)
        outs = [o.getID() for o in e.getToNode().getOutgoing()]
        dead = all(snet.getEdge(o).getToNode().getID() == e.getFromNode().getID() for o in outs)
    kind = "SANDWICH" if sandwich else ("DEAD_END" if dead else "FRONT_ONLY")
    return row | {"kind": kind}


if __name__ == "__main__":
    rows = [json.loads(l) for l in open(os.path.join(HERE, "endpoint.jsonl"))]
    rows = [r for r in rows if "failed" not in r and r["trapped"]]
    with mp.get_context("spawn").Pool(8) as pool:
        out = pool.map(one, rows)
    json.dump(out, open(os.path.join(HERE, "POSTHOC_TRAP_GEOMETRY.json"), "w"), indent=1)
    c = collections.Counter((r["policy"], r["kind"]) for r in out)
    for p in ("cut", "individual", "nearest", "pursuit", "random"):
        n = sum(v for (q, _), v in c.items() if q == p)
        print(p, n, {k: c[(p, k)] for k in ("SANDWICH", "DEAD_END", "FRONT_ONLY", "CONTACT_ONLY")})
    print("all", collections.Counter(r["kind"] for r in out))
