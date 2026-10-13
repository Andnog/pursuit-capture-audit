# Protocol — W0 revision r04: backward citation chasing on B06

## What this package does

One search move, decided and frozen before it was executed: **read the reference list of a source already
read at method depth, and screen it against the claim classes.** The source is B06 (Han et al., dynamic
termination). No keyword query was issued.

The move was chosen because every prior search step ran forward or sideways — keyword queries over recent
literature, forward citation traversal, family closure — and none had looked *backward*.

## Precondition discovered before the screen

B06 had been recorded in r03 at `METHOD_SECTIONS` depth over a *"full 6-page PDF"*, read from page images.
Text extraction (`pdftotext -layout`) returns **14 pages**. The r03 reading was made from a truncated render.
This package therefore also re-reads B06 at `FULL_TEXT` and corrects its matrix row.

## Acceptance rule, frozen before reading

| Verdict | Condition |
|---|---|
| `REFUTED` | A reference implements the conjunction |
| `CHASE_CLOSED` | All references screened, all relevant ones read at method level |
| `CHASE_PARTIAL` | All references screened; one or more relevant ones identified but not obtainable |
| `CHASE_FAILED` | The reference list could not be read |

A reference that is *identified but not obtainable* counts as **a blocker, not a closure**. It may not be
scored from a citing source's description of it.

## Reading-depth rule applied

A method description given **by a citing work** is recorded as
`SECONDHAND_METHOD_DESCRIPTION_NOT_A_READ`. It may be quoted, and it may sharpen a question. It may **not**
support a distinctness statement.

## Resource limits

No simulator, no optimizer, no checkpoint, no TEST split. Literature work only.
