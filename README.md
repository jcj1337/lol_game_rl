# League of Legends — Multi-Agent Reinforcement Learning

> An ongoing research project exploring whether agents can learn League of Legends macro strategy through multi-agent reinforcement learning and self-play.

**Status:** Planning and design stage · See the [Roadmap](docs/ROADMAP.md)

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

The project is currently in the planning and design stage.

See [ROADMAP.md](docs/ROADMAP.md) for the proposed milestones, research goals, and development plan.

## Previous Work

This project builds on [**Laning as a Two-Player Game**](https://github.com/jcj1337/lol_laning_gt_rl), which explored emergent laning strategies using game theory and PPO self-play in a simplified two-player environment.
