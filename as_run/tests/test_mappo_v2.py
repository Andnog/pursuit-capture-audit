"""A-116: unit tests for the corrected MAPPO training design (scripts/train_mappo_v2.py)."""

from __future__ import annotations

import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "src"))


class TestMappoV2(unittest.TestCase):
    def setUp(self):
        import train_mappo_v2 as t

        self.t = t

    def test_sampler_covers_all_sixteen_pairs(self):
        pairs = {self.t.combo(k) for k in range(16)}
        self.assertEqual(len(pairs), 16)
        self.assertEqual(pairs, {self.t.combo(k) for k in range(16, 32)})

    def test_old_sampler_covered_only_four_pairs(self):
        old = {(self.t.TRAINING[k % 4], self.t.SETTINGS[k % 4]) for k in range(64)}
        self.assertEqual(len(old), 4)

    def test_truncation_keeps_ticks_up_to_capture(self):
        ticks = [{"t": float(x)} for x in (0, 3, 6, 9)]
        self.assertEqual([x["t"] for x in self.t.truncate_ticks(ticks, 6.0)], [0.0, 3.0, 6.0])
        self.assertEqual(len(self.t.truncate_ticks(ticks, None)), 4)

    def test_rewards_terminal_success_and_collision(self):
        r = self.t.episode_rewards(3, True, False, step_cost=0.1)
        self.assertAlmostEqual(r[-1], 0.9)
        self.assertAlmostEqual(r[0], -0.1)
        r = self.t.episode_rewards(2, False, True, step_cost=0.0)
        self.assertEqual(r, [0.0, -1.0])
        self.assertEqual(self.t.episode_rewards(0, True, False), [])

    def test_gae_matches_hand_computation(self):
        rewards, values, g, lam = [0.0, 1.0], [0.5, 0.25], 0.9, 0.5
        d1 = 1.0 + 0.0 - 0.25
        d0 = 0.0 + g * 0.25 - 0.5
        expect = [d0 + g * lam * d1, d1]
        got = self.t.compute_gae(rewards, values, gamma=g, lam=lam)
        for a, b in zip(got, expect, strict=True):
            self.assertAlmostEqual(a, b)

    def test_gae_with_lambda_one_is_return_minus_value(self):
        rewards, values = [-0.1, -0.1, 1.0], [0.2, 0.3, 0.4]
        got = self.t.compute_gae(rewards, values, gamma=1.0, lam=1.0)
        returns = [0.8, 0.9, 1.0]
        for a, ret, v in zip(got, returns, values, strict=True):
            self.assertAlmostEqual(a, ret - v)

    def test_surrogate_is_clipped(self):
        import torch

        one = torch.tensor(1.0)
        self.assertAlmostEqual(float(self.t.surrogate(one, torch.tensor(2.0))), 2.0)
        self.assertAlmostEqual(float(self.t.surrogate(torch.tensor(1.5), torch.tensor(1.0))), 1.2)
        self.assertAlmostEqual(float(self.t.surrogate(torch.tensor(0.5), torch.tensor(-1.0))), -0.8)

    def test_rng_state_round_trip(self):
        a = random.Random(3)
        a.random()
        state = a.getstate()
        x = [a.random() for _ in range(3)]
        b = random.Random(99)
        b.setstate(state)
        self.assertEqual(x, [b.random() for _ in range(3)])

    def test_family_bootstrap_mean_and_bounds(self):
        fam = {("a", 0, "R"): [0.1, 0.2], ("b", 1, "A"): [0.3]}
        m, lo, hi = self.t.family_bootstrap(fam, reps=200)
        self.assertAlmostEqual(m, 0.2, places=3)
        self.assertLessEqual(lo, m)
        self.assertGreaterEqual(hi, m)

    # -- A-119 (second review): full actor-critic update and resumption -----------------------
    def _episodes(self, model, n_eps=3, n_ticks=4, seed=0):
        import numpy as np
        import torch

        rng = np.random.default_rng(seed)
        eps = []
        for e in range(n_eps):
            ticks = []
            for t in range(n_ticks):
                agents = []
                for _ in range(2):
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
            eps.append({"ticks": ticks, "success": e % 2 == 0, "collided": False})
        return eps

    def test_full_update_changes_parameters_and_stays_finite(self):
        import math

        import torch

        from joint_interception.rl.mappo_policy import MappoActorCritic

        for head in ("mlp", "kan"):
            torch.manual_seed(0)
            model = MappoActorCritic(head)
            before = [p.detach().clone() for p in model.parameters()]
            opt = torch.optim.Adam(model.parameters(), lr=1e-3)
            stats = self.t.mappo_update(model, opt, self._episodes(model), random.Random(1))
            self.assertTrue(all(math.isfinite(v) for v in stats.values()), head)
            changed = any(
                not torch.equal(a, b) for a, b in zip(before, model.parameters(), strict=True)
            )
            self.assertTrue(changed, head)

    def test_update_is_identical_after_restoring_saved_state(self):
        import copy
        import io

        import torch

        from joint_interception.rl.mappo_policy import MappoActorCritic

        torch.manual_seed(0)
        model = MappoActorCritic("mlp")
        opt = torch.optim.Adam(model.parameters(), lr=1e-3)
        rng = random.Random(4)
        self.t.mappo_update(model, opt, self._episodes(model, seed=1), rng)
        # snapshot as the training loop saves it
        blob = self.t._bytes(model)
        opt_state = copy.deepcopy(opt.state_dict())  # the training loop pickles it immediately
        rng_state = rng.getstate()
        eps = self._episodes(model, seed=2)
        self.t.mappo_update(model, opt, eps, rng)
        reference = [p.detach().clone() for p in model.parameters()]
        restored = MappoActorCritic("mlp")
        restored.load_state_dict(torch.load(io.BytesIO(blob), weights_only=True))
        opt2 = torch.optim.Adam(restored.parameters(), lr=1e-3)
        opt2.load_state_dict(opt_state)
        rng2 = random.Random(0)
        rng2.setstate(rng_state)
        self.t.mappo_update(restored, opt2, eps, rng2)
        for a, b in zip(reference, restored.parameters(), strict=True):
            self.assertTrue(torch.allclose(a, b, atol=1e-7))


if __name__ == "__main__":
    unittest.main()
