"""Adapter contract: boundary, masks, fallback, deadline, proposed vs executed.

Validated OFFLINE against the deterministic backend. No SUMO process is started: native
execution is gated behind W4 and W5.
"""

from __future__ import annotations

import copy
import os
import subprocess
import sys
import unittest

from _support import ROOT, SRC  # noqa: E402
from _w2_support import requires_contracts  # noqa: E402


def make_adapter(domain_overrides: dict | None = None, gap_m: float = 60.0):
    from joint_interception.domain.contracts import load_domain
    from joint_interception.simulator.backend import DeterministicBackend, VehicleState
    from joint_interception.simulator.sumo_adapter import EpisodeAdapter

    domain = copy.deepcopy(load_domain())
    for path, value in (domain_overrides or {}).items():
        node = domain
        parts = path.split(".")
        for part in parts[:-1]:
            node = node[part]
        node[parts[-1]] = value

    vehicles = [
        VehicleState("p1", "pursuer", 0.0, 0.0, 0.0, 3.0, "l1", 0.0, 5.0, 1.8),
        VehicleState("e1", "evader", gap_m, 0.0, 0.0, 3.0, "l1", gap_m, 5.0, 1.8),
    ]
    backend = DeterministicBackend.build(vehicles, seed=31337)
    return EpisodeAdapter(backend, domain=domain)


def always_first(_observation, _vehicle_id, _actions):
    return 0


def always_none(_observation, _vehicle_id, _actions):
    return None


@requires_contracts
class TestInformationBoundary(unittest.TestCase):
    """R3: every observation the adapter emits validates against both layers."""

    def test_every_decision_emits_a_valid_observation(self):
        from joint_interception.domain.contracts import validate_observation

        adapter = make_adapter()
        for _ in range(12):
            validate_observation(adapter.observe())
            adapter.decide_and_step(always_first)

    def test_observation_exposes_no_prohibited_key(self):
        from joint_interception.domain.contracts import load_domain, observation_invariants

        adapter = make_adapter()
        observation = adapter.observe()
        self.assertEqual(observation_invariants(observation), [])
        prohibited = set(load_domain()["observation"]["prohibited_observation_keys"])
        self.assertEqual(set(observation) & prohibited, set())
        for vehicle in observation["vehicles"]:
            self.assertEqual(set(vehicle) & prohibited, set())

    def test_clock_stays_synchronised_with_the_decision_index(self):
        adapter = make_adapter()
        for expected in range(6):
            observation = adapter.observe()
            self.assertEqual(observation["decision_index"], expected)
            self.assertAlmostEqual(observation["simulation_time_s"], float(expected))
            adapter.decide_and_step(always_first)

    def test_selector_receives_no_backend_handle(self):
        """The selector must not be able to reach around the observation."""
        seen = {}

        def probe(observation, vehicle_id, actions):
            seen["observation_keys"] = set(observation)
            seen["action_keys"] = set(actions[0])
            return 0

        make_adapter().decide_and_step(probe)
        self.assertNotIn("backend", seen["observation_keys"])
        self.assertEqual(
            seen["observation_keys"],
            {
                "contract_version",
                "simulation_time_s",
                "decision_index",
                "topology_version",
                "vehicles",
                "signals",
            },
        )


@requires_contracts
class TestMasksAndFallback(unittest.TestCase):
    """R4: an inadmissible action is never selectable; the fallback always exists."""

    def test_hold_lane_is_always_valid(self):
        adapter = make_adapter()
        mask = {a["action_id"]: a["valid"] for a in adapter.action_mask("p1")}
        self.assertTrue(mask["HOLD_LANE"])

    def test_crowded_state_invalidates_cruise_with_a_reason(self):
        """A neighbour within one decision interval must refuse the speed-increasing action."""
        adapter = make_adapter(gap_m=6.0)
        actions = {a["action_id"]: a for a in adapter.action_mask("p1")}
        self.assertFalse(actions["CRUISE"]["valid"])
        self.assertEqual(
            actions["CRUISE"]["invalid_reason"], "neighbour_within_one_decision_interval"
        )
        self.assertTrue(actions["HOLD_LANE"]["valid"])

    def test_selector_returning_nothing_uses_the_fallback(self):
        adapter = make_adapter()
        records = adapter.decide_and_step(always_none)
        self.assertEqual(records[0].executed_action_id, "HOLD_LANE")
        self.assertEqual(records[0].selection_label, "FALLBACK")

    def test_out_of_range_index_uses_the_fallback_not_a_crash(self):
        adapter = make_adapter()
        records = adapter.decide_and_step(lambda o, v, a: 99)
        self.assertEqual(records[0].executed_action_id, "HOLD_LANE")
        self.assertEqual(records[0].selection_label, "FALLBACK")

    def test_only_pursuers_are_commanded(self):
        adapter = make_adapter()
        records = adapter.decide_and_step(always_first)
        self.assertEqual({r.vehicle_id for r in records}, {"p1"})


@requires_contracts
class TestDeadline(unittest.TestCase):
    """R5: a late action is an action taken on a stale world, so it is not applied."""

    def test_deadline_miss_records_and_falls_back(self):
        adapter = make_adapter({"action_menu.inference_deadline_s": 0.0})
        records = adapter.decide_and_step(always_first)
        self.assertTrue(records[0].deadline_miss)
        self.assertEqual(records[0].executed_action_id, "HOLD_LANE")
        self.assertEqual(records[0].selection_label, "DEADLINE_FALLBACK")

    def test_within_deadline_the_selection_is_honoured(self):
        adapter = make_adapter({"action_menu.inference_deadline_s": 10.0})
        records = adapter.decide_and_step(always_first)
        self.assertFalse(records[0].deadline_miss)
        self.assertEqual(records[0].selection_label, "SELECTED")


@requires_contracts
class TestProposedVersusExecuted(unittest.TestCase):
    """R6: a guard may change the command without changing the intention."""

    def test_clamped_command_records_both(self):
        adapter = make_adapter({"action_menu.inference_deadline_s": 10.0})
        # Request a CRUISE fraction of a speed limit below what the action asks for.
        records = adapter.decide_and_step(
            lambda o, v, a: next(
                i for i, x in enumerate([y for y in a if y["valid"]]) if x["action_id"] == "CRUISE"
            ),
            speed_limit_mps=5.0,
        )
        record = records[0]
        self.assertEqual(record.proposed_action_id, "CRUISE")
        self.assertEqual(record.executed_action_id, "CRUISE")
        self.assertLessEqual(record.executed_command.target_speed_mps, 5.0)

    def test_two_intentions_can_produce_the_same_executed_command(self):
        """Finite assistance case A4, at the adapter layer."""
        from joint_interception.simulator.backend import Command

        first = Command("p1", 5.0, clamped_from=13.89)
        second = Command("p1", 5.0, clamped_from=8.0)
        self.assertEqual(first.target_speed_mps, second.target_speed_mps)
        self.assertNotEqual(first.clamped_from, second.clamped_from)
        self.assertTrue(first.was_clamped and second.was_clamped)

    def test_proposed_and_executed_are_separate_fields(self):
        adapter = make_adapter({"action_menu.inference_deadline_s": 0.0})
        record = adapter.decide_and_step(always_first)[0]
        self.assertEqual(record.executed_action_id, "HOLD_LANE")
        self.assertIn("proposed_action_id", vars(record))


def inspect_source(function) -> str:
    import inspect

    return inspect.getsource(function)


@requires_contracts
class TestNoSumoProcessStartsByAccident(unittest.TestCase):
    """Replaces the W3 guard `TestNoSumoProcessIsStarted`, which correctly fired at W4.

    At W3 the invariant was "a SUMO process cannot be started at all", enforced by making
    `TraciBackend.__init__` raise. W4 implemented and exercised it
    (`experiments/20260922_w04_traci_first_execution_r01`), so that assertion had to go.

    **The invariant did not go with it.** What must still hold is narrower and now more
    important, because starting a process is possible: importing the module must not start
    one, must not import TraCI, and constructing a backend must require every argument that
    determines the run to be stated explicitly. A process that starts because a default
    filled itself in is a process nobody decided to start.
    """

    def test_importing_the_module_does_not_import_traci(self):
        """Import-time cost and import-time side effects, checked at runtime not by AST.

        `TraciBackend.__init__` imports `traci` deliberately, so a static scan of this file
        now finds the name and cannot answer the question. What matters is whether importing
        the adapter *pulls TraCI in*, which is a fact about `sys.modules`.
        """
        source = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys;"
                    "import joint_interception.simulator.sumo_adapter as m;"
                    "print('traci' in sys.modules, 'libsumo' in sys.modules)"
                ),
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": SRC},
        )
        self.assertEqual(source.returncode, 0, source.stderr)
        self.assertEqual(source.stdout.strip(), "False False", source.stdout)

    def test_the_traci_import_is_inside_a_function_not_at_module_level(self):
        import ast

        import joint_interception.simulator.sumo_adapter as adapter

        with open(adapter.__file__, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=adapter.__file__)
        module_level = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                module_level |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                module_level.add(node.module.split(".")[0])
        self.assertNotIn("traci", module_level)
        self.assertNotIn("libsumo", module_level)

    def test_constructing_a_backend_requires_every_run_defining_argument(self):
        """No default may supply a seed, a step length, a network or a binary.

        Each of these determines what the run *is*. A default here would let a process start
        under parameters nobody chose, and the resource ledger would record a run whose
        configuration was never decided.
        """
        import inspect

        from joint_interception.simulator.sumo_adapter import TraciBackend

        signature = inspect.signature(TraciBackend.__init__)
        for name in ("net_file", "seed", "step_s", "sumo_binary"):
            self.assertIs(
                signature.parameters[name].default,
                inspect.Parameter.empty,
                f"{name} must not have a default: it determines what the run is",
            )

    def test_status_records_that_execution_has_happened(self):
        from joint_interception.simulator.sumo_adapter import TraciBackend

        self.assertEqual(
            TraciBackend.IMPLEMENTATION_STATUS,
            "IMPLEMENTED_W4_FIRST_EXECUTED_2026_09_22",
        )

    def test_per_instance_state_is_not_shared_between_backends(self):
        """`_classes` and `_state_path` were written as CLASS-level mutable attributes.

        Every backend in a process would have shared them. That is exactly the silent
        cross-run coupling the assistance audit must not have, and it was caught by reading
        the code rather than by any test (package `20260922_w04_traci_first_execution_r01`,
        deviation D-4). This is that test.
        """
        from joint_interception.simulator.sumo_adapter import TraciBackend

        for name in ("_classes", "_state_path"):
            self.assertFalse(
                hasattr(TraciBackend, name),
                f"{name} is a class attribute and would be shared by every instance",
            )
        source = inspect_source(TraciBackend.__init__)
        self.assertIn("self._classes", source)
        self.assertIn("self._state_path", source)


if __name__ == "__main__":
    unittest.main()
