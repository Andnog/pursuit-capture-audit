"""State restoration, and why a shared seed is not a shared noise realisation.

The assistance audit depends entirely on these properties. Its protocol requires pause and
resume to be validated against uninterrupted execution BEFORE any replay result is used.
"""

from __future__ import annotations

import unittest

from _w2_support import requires_contracts  # noqa: E402


def make_backend(seed: int = 12345):
    from joint_interception.simulator.backend import DeterministicBackend, VehicleState

    vehicles = [
        VehicleState("p1", "pursuer", 0.0, 0.0, 0.0, 3.0, "l1", 0.0, 5.0, 1.8),
        VehicleState("p2", "pursuer", -20.0, 0.0, 0.0, 3.0, "l1", 0.0, 5.0, 1.8),
        VehicleState("e1", "evader", 60.0, 0.0, 0.0, 3.0, "l1", 60.0, 5.0, 1.8),
    ]
    return DeterministicBackend.build(vehicles, seed=seed)


class TestDeterminism(unittest.TestCase):
    def test_same_seed_same_commands_reproduces_exactly(self):
        from joint_interception.policies.memory import CommitmentMemory
        from joint_interception.simulator import snapshot

        left, right = make_backend(), make_backend()
        left.step(50)
        right.step(50)
        self.assertEqual(
            snapshot.capture(left, CommitmentMemory(), 5).fingerprint(),
            snapshot.capture(right, CommitmentMemory(), 5).fingerprint(),
        )

    def test_draw_count_is_a_function_of_steps_and_vehicles(self):
        backend = make_backend()
        backend.step(10)
        self.assertEqual(backend.draws, 10 * 3)


class TestStateRestoration(unittest.TestCase):
    """R1: pause and resume must equal uninterrupted execution, exactly."""

    def _run(self, backend, steps, command_at=None):
        from joint_interception.simulator.backend import Command

        for i in range(steps):
            if command_at is not None and i == command_at:
                backend.queue_command(Command("p1", 8.0))
            backend.step(1)

    def test_pause_resume_equals_uninterrupted(self):
        from joint_interception.policies.memory import CommitmentMemory
        from joint_interception.simulator import snapshot

        uninterrupted = make_backend()
        self._run(uninterrupted, 60, command_at=10)
        expected = snapshot.capture(uninterrupted, CommitmentMemory(), 6)

        paused = make_backend()
        self._run(paused, 30, command_at=10)
        memory = CommitmentMemory(committed_opportunity_id="X", committed_at=1)
        taken = snapshot.capture(paused, memory, 3)

        resumed = make_backend()
        restored_memory, index = snapshot.restore(resumed, taken)
        self.assertEqual(restored_memory, memory)
        self.assertEqual(index, 3)
        self._run(resumed, 30)
        actual = snapshot.capture(resumed, CommitmentMemory(), 6)

        self.assertTrue(
            snapshot.states_identical(expected, actual),
            "\n".join(snapshot.first_difference(expected, actual)),
        )

    def test_pending_commands_survive_the_snapshot(self):
        """A snapshot that drops pending commands looks right and diverges next step."""
        from joint_interception.policies.memory import CommitmentMemory
        from joint_interception.simulator import snapshot
        from joint_interception.simulator.backend import Command

        backend = make_backend()
        backend.step(5)
        backend.queue_command(Command("p1", 9.0))
        taken = snapshot.capture(backend, CommitmentMemory(), 1)
        self.assertTrue(taken.pending_commands_present)
        self.assertIn("p1", taken.backend["pending_commands"])

        restored = make_backend()
        snapshot.restore(restored, taken)
        self.assertEqual(restored.pending_commands()["p1"].target_speed_mps, 9.0)

        backend.step(20)
        restored.step(20)
        self.assertTrue(
            snapshot.states_identical(
                snapshot.capture(backend, CommitmentMemory(), 3),
                snapshot.capture(restored, CommitmentMemory(), 3),
            )
        )

    def test_commitment_memory_round_trips(self):
        from joint_interception.opportunities.types import Verdict
        from joint_interception.policies.memory import CommitmentMemory
        from joint_interception.simulator import snapshot

        memory = CommitmentMemory(
            committed_opportunity_id="opp-7",
            committed_at=4,
            last_verdict=Verdict.SUPPORTED,
            consecutive_unknown=1,
            switch_count=2,
        )
        backend = make_backend()
        taken = snapshot.capture(backend, memory, 9)
        restored, index = snapshot.restore(make_backend(), taken)
        self.assertEqual(restored, memory)
        self.assertEqual(index, 9)

    def test_snapshot_version_mismatch_is_refused(self):
        from dataclasses import replace

        from joint_interception.policies.memory import CommitmentMemory
        from joint_interception.simulator import snapshot

        taken = snapshot.capture(make_backend(), CommitmentMemory(), 0)
        with self.assertRaises(ValueError):
            snapshot.restore(make_backend(), replace(taken, version="snapshot_v0"))

    def test_every_required_component_is_present(self):
        from joint_interception.policies.memory import CommitmentMemory
        from joint_interception.simulator import snapshot

        taken = snapshot.capture(make_backend(), CommitmentMemory(), 0)
        for component in snapshot.REQUIRED_COMPONENTS:
            self.assertIn(component, taken.as_record())


class TestSharedSeedIsNotSharedNoise(unittest.TestCase):
    """R2: the assistance protocol's claim, demonstrated rather than asserted."""

    def test_same_seed_diverges_once_the_draw_counts_differ(self):
        from joint_interception.simulator.backend import DeterministicBackend, VehicleState

        def build(vehicle_count: int):
            vehicles = [
                VehicleState(f"p{i}", "pursuer", -20.0 * i, 0.0, 0.0, 3.0, "l1", 0.0, 5.0, 1.8)
                for i in range(vehicle_count)
            ]
            return DeterministicBackend.build(vehicles, seed=999)

        two, three = build(2), build(3)
        two.step(10)
        three.step(10)
        # Identical seed, identical step count, different number of draws consumed.
        self.assertEqual(two.draws, 20)
        self.assertEqual(three.draws, 30)
        self.assertNotEqual(two.vehicle_state("p0").speed_mps, three.vehicle_state("p0").speed_mps)

    def test_a_single_different_command_separates_two_same_seed_runs(self):
        from joint_interception.policies.memory import CommitmentMemory
        from joint_interception.simulator import snapshot
        from joint_interception.simulator.backend import Command

        factual, counterfactual = make_backend(777), make_backend(777)
        factual.step(10)
        counterfactual.step(10)
        factual.queue_command(Command("p1", 10.0))
        counterfactual.queue_command(Command("p1", 2.0))
        factual.step(40)
        counterfactual.step(40)

        left = snapshot.capture(factual, CommitmentMemory(), 5)
        right = snapshot.capture(counterfactual, CommitmentMemory(), 5)
        self.assertFalse(snapshot.states_identical(left, right))
        # The seed alone does not couple them: an exact counterfactual needs the verified
        # prefix restoration above, not a shared seed.
        self.assertTrue(snapshot.first_difference(left, right))


@requires_contracts
class TestCoupledReplayFromAVerifiedPrefix(unittest.TestCase):
    """What a valid assistance replay actually requires."""

    def test_restored_prefix_plus_identical_commands_reproduces_the_factual_run(self):
        from joint_interception.policies.memory import CommitmentMemory
        from joint_interception.simulator import snapshot
        from joint_interception.simulator.backend import Command

        factual = make_backend(4242)
        factual.step(20)
        prefix = snapshot.capture(factual, CommitmentMemory(), 2)
        factual.queue_command(Command("p2", 6.0))
        factual.step(30)
        factual_end = snapshot.capture(factual, CommitmentMemory(), 5)

        replay = make_backend(4242)
        snapshot.restore(replay, prefix)
        replay.queue_command(Command("p2", 6.0))
        replay.step(30)
        replay_end = snapshot.capture(replay, CommitmentMemory(), 5)

        self.assertTrue(
            snapshot.states_identical(factual_end, replay_end),
            "\n".join(snapshot.first_difference(factual_end, replay_end)),
        )


if __name__ == "__main__":
    unittest.main()
