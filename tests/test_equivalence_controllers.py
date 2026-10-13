"""The decision kernels of the library against the planners that ran in the study.

The frozen planners (`as_run/src/joint_interception/native`) read their inputs from a context
that the simulator loop builds. Here the same context is built from a random road graph, the
frozen planner is asked for its decision, and the library's kernel must give the same one.
"""

import math
import random
from types import SimpleNamespace

import pytest

from pursuit_audit.controllers import (
    Edge,
    Link,
    PrepositioningRule,
    RoadGraph,
    Target,
    assign_blockers,
    exit_order,
    predict_path,
    preposition,
    stop_point_cost,
)

frozen_ambush = pytest.importorskip("joint_interception.native.ambush")
frozen_plus = pytest.importorskip("joint_interception.native.ambush_plus")


class FakeLane:
    def __init__(self, index: int, passenger: bool) -> None:
        self._index, self._passenger = index, passenger

    def getIndex(self) -> int:
        return self._index

    def allows(self, vehicle_class: str) -> bool:
        return self._passenger and vehicle_class == "passenger"


class FakeNetwork:
    """What the frozen planners ask of a sumolib network: the lanes of an edge."""

    def __init__(self, lanes: dict) -> None:
        self._lanes = lanes

    def getEdge(self, edge: str):
        return SimpleNamespace(getLanes=lambda: self._lanes[edge])


def random_world(rng: random.Random, pursuers: int):
    """A random road graph, with pursuers, in the two forms: the library's and the frozen one."""
    nodes = [f"n{i}" for i in range(rng.randint(5, 9))]
    edges, successors, links, lanes = {}, {}, {}, {}
    for a in nodes:
        for b in rng.sample(nodes, rng.randint(1, 3)):
            if a != b:
                edges[f"{a}>{b}"] = Edge(rng.uniform(40, 220), rng.choice([8.3, 13.9, 16.7]), b)
    for name, edge in edges.items():
        following = [other for other in edges if other.startswith(edge.to_node + ">")]
        successors[name] = rng.sample(following, len(following))
        for other in following:
            links[(name, other)] = Link(rng.uniform(6, 25), rng.uniform(4, 12))
        count = rng.randint(1, 3)
        lanes[name] = [FakeLane(i, passenger=rng.random() > 0.1) for i in range(count)]
    graph = RoadGraph(edges, links, successors)
    ids = [f"p{i + 1}" for i in range(pursuers)]
    node_times = {v: {n: rng.uniform(0, 90) for n in nodes if rng.random() > 0.1} for v in ids}
    edge_times = {v: {e: rng.uniform(0, 90) for e in edges if rng.random() > 0.1} for v in ids}
    positions = {v: (rng.choice(sorted(edges)), rng.uniform(0, 60)) for v in ids}
    start = rng.choice(sorted(edges))
    offset = rng.uniform(0, edges[start].length_m)
    speed_factor = rng.choice([1.0, 1.0, 1.2])
    context = {
        "net": SimpleNamespace(
            edges={k: SimpleNamespace(**vars(v)) for k, v in edges.items()},
            links={k: SimpleNamespace(**vars(v)) for k, v in links.items()},
        ),
        "reach": SimpleNamespace(succ=successors),
        "snet": FakeNetwork(lanes),
        "per": {v: (node_times[v], edge_times[v]) for v in ids},
        "p_pos": positions,
        "e_pos": (start, offset),
        "speed_factor": speed_factor,
    }
    passenger_lanes = {
        e: [ln.getIndex() for ln in ls if ln.allows("passenger")] for e, ls in lanes.items()
    }
    world = SimpleNamespace(
        graph=graph,
        ids=ids,
        node_times=node_times,
        edge_times=edge_times,
        positions=positions,
        start=start,
        offset=offset,
        speed_factor=speed_factor,
        lanes=passenger_lanes,
    )
    return world, context


def test_the_predicted_path_is_that_of_the_frozen_planner():
    rng = random.Random(94)
    longest = 0
    for _ in range(400):
        world, context = random_world(rng, pursuers=rng.randint(1, 5))
        depth = rng.randint(1, 5)
        expected = frozen_ambush.AmbushPlanner(depth=depth)._predict(context)
        path = predict_path(
            world.graph,
            world.start,
            world.offset,
            world.node_times,
            depth=depth,
            speed_factor=world.speed_factor,
        )
        assert [(s.arrival_edge, s.junction) for s in path] == [(a, j) for a, j, _ in expected]
        assert [s.time_s for s in path] == pytest.approx([t for _, _, t in expected])
        longest = max(longest, len(path))
    assert longest >= 4


def cost_table(world, lanes, hold_m, slow, startup_s):
    """The estimated time of every pursuer to every lane, and its stopping distance."""
    table = {}
    for pursuer in world.ids:
        for edge, lane in lanes:
            info = world.graph.edges[edge]
            table[(pursuer, (edge, lane))] = stop_point_cost(
                world.positions[pursuer],
                edge,
                edge_length_m=info.length_m,
                speed_cap_mps=info.speed_cap_mps,
                hold_m=min(hold_m, 0.5 * info.length_m),
                time_to_edge_end_s=world.edge_times[pursuer].get(edge),
                slow=slow,
                startup_s=startup_s,
            )
    return table


@pytest.mark.parametrize("team", [3, 5])
def test_the_junction_ambush_assigns_the_same_blockers(team):
    rng = random.Random(95 + team)
    closed = 0
    for _ in range(300):
        world, context = random_world(rng, pursuers=team)
        arrival = world.start
        deadline = rng.uniform(5, 120)
        planner = frozen_ambush.AmbushPlanner()
        expected = planner._assign(context, arrival, None, deadline)
        lanes = [
            (s, i) for s in sorted(world.graph.successors.get(arrival, ())) for i in world.lanes[s]
        ]
        table = cost_table(
            world, lanes, frozen_ambush.HOLD_M, frozen_ambush.SLOW, frozen_ambush.STARTUP_S
        )
        result = assign_blockers(
            sorted(world.ids),
            lanes,
            {key: cost for key, (cost, _hold) in table.items()},
            evader_arrival_s=deadline,
            margin_s=frozen_ambush.MARGIN_S,
        )
        if expected is None:
            assert result is None
            continue
        closed += 1
        assert result is not None
        assert result.blockers == {v: (s, i) for v, (s, i, _hold) in expected.items()}
        for pursuer, (edge, lane, hold) in expected.items():
            assert table[(pursuer, (edge, lane))][1] == pytest.approx(hold)
    assert closed > 20


def test_the_greedy_rule_for_large_teams_matches_the_frozen_planner():
    rng = random.Random(98)
    closed = 0
    parameters = {"depth": 2, "margin_s": 0.0, "slow": 1.05, "startup_s": 5.0, "hold_m": 21.776}
    for _ in range(300):
        world, context = random_world(rng, pursuers=7)
        deadline = rng.uniform(5, 150)
        planner = frozen_plus.AmbushPlusPlanner(parameters)
        expected = planner._assign(context, world.start, None, deadline)
        lanes = [
            (s, i)
            for s in sorted(world.graph.successors.get(world.start, ()))
            for i in world.lanes[s]
        ]
        table = cost_table(
            world, lanes, parameters["hold_m"], parameters["slow"], parameters["startup_s"]
        )
        result = assign_blockers(
            sorted(world.ids),
            lanes,
            {key: cost for key, (cost, _hold) in table.items()},
            evader_arrival_s=deadline,
            margin_s=parameters["margin_s"],
            exhaustive_up_to=5,
        )
        if expected is None:
            assert result is None
            continue
        closed += 1
        assert result.blockers == {v: (s, i) for v, (s, i, _hold) in expected.items()}
    assert closed > 20


@pytest.mark.parametrize("independent", [False, True])
def test_prepositioning_chooses_the_same_lanes(independent):
    rng = random.Random(99 + independent)
    placed = shared = 0
    parameters = {
        "depth": 2, "margin_s": 0.0, "slow": 1.05, "startup_s": 5.0, "hold_m": 21.776,
        "chasers": 0, "pre_k_min": 1, "pre_k_max": 2, "pre_margin": -1.007,
        "independent": int(independent),
    }  # fmt: skip
    rule = PrepositioningRule(
        first_junction=parameters["pre_k_min"],
        last_junction=parameters["pre_k_max"],
        margin_s=parameters["pre_margin"],
        hold_m=parameters["hold_m"],
        independent=independent,
    )
    for _ in range(300):
        world, context = random_world(rng, pursuers=rng.randint(2, 6))
        planner = frozen_plus.AmbushPlusPlanner(parameters)
        frozen_path = planner._predict(context)
        free = rng.sample(world.ids, rng.randint(1, len(world.ids)))
        if rng.random() < 0.3 and frozen_path:
            kept = rng.choice(free)
            edge = rng.choice(sorted(world.graph.edges))
            planner.pre = {kept: (edge, 0, 9.0, rng.choice(frozen_path)[1])}
        previous = {v: Target(*t) for v, t in planner.pre.items()}
        expected = planner._preposition(context, frozen_path, free)
        path = predict_path(
            world.graph, world.start, world.offset, world.node_times,
            depth=planner.depth, speed_factor=world.speed_factor,
        )  # fmt: skip

        def cost_of(pursuer, edge, nominal, world=world):
            info = world.graph.edges[edge]
            return stop_point_cost(
                world.positions[pursuer],
                edge,
                edge_length_m=info.length_m,
                speed_cap_mps=info.speed_cap_mps,
                hold_m=nominal,
                time_to_edge_end_s=world.edge_times[pursuer].get(edge),
                slow=parameters["slow"],
                startup_s=parameters["startup_s"],
            )

        result = preposition(
            path,
            free,
            rule,
            exits_of=lambda step, world=world: exit_order(
                world.graph, step.arrival_edge, step.time_s, world.node_times, world.speed_factor
            ),
            lanes_of=lambda edge, world=world: world.lanes[edge],
            edge_length_m=lambda edge, world=world: world.graph.edges[edge].length_m,
            cost_of=cost_of,
            previous=previous,
        )
        assert {v: (t.edge, t.lane, t.junction) for v, t in result.items()} == {
            v: (s, i, j) for v, (s, i, _h, j) in expected.items()
        }
        for pursuer, target in result.items():
            assert target.hold_m == pytest.approx(expected[pursuer][2])
        placed += len(result)
        lanes = [(t.edge, t.lane) for t in result.values()]
        shared += len(lanes) - len(set(lanes))
    assert placed > 200
    # With joint assignment no lane is chosen twice at one step; without it, lanes are shared.
    assert (shared > 0) == independent


def test_a_junction_with_more_lanes_than_pursuers_is_not_closed():
    lanes = [("a", 0), ("a", 1), ("b", 0)]
    cost = {(p, lane): 1.0 for p in ("p1", "p2") for lane in lanes}
    assert assign_blockers(["p1", "p2"], lanes, cost, evader_arrival_s=60.0, margin_s=2.0) is None


def test_the_assignment_serves_the_worst_lane_not_the_sum():
    lanes = [("a", 0), ("b", 0)]
    cost = {
        ("p1", lanes[0]): 1.0,
        ("p1", lanes[1]): 9.0,
        ("p2", lanes[0]): 2.0,
        ("p2", lanes[1]): 30.0,
    }
    result = assign_blockers(["p1", "p2"], lanes, cost, evader_arrival_s=20.0, margin_s=2.0)
    # The cheapest total sends p1 to its near lane and leaves the far lane 10 s late. The rule
    # sends p1 to the far lane instead, and both lanes are closed in time.
    assert result.blockers == {"p2": lanes[0], "p1": lanes[1]}
    assert result.slack_s == pytest.approx(11.0)


def test_an_unreachable_exit_cannot_be_closed():
    cost, hold = stop_point_cost(
        ("x", 0.0), "a", edge_length_m=100.0, speed_cap_mps=13.9, hold_m=12.0,
        time_to_edge_end_s=None, slow=1.3, startup_s=3.0,
    )  # fmt: skip
    assert math.isinf(cost) and hold == 12.0
