"""Build the public evidence map and reviewer guide from an explicit claim index.

This reads the frozen snapshot. It never rewrites seals or registration records.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://github.com/Andnog/pursuit-capture-audit/blob/main/"
EXP = "as_run/experiments/"
# These entries identify original records; they do not assert historical source recoverability.
CLAIMS = [
    (
        "endpoints",
        "Proximity and operational capture",
        "Null-team calibration; identical episodes under different endpoints",
        [
            EXP + "20261004_audit_addendum_r01/results.jsonl",
            EXP + "20261004_audit_addendum_r02/ADDENDUM_R02_SUMMARY.json",
            EXP + "20261003_test_confirmation_r01/results.jsonl",
            EXP + "20261005_heldout_b_r01/summary.json",
        ],
        "src/pursuit_audit/reporting/headline.py",
        "uv run pursuit-audit recompute",
        "Held-out contrasts are independently recomputed. Null-team uncertainty is read from sealed summaries (N_I).",
    ),
    (
        "published",
        "Published environments",
        "Capture events in DGMARL-MVP and PEPCRL-MVP",
        [
            EXP + "20261005_published_env_audit_r01/summary.json",
            EXP + "20261005_published_env_pepcrl_r01/summary.json",
            "THIRD_PARTY.md",
        ],
        "as_run/scripts/analyse_published_env.py",
        "uv run python tools/build_site_data.py --check",
        "The site cross-check reads sealed summaries. A new simulation needs the upstream repositories at the recorded commits; published learners were not trained.",
    ),
    (
        "persistence",
        "Persistence and active escape",
        "Hold audit, completed follow-up and lane-change probe",
        [
            EXP + "20261003_d06_persistence_audit_r01/results.jsonl",
            EXP + "20261004_audit_addendum_r01/ADDENDUM_SUMMARY.json",
            EXP + "20261004_audit_addendum_r02/ADDENDUM_R02_SUMMARY.json",
            EXP + "20261004_audit_addendum_r03/ADDENDUM_R03_SUMMARY.json",
        ],
        "as_run/scripts/audit_d06_persistence.py",
        "cd as_run && uv run python scripts/audit_d06_persistence.py --package /tmp/pursuit_review_replay --limit 6 --workers 2",
        "Blocks B1 and P complete/check follow-up; AE is the active probe. Six local replays matched on 14 October 2026, not a fresh repeat of all captures.",
    ),
    (
        "containment",
        "Containment indicators",
        "Joint escape through a gate or out of the network within 60 seconds",
        [
            EXP + "20261004_audit_addendum_r01/results.jsonl",
            EXP + "20261004_audit_addendum_r02/ADDENDUM_R02_SUMMARY.json",
        ],
        "as_run/scripts/addendum_reanalysis.py",
        "uv run python tools/build_site_data.py --check",
        "Site values read the corrected N_I/B2F and B2T summaries. Earlier gate-only analyses remain in the record and are superseded.",
    ),
    (
        "heldout",
        "Held-out controller comparisons",
        "PLB versus pursuit and the simpler junction ambush, reported separately for TEST and HELD-OUT B",
        [
            EXP + "20261003_test_confirmation_r01/results.jsonl",
            EXP + "20261004_audit_addendum_r01/ADDENDUM_SUMMARY.json",
            EXP + "20261005_heldout_b_r01/results.jsonl",
            EXP + "20261005_heldout_b_r01/summary.json",
        ],
        "src/pursuit_audit/statistics/contrasts.py",
        "uv run pursuit-audit recompute",
        "Independent raw-record recomputation includes family and city–family intervals. No clear PLB advantage over junction ambush was established on HELD-OUT B.",
    ),
    (
        "coordination",
        "Coordination ablation",
        "Joint lane assignment versus independent choices",
        [
            EXP + "20261004_audit_addendum_r03/results.jsonl",
            EXP + "20261004_audit_addendum_r03/ADDENDUM_R03_SUMMARY.json",
        ],
        "as_run/scripts/addendum_r03_reanalysis.py",
        "uv run python tools/build_site_data.py --check",
        "Block AB removes both the joint junction ambush and exclusion of lanes already assigned to teammates. The contrast measures this bundle.",
    ),
    (
        "learning",
        "Learning and corrected implementations",
        "Fine-tuning relative to imitation; final corrected training loop",
        [
            EXP + "20261006_mappo_v4_r01/ANALYSIS.json",
            EXP + "20261006_mappo_v4_r01/PROTOCOL_EN.md",
            EXP + "20261006_mappo_v4_r01/SCIENTIFIC_DECISION_EN.md",
        ],
        "as_run/scripts/analyse_mappo_v4.py",
        "uv run python tools/build_site_data.py --check",
        "Site values read the final sealed analysis. Non-significance does not establish equivalence. Training states require the companion archive.",
    ),
    (
        "robustness",
        "Robustness and scope",
        "Alternative kinematics, background traffic and an evader tuned against PLB",
        [
            EXP + "20261005_kinematic_sensitivity_r01/summary.json",
            EXP + "20261005_traffic_sensitivity_r01/summary.json",
            EXP + "20261005_tuned_evader_r01/summary.json",
        ],
        "tools/build_site_data.py",
        "uv run python tools/build_site_data.py --check",
        "These are sensitivity studies inside SUMO, not independent simulators or field validation.",
    ),
]


def link(path: str, label: str | None = None) -> str:
    """Return an escaped link to a verified repository file."""
    if not (ROOT / path).is_file():
        raise ValueError(f"Missing reviewer resource: {path}")
    return f'<a href="{BASE}{path}">{html.escape(label or path)}</a>'


def source_rows() -> tuple[str, str]:
    """Build readable and machine-linked source-recoverability rows."""
    inventory = json.loads((ROOT / "src/pursuit_audit/evidence/inventory.json").read_text())
    status = json.loads((ROOT / "as_run/provenance/PACKAGE_SOURCE_STATUS.json").read_text())
    rows, markdown = [], []
    for name, entry in inventory["packages"].items():
        package = ROOT / EXP / name
        historical = (
            status["packages"].get(name, {}).get("status", "not recorded in source inventory")
        )
        protocol = (
            "protocol file"
            if (package / "PROTOCOL_EN.md").is_file()
            else "see amendments / decision"
        )
        rows.append(
            f'<tr><td><a href="{BASE.replace("/blob/", "/tree/")}{EXP}{name}">{name}</a></td><td>{entry["kind"]}</td><td>{protocol}</td><td>{historical}</td></tr>'
        )
        markdown.append(f"| `{name}` | {entry['kind']} | {protocol} | {historical} |")
    return "\n".join(rows), "\n".join(markdown)


def evidence_map(source_table: str) -> str:
    """Produce the public map using repository-relative paths."""
    out = [
        "# Public evidence map",
        "",
        "Paths below are relative to this public repository, not an author's private workspace.",
        "",
        "## Manuscript and scope",
        "",
        "- [Author manuscript](../docs/paper/manuscript.pdf), [supplement](../docs/paper/supplement.pdf), [source bundle](../docs/paper/manuscript-source.tar.gz) and [manuscript hashes](../docs/paper/MANIFEST.json).",
        "- These are author drafts, not an accepted publication. The manuscript retains a pending companion-data DOI marker.",
        "- [Reviewer guide](../docs/review.html), [reproduction instructions](../REPRODUCE.md), [availability](../DATA_AVAILABILITY.md).",
        "- Internal registration is not an externally timestamped registry. Some launch-time sources are not fully recoverable.",
        "",
        "## Claim → records → analysis",
        "",
    ]
    for _identifier, title, claim, files, script, command, scope in CLAIMS:
        out += [f"### {title}", "", claim, ""]
        out += [f"- [{path}](../{path})" for path in files]
        out += [
            f"- Analysis: [{script}](../{script})",
            "",
            f"```bash\n{command}\n```",
            "",
            scope,
            "",
        ]
    out += [
        "## Methods and governance",
        "",
        "- [Endpoint parameters](../as_run/configs/domain_v1.json) and [judge](../as_run/src/joint_interception/evaluation/capture_judge.py).",
        "- [Split protocol](../as_run/contracts/SPLIT_PROTOCOL_EN.md), [current split status](../as_run/contracts/SPLIT_STATUS_EN.md) and [HELD-OUT B manifest](../as_run/assets/osm_b/MANIFEST.json).",
        "- [Amendments](../as_run/governance/AMENDMENTS_EN.md) preserve registrations, corrections and post hoc analyses.",
        "- [113 numerical checks](ARTICLE_NUMBERS.md) and [study commands](STUDIES.md). Pattern matching against manuscript text does not establish semantic correctness.",
        "",
        "## Package inventory and historical source recovery",
        "",
        "89 sealed packages and one unsealed demonstration directory. A protocol-file label only describes the files present; it does not itself establish preregistration. Historical recovery labels are taken from PACKAGE_SOURCE_STATUS.json: partial sometimes means only a manifest is absent from historical archives. Read its per-file explanations.",
        "",
        "| Package | Kind | Protocol location | Historical source recovery |",
        "|---|---|---|---|",
        source_table,
        "",
        "Private review correspondence, earlier manuscript drafts and all historical launch-time source versions are not provided here. No exact rerun claim is made for every historical package.",
        "",
    ]
    return "\n".join(out)


def review_page(source_table: str) -> str:
    """Render the editorial resource hub with no JavaScript dependency."""
    claims = []
    for identifier, title, claim, files, script, command, scope in CLAIMS:
        sources = "<br>".join(link(p, p.removeprefix(EXP)) for p in files)
        claims.append(
            f'<section class="review-section" id="{identifier}"><p class="eyebrow">Evidence / {identifier}</p><h2>{title}</h2><p>{claim}</p><div class="review-table-wrap"><table class="review-table"><thead><tr><th>Original records and summaries</th><th>Analysis and verification scope</th></tr></thead><tbody><tr><td>{sources}</td><td>{link(script)}<p>{scope}</p></td></tr></tbody></table></div><pre><code>{html.escape(command)}</code></pre></section>'
        )
    methods = " · ".join(
        link(path, label)
        for path, label in [
            ("as_run/configs/domain_v1.json", "Capture parameters"),
            ("as_run/contracts/SPLIT_STATUS_EN.md", "Split status"),
            ("as_run/assets/osm_b/MANIFEST.json", "Second held-out set"),
            ("as_run/governance/AMENDMENTS_EN.md", "Registration & amendments"),
            ("results/STUDIES.md", "Study commands"),
        ]
    )
    return (
        """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Review guide · When proximity is not interception</title><meta name="description" content="Manuscript, source records, reproducibility checks and their limits."><link rel="stylesheet" href="assets/css/site.css"><link rel="stylesheet" href="assets/css/editorial.css"></head>
<body><a class="skip-link" href="#guide">Skip to review guide</a><header class="site-header"><div class="wrap"><a class="wordmark" href="index.html">Proximity ≠ interception</a><nav class="site-nav" aria-label="Review navigation"><a href="index.html">Research page</a><a href="#availability">Materials</a><a href="#reproduction">Verify</a></nav></div></header>
<main id="guide" class="wrap"><div class="review-intro"><p class="eyebrow">For editors, reviewers &amp; researchers</p><h1>From a claim<br>to its evidence.</h1><p class="lede">Read the manuscript, inspect the original records, and see exactly what each reproduction check establishes. The experimental evidence is preserved; later corrections remain visible as versioned addenda.</p><p class="publication-state">Editorial companion revision · author manuscript, October 2026 · original code archive v1.0.0</p></div>
<nav class="review-contents" aria-label="Guide sections"><a href="#availability">01 / Materials</a><a href="#reproduction">02 / Verification</a><a href="#endpoints">03 / Claim index</a><a href="#sources">04 / Source recovery</a></nav>
<section class="review-section" id="availability"><h2>Materials &amp; availability</h2><div class="resource-grid">
<div class="resource-card"><span class="status">Author draft</span><h3>Manuscript</h3><p>The article, authors and declared limits. Not yet published. It retains a pending companion-data DOI marker.</p><a href="paper/manuscript.pdf">Read PDF ↗</a></div>
<div class="resource-card"><span class="status">Author draft</span><h3>Supplement</h3><p>Extended methods, audit details, full tables and secondary analyses.</p><a href="paper/supplement.pdf">Read PDF ↗</a></div>
<div class="resource-card"><span class="status">Sources &amp; hashes</span><h3>Manuscript source</h3><p>LaTeX, bibliography and figure PDFs, plus a file manifest identifying this manuscript revision.</p><a href="paper/manuscript-source.tar.gz">Download sources</a> · <a href="paper/MANIFEST.json">Hashes</a></div>
<div class="resource-card"><span class="status">Public archive</span><h3>Code &amp; light evidence</h3><p>The preserved v1.0.0 archive predates this editorial revision. The repository contains scripts, road networks, records and summaries.</p><a href="https://doi.org/10.5281/zenodo.23356338">Archived release ↗</a> · <a href="https://github.com/Andnog/pursuit-capture-audit">Repository ↗</a></div>
<div class="resource-card"><span class="status pending">DOI pending</span><h3>Companion data archive</h3><p>137 files: logs, training states and animations (552 MB unpacked). The separate deposit is in progress; a public download is not yet linked. Complete verification needs these files.</p><a href="downloads/companion-manifest.json">Inspect the file manifest</a></div>
<div class="resource-card"><span class="status">Instructions</span><h3>Reproduce &amp; cite</h3><p>Commands, environment requirements, available checks and historical limitations.</p><a href="downloads/REPRODUCE.txt">Reproduction guide</a> · <a href="https://github.com/Andnog/pursuit-capture-audit/blob/main/CITATION.cff">Citation ↗</a></div></div>
<p class="caption">The website is a guide to the evidence, not an independent archival deposit. Use a versioned archive for citation. The source files and PDFs identify the author draft; editorial acceptance is not implied.</p></section>
<section class="review-section" id="reproduction"><h2>Four checks, four different claims.</h2><div class="review-table-wrap"><table class="review-table"><thead><tr><th>Check</th><th>What it establishes</th><th>What it does not establish</th></tr></thead><tbody>
<tr><td>Inventory &amp; integrity</td><td>Expected package directories, unchanged seal files, and matching SHA-256 values. Only omissions listed in the pinned snapshot manifest are permitted.</td><td>A hash is not a proof of scientific correctness or an external registration timestamp. Public-copy verification is not complete-archive verification.</td></tr>
<tr><td>Independent recomputation</td><td>13 headline values, including held-out effects and intervals, recomputed from per-episode records.</td><td>It does not independently recalculate every secondary analysis. Other site values are read from sealed summaries.</td></tr>
<tr><td>Simulator replay</td><td>Six of six sampled replay records matched the sealed records on 14 October 2026, using SUMO 1.21 and the existing research Python environment.</td><td>A six-episode check is not a rerun of all studies or a test of installation on another platform.</td></tr>
<tr><td>Historical source recovery</td><td>A per-file map identifies which recorded launch-time sources exist in the historical archives.</td><td>Some launch-time versions are not fully recoverable. Current research code is not guaranteed to be identical to every earlier launch.</td></tr>
</tbody></table></div>
<pre><code>git clone https://github.com/Andnog/pursuit-capture-audit.git
cd pursuit-capture-audit
uv sync --frozen
uv run pursuit-audit verify
uv run pursuit-audit recompute
uv run pytest
uv run python tools/build_site_data.py --check
uv run python tools/build_review.py --check</code></pre>
<p>After the companion archive is available, verify its download checksum, extract it over <code>as_run/</code> as described in the reproduction guide, and run <code>uv run pursuit-audit verify --complete</code>. Until then, this stricter check is expected to fail.</p>
<p class="notice">The historical test suite needs a training-state file from the companion archive. The light copy alone is not a complete test environment. Both held-out sets have already been evaluated; repeating their fixed analysis is replication, not a new held-out evaluation.</p></section>
<section class="review-section" id="methods"><h2>Methods &amp; registration</h2><p>"""
        + methods
        + """</p><p class="caption">Read current split status alongside the historical manifest: historical “CLOSED” entries were preserved, while subsequent opening and expenditure of TEST are recorded in the status and amendments.</p></section>
"""
        + "\n".join(claims)
        + """
<section class="review-section" id="sources"><h2>Package inventory &amp; source recovery</h2><p>89 sealed evidence packages and one unsealed demonstration directory. A protocol-file entry describes an available file; it does not independently establish that the analysis was registered before execution.</p><p>The historical source inventory reports 14 fully and 55 partially recoverable packages among 69 with recorded source hashes. Some partial entries concern only a manifest; others concern executable code. Read the individual explanations in <a href="https://github.com/Andnog/pursuit-capture-audit/blob/main/as_run/provenance/PACKAGE_SOURCE_STATUS.json">the source-recovery inventory</a>. Unlisted packages are not classified as fully recoverable.</p><details class="method-details"><summary>Inspect all 90 package directories</summary><div class="review-table-wrap"><table class="review-table" id="source-table"><thead><tr><th>Package</th><th>Kind</th><th>Protocol location</th><th>Historical source recovery</th></tr></thead><tbody>"""
        + source_table
        + """</tbody></table></div></details>
<p><a href="downloads/EVIDENCE_MAP.txt">Download the full evidence map</a> · <a href="downloads/REPRODUCE.txt">Reproduction guide</a> · <a href="index.html#limits">Scientific limitations</a></p></section>
</main><footer class="site-footer"><div class="wrap"><p><a href="index.html">← Research overview</a> · Code: MIT. Documents and results: CC BY 4.0. Road networks: © OpenStreetMap contributors, ODbL.</p></div></footer></body></html>\n"""
    )


def main() -> int:
    """Write the guide or check for stale generated resources."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rows, markdown = source_rows()
    evidence = evidence_map(markdown)
    outputs = {
        "docs/review.html": review_page(rows),
        "results/EVIDENCE_MAP.md": evidence,
        "docs/downloads/EVIDENCE_MAP.txt": evidence,
        "docs/downloads/REPRODUCE.txt": (ROOT / "REPRODUCE.md").read_text(),
    }
    stale = []
    for name, content in outputs.items():
        path = ROOT / name
        if not path.exists() or path.read_text() != content:
            stale.append(name)
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
    print("Review resources: " + (", ".join(stale) if stale else "all current"))
    return int(args.check and bool(stale))


if __name__ == "__main__":
    raise SystemExit(main())
