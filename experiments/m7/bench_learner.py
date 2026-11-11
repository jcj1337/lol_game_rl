"""Learner-side throughput on this machine's CPU, for the pilot budget.

Times a shared policy-value network of the size the predecessor used, scaled to the
ten-champion observation: batched inference (agent decisions per second) and a PPO-style
minibatch update (transitions per second). No environment is involved.

Run: .venv/Scripts/python.exe -m experiments.m7.bench_learner
Needs torch (pip install torch --index-url https://download.pytorch.org/whl/cpu).
"""

import json
import statistics
import time
from pathlib import Path

import torch
from torch import nn

OBS_DIM = 256
N_ACTIONS = 64
HIDDEN = 256
RUNS = 7
RESULTS = Path(__file__).parent / "results" / "learner.json"


def make_net() -> nn.Module:
    return nn.Sequential(
        nn.Linear(OBS_DIM, HIDDEN), nn.Tanh(),
        nn.Linear(HIDDEN, HIDDEN), nn.Tanh(),
        nn.Linear(HIDDEN, N_ACTIONS + 1),
    )


def time_inference(net: nn.Module, batch: int, seconds: float = 1.0) -> float:
    obs = torch.randn(batch, OBS_DIM)
    mask = torch.rand(batch, N_ACTIONS) > 0.3
    done, checksum = 0, 0.0
    start = time.perf_counter()
    with torch.no_grad():
        while time.perf_counter() - start < seconds:
            out = net(obs)
            logits = out[:, :N_ACTIONS].masked_fill(~mask, -1e9)
            action = torch.distributions.Categorical(logits=logits).sample()
            checksum += float(action.sum())
            done += batch
    assert checksum > 0
    return done / (time.perf_counter() - start)


def time_update(net: nn.Module, minibatch: int, seconds: float = 2.0) -> float:
    opt = torch.optim.Adam(net.parameters(), lr=3e-4)
    obs = torch.randn(minibatch, OBS_DIM)
    actions = torch.randint(0, N_ACTIONS, (minibatch,))
    advantages = torch.randn(minibatch)
    returns = torch.randn(minibatch)
    old_logp = torch.full((minibatch,), -3.0)
    before = [p.detach().clone() for p in net.parameters()]
    done = 0
    start = time.perf_counter()
    while time.perf_counter() - start < seconds:
        out = net(obs)
        dist = torch.distributions.Categorical(logits=out[:, :N_ACTIONS])
        ratio = torch.exp(dist.log_prob(actions) - old_logp)
        policy_loss = -torch.min(ratio * advantages, ratio.clamp(0.8, 1.2) * advantages).mean()
        value_loss = (out[:, N_ACTIONS] - returns).pow(2).mean()
        loss = policy_loss + 0.5 * value_loss - 0.01 * dist.entropy().mean()
        opt.zero_grad()
        loss.backward()
        opt.step()
        done += minibatch
    elapsed = time.perf_counter() - start
    assert any(not torch.equal(a, b) for a, b in zip(before, net.parameters())), "weights did not move"
    return done / elapsed


def summarize(samples: list[float]) -> dict:
    return {"median": round(statistics.median(samples)), "min": round(min(samples)), "max": round(max(samples)),
            "runs": len(samples)}


def main() -> None:
    out = {"torch": torch.__version__, "obs_dim": OBS_DIM, "n_actions": N_ACTIONS, "hidden": HIDDEN, "device": "cpu"}
    for threads in (1, 6):
        torch.set_num_threads(threads)
        net = make_net()
        key = f"threads_{threads}"
        out[key] = {
            "inference_batch_10_decisions_per_s": summarize([time_inference(net, 10) for _ in range(RUNS)]),
            "inference_batch_640_decisions_per_s": summarize([time_inference(net, 640) for _ in range(RUNS)]),
            "update_minibatch_256_transitions_per_s": summarize([time_update(net, 256) for _ in range(RUNS)]),
            "update_minibatch_2048_transitions_per_s": summarize([time_update(net, 2048) for _ in range(RUNS)]),
        }
        print(key, json.dumps(out[key], indent=1))
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
