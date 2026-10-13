# Third-party software notices

Stage: W2. Date: 21 September 2026. Decision: **D16 resolved** (see [`governance/AMENDMENTS_EN.md`](governance/AMENDMENTS_EN.md)).

This project uses external software as declared dependencies. Rebuilding from scratch means writing the
research implementation afresh; it does not mean reimplementing a traffic simulator or a tensor library.
Every component below is pinned, and the pin is enforced by `scripts/preflight.py`.

## Pinned versions

| Component | Version | Channel | Role | License |
|---|---|---|---|---|
| CPython | 3.14.6 | system interpreter, pinned by `requires-python = "==3.14.*"` | project interpreter | PSF-2.0 |
| Eclipse SUMO (binaries) | 1.21.0 | **external system installation, not pip** | traffic simulation | EPL-2.0 |
| `traci` | 1.21.0 | PyPI, pure Python | TraCI client bindings | EPL-2.0 |
| `sumolib` | 1.21.0 | PyPI, pure Python | network and route utilities | EPL-2.0 |
| `numpy` | 2.3.3 | PyPI | numerics | BSD-3-Clause |
| `ruff` | 0.14.5 | PyPI, dev group | lint and format | MIT |
| `torch` | 2.14.0 | PyPI, **optional group `learning`, NOT installed at W2** | learner (W6) | BSD-3-Clause |

License identifiers are recorded as declared by each project. They are a provenance record, not legal advice.

## The SUMO binary is not a Python dependency on this platform — and this matters

`uv` will resolve `eclipse-sumo==1.21.0`, but it **cannot install it on macOS arm64**: the package
publishes wheels only for `manylinux_2_17_aarch64`, `manylinux_2_17_x86_64` and `win_amd64`.

The SUMO 1.21.0 binaries present on the development machine were installed separately. Their wheel tag,
read from the installed distribution metadata, is `cp310-cp310-macosx_14_0_arm64` — a CPython 3.10 build,
which cannot be imported or reused by the project's CPython 3.14 interpreter.

The consequence is a real reproducibility hazard and is handled explicitly:

- **The binary and the bindings come from different channels and can drift apart silently.** A `traci`
  client that speaks a different TraCI version from the binary returns *wrong state* rather than raising,
  which would corrupt every downstream physical claim without any visible failure.
- `scripts/preflight.py` therefore checks the binary's self-reported version, both binding versions, and
  their mutual agreement, and **blocks** on any mismatch. It runs no simulation.
- A fresh environment must install the SUMO 1.21.0 binaries from the Eclipse SUMO distribution for its
  platform, then either set `SUMO_HOME` or place `sumo` on `PATH`. `uv sync` alone is not sufficient.

`SUMO_HOME` is currently unset on the development machine, so `sumo` is resolved from `PATH`. This is
recorded rather than silently relied upon.

## Version choice rationale

**SUMO 1.21.0** is pinned because it is the version already present and because the historical programme's
safety work was bound to the same release — the legacy record cites "Official SUMO 1.21 `MSLane.cpp`
retained/hash bound" while analysing the obligation O22 collision. Pinning the same major release keeps the
historical scenario definitions interpretable for the W5 legacy comparison. This is a compatibility
argument, not an endorsement of the historical results.

**CPython 3.14.6** is pinned after checking that it does not block later stages: `traci` and `sumolib` are
pure Python and import cleanly, and `torch` 2.14.0 publishes `cp314` macOS arm64 wheels. Choosing an
interpreter that worked for W2 but blocked the learner at W6 would have forced a re-pin and invalidated the
environment record.

**`libsumo` is not available** on this platform, so the adapter must use the TraCI socket interface. This is
recorded as a non-blocking finding with consequences for determinism and speed that W3 must address.

## Reproducing the environment

```bash
uv sync
```

installs the default dependencies only. `torch` is deliberately excluded: installing it is a W6 action with
its own ledger entry. The finite-example results from W0–W1 require **no** third-party package at all and
run on the standard library alone.

```bash
uv run python scripts/preflight.py
```

verifies the simulator environment. It must exit 0 before any W3 adapter work.
