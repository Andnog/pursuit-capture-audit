# About

## The article

*When Proximity Is Not Interception: Auditing Capture Endpoints and Predictive Lane Blocking for Vehicle Pursuit in
Microscopic Urban Traffic Simulation.* Andrei Noguera Gil and Felix Martinez-Rios (Universidad Panamericana,
Facultad de Ingeniería, Ciudad de México) and Edgar Avalos-Gauna (Rice University, Houston). The article has not
been published yet; its reference will be added here on publication.

To cite the software and the data, use
[`CITATION.cff`](https://github.com/Andnog/pursuit-capture-audit/blob/main/CITATION.cff).

## The data archive

The repository holds every evidence package with its protocol, its per-episode records, its summary and its
checksums. The heavy files (run logs, pickled training states and animations: 137 files, 552 MB) are in the data
archive; the repository lists each one with its size and its sealed checksum. The DOI of the archive will be added
here when the deposit is made.

## How this was made

Two AI models were used in the research process, under the supervision of the first author, and the article
declares it. Claude Opus 5.5 (Anthropic) wrote and edited the code, ran the experiments and produced the figures
from the sealed result files; it also wrote this site, whose numbers are computed from those files. Astra (OpenAI)
helped the first author and his advisor to check the work in six rounds of audit, which found defects in the
training code that were corrected and are reported.

The safeguards against errors in AI-written code are in the repository: more than 500 unit tests, among them tests
that reproduce each defect found; sealed result packages with checksums; a script that checks every number of the
text against the sealed summaries; a registration record with every amendment; and, for the library of this
repository, tests that compare it with the code that ran.

## Earlier work by the authors

An earlier study by the same authors trained two decentralized pursuers by multi-agent reinforcement learning
against a static prey on one network, and interpreted the learned policies with a Kolmogorov–Arnold network
(IEEE ISADS 2025, [doi:10.1109/ISADS66912.2025.11159312](https://doi.org/10.1109/ISADS66912.2025.11159312)). Its
capture rule was a distance below 20 m, which is an instance of the proximity scoring examined here. This
repository reuses no code, data or trained model of that study.

## Licences

Code: MIT. Results, documents and this site: CC BY 4.0. Road networks derived from OpenStreetMap: ODbL,
© OpenStreetMap contributors. The released code of the two published environments that were audited is not
redistributed; the repository gives their addresses and the commits that were run.
