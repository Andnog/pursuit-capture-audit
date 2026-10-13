# Same episode, two endpoints

Each animation below is one episode, drawn to scale. The dashed outline around the evader is the 5 m body-gap rule:
when a pursuer's body enters it, a proximity endpoint declares a capture. The panel on the right shows the
conditions of operational capture for the nearest pursuer, at every instant, and how long they have held.

## The rules

**A proximity endpoint** is met at the first instant a distance falls to a threshold. Which distance is part of the
rule, and the three in use are not interchangeable: between the two bodies, between their centres, or between
their front bumpers, which is what a simulator usually reports as "position".

**Operational capture** holds at time \(t\) when one and the same pursuer \(i\) satisfies a contact condition
throughout a dwell of \(T = 2\) s:

\[
\mathrm{OC}(t) \iff \exists\, i \;\; \forall\, \tau \in [t-T,\, t] : \; \kappa_i(\tau)
\]

and the contact condition \(\kappa_i\) asks for four things at once: a gap of 0.3 to 2.0 m between the two bodies;
both speeds at most 1 m/s; headings within 15°; and the evader behind the pursuer, within 1 m of its axis. The
order of the quantifiers matters: a sequence of brief contacts with different pursuers does not count.

## Three situations, by construction

<div class="episode-player" data-src="../assets/data/passing_cars.json" data-view="60" data-speed="1"></div>

Two cars in opposite lanes. Every proximity rule fires. The evader never slows down.

<div class="episode-player" data-src="../assets/data/follower_behind.json" data-view="60" data-speed="1"></div>

A pursuer that trails the evader at speed. The body-gap rule is met from the first instant; the front-bumper rule
never is, because the two bumpers are a car length apart. The same episode is a success or a failure depending on
which points of the vehicles the distance joins.

<div class="episode-player" data-src="../assets/data/blocked_stop.json" data-view="60" data-speed="1"></div>

The evader stops behind a stopped pursuer and stays. The proximity rule is met on the way in, at 2.5 s; operational
capture is reached at 5.0 s, when the stop has lasted for 2 s.

## One real scenario, two teams

The next two animations are the same scenario in central Adelaide, one of the cities of the development phase:
same start positions, same evader, same simulator seed. Five pursuers chase in the first and use predictive lane
blocking in the second. Playback starts shortly before the first approach, at ten times real speed.

<div class="episode-player" data-src="../assets/data/adelaide_25_pursuit.json" data-view="150" data-speed="10" data-start="24"></div>

With pursuit, a pursuer comes within 5 m of the evader at 31.4 s. A proximity endpoint stops the clock there and
counts a capture. The evader drives on, and in the 300 s of the episode it is never stopped.

<div class="episode-player" data-src="../assets/data/adelaide_25_ambush_plus.json" data-view="150" data-speed="10" data-start="36"></div>

With predictive lane blocking, the proximity rule is met at 42.7 s, the evader comes to a stop behind a pursuer,
and operational capture is reached at 53.4 s, when the stop has lasted for 2 s.

!!! warning "These two episodes are an illustration"
    They were chosen, among a handful of demonstration scenarios, because they show the difference clearly. They
    are not part of any evaluation of the article and say nothing about how often it happens. The rates are in the
    [results](results.md): on the held-out TEST cities the pursuit team reaches operational capture in 17 % of
    episodes and meets the 5 m body-gap rule in 85 %.

## What the animations are made of

The positions come from the simulator. Everything else in the panel is computed by the library of this repository
from those positions (`tools/build_site_data.py`): the same code that is tested against the judge of the study on
thousands of random situations. The script of this page only draws.
