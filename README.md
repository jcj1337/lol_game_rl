# League of Legends — Multi-Agent Reinforcement Learning

> An ongoing research project exploring whether agents can learn League of Legends macro strategy through multi-agent reinforcement learning and self-play.

**Status:** Building the full-map foundation (roadmap milestone M8). Six of its eight checkpoints pass their criteria, including fog of war, wards, and scripted ten-champion games. A seventh (lanes and waves) is built but not complete, the last (scenarios and the comparison harness) has not started, and nothing is validated against the real game yet · See the [Roadmap](docs/ROADMAP.md)

---

## Overview

The goal is to build a simplified but strategically faithful simulation of the full game. Agents will learn to make macro decisions without being explicitly taught any strategy, including:

- **Wave management**
- **Jungle pathing**
- **Vision**
- **Rotations**
- **Objectives**

The simulator does not try to recreate League's mechanics (atleast for now) exactly. It focuses on **high-level decision-making** and uses abstractions for combat, champions, and other complex interactions.

## Long-Term Goal

The eventual goal is a **post-game decision review tool**, similar in concept to how chess engines evaluate moves.

Given a game state, the system would compare possible actions and identify the strategically preferable ones, helping players understand what they did well and what they could have done differently.

## Development

The simulator's foundation is under construction in `riftgame/`. No agent has been trained on it yet.

See [ROADMAP.md](docs/ROADMAP.md) for the milestones, research goals, and development plan, and [docs/design/M8_foundation.md](docs/design/M8_foundation.md) for what is built, how it is tested, and what is still open.

## Previous Work

This project builds on [**Laning as a Two-Player Game**](https://github.com/jcj1337/lol_laning_gt_rl), which explored emergent laning strategies using game theory and PPO self-play in a simplified two-player environment.
