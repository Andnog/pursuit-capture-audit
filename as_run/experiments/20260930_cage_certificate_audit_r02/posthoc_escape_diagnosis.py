"""Post-hoc diagnosis of hold-condition escapes (cut checkpoint): where was the holding pursuer?"""
import json, math, sys, collections, multiprocessing as mp
ROOT="/Volumes/SSD Mac/PHD/Union/doctoral_joint_interception"
sys.path.insert(0, ROOT+"/src"); sys.path.insert(0, ROOT+"/scripts")

def one(args):
    import sumolib
    from audit_cage_certificate import replay, measures
    from train_caging_pilot import _net, _paths
    m, idx, seed = args
    ep, rec = replay(m, idx, seed, "PE3", "T", None, "hold", 60.0)
    net = _net(m)
    row = measures(ep, rec, net, 60.0)
    if not row.get("escaped"):
        return None
    coords = {n.getID(): n.getCoord() for n in sumolib.net.readNet(_paths()[m]).getNodes()}
    g = row["escape_gate"]; t_cert = row["t_cert"]
    at = min(rec, key=lambda x: abs(x["t"] - t_cert))
    pd = {v: math.dist(xy, coords[g]) for v, xy in at["pursuer_xy"].items()}
    hv = min(pd, key=pd.get)
    t_esc = t_cert + row["escape_after_s"]
    before = [x for x in rec if x["t"] < t_esc - 1e-6 and not x["edge"].startswith(":")]
    e_in = before[-1]["edge"] if before else None
    lane_in = before[-1]["evader_lane"] if before else None
    # pursuer state at the moment the evader crosses
    cross = min(rec, key=lambda x: abs(x["t"] - t_esc))
    pedge = cross["pursuer_edges"][hv]; plane = cross["pursuer_lanes"][hv]
    info = net.edges.get(pedge)
    if pedge == e_in:
        cat = "same_approach_same_lane" if plane == lane_in else "same_approach_other_lane"
    elif pedge.startswith(":"):
        cat = "pursuer_inside_junction"
    elif info is not None and info.to_node == g:
        cat = "pursuer_on_other_approach"
    elif info is not None and info.from_node == g:
        cat = "pursuer_on_exit_edge_beyond_gate"
    else:
        cat = "pursuer_elsewhere"
    return {"map": m, "index": idx, "cat": cat, "holder": hv, "holder_dist_to_gate_at_cert": round(pd[hv], 1),
            "holder_speed_at_cert": at["pursuers"][hv], "escape_after_s": row["escape_after_s"],
            "evader_in": e_in, "lanes_in": net.edges[e_in].lanes if e_in in net.edges else None,
            "holder_edge": pedge, "state_at_cert": row["state_at_cert"],
            "escape_edge_same_as_holder": pedge == cross["edge"]}

if __name__ == "__main__":
    ev = [json.loads(l) for l in open(ROOT + "/experiments/20260930_marl_pilot_r03/eval.jsonl")]
    tasks = [(r["map_id"], r["index"], r["seed"]) for r in ev if r["checkpoint"] == "cut" and r["caged"]]
    with mp.get_context("spawn").Pool(8) as pool:
        rows = [r for r in pool.map(one, tasks) if r]
    json.dump(rows, open(sys.argv[1], "w"), indent=1)
    print(len(rows), collections.Counter(r["cat"] for r in rows))
    print("lanes on evader approach", collections.Counter(r["lanes_in"] for r in rows))
    print("holder dist to gate at cert: median", sorted(r["holder_dist_to_gate_at_cert"] for r in rows)[len(rows)//2])
    for c in set(r["cat"] for r in rows):
        print(c, [ (r["map"], r["index"]) for r in rows if r["cat"]==c][:4])
