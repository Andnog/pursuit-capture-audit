#!/bin/bash
cd "/Volumes/SSD Mac/PHD/Union/doctoral_joint_interception"
PJ='{"depth": 2, "margin_s": 0.0, "slow": 1.05, "startup_s": 5.0, "hold_m": 21.776, "chasers": 0, "pre_k_min": 1, "pre_k_max": 2, "pre_margin": -1.007, "prepos_during_plan": 0}'
run() { m=$1; i=$2; meth=$3; withp=$4
  if [ "$withp" = "P" ]; then
    uv run python scripts/render_cage_gif.py --checkpoint $meth --params-json "$PJ" --map $m --index $i --seed $((9500+i)) --salt DEMO --speed 1.0 --level AVOIDANT --team 5 --condition policy --post-cage-s 300 --trap --out experiments/20261003_method_gifs/${m}_${i}_${meth}.gif 2>&1 | grep -E "frames|Error|Traceback" | sed "s/^/$meth $m $i: /"
  else
    uv run python scripts/render_cage_gif.py --checkpoint $meth --map $m --index $i --seed $((9500+i)) --salt DEMO --speed 1.0 --level AVOIDANT --team 5 --condition policy --post-cage-s 300 --trap --out experiments/20261003_method_gifs/${m}_${i}_${meth}.gif 2>&1 | grep -E "frames|Error|Traceback" | sed "s/^/$meth $m $i: /"
  fi
}
for sc in "adelaide_cbd 20" "phoenix_downtown 32"; do
  set -- $sc
  run $1 $2 pursuit N &
  run $1 $2 cut N &
  run $1 $2 ambush N &
  run $1 $2 ambush_plus P &
  run $1 $2 mappo_kan_s1 P &
done
wait
