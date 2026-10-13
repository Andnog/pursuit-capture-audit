"""MAPPO actor-critic for the multi-agent ambush (A-103).

Each pursuer is an agent with a shared (parameter-sharing) actor that scores its own candidate
tokens: blocking slots (one lane of one exit of one of the next junctions on the evader's predicted
path), CHASE and STAY. The critic is centralised: it maps a fixed-size global state to a value.
The actor head is an MLP or a KAN (`option_policy.KANLinear`, verified against pykan).
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn

from .option_policy import KANLinear

SLOT_FEATURES = (
    "is_chase",
    "is_stay",
    "depth",
    "exit_rank",
    "lane_index",
    "my_slack",
    "best_other_slack",
    "teammates_targeting",
    "junction_lanes",
    "n_exits",
    "is_my_target",
    "in_place",
)
AGENT_CTX = (
    "team",
    "time",
    "evader_speed",
    "my_speed",
    "my_distance",
    "coverage_next",
    "has_target",
)
GLOBAL_STATE = (
    "team",
    "time",
    "evader_speed",
    "coverage_j1",
    "coverage_j2",
    "min_distance",
    "mean_distance",
)
N_SLOT, N_ACTX, N_GLOBAL = len(SLOT_FEATURES), len(AGENT_CTX), len(GLOBAL_STATE)


class MappoActorCritic(nn.Module):
    def __init__(self, head: str = "mlp", hidden: int = 64, kan_hidden: int = 8):
        super().__init__()
        self.head = head
        d = N_SLOT + N_ACTX
        if head == "kan":
            self.actor = nn.Sequential(KANLinear(d, kan_hidden), KANLinear(kan_hidden, 1))
        else:
            self.actor = nn.Sequential(
                nn.Linear(d, hidden),
                nn.Tanh(),
                nn.Linear(hidden, hidden),
                nn.Tanh(),
                nn.Linear(hidden, 1),
            )
        self.critic = nn.Sequential(
            nn.Linear(N_GLOBAL, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh(), nn.Linear(64, 1)
        )

    def logits(self, tokens: torch.Tensor, ctx: torch.Tensor) -> torch.Tensor:
        x = torch.cat([tokens, ctx.expand(tokens.shape[0], -1)], dim=1)
        return self.actor(x).squeeze(-1)

    def value(self, g: torch.Tensor) -> torch.Tensor:
        return self.critic(g).squeeze(-1)


def act(model, tokens: np.ndarray, ctx: np.ndarray, mode: str, rng, forced=None):
    t = torch.from_numpy(tokens.astype(np.float32))
    c = torch.from_numpy(ctx.astype(np.float32))
    with torch.no_grad():
        lg = model.logits(t, c)
    dist = torch.distributions.Categorical(logits=lg)
    if forced is not None:
        idx = forced
    elif mode == "greedy":
        idx = int(torch.argmax(lg))
    elif mode == "random":
        idx = rng.randrange(len(tokens))
    else:
        idx = int(dist.sample())
    return idx, float(dist.log_prob(torch.tensor(idx)))


def act_seeded(model, tokens: np.ndarray, ctx: np.ndarray, mode: str, rng, forced=None):
    """As `act`, but a sampled index is drawn from `rng` and from nothing else (A-133, F4-2).

    `act` samples with PyTorch's global generator, so a rollout could not be reproduced from the
    seed of its controller, and its noise depended on which worker ran it. Here the index is
    drawn by inverse CDF from a single `rng.random()` per decision (`rng` is a `random.Random`).
    The returned log-probability is the model's log-probability of the returned index.
    """
    t = torch.from_numpy(tokens.astype(np.float32))
    c = torch.from_numpy(ctx.astype(np.float32))
    with torch.no_grad():
        logp = torch.log_softmax(model.logits(t, c), dim=0)
    if forced is not None:
        idx = forced
    elif mode == "greedy":
        idx = int(torch.argmax(logp))
    elif mode == "random":
        idx = rng.randrange(len(tokens))
    else:
        u, acc, idx = rng.random(), 0.0, len(tokens) - 1
        for k, p in enumerate(torch.exp(logp.double()).tolist()):
            acc += p
            if u < acc:
                idx = k
                break
    return idx, float(logp[idx])
