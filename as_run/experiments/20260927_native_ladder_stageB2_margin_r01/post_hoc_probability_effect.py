# Development: capture probability with vs without the helper, 10 SUMO seeds, sigma 0.5.
import json, sys
from multiprocessing import get_context
def one(args):
    stage, mid, level, idx, c = args
    from joint_interception.domain.contracts import load_domain
    from joint_interception.simulator.evader import EvaderLevel
    from joint_interception.world.construction import make_scenario, Plan, Segment
    from joint_interception.world.network import GraphNetwork
    from joint_interception.native.engine import run_plan
    dom=load_domain(); SUMO="/Library/Frameworks/Python.framework/Versions/3.10/bin/sumo"
    path=json.load(open("assets/controlled/manifest.json"))[mid]["path"]
    net=GraphNetwork.from_sumo(path)
    sc=make_scenario(net,mid,EvaderLevel[level],dom['team']['pursuer_ids'],f"LBs{idx}")
    plan=Plan({k:[Segment(**s) for s in x] for k,x in c["plan"].items()})
    absent=Plan({k:v for k,v in plan.segments.items() if k!=c["helper"]})
    w=wo=0
    for k in range(1,11):
        w += run_plan(net,path,sc,plan,dom,SUMO,sigma=0.5,seed=2000+k,label=f"pw{mid}{idx}{k}").verdict.verdict.value=="SUPPORTED"
        wo+= run_plan(net,path,sc,absent,dom,SUMO,sigma=0.5,seed=2000+k,label=f"po{mid}{idx}{k}").verdict.verdict.value=="SUPPORTED"
    return (stage, mid, idx, w, wo)
if __name__=="__main__":
    tasks=[]
    for stage in ("stageB_r01","stageB2_margin_r01"):
        for l in open(f"experiments/20260927_native_ladder_{stage}/results.jsonl"):
            r=json.loads(l)
            for c in r.get("constructions",[]): tasks.append((stage,r["map_id"],r["level"],r["index"],c))
    with get_context("spawn").Pool(8) as p:
        out=p.map(one,tasks)
    tw=two=0
    for s,m,i,w,wo in out:
        tw+=w; two+=wo; print(f"{s:20s} {m:14s} s{i}  P(capture) with helper {w}/10  without {wo}/10")
    print("POOLED with",tw,"/",10*len(out)," without",two,"/",10*len(out))
