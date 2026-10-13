"""Render one caging episode (learned checkpoint or heuristic) as a two-panel GIF.

Re-runs the episode in SUMO with the same scenario, seed and settings as the pilot evaluation
(salt PE, seed 9500 + index), records the trace and the certificate overlays, and renders the
window [end - window_s, end] with `render_capture_gif.render`.
"""

from __future__ import annotations

import argparse
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from render_capture_gif import render  # noqa: E402
from train_caging_pilot import SPEED, SUMO, TEAM, _net, _paths  # noqa: E402


def main() -> int:
    import torch

    from joint_interception.domain.contracts import load_domain
    from joint_interception.rl.policy import TokenPolicy, decide
    from joint_interception.rl.rollout import cut_policy, run_episode
    from joint_interception.simulator.evader import EvaderLevel
    from joint_interception.world.construction import make_scenario

    parser = argparse.ArgumentParser()
    parser.add_argument("--map", required=True)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--policy", required=True, help="checkpoint .pt path, or 'cut'")
    parser.add_argument("--arm", default="T")
    parser.add_argument("--salt", default="PE")
    parser.add_argument("--seed-base", type=int, default=9500)
    parser.add_argument("--window-s", type=float, default=60.0)
    parser.add_argument("--name", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    domain = load_domain()
    net = _net(args.map)
    sc = make_scenario(
        net,
        args.map,
        EvaderLevel.AVOIDANT,
        domain["team"]["pursuer_ids"][:TEAM],
        f"{args.salt}s{args.index}",
    )
    if args.policy == "cut":
        policy, arm = cut_policy(), "T"
    else:
        model = TokenPolicy()
        with open(args.policy, "rb") as h:
            model.load_state_dict(torch.load(io.BytesIO(h.read()), weights_only=True))
        model.eval()
        arm = args.arm

        def policy(obs):
            return decide(model, obs, greedy=True)[0]

    ep = run_episode(
        net,
        _paths()[args.map],
        sc,
        domain,
        SUMO,
        policy,
        speed_factor=SPEED,
        seed=args.seed_base + args.index,
        label=f"gif{args.map[:3]}{args.index}",
        arm=arm,
        keep_trace=True,
    )
    end = ep.caged_at + 10.0 if ep.caged_at is not None else ep.end_s
    end = min(end, ep.end_s)
    name = args.name or os.path.basename(args.policy)
    verdict = (
        f"PHYSICAL CAGE certified at t = {ep.caged_at:.1f} s (held 10 s)"
        if ep.caged_at is not None
        else "NO physical cage within 300 s"
    )
    verdict += f" | emergencies {ep.emergencies} | collision {ep.collided}"
    render(
        args.out,
        _paths()[args.map],
        ep.trace,
        None,
        None,
        max(0.0, end - args.window_s),
        end,
        title=f"{args.map} | scenario {args.index} | 3 pursuers, evader AVOIDANT x{SPEED}",
        subtitle=f"policy: {name} (arm {arm})",
        verdict_line=verdict,
        zoom_radius=45.0,
        overlays=ep.overlays,
    )
    print(verdict, "->", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
