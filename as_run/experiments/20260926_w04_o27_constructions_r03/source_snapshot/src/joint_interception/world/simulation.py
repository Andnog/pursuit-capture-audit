"""The declared model's dynamics: a deterministic world on the junction graph.

Declared approximation direction: OPTIMISTIC (A-43; O28). A construction found here is
feasibility under this model and nothing more.

What is modelled: per-edge speed caps, internal junction lanes, fixed-time signals, bounded
acceleration and deceleration, following at each class's min_gap on SINGLE-LANE channels,
holds, and the scripted evader choosing continuations at junctions.

What is NOT modelled, and how each is handled rather than hidden:

- **Multi-lane edges.** A stopped vehicle there is assumed passable, so vehicles do not follow
  or block one another on them. No capture may be claimed from blocking a multi-lane edge.
- **Lane changes and overtaking** within a single-lane edge: impossible by construction.
- **Right-of-way beyond signals.** At a merge onto a single-lane edge the lower-priority
  vehicle yields at its merge point: a vehicle that can no longer stop before it goes first,
  then the nearer one, then by id. This is NOT SUMO's junction model, whose priorities follow
  the road hierarchy.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from ..evaluation.capture_judge import TraceFrame, VehicleFrame
from ..simulator.evader import ScriptedEvader
from .network import GraphNetwork, Link, point_on_shape

TOL = 1e-9


@dataclass
class Vehicle:
    vid: str
    klass: str
    length: float
    width: float
    min_gap: float
    edge: str
    offset: float
    speed: float
    in_link: Link | None = None
    route: list[str] = field(default_factory=list)
    hold: tuple[str, float] | None = None
    decided_on: str | None = None
    stuck: bool = False
    entered_via: tuple[str, str] | None = None

    @property
    def channel(self) -> tuple:
        return (
            ("link", self.in_link.from_edge, self.in_link.to_edge)
            if self.in_link
            else (
                "edge",
                self.edge,
            )
        )


@dataclass
class CaptureWatch:
    pursuer: str | None = None
    frames: int = 0


@dataclass
class World:
    network: GraphNetwork
    vehicles: dict[str, Vehicle]
    evader: ScriptedEvader
    evader_id: str
    step_s: float
    decision_s: float
    accel: float
    decel: float
    capture: dict
    speed_ratio: float = 1.0
    record_trace: bool = False
    time_s: float = 0.0
    step_index: int = 0
    trace: list[TraceFrame] = field(default_factory=list)
    collisions: list[dict] = field(default_factory=list)
    safety_failures: list[dict] = field(default_factory=list)
    watch: CaptureWatch = field(default_factory=CaptureWatch)
    captured_at_s: float | None = None
    captured_by: str | None = None

    # -- geometry of the chain -------------------------------------------------------

    def _channel_length(self, v: Vehicle) -> float:
        return v.in_link.via_length_m if v.in_link else self.network.edges[v.edge].length_m

    def _next_edge(self, v: Vehicle) -> str | None:
        if v.in_link:
            return v.in_link.to_edge
        return v.route[0] if v.route else None

    def _merge_approach(self, v: Vehicle) -> tuple[str, float, float, Link] | None:
        """(target edge, distance to the junction ENTRY, distance to the target's start, link).

        A vehicle already inside the junction has entry distance 0.
        """
        if v.in_link:
            return v.in_link.to_edge, 0.0, v.in_link.via_length_m - v.offset, v.in_link
        if not v.route:
            return None
        link = self.network.link(v.edge, v.route[0])
        if link is None:
            return None
        remaining = self.network.edges[v.edge].length_m - v.offset
        return v.route[0], remaining, remaining + link.via_length_m, link

    def _merge_key(self, v: Vehicle, entry: float, to_target: float) -> tuple:
        """Priority into a merge: inside the junction first; then a vehicle that can no longer
        stop before the junction; then the one nearer the target; then by id."""
        inside = v.in_link is not None
        committed = inside or (self._safe_speed(entry) < v.speed - self.decel * self.step_s - 1e-9)
        return (0 if inside else 1, 0 if committed else 1, round(to_target, 9), v.vid)

    def _merge_yield(self, v: Vehicle) -> float:
        """Distance to v's junction ENTRY if v must yield there, else inf.

        Two vehicles entering the same single-lane edge through different internal lanes do
        not see each other as leaders, and a construction's finisher and evader overlapped
        entering one. Two corrections were needed, both recorded:

        - the first fix projected the other vehicle onto the target edge as a virtual leader,
          which demanded an emergency stop while both were still 30 m out side by side;
        - the second yielded at the END of the internal lane, but internal lanes CONVERGE,
          so two bodies inside one junction overlapped before either reached the edge.

        The rule now is a junction's: the lower-priority vehicle stops at the junction entry
        and waits until the other has entered the target edge with its rear clear of the
        junction by v's own min_gap. A vehicle already inside the junction is not asked to
        yield - that is priority, not physics, and was settled before it entered.
        """
        if v.in_link:
            return math.inf
        mine = self._merge_approach(v)
        if mine is None or not self.network.edges[mine[0]].single_lane:
            return math.inf
        target, my_entry, my_target, my_link = mine
        my_key = self._merge_key(v, my_entry, my_target)
        for other in self.vehicles.values():
            if other.vid == v.vid:
                continue
            if (
                other.in_link is None
                and other.edge == target
                and other.entered_via != (my_link.from_edge, my_link.to_edge)
                and other.offset - other.length < v.min_gap
            ):
                # Only a vehicle that came through ANOTHER internal lane. One queued ahead
                # on v's own approach is an ordinary leader; making v stop at the junction
                # entry behind it demanded emergency braking in a two-vehicle queue.
                return max(0.0, my_entry - 0.5)
            theirs = self._merge_approach(other)
            if theirs is None or theirs[0] != target:
                continue
            if theirs[3] is my_link:
                # Same internal lane. From a SINGLE-lane edge the two are already in file
                # and ordinary following orders them. From a MULTI-lane edge they are side
                # by side and converge into one internal lane: two pursuers stopped abreast
                # at a two-lane edge's end entered together and overlapped for 1656 steps.
                abreast = (
                    other.in_link is None
                    and other.edge == v.edge
                    and not self.network.edges[v.edge].single_lane
                )
                if not abreast:
                    continue
            if self._merge_key(other, theirs[1], theirs[2]) < my_key:
                return max(0.0, my_entry - 0.5)
        return math.inf

    def _ahead(self, v: Vehicle, physical_only: bool = False) -> list[tuple[float, Vehicle]]:
        """Vehicles physically ahead of v: same channel, the next link, the next edge.

        Returns `(distance from v's front to the other's FRONT, other)`. Only single-lane
        channels are considered: on a multi-lane edge vehicles are assumed passable.

        Merges are NOT handled here but in `_stop_distance`, as a yield at the merge point.
        `physical_only` is kept for the collision check's readability.
        """
        out: list[tuple[float, Vehicle]] = []
        remaining = self._channel_length(v) - v.offset
        here = v.channel
        single_here = v.in_link is not None or self.network.edges[v.edge].single_lane
        nxt = self._next_edge(v)
        link = None
        if not v.in_link and nxt is not None:
            link = self.network.link(v.edge, nxt)
        for other in self.vehicles.values():
            if other.vid == v.vid:
                continue
            if other.channel == here and single_here and other.offset > v.offset - TOL:
                out.append((other.offset - v.offset, other))
            elif link is not None and other.in_link is link:
                if physical_only and not single_here:
                    # v is still on a MULTI-lane edge, in its own lane. A vehicle that
                    # has just entered the internal lane from the lane beside it overlaps
                    # v longitudinally but not laterally. The dynamics still treat it as
                    # a leader, so v cannot follow it in too soon; only the collision
                    # CHECK must not project it into v's lane - seattle recorded that as
                    # a 4.47 m overlap between two pursuers abreast.
                    continue
                out.append((remaining + other.offset, other))
            elif (
                nxt is not None
                and other.in_link is None
                and other.edge == nxt
                and self.network.edges[nxt].single_lane
            ):
                via = link.via_length_m if (link is not None and not v.in_link) else 0.0
                out.append((remaining + via + other.offset, other))
        return out

    def _leader_gap(self, v: Vehicle) -> float:
        """Bumper gap to the nearest vehicle ahead in a single-lane context, or inf."""
        gaps = [d - other.length for d, other in self._ahead(v)]
        return min(gaps) if gaps else math.inf

    def _following_room(self, v: Vehicle) -> float:
        """Distance v may use to stop behind its leaders, net of v's min_gap.

        Includes each leader's OWN braking distance: v must be able to stop behind a leader
        that brakes at the same ordinary rate, which is the standard safe-following rule.
        The first version treated every leader as a wall, so ordinary following at speed was
        flagged as emergency braking that never happened - four times across two baselines.
        """
        room = math.inf
        for distance, other in self._ahead(v):
            gap = distance - other.length - v.min_gap
            room = min(room, gap + other.speed**2 / (2.0 * self.decel))
        return room

    def _safe_speed(self, gap: float, arrive_at: float = 0.0) -> float:
        """Largest speed from which the vehicle can slow to `arrive_at` within `gap`.

        With `arrive_at = 0` this is the stopping rule. With the next channel's cap it is the
        anticipation SUMO performs before a slower internal lane: without it the first model
        reached a junction at edge speed and "braked" instantly to the internal lane's cap,
        which the safety record correctly flagged as emergency braking - 30 times in one
        baseline run.
        """
        if gap <= 0:
            return arrive_at
        b, dt = self.decel, self.step_s
        return -b * dt + math.sqrt((b * dt) ** 2 + arrive_at**2 + 2.0 * b * gap)

    def admissible(self, v: Vehicle, route: list[str], hold: tuple[str, float] | None) -> bool:
        """Can v take `route` and `hold` from its current state with ORDINARY braking?

        A command that would require emergency braking is inadmissible: the contract treats
        emergency braking as a safety failure, not an available manoeuvre. Construction plans
        that switched routes or set holds at a decision boundary without this check demanded
        it - 238 times across two scenarios.
        """
        saved_route, saved_hold = v.route, v.hold
        v.route, v.hold = list(route), hold
        try:
            floor = v.speed - self.decel * self.step_s - 1e-9
            if self._safe_speed(self._stop_distance(v)) < floor:
                return False
            return all(self._safe_speed(d, req) >= floor for d, req in self._upcoming(v))
        finally:
            v.route, v.hold = saved_route, saved_hold

    def reachable_hold(self, v: Vehicle, route: list[str], edge: str, offset: float) -> float:
        """The nearest hold offset on `edge`, at or beyond `offset`, v can stop at ordinarily."""
        end = self.network.edges[edge].length_m - 0.5
        candidate = offset
        while candidate <= end + 1e-9:
            if self.admissible(v, route, (edge, candidate)):
                return candidate
            candidate += 1.0
        return end

    def _upcoming(self, v: Vehicle) -> list[tuple[float, float]]:
        """Speed constraints ahead: `(distance to where it applies, speed required there)`.

        Walks the KNOWN route channel by channel - internal lanes included - until the
        distance exceeds what braking from the current speed could need. Where the known
        route ends it adds the most demanding case v cannot rule out:

        - a pursuer whose route ends stops there (its hold, if any, is handled separately);
        - a terminal edge (no continuation) means stopping at its end;
        - the EVADER has no route oracle (D08): beyond its one decided edge it must still be
          able to take its SLOWEST admissible continuation - worst case over public options.

        Earlier versions looked one or two channels ahead and let a vehicle enter a short fast
        edge with no room to slow for the turn after it; baselines flagged it as emergency
        braking.
        """
        ratio = self.speed_ratio if v.klass == "evader" else 1.0
        horizon = v.speed**2 / (2.0 * self.decel) + v.speed * self.step_s + 25.0
        out: list[tuple[float, float]] = []
        distance = self._channel_length(v) - v.offset
        if v.in_link:
            last = v.in_link.to_edge
            out.append((distance, self.network.edges[last].speed_cap_mps * ratio))
            distance += self.network.edges[last].length_m
            route = list(v.route[1:] if v.route and v.route[0] == last else v.route)
        else:
            last = v.edge
            route = list(v.route)
        for target in route:
            if distance > horizon:
                return out
            link = self.network.link(last, target)
            if link is None:
                return out
            if self._signal_stops(link, v, distance):
                out.append((distance, 0.0))
                return out
            if link.via_length_m > TOL:
                out.append((distance, link.via_speed_mps * ratio))
                distance += link.via_length_m
            out.append((distance, self.network.edges[target].speed_cap_mps * ratio))
            distance += self.network.edges[target].length_m
            last = target
        if distance > horizon or last == v.edge and not v.in_link:
            return out
        if v.klass != "evader" or not self.network.successors(last):
            if not (v.hold and v.hold[0] == last):
                out.append((distance, 0.0))
        else:
            self._every_continuation(v, last, distance, horizon, ratio, out, set())
        return out

    def _every_continuation(
        self,
        v: Vehicle,
        last: str,
        distance: float,
        horizon: float,
        ratio: float,
        out: list[tuple[float, float]],
        seen: set[str],
    ) -> None:
        """Constraints of EVERY continuation the evader might pick, within the horizon.

        The evader's choice is made by its policy, not by its dynamics, so it must be able to
        follow any of them. Looking only one channel past the known route let it enter a
        4.9 m edge at 27.8 m/s whose sole exit led to a dead end 27 m later.
        """
        successors = self.network.successors(last)
        if not successors:
            out.append((distance, 0.0))
            return
        for nxt in successors:
            link = self.network.links[(last, nxt)]
            if self._signal_stops(link, v, distance):
                out.append((distance, 0.0))
                continue
            far = distance
            if link.via_length_m > TOL:
                out.append((far, link.via_speed_mps * ratio))
                far += link.via_length_m
            out.append((far, self.network.edges[nxt].speed_cap_mps * ratio))
            far += self.network.edges[nxt].length_m
            if far <= horizon and nxt not in seen:
                self._every_continuation(v, nxt, far, horizon, ratio, out, seen | {nxt})

    def _signal_stops(self, link: Link, v: Vehicle, distance: float) -> bool:
        """Whether a signalled link must be treated as a stop line `distance` ahead.

        Signal state is public; not green means stop, except the dilemma zone: on YELLOW a
        vehicle that can no longer stop at ordinary deceleration proceeds (as in
        `_stop_distance`).
        """
        if link.signal is None:
            return False
        program = self.network.programs.get(link.signal[0])
        if program is None or program.is_green(link.signal[1], self.time_s):
            return False
        yellow = program.state(link.signal[1], self.time_s) in "yY"
        committed = self._safe_speed(distance) < v.speed - self.decel * self.step_s - 1e-9
        return not (yellow and committed)

    def _stop_distance(self, v: Vehicle) -> float:
        """Distance to the nearest point v is required to stop at, or inf."""
        remaining = self._channel_length(v) - v.offset
        best = self._merge_yield(v)
        if v.in_link:
            # A hold just past the internal lane stays binding while v is on it. Dropping it
            # here let a pursuer that had room to stop enter a 14 m internal lane at full
            # speed and reach the edge 10.9 m short of its hold (O27 r02, A-52).
            if v.hold and v.hold[0] == v.in_link.to_edge:
                best = min(best, remaining + v.hold[1])
            return best
        nxt = self._next_edge(v)
        if v.hold and v.hold[0] == v.edge and v.offset <= v.hold[1] + TOL:
            best = min(best, v.hold[1] - v.offset)
        if nxt is None:
            best = min(best, remaining)
        else:
            link = self.network.link(v.edge, nxt)
            if link is None:
                best = min(best, remaining)
            else:
                if link.signal is not None:
                    program = self.network.programs.get(link.signal[0])
                    if program is not None and not program.is_green(link.signal[1], self.time_s):
                        # The dilemma zone. When a light leaves green with the vehicle too
                        # close to stop at ORDINARY deceleration, it proceeds on yellow -
                        # as SUMO does and as traffic law requires. On red it never does.
                        # Found when a light changed 4 m ahead of a vehicle at 27.8 m/s
                        # and the model demanded 22 m/s of braking in one step.
                        yellow = program.state(link.signal[1], self.time_s) in "yY"
                        can_stop = (
                            self._safe_speed(remaining) >= v.speed - self.decel * self.step_s - 1e-9
                        )
                        if not (yellow and not can_stop):
                            best = min(best, remaining)
                if v.hold and v.hold[0] == nxt:
                    best = min(best, remaining + link.via_length_m + v.hold[1])
        return best

    # -- decisions ------------------------------------------------------------------

    def _pursuer_nodes(self) -> dict[str, str]:
        nodes = {}
        for vid, v in self.vehicles.items():
            if v.klass != "pursuer":
                continue
            if v.in_link:
                nodes[vid] = self.network.edges[v.in_link.to_edge].from_node
            else:
                nodes[vid] = self.network.edges[v.edge].to_node
        return nodes

    def _evader_decides(self, v: Vehicle) -> None:
        if v.in_link or v.route or v.stuck or v.decided_on == v.edge:
            return
        remaining = self._channel_length(v) - v.offset
        lookahead = v.speed**2 / (2 * self.decel) + v.speed * self.step_s + 1.0
        if remaining > lookahead:
            return
        decision_index = int(round(self.time_s / self.decision_s))
        decision = self.evader.choose(decision_index, v.edge, self._pursuer_nodes())
        v.decided_on = v.edge
        if decision.chosen is None:
            v.stuck = True
        else:
            v.route = [decision.chosen]

    # -- one physical step -----------------------------------------------------------

    def step(self) -> None:
        dt = self.step_s
        for vid in sorted(self.vehicles):
            v = self.vehicles[vid]
            if v.klass == "evader":
                self._evader_decides(v)
        new_speed: dict[str, float] = {}
        for vid in sorted(self.vehicles):
            v = self.vehicles[vid]
            cap = v.in_link.via_speed_mps if v.in_link else self.network.edges[v.edge].speed_cap_mps
            if v.klass == "evader":
                cap *= self.speed_ratio
            gap_leader = self._following_room(v)
            gap_stop = self._stop_distance(v)
            safe = min(self._safe_speed(gap_leader), self._safe_speed(gap_stop))
            for distance, required in self._upcoming(v):
                safe = min(safe, self._safe_speed(distance, required))
            target = min(cap, v.speed + self.accel * dt, safe)
            floor = v.speed - self.decel * dt
            if target < floor - 1e-6:
                self.safety_failures.append(
                    {
                        "time_s": round(self.time_s, 6),
                        "vehicle": vid,
                        "required_mps": target,
                        "ordinary_floor_mps": floor,
                    }
                )
            new_speed[vid] = max(0.0, target)
        for vid in sorted(self.vehicles):
            v = self.vehicles[vid]
            v.speed = new_speed[vid]
            v.offset += v.speed * dt
            self._cross_boundaries(v)
        self.time_s = round(self.time_s + dt, 9)
        self.step_index += 1
        self._check_collisions()
        self._watch_capture()
        if self.record_trace:
            self.trace.append(self.frame())

    def _cross_boundaries(self, v: Vehicle) -> None:
        for _ in range(4):
            length = self._channel_length(v)
            # Reaching a boundary is not crossing it. The safe-speed rule brings a vehicle
            # to EXACTLY its stop point, so treating "at the line" as "past the line" let
            # a vehicle held at a red signal drive through it.
            if v.offset <= length + TOL:
                return
            excess = v.offset - length
            if v.in_link:
                target = v.in_link.to_edge
                if self._start_blocked(v, target):
                    v.offset, v.speed = length, 0.0
                    return
                v.entered_via = (v.in_link.from_edge, target)
                v.edge, v.in_link, v.offset = target, None, excess
                if v.route and v.route[0] == target:
                    v.route.pop(0)
                v.decided_on = None
                continue
            nxt = self._next_edge(v)
            link = self.network.link(v.edge, nxt) if nxt else None
            if link is None:
                v.offset, v.speed = length, 0.0
                return
            if link.via_length_m <= TOL:
                if self._start_blocked(v, nxt):
                    v.offset, v.speed = length, 0.0
                    return
                v.entered_via = (v.edge, nxt)
                v.edge, v.offset = nxt, excess
                v.route.pop(0)
                v.decided_on = None
            else:
                v.in_link, v.offset = link, excess

    def _start_blocked(self, v: Vehicle, edge_id: str) -> bool:
        if not self.network.edges[edge_id].single_lane:
            return False
        return any(
            other.vid != v.vid
            and other.in_link is None
            and other.edge == edge_id
            and other.offset - other.length < v.min_gap + TOL
            for other in self.vehicles.values()
        )

    def _check_collisions(self) -> None:
        for vid in sorted(self.vehicles):
            v = self.vehicles[vid]
            for distance, other in self._ahead(v, physical_only=True):
                if distance - other.length < -1e-6 and distance >= -TOL:
                    self.collisions.append(
                        {
                            "time_s": round(self.time_s, 6),
                            "vehicles": sorted((vid, other.vid)),
                            "overlap_m": round(distance - other.length, 6),
                        }
                    )

    # -- capture watch (early stop only; the official verdict is the independent judge) --

    def _watch_capture(self) -> None:
        if self.captured_at_s is not None or self.evader_id not in self.vehicles:
            return
        e = self.vehicles[self.evader_id]
        c = self.capture
        holder = None
        for distance, other in self._ahead(e):
            if other.klass != "pursuer":
                continue
            gap = distance - other.length
            if (
                c["contact_gap_min_m"] <= gap <= c["contact_gap_max_m"]
                and e.speed <= c["capture_speed_max_mps"]
                and other.speed <= c["capture_speed_max_mps"]
                and abs(e.speed - other.speed) <= c["relative_speed_max_mps"]
                and other.channel == e.channel
            ):
                holder = other.vid
                break
        if holder is not None and holder == self.watch.pursuer:
            self.watch.frames += 1
        elif holder is not None:
            self.watch = CaptureWatch(holder, 1)
        else:
            self.watch = CaptureWatch()
        needed = int(round(c["dwell_time_s"] / self.step_s)) + 1
        if self.watch.frames >= needed:
            self.captured_at_s, self.captured_by = self.time_s, holder

    # -- trace -----------------------------------------------------------------------

    def frame(self) -> TraceFrame:
        vehicles = {}
        for vid, v in self.vehicles.items():
            shape = v.in_link.via_shape if v.in_link else self.network.edges[v.edge].shape
            if not shape:
                shape = self.network.edges[v.in_link.from_edge if v.in_link else v.edge].shape
            x, y, heading = point_on_shape(shape, v.offset - v.length / 2.0)
            vehicles[vid] = VehicleFrame(vid, x, y, heading, v.speed, v.length, v.width)
        return TraceFrame(round(self.time_s, 6), vehicles)

    def run(
        self,
        horizon_s: float,
        controller: Callable[[World, int], None] | None = None,
        stop: Callable[[World], bool] | None = None,
    ) -> None:
        steps_per_decision = int(round(self.decision_s / self.step_s))
        if self.record_trace and not self.trace:
            self.trace.append(self.frame())
        while self.time_s < horizon_s - TOL:
            if controller is not None and self.step_index % steps_per_decision == 0:
                controller(self, self.step_index // steps_per_decision)
            self.step()
            if self.captured_at_s is not None:
                return
            if stop is not None and stop(self):
                return
