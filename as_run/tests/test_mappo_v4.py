"""A-139: the corrected training loop (transition contract, capture instant, ledger)."""

from __future__ import annotations

import json
import math
import os
import random
import sys
import tempfile
import unittest
from types import SimpleNamespace

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "src"))

from _w2_support import requires_contracts  # noqa: E402


def _frame(t, hold=True, missing=(), evader_speed=0.0, far=False):
    """Evader at the origin; p1 6 m ahead in file (body gap 1.0 m), or 100 m ahead if `far`."""
    from joint_interception.evaluation.capture_judge import TraceFrame, VehicleFrame

    vehicles = {
        "e1": VehicleFrame("e1", 0.0, 0.0, 0.0, evader_speed, 5.0, 1.8),
        "p1": VehicleFrame("p1", 100.0 if far else 6.0, 0.0, 0.0, 0.0 if hold else 2.0, 5.0, 1.8),
    }
    for vid in missing:
        vehicles.pop(vid, None)
    return TraceFrame(round(t, 1), vehicles)


def _ticks(times):
    return [
        {
            "t": float(t),
            "global": np.full(7, t / 300.0, dtype=np.float32),
            "global_post": np.zeros(7, dtype=np.float32),
            "agents": [{"vid": "p1"}],
        }
        for t in times
    ]


def _episode(frames, captured, collisions=(), ticks=None, exited=False):
    return SimpleNamespace(
        trace=frames,
        contact_capture=captured,
        collided=bool(collisions),
        collision_events=[{"t": t, "vehicles": ["p1", "x"]} for t in collisions],
        mappo_ticks=_ticks(range(0, 301, 3)) if ticks is None else ticks,
        end_s=frames[-1].time_s,
        evader_exited=exited,
    )


FULL = range(3001)


@requires_contracts
class TestMeasure(unittest.TestCase):
    def setUp(self):
        import train_mappo_v4 as v4

        self.v4 = v4

    def measure(self, ep, reward="oc", keep=True):
        return self.v4.measure(ep, reward, keep, 1)

    def test_capture_exactly_on_a_decision_tick(self):
        """The predicate holds from 1.0 s, so the dwell completes at 3.0 s, on the second tick."""
        ep = _episode([_frame(i / 10, hold=i >= 10) for i in FULL], True)
        row = self.measure(ep)
        self.assertEqual(row["capture_s"], 3.0)
        self.assertEqual([t["t"] for t in row["ticks"]], [0.0])
        self.assertEqual(len(row["rewards"]), 1)
        self.assertAlmostEqual(row["rewards"][0], 0.995)
        self.assertEqual(row["transitions"], 1)
        self.assertEqual(row["terminal_observation_ticks"], 100)
        self.assertEqual(row["end_reason"], "event")
        self.assertNotIn("global_post", row["ticks"][0])
        # what the earlier contract did with this episode
        self.assertEqual(row["legacy"]["ticks"], 2)
        self.assertEqual(row["legacy"]["trained_decisions_without_future"], 1)
        self.assertTrue(row["legacy"]["capture_on_a_tick"])

    def test_capture_between_ticks(self):
        """Holds from 2.0 s: capture at 4.0 s, during the interval of the decision at 3.0 s."""
        ep = _episode([_frame(i / 10, hold=i >= 20) for i in FULL], True)
        row = self.measure(ep)
        self.assertEqual(row["capture_s"], 4.0)
        self.assertEqual([t["t"] for t in row["ticks"]], [0.0, 3.0])
        self.assertAlmostEqual(row["rewards"][0], -0.005)
        self.assertAlmostEqual(row["rewards"][1], 1.0 - 0.005 / 3.0)
        self.assertEqual(row["legacy"]["trained_decisions_without_future"], 0)
        self.assertFalse(row["legacy"]["capture_on_a_tick"])

    def test_horizon_without_capture(self):
        ep = _episode([_frame(i / 10, hold=False) for i in FULL], False)
        row = self.measure(ep)
        self.assertFalse(row["success"])
        self.assertEqual(row["end_reason"], "horizon")
        self.assertEqual(row["transitions"], 100)
        self.assertEqual(row["ticks"][-1]["t"], 297.0)
        self.assertEqual(row["terminal_observation_ticks"], 1)
        self.assertAlmostEqual(row["reward_sum"], -0.5)
        self.assertEqual(row["legacy"]["ticks"], 101)
        self.assertEqual(row["legacy"]["trained_decisions_without_future"], 1)

    def test_evader_exit_ends_the_interval(self):
        frames = [_frame(i / 10, hold=False) for i in range(75)]
        frames[-1] = _frame(7.4, hold=False, missing=("e1",))
        ep = _episode(frames, False, ticks=_ticks([0, 3, 6]), exited=True)
        row = self.measure(ep)
        self.assertEqual(row["end_reason"], "evader_exit")
        self.assertEqual(row["transitions"], 3)
        self.assertAlmostEqual(row["rewards"][-1], -0.005 * 1.4 / 3.0)
        self.assertEqual(row["absent_frames"], {"e1": 1})
        self.assertEqual(row["inner_gap_frames"], 0)

    def test_collision_after_the_capture_is_not_penalised(self):
        frames = [_frame(i / 10, hold=i >= 10) for i in FULL]
        clean = self.measure(_episode(frames, True))
        late = self.measure(_episode(frames, True, collisions=[10.0, 10.1]))
        self.assertEqual(late["rewards"], clean["rewards"])
        self.assertTrue(late["collided"])
        self.assertFalse(late["collision_in_interval"])
        self.assertEqual(late["collisions_outside"], 2)
        self.assertEqual(late["collision_times"], [10.0, 10.1])
        self.assertTrue(late["legacy"]["penalised_a_collision_outside_the_interval"])
        self.assertFalse(clean["legacy"]["penalised_a_collision_outside_the_interval"])

    def test_collision_before_the_capture_is_penalised_where_it_happened(self):
        frames = [_frame(i / 10, hold=i >= 45) for i in FULL]  # capture at 6.5 s
        row = self.measure(_episode(frames, True, collisions=[2.0]))
        self.assertEqual(row["capture_s"], 6.5)
        self.assertAlmostEqual(row["rewards"][0], -0.005 - 1.0)
        self.assertAlmostEqual(row["rewards"][1], -0.005)
        self.assertAlmostEqual(row["rewards"][2], 1.0 - 0.005 * 0.5 / 3.0)
        self.assertTrue(row["collision_in_interval"])
        self.assertFalse(row["legacy"]["penalised_a_collision_outside_the_interval"])

    def test_proximity_already_present_at_the_first_decision(self):
        """Proximity reward with the body gap under 5 m from the first frame: a success with no
        trainable decision, excluded from the update and counted as such."""
        ep = _episode([_frame(i / 10, hold=False) for i in FULL], False)
        row = self.measure(ep, reward="prox")
        self.assertTrue(row["success"])
        self.assertEqual(row["proximity_s"], 0.0)
        self.assertEqual(row["ticks"], [])
        self.assertEqual(row["exclusion"], "ended_before_first_decision")
        self.assertFalse(self.v4.usable(row))
        self.assertEqual(row["legacy"]["ticks"], 1)  # the earlier contract trained this decision

    def test_proximity_reward_between_ticks(self):
        frames = [_frame(i / 10, hold=False, far=i < 44) for i in FULL]  # within 5 m from 4.4 s
        row = self.measure(_episode(frames, False), reward="prox")
        self.assertEqual(row["proximity_s"], 4.4)
        self.assertEqual([t["t"] for t in row["ticks"]], [0.0, 3.0])
        self.assertAlmostEqual(row["rewards"][1], 1.0 - 0.005 * 1.4 / 3.0)
        self.assertFalse(row["d06"])

    def test_an_absent_pursuer_does_not_bring_the_cut_forward(self):
        """F5-2 on the training path: the earlier helper would cut at 2.1 s, before any valid
        capture; the corrected instant is 4.1 s."""
        frames = [_frame(i / 10, missing=("p1",) if 1 <= i <= 20 else ()) for i in FULL]
        row = self.measure(_episode(frames, True))
        self.assertEqual(row["capture_s"], 4.1)
        self.assertEqual(row["legacy"]["capture_s"], 2.1)
        self.assertEqual([t["t"] for t in row["ticks"]], [0.0, 3.0])
        self.assertEqual(row["inner_gap_frames"], 20)

    def test_an_invalid_trace_is_excluded_as_unresolved(self):
        frames = [_frame(i / 10, evader_speed=float("nan") if i == 5 else 0.0) for i in range(60)]
        row = self.measure(_episode(frames, False, ticks=_ticks([0, 3])))
        self.assertTrue(row["failed"].startswith("invalid_trace"))
        self.assertNotIn("ticks", row)

    def test_a_disagreement_between_judge_and_extractor_is_excluded(self):
        frames = [_frame(i / 10, hold=i >= 10) for i in range(100)]
        row = self.measure(_episode(frames, False, ticks=_ticks([0, 3, 6, 9])))
        self.assertEqual(row["failed"], "judge_and_extractor_disagree")

    def test_without_keep_no_tensor_is_returned(self):
        ep = _episode([_frame(i / 10, hold=i >= 10) for i in FULL], True)
        row = self.measure(ep, keep=False)
        self.assertNotIn("ticks", row)
        self.assertEqual(row["transitions"], 1)


@requires_contracts
class TestLedger(unittest.TestCase):
    def setUp(self):
        import train_mappo_v4 as v4

        self.v4 = v4
        captured = _episode([_frame(i / 10, hold=i >= 20) for i in FULL], True)
        horizon = _episode([_frame(i / 10, hold=False) for i in FULL], False)
        late = _episode([_frame(i / 10, hold=i >= 10) for i in FULL], True, collisions=[50.0])
        nothing = _episode([_frame(i / 10, hold=False) for i in FULL], False)
        self.eps = [
            {"key": "a", **v4.measure(captured, "oc", True, 1)},
            {"key": "b", **v4.measure(horizon, "oc", True, 1)},
            {"key": "c", **v4.measure(late, "oc", True, 1)},
            {"key": "d", **v4.measure(nothing, "prox", True, 1)},
            {"key": "e", "failed": "ValueError: scenario could not place the team"},
        ]

    def test_batch_counts_are_the_denominators_of_an_update(self):
        c = self.v4.batch_counts(self.eps)
        self.assertEqual((c["attempted"], c["failed"], c["valid"], c["used"]), (5, 1, 4, 3))
        self.assertEqual(c["excluded"], {"ended_before_first_decision": 1})
        self.assertEqual(c["transitions"], 2 + 100 + 1)
        self.assertEqual(c["agent_decisions"], 103)
        self.assertEqual(c["end_reasons"], {"event": 3, "horizon": 1})
        self.assertEqual((c["collided"], c["collision_in_interval"]), (1, 0))
        self.assertEqual(c["legacy_penalised_collision_outside"], 1)
        self.assertEqual(c["legacy_capture_on_a_tick"], 1)
        # b (horizon tick), c (capture on a tick) and d (proximity at the first decision)
        self.assertEqual(c["legacy_episodes_with_such_a_decision"], 3)
        self.assertEqual(c["legacy_capture_instant_differs"], 0)
        self.assertEqual(self.v4.rate(self.eps), (3, 4))
        self.assertEqual(self.v4.rate(self.eps, "d06"), (2, 4))

    def test_ledger_rows_carry_no_tensor_and_say_what_was_used(self):
        rows = self.v4.ledger_rows(self.eps, run="W_mlp_s1", phase="train", iteration=3)
        self.assertEqual([r["included"] for r in rows], [True, True, True, False, False])
        self.assertEqual([r["status"] for r in rows], ["ok"] * 4 + ["failed"])
        for r in rows:
            self.assertNotIn("ticks", r)
            self.assertNotIn("rewards", r)
            self.assertEqual((r["run"], r["phase"], r["iteration"]), ("W_mlp_s1", "train", 3))
            json.dumps(r)  # serialisable
        self.assertNotIn("included", self.v4.ledger_rows(self.eps, training=False)[0])

    def test_ledger_summary_counts_a_repeated_batch_once(self):
        rows = self.v4.ledger_rows(self.eps, run="F_mlp_s1", phase="train", iteration=1)
        with tempfile.TemporaryDirectory() as package:
            with open(os.path.join(package, "train_ledger.jsonl"), "w", encoding="utf-8") as h:
                for r in rows + rows:  # the batch written twice, as after an interrupted chunk
                    h.write(json.dumps(r) + "\n")
            out = self.v4.ledger_summary(package)["F_mlp_s1|train"]
        self.assertEqual((out["attempted"], out["failed"], out["valid"], out["used"]), (5, 1, 4, 3))
        self.assertEqual(out["failure_reasons"], {"ValueError": 1})
        self.assertEqual(out["excluded"], {"ended_before_first_decision": 1})
        self.assertEqual(out["transitions_used"], 103)
        self.assertEqual(out["collision_only_outside"], 1)
        self.assertEqual(out["collision_inside_the_trained_interval"], 0)
        self.assertEqual(out["legacy"]["episodes_penalised_for_a_collision_outside"], 1)
        self.assertEqual(out["legacy"]["captures_on_a_decision_tick"], 1)


class TestUpdate(unittest.TestCase):
    def setUp(self):
        import train_mappo_v2 as v2
        import train_mappo_v4 as v4

        self.v2, self.v4 = v2, v4

    def _episodes(self, model, seed=0, n=6, steps=5):
        import torch

        rng = np.random.default_rng(seed)
        eps = []
        for e in range(n):
            ticks = []
            for t in range(steps):
                agents = []
                for _ in range(3):
                    toks = rng.normal(size=(5, 12)).astype(np.float32)
                    ctx = rng.normal(size=7).astype(np.float32)
                    with torch.no_grad():
                        lg = model.logits(torch.from_numpy(toks), torch.from_numpy(ctx))
                    dist = torch.distributions.Categorical(logits=lg)
                    idx = int(rng.integers(0, 5))
                    agents.append(
                        {
                            "tokens": toks,
                            "ctx": ctx,
                            "idx": idx,
                            "logp": float(dist.log_prob(torch.tensor(idx))),
                        }
                    )
                ticks.append(
                    {
                        "global": rng.normal(size=7).astype(np.float32),
                        "agents": agents,
                        "t": 3.0 * t,
                    }
                )
            success = e % 2 == 0
            eps.append(
                {
                    "ticks": ticks,
                    "success": success,
                    "collided": False,
                    "rewards": self.v2.episode_rewards(len(ticks), success, False),
                }
            )
        return eps

    def test_same_rewards_give_the_update_of_the_earlier_code(self):
        """The corrected loop changes which decisions are trained and their rewards, not PPO:
        fed the rewards of the earlier contract, it reproduces the earlier update exactly."""
        import torch

        from joint_interception.rl.mappo_policy import MappoActorCritic

        for head in ("mlp", "kan"):
            torch.manual_seed(0)
            a = MappoActorCritic(head)
            b = MappoActorCritic(head)
            b.load_state_dict(a.state_dict())
            eps = self._episodes(a)
            opt_a = torch.optim.Adam(a.parameters(), lr=1e-3)
            opt_b = torch.optim.Adam(b.parameters(), lr=1e-3)
            old = self.v2.mappo_update(a, opt_a, eps, random.Random(1))
            new = self.v4.mappo_update(b, opt_b, eps, random.Random(1))
            for x, y in zip(a.parameters(), b.parameters(), strict=True):
                self.assertTrue(torch.equal(x, y), head)
            self.assertTrue(all(math.isfinite(v) for v in new.values()))
            self.assertEqual(new["minibatches"], 4)  # 4 epochs, one minibatch each
            self.assertNotEqual(new["value_loss"], old["value_loss"])  # mean, not the last one

    def test_rewards_change_the_update(self):
        import torch

        from joint_interception.rl.mappo_policy import MappoActorCritic

        torch.manual_seed(0)
        a = MappoActorCritic("mlp")
        b = MappoActorCritic("mlp")
        b.load_state_dict(a.state_dict())
        eps = self._episodes(a)
        moved = [
            dict(e, rewards=[r - 1.0 * (k == 0) for k, r in enumerate(e["rewards"])]) for e in eps
        ]
        self.v4.mappo_update(a, torch.optim.Adam(a.parameters(), lr=1e-3), eps, random.Random(1))
        self.v4.mappo_update(b, torch.optim.Adam(b.parameters(), lr=1e-3), moved, random.Random(1))
        self.assertFalse(
            all(torch.equal(x, y) for x, y in zip(a.parameters(), b.parameters(), strict=True))
        )

    def test_episodes_without_a_trainable_decision_are_skipped(self):
        import torch

        from joint_interception.rl.mappo_policy import MappoActorCritic

        torch.manual_seed(0)
        model = MappoActorCritic("mlp")
        before = [p.detach().clone() for p in model.parameters()]
        opt = torch.optim.Adam(model.parameters(), lr=1e-3)
        eps = [{"ticks": [], "rewards": []}, {"key": "x", "failed": "ValueError"}]
        self.assertEqual(
            self.v4.mappo_update(model, opt, eps, random.Random(1)), {"minibatches": 0}
        )
        for x, y in zip(before, model.parameters(), strict=True):
            self.assertTrue(torch.equal(x, y))

    def test_critic_warm_up_leaves_the_actor_untouched(self):
        import torch

        from joint_interception.rl.mappo_policy import MappoActorCritic

        torch.manual_seed(0)
        model = MappoActorCritic("mlp")
        critic_ids = {id(p) for p in model.critic.parameters()}
        before = [(id(p) in critic_ids, p.detach().clone()) for p in model.parameters()]
        stats = self.v4.critic_fit(model, self._episodes(model), random.Random(2))
        self.assertEqual(stats["transitions"], 30)
        self.assertTrue(math.isfinite(stats["value_loss_mean"]))
        for (is_critic, old), new in zip(before, model.parameters(), strict=True):
            if not is_critic:
                self.assertTrue(torch.equal(old, new))
        self.assertTrue(
            any(
                c and not torch.equal(o, n)
                for (c, o), n in zip(before, model.parameters(), strict=True)
            )
        )


class TestDesign(unittest.TestCase):
    def setUp(self):
        import train_mappo_v3 as v3
        import train_mappo_v4 as v4

        self.v3, self.v4 = v3, v4

    def test_training_batches_are_the_scenarios_and_seeds_of_v3(self):
        for name in self.v4.ORDER:
            for warm in (False, True):
                old = self.v3.train_tasks(name, b"w", 64, 64, warm)
                new = self.v4.train_tasks(name, b"w", 64, 64, self.v4.SALTS, warm)
                self.assertEqual(old, new, name)

    def test_validation_is_that_of_v3_and_the_test_scenarios_are_new(self):
        old = self.v3.val_tasks("mlp", b"w", "v|x|0", "oc")
        new = self.v4.val_tasks("mlp", b"w", "v|x|0", "oc", self.v4.SALTS)
        self.assertEqual(old, new)
        pols = [("pursuit", "pursuit", None, None)]
        a, b = self.v3.test_tasks(pols), self.v4.test_tasks(pols, self.v4.SALTS)
        self.assertEqual(len(a), len(b))
        self.assertEqual(len(b), 7 * 20 * 2 * 2 * 3)  # 1,680 scheduled episodes per policy
        self.assertEqual({t[4] for t in a}, {"PE23"})
        self.assertEqual({t[4] for t in b}, {"PE24"})
        self.assertEqual([t[:4] + t[5:] for t in a], [t[:4] + t[5:] for t in b])

    def test_a_smoke_run_touches_no_registered_scenario(self):
        registered = set(self.v4.SALTS.values()) | {"PE23", "PV23", "PT23", "PE19", "PE17", "PE11"}
        self.assertFalse(registered & set(self.v4.SMOKE_SALTS.values()))
        for name in self.v4.ORDER:
            for t in self.v4.train_tasks(name, b"w", 0, 4, self.v4.SMOKE_SALTS):
                self.assertTrue(t[4].startswith("SMT24"))

    def test_budgets_are_those_of_v3(self):
        self.assertEqual(self.v4.CFG, self.v3.CFG)
        for arm in ("F", "W", "P"):
            self.assertEqual(self.v4.limits(arm), self.v3.limits(arm))
        self.assertEqual(
            (self.v4.WARM_ITERS, self.v4.WARM_EPOCHS, self.v4.WARM_LR),
            (self.v3.WARM_ITERS, self.v3.WARM_EPOCHS, self.v3.WARM_LR),
        )


if __name__ == "__main__":
    unittest.main()
