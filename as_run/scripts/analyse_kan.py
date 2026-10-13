"""KAN interpretability analysis for the learned ambush selector (A-96, descriptive, post-test).

Inputs: the package state (best MLP and KAN checkpoints) and the rule-demonstration decisions (the
states the policies face). Outputs (KAN_ANALYSIS.json):
- permutation importance: for each feature, the share of decisions whose greedy choice changes when
  that feature is shuffled across the dataset (10 random permutations, mean and s.d.), for the
  trained KAN, the trained MLP, and a randomly initialised KAN (control);
- KAN first-layer edge amplitude per input (mean |phi| over observed values, summed over units);
- partial-dependence curves of the KAN logit for the top features (others held at their medians);
- agreement of each trained model with the rule on the same decisions.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import pickle
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


def main() -> int:
    import numpy as np
    import torch

    from joint_interception.rl.option_policy import CTX_FEATURES, OPT_FEATURES, OptionScorer

    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--perms", type=int, default=10)
    parser.add_argument("--max-decisions", type=int, default=3000)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    with open(os.path.join(package, "state.pkl"), "rb") as h:
        st = pickle.load(h)
    rng = random.Random(11)
    data = list(st["demos"])
    rng.shuffle(data)
    data = data[: args.max_decisions]
    names = list(OPT_FEATURES) + list(CTX_FEATURES)

    def load(head, blob):
        m = OptionScorer(head)
        if blob is not None:
            m.load_state_dict(torch.load(io.BytesIO(blob), weights_only=True))
        m.eval()
        return m

    models = {}
    for name, run in st["runs"].items():
        if run.get("done"):
            models[name] = load(name.split("_s")[0], run["best_model"])
    torch.manual_seed(123)
    models["kan_random_init"] = load("kan", None)

    def choices(model, toks, ctxs):
        out = []
        with torch.no_grad():
            for t, c in zip(toks, ctxs, strict=True):
                out.append(
                    int(torch.argmax(model.logits(torch.from_numpy(t), torch.from_numpy(c))))
                )
        return out

    toks = [r["tokens"] for r in data]
    ctxs = [r["ctx"] for r in data]
    rule = [r["rule_idx"] for r in data]
    result = {"decisions": len(data), "features": names, "models": {}}
    for mname, model in models.items():
        base = choices(model, toks, ctxs)
        agree_rule = sum(a == b for a, b in zip(base, rule, strict=True)) / len(rule)
        imp = {}
        for f, fname in enumerate(names):
            vals = []
            for p in range(args.perms):
                prng = np.random.default_rng(1000 * f + p)
                if f < len(OPT_FEATURES):
                    pool = np.concatenate([t[:, f] for t in toks])
                    perm = prng.permutation(pool)
                    new_t, k = [], 0
                    for t in toks:
                        t2 = t.copy()
                        t2[:, f] = perm[k : k + len(t)]
                        k += len(t)
                        new_t.append(t2)
                    new_c = ctxs
                else:
                    j = f - len(OPT_FEATURES)
                    perm = prng.permutation(np.array([c[j] for c in ctxs]))
                    new_c = []
                    for c, v in zip(ctxs, perm, strict=True):
                        c2 = c.copy()
                        c2[j] = v
                        new_c.append(c2)
                    new_t = toks
                ch = choices(model, new_t, new_c)
                vals.append(sum(a != b for a, b in zip(ch, base, strict=True)) / len(base))
            imp[fname] = [round(float(np.mean(vals)), 4), round(float(np.std(vals)), 4)]
        entry = {"agreement_with_rule": round(agree_rule, 4), "permutation_importance": imp}
        if model.head == "kan":
            layer = model.scorer[0]
            x_all = torch.from_numpy(
                np.concatenate(
                    [
                        np.concatenate([t, np.repeat(c[None], len(t), 0)], 1)
                        for t, c in zip(toks, ctxs, strict=True)
                    ]
                )
            )
            amp = {}
            with torch.no_grad():
                for i, fname in enumerate(names):
                    xs = x_all[:, i]
                    total = 0.0
                    for o in range(layer.base.out_features):
                        total += float(layer.edge_function(i, o, xs).abs().mean())
                    amp[fname] = round(total, 4)
            entry["kan_first_layer_amplitude"] = amp
            # Partial dependence of the logit on the top-4 token features.
            top = sorted([n for n in OPT_FEATURES], key=lambda n: -imp[n][0])[:4]
            med_t = np.median(np.concatenate(toks), axis=0).astype(np.float32)
            med_c = np.median(np.stack(ctxs), axis=0).astype(np.float32)
            pdp = {}
            with torch.no_grad():
                for fname in top:
                    f = names.index(fname)
                    col = np.concatenate([t[:, f] for t in toks])
                    grid = np.linspace(
                        float(np.percentile(col, 2)), float(np.percentile(col, 98)), 15
                    )
                    ys = []
                    for g in grid:
                        t = med_t.copy()
                        t[f] = g
                        ys.append(
                            float(model.logits(torch.from_numpy(t[None]), torch.from_numpy(med_c)))
                        )
                    pdp[fname] = {
                        "x": [round(float(v), 3) for v in grid],
                        "logit": [round(v, 4) for v in ys],
                    }
            entry["partial_dependence"] = pdp
        result["models"][mname] = entry
        print(
            mname,
            "agree_rule",
            entry["agreement_with_rule"],
            "top",
            sorted(imp, key=lambda n: -imp[n][0])[:5],
            flush=True,
        )
    with open(os.path.join(package, "KAN_ANALYSIS.json"), "w", encoding="utf-8") as h:
        json.dump(result, h, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
