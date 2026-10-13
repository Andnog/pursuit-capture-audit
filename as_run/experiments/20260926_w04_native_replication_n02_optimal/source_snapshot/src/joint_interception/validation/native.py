"""A-58 revised prerequisite: a model construction must replicate natively in SUMO.

Native replication of a CONSTRUCTED result means, in SUMO, open loop AND closed loop:
- the factual plan captures (same judge, same finisher, witness start within 5 s of the model's)
  with no SUMO collision;
- the D12 b1 counterfactual (same helper and window as the model's) does NOT capture;
- the plan with the helper never acting does NOT capture.
"""

from __future__ import annotations

from ..domain.contracts import CaptureParameters
from ..evaluation.capture_judge import judge_capture
from ..opportunities.types import Verdict
from ..world.construction import Plan, Scenario
from ..world.network import GraphNetwork
from .diagnostic_set import run_model
from .sumo_replay import replay

WITNESS_WINDOW_S = 5.0


def native_check(
    result: dict,
    plan: Plan,
    net: GraphNetwork,
    sumo_net,
    net_file: str,
    scenario: Scenario,
    domain: dict,
    sumo_binary: str,
    label: str = "native",
) -> tuple[bool, dict]:
    params = CaptureParameters.from_domain(domain)
    step_s = domain["timing"]["physical_step_s"]
    helper = result["d12"]["helper"]
    begin = result["d12"]["intervention_decisions"][0]
    finisher = result["factual"]["finisher"]
    t_model = result["factual"]["witness_start_s"]
    arms = {
        "factual": (plan, None),
        "b1": (plan, (helper, begin, begin + 5)),
        "helper_never_acts": (
            Plan({vid: segs for vid, segs in plan.segments.items() if vid != helper}),
            None,
        ),
    }
    detail: dict = {"helper": helper, "finisher": finisher, "model_witness_start_s": t_model}
    ok = True
    starts = 0
    for arm, (arm_plan, b1) in arms.items():
        run = run_model(net, scenario, arm_plan, domain, arm, b1)
        for loop in ("open", "closed"):
            rec = replay(
                run,
                net,
                sumo_net,
                net_file,
                domain,
                sumo_binary,
                closed_loop=(loop == "closed"),
                label=f"{label}_{arm}_{loop}",
            )
            starts += 1
            j = judge_capture(rec.trace, "e1", params, step_s)
            entry = {
                "judge": j.verdict.value,
                "finisher": j.finisher,
                "witness_start_s": j.witness_start_s,
                "sumo_collisions": len(rec.collisions),
            }
            if arm == "factual":
                good = (
                    j.verdict is Verdict.SUPPORTED
                    and j.finisher == finisher
                    and abs(j.witness_start_s - t_model) <= WITNESS_WINDOW_S
                    and not rec.collisions
                )
            else:
                good = j.verdict is not Verdict.SUPPORTED
            entry["passes"] = good
            detail[f"{arm}_{loop}"] = entry
            ok = ok and good
            if not ok:
                detail["sumo_process_starts"] = starts
                return False, detail
    detail["sumo_process_starts"] = starts
    return True, detail
