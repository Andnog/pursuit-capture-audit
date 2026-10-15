# Data and manuscript availability

## Available now

- [Author manuscript](docs/paper/manuscript.pdf), [supplement](docs/paper/supplement.pdf), [source bundle](docs/paper/manuscript-source.tar.gz) and [manuscript file hashes](docs/paper/MANIFEST.json). These are author drafts, not an accepted publication; the pending companion-data DOI remains visible in the manuscript.
- The original code and light evidence release v1.0.0: [Zenodo 10.5281/zenodo.23356338](https://doi.org/10.5281/zenodo.23356338). Its contents predate the current editorial revision.
- 89 sealed result packages and one separate demonstration directory under `as_run/experiments/`; road networks, analysis scripts, contracts, amendments and available source archives.
- [Public evidence map](results/EVIDENCE_MAP.md), [study catalogue](results/STUDIES.md) and [reproduction instructions](REPRODUCE.md).

## Companion archive: upload in progress, DOI pending

The companion is `pursuit-capture-audit-heavy-files-v1.0.0.tar.gz`, containing 137 manifest-listed files (552 MB unpacked), including run logs, training states and animations. 126 of those files have hashes in package seals; the others are separately identified by the manifest. A public download must be linked here, in the review guide and in the manuscript once the deposit completes. No download link or DOI is invented.

[Inspect the companion manifest](docs/downloads/companion-manifest.json).

The prepared archive's SHA-256 is:

```text
2d3a84c8395d0ac5ae841d0f04269134ac36ccca5bdd414cf646e61dc6208f8b
```

After downloading that exact archive, compare its SHA-256 with the value above. From the repository root, extract into `as_run/` of a separate copy if you want to keep the light checkout unchanged:

```bash
# macOS: shasum -a 256 pursuit-capture-audit-heavy-files-v1.0.0.tar.gz
# Linux: sha256sum pursuit-capture-audit-heavy-files-v1.0.0.tar.gz
tar -xzf pursuit-capture-audit-heavy-files-v1.0.0.tar.gz -C as_run
uv run pursuit-audit verify --complete
```

The prepared tar also contains macOS AppleDouble metadata (`._` files). These are not experiment records and are not covered by the companion file manifest. Do not replace the archive silently to remove them: any new packaging needs a new documented checksum/version.

The light copy intentionally lacks these files. Its public-copy verification can pass, but `--complete` must fail until the companion is restored. The historical test suite also requires a training-state file from the companion.

## Limits of preservation

A matching hash establishes consistency with the checked-in reference, not authenticity or an external registration time. Some launch-time source versions cannot be recovered in full. Read [the per-file source-recovery inventory](as_run/provenance/PACKAGE_SOURCE_STATUS.json); a current script is not automatically the exact source used by every earlier study. Six successful replay checks do not establish reproducibility of all campaigns.

## Remaining availability updates

The editorial website can be published while the companion deposit is pending; its availability notice must remain explicit. When the upload completes, add its DOI and update the manuscript's pending marker, PDFs and source manifest in a new revision. Archive an identifiable code release for journal citation. Keep the original version and every experimental seal intact.
