"""Token policy for the caging MARL pilot (docs/MARL_DESIGN_EN.md).

One network serves both arms: a SCORER maps each candidate token (6 features) plus the global
context (7 features) to a logit; two extra logits (CHASE, HOLD) come from the context alone; a
centralized critic maps the context to a value. Arms differ only in their candidate set (T: the
escape gates; U: the junctions the evader reaches soonest).

Joint action: pursuers decide in a fixed order; a token already chosen by an earlier pursuer in
the same decision has its "taken" feature set (autoregressive decoding), so the joint log-prob is
the sum over pursuers and the team is trained with single-agent PPO on the joint action.
"""

from __future__ import annotations

import math

import numpy as np
import torch
from torch import nn

N_FEAT = 9
N_CTX = 7
TAKEN = 5


def _mlp(i, h, o):
    return nn.Sequential(nn.Linear(i, h), nn.Tanh(), nn.Linear(h, h), nn.Tanh(), nn.Linear(h, o))


def norm_tokens(raw: np.ndarray) -> np.ndarray:
    x = raw.astype(np.float32).copy()
    if len(x):
        x[:, :4] = np.clip(x[:, :4] / 60.0, -5.0, 5.0)
        x[:, 4] = x[:, 4] / 4.0
        x[:, 8] = np.clip(x[:, 8] / 60.0, -5.0, 5.0)
    return x


def norm_ctx(raw) -> np.ndarray:
    c = np.asarray(raw, dtype=np.float32).copy()
    c[0] /= 5.0
    c[1] /= 10.0
    c[4] /= 5.0
    return np.clip(c, -5.0, 5.0)


class TokenPolicy(nn.Module):
    def __init__(self, hidden: int = 64):
        super().__init__()
        self.scorer = _mlp(N_FEAT + N_CTX, hidden, 1)
        self.special = _mlp(N_CTX, hidden, 2)
        self.value = _mlp(N_CTX, hidden, 1)

    def logits(self, tokens: torch.Tensor, ctx: torch.Tensor) -> torch.Tensor:
        """tokens (N, 6), ctx (7) -> (N + 2): candidates, then CHASE, HOLD."""
        special = self.special(ctx)
        if tokens.shape[0] == 0:
            return special
        x = torch.cat([tokens, ctx.expand(tokens.shape[0], -1)], dim=1)
        return torch.cat([self.scorer(x).squeeze(-1), special])


def decide(model: TokenPolicy, obs: dict, greedy: bool = False, forced: dict | None = None):
    """Joint action for one decision.

    Returns (actions for the rollout, record) where the record holds, per pursuer in order, the
    token matrix actually scored (with within-decision "taken" flags), the chosen index, and the
    joint log-prob and value. `forced` (BC) fixes each pursuer's index instead of sampling."""
    from .rollout import CHASE, HOLD

    ctx = torch.from_numpy(norm_ctx(obs["_state"]))
    pursuers = sorted(k for k in obs if not k.startswith("_"))
    chosen_nodes: set[str] = set()
    actions, steps = {}, []
    logp_total = 0.0
    with torch.no_grad():
        value = float(model.value(ctx))
    for vid in pursuers:
        names = [g for g, _ in obs[vid]]
        raw = np.array([f for _, f in obs[vid]], dtype=np.float32).reshape(-1, N_FEAT)
        for i, g in enumerate(names):
            if g in chosen_nodes:
                raw[i, TAKEN] = 1.0
        feats = norm_tokens(raw)
        with torch.no_grad():
            lg = model.logits(torch.from_numpy(feats), ctx)
        dist = torch.distributions.Categorical(logits=lg)
        if forced is not None:
            idx = forced[vid]
        elif greedy:
            idx = int(torch.argmax(lg))
        else:
            idx = int(dist.sample())
        logp_total += float(dist.log_prob(torch.tensor(idx)))
        n = len(names)
        if idx < n:
            actions[vid] = idx
            chosen_nodes.add(names[idx])
        else:
            actions[vid] = CHASE if idx == n else HOLD
        steps.append((feats, idx))
    return actions, {
        "ctx": norm_ctx(obs["_state"]),
        "steps": steps,
        "logp": logp_total,
        "value": value,
    }


def joint_logp_entropy(model: TokenPolicy, record: dict):
    ctx = torch.from_numpy(record["ctx"])
    logp = torch.zeros(())
    ent = torch.zeros(())
    for feats, idx in record["steps"]:
        dist = torch.distributions.Categorical(logits=model.logits(torch.from_numpy(feats), ctx))
        logp = logp + dist.log_prob(torch.tensor(idx))
        ent = ent + dist.entropy()
    # A-80: mean entropy per pursuer (the summed joint entropy dominated PPO's objective).
    return logp, ent / max(1, len(record["steps"]))


def to_index(obs_tokens, action) -> int:
    """Rollout action (token index, CHASE or HOLD) -> network index."""
    from .rollout import CHASE, HOLD

    n = len(obs_tokens)
    if action == CHASE:
        return n
    if action == HOLD:
        return n + 1
    return int(action)


def gae(rewards, values, gamma=0.99, lam=0.95):
    adv = [0.0] * len(rewards)
    last = 0.0
    for t in reversed(range(len(rewards))):
        nxt = values[t + 1] if t + 1 < len(values) else 0.0
        delta = rewards[t] + gamma * nxt - values[t]
        last = delta + gamma * lam * last
        adv[t] = last
    return adv, [a + v for a, v in zip(adv, values, strict=False)]


def finite(x: float) -> float:
    return x if math.isfinite(x) else 0.0
