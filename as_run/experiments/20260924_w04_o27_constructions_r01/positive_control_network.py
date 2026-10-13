"""Positive control: a junction WITH cycles, so the evader's scores are finite and a helper
can change its choice. Returns (net, scenario-builder)."""
from joint_interception.domain.contracts import load_domain
from joint_interception.simulator.evader import EvaderLevel
from joint_interception.world.network import EdgeInfo, GraphNetwork, Link
from joint_interception.world.construction import Constructor, Scenario, Plan, Segment
from joint_interception.evaluation.capture_judge import judge_capture
dom=load_domain()
def E(i,f,t,L,x0,y0,x1,y1): return EdgeInfo(i,f,t,L,1,13.89,((x0,y0),(x1,y1)))
edges={
 "D":E("D","n0","N",150,0,0,150,0),
 "E":E("E","N","M",100,160,0,260,0),   "E2":E("E2","M","n0",120,260,10,0,10),     # E leads back to n0 quickly
 "X":E("X","N","Q",100,150,10,150,110),"X2":E("X2","Q","n0",400,150,120,0,20),    # X leads back to n0 slowly
 "F":E("F","f0","N",120,150,-130,150,-10),"G":E("G","g0","N",120,20,40,145,5),
}
L=lambda a,b: Link(a,b,8.0,8.0,(),None)
links={k:L(*k) for k in [("D","E"),("D","X"),("F","E"),("F","X"),("G","X"),("G","E"),("E","E2"),("X","X2"),("E2","D"),("X2","D")]}
net=GraphNetwork(edges,links,{})
def scenario(level): return Scenario("positive_control",level,7,("D",10.0,6.9),{"p1":("F",10.0,0.0),"p2":("G",10.0,0.0)})
