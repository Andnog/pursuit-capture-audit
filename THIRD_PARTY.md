# Code of other authors that the study ran

Two studies of this repository audit the capture events of the official environments of two
published methods. Their code is not redistributed here. To run those studies again, clone each
repository at the commit below into `as_run/third_party/`:

| Environment | Repository | Commit | Studies |
|---|---|---|---|
| DGMARL-MVP | <https://github.com/BUPT-ANTlab/DGMARL-MVP> | `62bd72e2a6ae94c1b5afba0ddee89aeee5ea9257` | `20261005_published_env_audit_r01`, `20261005_published_env_audit_r02` |
| PEPCRL-MVP | <https://github.com/BUPT-ANTlab/PEPCRL-MVP> | `ac8ca695ed9defc8728ede131a4840f7949b4c31` | `20261005_published_env_pepcrl_r01` |

```bash
mkdir -p as_run/third_party && cd as_run/third_party
git clone https://github.com/BUPT-ANTlab/DGMARL-MVP && git -C DGMARL-MVP checkout 62bd72e2a6ae94c1b5afba0ddee89aeee5ea9257
git clone https://github.com/BUPT-ANTlab/PEPCRL-MVP && git -C PEPCRL-MVP checkout ac8ca695ed9defc8728ede131a4840f7949b4c31
```

The audits ran that code without modifying it and observed its capture events. They used the
released configurations, which differ from the ones reported in the articles, and a later version
of the simulator; they did not train the published learners. They say what the capture rule of
each environment rewards, not how good the published methods are. Both environments come from one
research group.

The software that this project depends on, with versions and licences, is listed in
[`as_run/THIRD_PARTY_NOTICES.md`](as_run/THIRD_PARTY_NOTICES.md).
