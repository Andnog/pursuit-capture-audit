"""A-133: the corrected MAPPO controller (critic input, sampling seed, sequential actor)."""

from __future__ import annotations

import os
import random
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "src"))

SLOT = {
    "edge": "exit",
    "lane": 0,
    "k": 0,
    "rank": 0,
    "t_ev": 20.0,
    "junction_lanes": 1,
    "n_exits": 1,
    "junction": "j",
}


def fixed_ctx(t=0.0):
    positions = {"e1": (0.0, 0.0), "p1": (10.0, 0.0), "p2": (20.0, 0.0)}
    return {
        "t": t,
        "per": {"p1": None, "p2": None},
        "states": {"e1": ("road", 0, 0, 1.0), "p1": ("a", 0, 0, 1.0), "p2": ("b", 0, 0, 1.0)},
        "e_pos": ("road", 0.0),
        "p_pos": {},
        "net": SimpleNamespace(edges={"exit": SimpleNamespace(length_m=100.0)}),
        "conn": SimpleNamespace(vehicle=SimpleNamespace(getPosition=lambda v: positions[v])),
    }


def controller(cls):
    class Fixed(cls):
        def _predict(self, ctx):
            return []

        def _slots(self, ctx, path):
            return [dict(SLOT)]

        def _slack(self, ctx, v, sl):
            return 10.0

    return Fixed({}, model=object(), mode="sample", seed=17)


def run_ticks(cls, choices, times=(0.0,)):
    """Drive the controller with forced choices; returns its recorded ticks."""
    ctrl, it = controller(cls), iter(choices)
    name = "act_seeded" if cls.__name__.endswith("V3") else "act"
    with patch(
        f"joint_interception.rl.mappo_policy.{name}", side_effect=lambda *a, **k: (next(it), 0.0)
    ):
        for t in times:
            ctrl(fixed_ctx(t))
    return ctrl.ticks


class TestCriticInput(unittest.TestCase):
    def setUp(self):
        from joint_interception.native.mappo_ambush_v2 import MappoAmbushV2
        from joint_interception.native.mappo_ambush_v3 import MappoAmbushV3

        self.v2, self.v3 = MappoAmbushV2, MappoAmbushV3

    def test_v2_critic_input_depends_on_the_actions_of_the_step(self):
        """The defect (F4-1), kept as a regression record of the legacy controller."""
        chase = run_ticks(self.v2, [0, 0])[0]
        block = run_ticks(self.v2, [2, 0])[0]
        np.testing.assert_array_equal(chase["agents"][0]["tokens"], block["agents"][0]["tokens"])
        self.assertFalse(np.array_equal(chase["global"], block["global"]))

    def test_v3_critic_input_does_not_depend_on_the_actions_of_the_step(self):
        for a, b in (([0, 0], [2, 0]), ([0, 0], [2, 2]), ([0, 2], [2, 0]), ([1, 1], [2, 2])):
            x, y = run_ticks(self.v3, a)[0], run_ticks(self.v3, b)[0]
            np.testing.assert_array_equal(x["global"], y["global"])
            np.testing.assert_array_equal(x["agents"][0]["tokens"], y["agents"][0]["tokens"])

    def test_v3_post_vector_is_kept_for_diagnostics_only(self):
        chase = run_ticks(self.v3, [0, 0])[0]
        block = run_ticks(self.v3, [2, 0])[0]
        self.assertFalse(np.array_equal(chase["global_post"], block["global_post"]))
        np.testing.assert_array_equal(block["global_post"], run_ticks(self.v2, [2, 0])[0]["global"])

    def test_v3_next_state_reflects_the_previous_actions(self):
        """(state, action, reward, next state): what step t chose is in the state of step t+1."""
        ticks = run_ticks(self.v3, [2, 0, 1, 1], times=(0.0, 3.0))
        self.assertEqual(float(ticks[0]["global"][3]), 0.0)
        self.assertEqual(float(ticks[1]["global"][3]), 1.0)
        chased = run_ticks(self.v3, [0, 0, 1, 1], times=(0.0, 3.0))
        self.assertEqual(float(chased[1]["global"][3]), 0.0)

    def test_gae_baseline_is_equal_for_two_actions_from_the_same_state(self):
        import torch

        import train_mappo_v2 as v2
        from joint_interception.rl.mappo_policy import MappoActorCritic

        torch.manual_seed(3)
        model = MappoActorCritic("mlp")
        values = []
        for choices in ([0, 0], [2, 0]):
            tick = run_ticks(self.v3, choices)[0]
            with torch.no_grad():
                values.append(float(model.value(torch.from_numpy(tick["global"][None]))[0]))
        self.assertEqual(values[0], values[1])
        adv = [v2.compute_gae([0.0], [v])[0] for v in values]
        self.assertEqual(adv[0], adv[1])

    def test_actor_is_sequential_within_a_step(self):
        """Documented behaviour (F4-5): the second agent sees the first agent's choice."""
        chase = run_ticks(self.v3, [0, 0])[0]
        block = run_ticks(self.v3, [2, 0])[0]
        self.assertEqual(float(chase["agents"][1]["tokens"][2, 7]), 0.0)
        self.assertEqual(float(block["agents"][1]["tokens"][2, 7]), 1.0)


class TestSeededSampling(unittest.TestCase):
    def setUp(self):
        import torch

        from joint_interception.rl.mappo_policy import MappoActorCritic, act, act_seeded

        self.torch, self.act, self.act_seeded = torch, act, act_seeded
        torch.manual_seed(0)
        self.model = MappoActorCritic("mlp")
        rng = np.random.default_rng(5)
        self.tokens = rng.normal(size=(5, 12)).astype(np.float32)
        self.ctx = rng.normal(size=7).astype(np.float32)

    def _sequence(self, fn, torch_seed, supplied_seed, n=64):
        self.torch.manual_seed(torch_seed)
        rng = random.Random(supplied_seed)
        return [fn(self.model, self.tokens, self.ctx, "sample", rng)[0] for _ in range(n)]

    def test_legacy_sampler_ignores_the_supplied_seed(self):
        """The defect (F4-2), kept as a regression record of `act`."""
        self.assertEqual(self._sequence(self.act, 11, 17), self._sequence(self.act, 11, 999))
        self.assertNotEqual(self._sequence(self.act, 11, 17), self._sequence(self.act, 12, 17))

    def test_seeded_sampler_depends_only_on_the_supplied_seed(self):
        a = self._sequence(self.act_seeded, 11, 17)
        self.assertEqual(a, self._sequence(self.act_seeded, 12, 17))
        self.assertNotEqual(a, self._sequence(self.act_seeded, 11, 999))

    def test_seeded_sampler_does_not_consume_the_global_generator(self):
        self.torch.manual_seed(4)
        before = self.torch.get_rng_state().clone()
        rng = random.Random(1)
        for _ in range(20):
            self.act_seeded(self.model, self.tokens, self.ctx, "sample", rng)
        self.assertTrue(self.torch.equal(before, self.torch.get_rng_state()))

    def test_log_probability_is_that_of_the_returned_index(self):
        t, c = self.torch.from_numpy(self.tokens), self.torch.from_numpy(self.ctx)
        with self.torch.no_grad():
            logp = self.torch.log_softmax(self.model.logits(t, c), dim=0)
        rng = random.Random(2)
        for _ in range(30):
            idx, lp = self.act_seeded(self.model, self.tokens, self.ctx, "sample", rng)
            self.assertAlmostEqual(lp, float(logp[idx]), places=6)
        idx, lp = self.act_seeded(self.model, self.tokens, self.ctx, "greedy", rng)
        self.assertEqual(idx, int(self.torch.argmax(logp)))
        idx, lp = self.act_seeded(self.model, self.tokens, self.ctx, "sample", rng, forced=3)
        self.assertEqual(idx, 3)
        self.assertAlmostEqual(lp, float(logp[3]), places=6)

    def test_sampling_frequencies_follow_the_policy(self):
        t, c = self.torch.from_numpy(self.tokens), self.torch.from_numpy(self.ctx)
        with self.torch.no_grad():
            probs = self.torch.softmax(self.model.logits(t, c), dim=0).tolist()
        rng, n = random.Random(8), 20000
        counts = [0] * len(probs)
        for _ in range(n):
            counts[self.act_seeded(self.model, self.tokens, self.ctx, "sample", rng)[0]] += 1
        for k, p in enumerate(probs):
            self.assertAlmostEqual(counts[k] / n, p, delta=4 * (p * (1 - p) / n) ** 0.5 + 1e-3)

    def test_controller_rollout_is_reproducible_from_its_seed(self):
        from joint_interception.native.mappo_ambush_v3 import MappoAmbushV3

        def rollout(torch_seed, seed):
            self.torch.manual_seed(torch_seed)

            class Fixed(MappoAmbushV3):
                def _predict(self, ctx):
                    return []

                def _slots(self, ctx, path):
                    return [dict(SLOT)]

                def _slack(self, ctx, v, sl):
                    return 10.0

            ctrl = Fixed({}, model=self.model, mode="sample", seed=seed)
            for k in range(40):
                ctrl(fixed_ctx(3.0 * k))
            return [a["idx"] for tick in ctrl.ticks for a in tick["agents"]]

        a = rollout(1, 123)
        self.assertEqual(len(a), 80)
        self.assertEqual(a, rollout(2, 123))
        self.assertNotEqual(a, rollout(1, 124))


class TestTrainingDesign(unittest.TestCase):
    def setUp(self):
        import train_mappo_v3 as t

        self.t = t

    def test_registered_runs_and_limits(self):
        self.assertEqual(len(self.t.ORDER), 8)
        self.assertEqual({self.t.parse(n)[0] for n in self.t.ORDER}, {"F", "W", "P"})
        self.assertEqual(self.t.limits("P"), (2048, 2048, 10**9))
        self.assertEqual(self.t.limits("F"), (4096, 1536, 4))
        self.assertEqual(self.t.limits("W"), self.t.limits("F"))
        self.assertEqual(self.t.REWARD, {"F": "oc", "W": "oc", "P": "prox"})

    def test_every_sampled_episode_has_its_own_seed(self):
        seeds = set()
        for name in self.t.ORDER:
            arm, head, seed = self.t.parse(name)
            for index in range(4096):
                seeds.add(self.t.sampling_seed(arm, head, seed, index))
            for index in range(256):
                seeds.add(self.t.sampling_seed(arm, head, seed, index, warm=True))
        self.assertEqual(len(seeds), 8 * (4096 + 256))

    def test_training_tasks_carry_reward_mode_and_distinct_keys(self):
        a = self.t.train_tasks("P_mlp_s2", b"w", 64, 64)
        b = self.t.train_tasks("W_mlp_s2", b"w", 64, 64)
        w = self.t.train_tasks("W_mlp_s2", b"w", 64, 64, warm=True)
        self.assertEqual({x[-1] for x in a}, {"prox"})
        self.assertEqual({x[-1] for x in b}, {"oc"})
        self.assertTrue(all(x[7] == "mappo_v3" and x[10] == "sample" and x[12] for x in a + b + w))
        keys = [x[0] for x in a + b + w]
        self.assertEqual(len(set(keys)), len(keys))
        self.assertTrue({x[11] for x in b}.isdisjoint({x[11] for x in w}))
        self.assertNotEqual({x[4] for x in b}, {x[4] for x in w})

    def test_returns_are_discounted_sums(self):
        got = self.t.returns([0.0, 0.0, 1.0], gamma=0.5)
        self.assertEqual(got, [0.25, 0.5, 1.0])
        self.assertEqual(self.t.returns([]), [])

    def test_critic_warmup_fits_the_critic_and_leaves_the_actor_untouched(self):
        import torch

        from joint_interception.rl.mappo_policy import MappoActorCritic

        torch.manual_seed(1)
        model = MappoActorCritic("mlp")
        actor_before = [p.clone() for p in model.actor.parameters()]
        rng = np.random.default_rng(0)
        eps = []
        for k in range(40):
            g = rng.normal(size=(5, 7)).astype(np.float32)
            g[:, 3] = k % 2  # the only feature that predicts success
            eps.append(
                {"ticks": [{"global": row} for row in g], "success": bool(k % 2), "collided": False}
            )
        eps.append({"failed": "x"})

        def mse():
            err = []
            for ep in eps[:-1]:
                ret = self.t.returns(self.t.v2.episode_rewards(5, ep["success"], False))
                x = torch.from_numpy(np.stack([t["global"] for t in ep["ticks"]]))
                with torch.no_grad():
                    err += ((model.value(x) - torch.tensor(ret)) ** 2).tolist()
            return sum(err) / len(err)

        before = mse()
        stats = self.t.critic_fit(model, eps, random.Random(3), epochs=60)
        self.assertEqual(stats["ticks"], 200)
        self.assertLess(mse(), 0.25 * before)
        for a, b in zip(actor_before, model.actor.parameters(), strict=True):
            self.assertTrue(torch.equal(a, b))

    def test_policies_do_not_duplicate_a_selected_start(self):
        st = {"starts": {f"{h}_s{s}": f"{h}{s}".encode() for h in ("mlp", "kan") for s in (1, 2)}}
        st["runs"] = {}
        for name in self.t.ORDER:
            _, head, seed = self.t.parse(name)
            st["runs"][name] = {
                "best_model": f"{head}{seed}".encode(),
                "model": b"final-" + name.encode(),
            }
        st["runs"]["W_mlp_s1"]["best_model"] = b"improved"
        pols, alias = self.t.policies(st)
        names = [p[0] for p in pols]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("sel_W_mlp_s1", names)
        self.assertNotIn("sel_W_mlp_s2", names)
        self.assertEqual(alias["sel_W_mlp_s2"], "start_mlp_s2")
        self.assertNotIn("sel_P_mlp_s1", alias)
        self.assertEqual(sum(n.startswith("final_") for n in names), 8)
        self.assertEqual(len(self.t.test_tasks(pols)), len(pols) * 7 * 20 * 2 * 2 * 3)

    def test_summary_primaries_on_synthetic_rows(self):
        st = {"runs": {n: {} for n in self.t.ORDER}}
        alias = {f"sel_{n}": f"start_{n[2:]}" for n in self.t.ORDER if not n.startswith("P")}
        del alias["sel_W_mlp_s1"]
        rows, rng = {}, random.Random(0)
        names = ["planner_c215", "pursuit", "sel_W_mlp_s1"]
        names += [f"start_{h}_s{s}" for h in ("mlp", "kan") for s in (1, 2)]
        names += [f"final_{n}" for n in self.t.ORDER]
        for m in ("a", "b", "c"):
            for i in range(6):
                for team in (3, 5):
                    for p in names:
                        d06 = rng.random() < (0.9 if p == "sel_W_mlp_s1" else 0.3)
                        if p.startswith("final_P"):
                            d06 = False
                        key = f"test|{p}|{m}|{i}|1|AVOIDANT|{team}"
                        rows[key] = {"d06": d06, "prox_5m": True, "prox_5m_centre": True}
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out = self.t.summarise(tmp, rows, st, alias)
        self.assertTrue(out["primary_1_W_selected_minus_start_oc"]["passes"])
        self.assertTrue(out["primary_2_gap_P_final_minus_start"]["passes"])
        self.assertEqual(out["rates"]["final_P_mlp"]["d06"], 0.0)
        self.assertEqual(out["secondary"]["d06:sel_F_mlp_minus_start"], [0.0, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
