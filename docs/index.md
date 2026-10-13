# When proximity is not interception

**An audit of capture endpoints for multi-vehicle pursuit in microscopic urban traffic simulation.**
Andrei Noguera Gil, Felix Martinez-Rios and Edgar Avalos-Gauna.

Pursuit studies usually score success by proximity: the episode is a capture when a pursuer comes within a few
metres of the evader. Press play. Two cars pass each other in opposite lanes at 12 m/s, and for an instant they are
less than 5 m apart.

<div class="episode-player" data-src="assets/data/passing_cars.json" data-view="60" data-speed="1"></div>

A 5 m rule calls that a capture. Nobody was stopped. We audited what such endpoints measure, in the SUMO simulator
on fifteen real downtown networks, against an endpoint that asks for what an interception is: a pursuer directly
ahead of a nearly stopped evader, with 0.3 to 2 m between the two bodies, held for 2 s.

<div class="key-figures" markdown>
<div class="key-figure" markdown><strong>21–42 %</strong><span>success of a team that does not pursue, under proximity endpoints. Under operational capture: 2–3 %.</span></div>
<div class="key-figure" markdown><strong>3 to 5 times</strong><span>more successes reported by a 5 m rule than by an operational stop, on two held-out sets of four cities.</span></div>
<div class="key-figure" markdown><strong>0 of 3 379</strong><span>capture events in the official environments of two published methods joined two vehicles in the same lane.</span></div>
<div class="key-figure" markdown><strong>+14.5 and +6.4</strong><span>points of capture for waiting ahead over chasing, on the two held-out sets, each evaluated once.</span></div>
</div>

## Three findings

**1. Proximity is not interception.** A team that drives random routes, without pursuing, is scored as successful
in a fifth to two fifths of episodes by proximity rules. In the released environments of two published methods, a
team that turns at random met the published success criterion in 31–59 % of episodes, against 2–11 % for a team
that chases: chasing puts the pursuer behind the evader, where the rule cannot fire. And the endpoint changes which
controller looks better. [Read more](findings/proximity.md)

**2. Containment indicators need auditing.** An indicator that certifies the evader as enclosed when pursuers are
near the surrounding junctions lets 72–82 % of the evaders that it certifies escape. Asked at the level of lanes,
the same question lets about 8 % escape: useful, and fallible. [Read more](findings/containment.md)

**3. Waiting ahead beats chasing, and assignment matters.** Under the audited endpoint, pursuers that wait in the
lanes that the evader is predicted to take capture more than pursuers that chase, on two held-out sets of cities
and against five evader behaviours, one of them tuned against the controller. Removing the joint assignment of
lanes costs 7.1 points. [Read more](findings/controllers.md)

The endpoint we use is fallible too, and we say how: it held in all 1 433 audited captures with the pursuers
stopped, and an active lane-change probe released 15. Everything here is simulation with scripted evaders in one
simulator. [The limits](limits.md)

## What you can do here

- [Watch the same episode under two endpoints](endpoints.md), with every condition of the rule shown frame by frame.
- [Check the evidence](reproduce.md): every sealed file against its checksum in seconds, every headline number
  recomputed from the raw records in a minute, and the commands to run each study again.
- [Score your own study](library.md) under several endpoints with a small library that has no dependency.
- [Read the results](results.md), with the tables computed from the sealed records.

!!! note "A reporting checklist"
    The audits suggest six things that a pursuit study can report at low cost: the capture rule in full (which
    points of the vehicles the distance joins, the speeds allowed, whether the evader is removed at capture); the
    score of a team that does not pursue, under the same rule; a hold audit, with complete follow-up; for any
    containment indicator, the share of certified evaders that escape; an evaluation on networks not used for
    design, opened once; and which analyses were registered before the runs.
