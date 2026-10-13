"""Option scorer for the learned ambush (A-96): MLP or KAN head over ambush options.

Each decision offers a small set of options (chase, keep the current plan, full or partial
lane-level blocking at one of the next junctions). Each option is a token of OPT_FEATURES; the
decision context has CTX_FEATURES. The scorer maps [token, context] to a logit; a softmax over the
offered options is the policy. The critic maps the context to a value (always an MLP, so the two
heads differ only in the scorer).

KANLinear: Kolmogorov-Arnold layer with learnable cubic B-spline functions on every edge plus a
SiLU base term (efficient-KAN formulation), implemented here to avoid a new dependency.
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn

OPT_FEATURES = (
    "is_chase",
    "is_keep",
    "is_full",
    "is_partial",
    "depth",
    "lanes_to_close",
    "min_slack",
    "mean_slack",
    "evader_time_to_junction",
    "exit_fraction_covered",
    "covers_predicted_exit",
    "n_exits",
)
CTX_FEATURES = ("team", "n_options", "time", "has_plan", "nearest_pursuer_distance", "evader_speed")
N_OPT = len(OPT_FEATURES)
N_CTX = len(CTX_FEATURES)
KAN_LO, KAN_HI = -1.5, 3.0


class KANLinear(nn.Module):
    def __init__(self, in_f: int, out_f: int, grid: int = 8, order: int = 3):
        super().__init__()
        h = (KAN_HI - KAN_LO) / grid
        pts = torch.arange(-order, grid + order + 1, dtype=torch.float32) * h + KAN_LO
        self.register_buffer("grid", pts.expand(in_f, -1).contiguous())
        self.order = order
        self.base = nn.Linear(in_f, out_f)
        self.spline = nn.Parameter(torch.randn(out_f, in_f, grid + order) * 0.05)

    def b_splines(self, x: torch.Tensor) -> torch.Tensor:
        g = self.grid
        x = x.clamp(KAN_LO, KAN_HI - 1e-4).unsqueeze(-1)
        bases = ((x >= g[:, :-1]) & (x < g[:, 1:])).to(x.dtype)
        for k in range(1, self.order + 1):
            left = (x - g[:, : -(k + 1)]) / (g[:, k:-1] - g[:, : -(k + 1)]) * bases[:, :, :-1]
            right = (g[:, k + 1 :] - x) / (g[:, k + 1 :] - g[:, 1:(-k)]) * bases[:, :, 1:]
            bases = left + right
        return bases

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        spl = torch.einsum("bik,oik->bo", self.b_splines(x), self.spline)
        return self.base(nn.functional.silu(x)) + spl

    def edge_function(self, i: int, o: int, xs: torch.Tensor) -> torch.Tensor:
        """phi_{o,i}(x) for interpretation: base + spline contribution of input i to output o."""
        x = torch.zeros(len(xs), self.base.in_features)
        x[:, i] = xs
        b = self.b_splines(x)[:, i, :]
        return self.base.weight[o, i] * nn.functional.silu(xs) + b @ self.spline[o, i]


class OptionScorer(nn.Module):
    def __init__(self, head: str = "mlp", hidden: int = 64, kan_hidden: int = 8):
        super().__init__()
        self.head = head
        d = N_OPT + N_CTX
        if head == "kan":
            self.scorer = nn.Sequential(KANLinear(d, kan_hidden), KANLinear(kan_hidden, 1))
        else:
            self.scorer = nn.Sequential(
                nn.Linear(d, hidden),
                nn.Tanh(),
                nn.Linear(hidden, hidden),
                nn.Tanh(),
                nn.Linear(hidden, 1),
            )
        self.value = nn.Sequential(nn.Linear(N_CTX, 64), nn.Tanh(), nn.Linear(64, 1))

    def logits(self, tokens: torch.Tensor, ctx: torch.Tensor) -> torch.Tensor:
        x = torch.cat([tokens, ctx.expand(tokens.shape[0], -1)], dim=1)
        return self.scorer(x).squeeze(-1)


def decide(model: OptionScorer, tokens: np.ndarray, ctx: np.ndarray, mode: str, rng, forced=None):
    """Returns (index, logp, value). mode: sample | greedy | random | forced."""
    t = torch.from_numpy(tokens.astype(np.float32))
    c = torch.from_numpy(ctx.astype(np.float32))
    with torch.no_grad():
        lg = model.logits(t, c)
        value = float(model.value(c))
    dist = torch.distributions.Categorical(logits=lg)
    if forced is not None:
        idx = forced
    elif mode == "greedy":
        idx = int(torch.argmax(lg))
    elif mode == "random":
        idx = rng.randrange(len(tokens))
    else:
        idx = int(dist.sample())
    return idx, float(dist.log_prob(torch.tensor(idx))), value
