# Deviations

## D-1. This package has no pre-registered acceptance rule, and says so

A-41 left the mechanism open. There was no hypothesis to test, only a cause to find. Writing a frozen
acceptance rule afterwards would misrepresent the shape of the work. What was fixed in advance instead: check
candidates against the whole corpus, apply corrections to the model rather than fit them to the residual, and
re-state a previous refutation rather than soften it quietly.

## D-2. The correction weakens two of my own sealed results, and is reported in those words

It would have been easy to present "median error 39.6 s → 4.35 s" as progress. It is progress, and it is also
evidence that **A-40 and A-41 overstated the refutation by roughly an order of magnitude** because of a defect
in the runner they shared. Both framings are true; only the second is the one a reader needs.

## D-3. The corrected speed limit is a model input, not a fitted margin

The protocol for A-41 forbade fitting a delay term, and this does not do that. The minimum over traversed
lanes — including internal ones — is the conservative bound the `UNDER` semantics always required. The
distinction matters: a fitted term is calibrated on the residual it is meant to explain, and this quantity is
read from the network file without looking at any error.

## D-4. A count was the wrong variable for the second time

A-40 attributed the deficit to junction **count**; A-41 refuted it at r = 0.02. This package finds signal
**count** equally non-determining. The pattern is the same both times: what matters is time spent, or phase
encountered, not how many of a thing lie on the route.

Recorded so a third count-based explanation is not reached for.

## D-5. The residual mechanism is left unconfirmed rather than asserted

The evidence is suggestive at both extremes and contradicted in the middle. Confirming it needs a
signal-phase trace, which was not recorded. A-40 asserted a mechanism on weaker evidence than this and had to
withdraw it.

## D-6. No resource limit exceeded

60 SUMO process starts permitted, 40 used. No optimizer update, no checkpoint load, no TEST access.
