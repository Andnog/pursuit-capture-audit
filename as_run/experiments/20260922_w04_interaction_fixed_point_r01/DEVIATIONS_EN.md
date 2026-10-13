# Deviations

## D-1. The first witness was vacuous and the package nearly recorded it as success

Every check passed on a configuration in which the interaction did no work: one blocking window, positioned
entirely before the blocked participant's earliest arrival, removing nothing. All arrival sets were single
intervals.

A package that had stopped there would have reported "the interaction half is implemented" on evidence that
showed only that the code runs. The non-vacuity checks (`C4`, and three tests) were added **because** of
this, and they assert the thing that matters: that the coupling produces a **nonconvex** set and that the
hull of that set readmits a genuinely blocked time.

**This was not caught by a test.** It was caught by printing the witness and reading it. There is now a test.

## D-2. No existence result, and the reason is not fixable by effort

Kakutani needs convex values; these sets are nonconvex by design. **No better search recovers the theorem.**
The honest verdict vocabulary follows: `NOT_FOUND_ON_THIS_GRID` is a statement about the search, and the word
"exists" appears nowhere in it.

This is a cost of the representation, and the package records it as a cost rather than as an open task that
someone might later close.

## D-3. Grid enumeration was chosen deliberately over a better algorithm

A best-response iteration or a constraint solver would be faster and would scale further. Both would make a
negative result ambiguous — a failure to converge is not a failure to exist, and distinguishing them is work
this package would then owe. Enumeration makes `NOT_FOUND_ON_THIS_GRID` mean exactly what it says.

The cost is real and stated: exponential in participants, usable at three to five.

## D-4. The negative controls were specified in the protocol before the module existed

All three — pairwise-passes-joint-fails, provable inconsistency, and hull-readmits-a-blocked-time — were
written into `PROTOCOL_EN.md` before any code. The fourth control, non-vacuity, was **not**: it was added
after D-1. That ordering is recorded rather than smoothed over.

## D-5. Nothing was relaxed to obtain a witness

The capacity arithmetic, the integration tolerance and the `UNDER` discharge are unchanged from
`constructive_arrival_set`, which the interaction module imports rather than reimplements.

## D-6. No resource consumed

Analytical only. No SUMO process, no optimizer update, no checkpoint load, no TEST access.
