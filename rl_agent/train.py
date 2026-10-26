"""
Pre-training and Evaluation pipeline for Double DQN Cyber Defender Agent.
Trains agent against multi-stage APT attacker and generates performance telemetry.
"""

import os
import json
import time
from typing import Dict, List, Any
import numpy as np
import torch

from cyberbattle_env.env import CyberDefenderEnv
from cyberbattle_env.attacker import ThreatLevel
from rl_agent.double_dqn import DoubleDQNAgent


def train_cyber_defender(
    num_episodes: int = 400,
    max_steps_per_episode: int = 40,
    save_path: str = "models/double_dqn_defender.pth",
    metrics_path: str = "models/training_metrics.json",
    replay_path: str = "models/replay_buffer.pth",
    threat_level: ThreatLevel = ThreatLevel.AGGRESSIVE_APT,
    resume: bool = True,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Trains the Double DQN agent on the enterprise network against the APT threat actor.
    Can resume from existing checkpoints and incorporate saved fine-tuning experience.
    """
    env = CyberDefenderEnv(threat_level=threat_level, max_steps=max_steps_per_episode)
    agent = DoubleDQNAgent(state_dim=64, action_dim=40)

    # Resume from checkpoint if present
    is_resumed = False
    if resume and os.path.exists(save_path):
        try:
            agent.load_checkpoint(save_path)
            is_resumed = True
            print(f"[✓] Loaded existing model weights from: {save_path}")
        except Exception as e:
            print(f"[!] Warning: Could not load model checkpoint ({e}). Starting fresh.")

    # Load previously collected fine-tuning replay buffer experiences
    if resume and os.path.exists(replay_path):
        try:
            agent.replay_buffer.load_from_disk(replay_path)
            print(f"[✓] Loaded {len(agent.replay_buffer)} fine-tuning transitions into Experience Replay Buffer!")
        except Exception as e:
            print(f"[!] Warning: Could not load replay buffer ({e}).")

    # Exploration parameters: start lower if resuming so we don't wipe out learned defense
    if is_resumed:
        epsilon_start = 0.25
        epsilon_decay = 0.990
    else:
        epsilon_start = 1.0
        epsilon_decay = 0.992

    epsilon_end = 0.05
    epsilon = epsilon_start

    # Metrics tracking
    episode_rewards: List[float] = []
    episode_lengths: List[int] = []
    outcomes: Dict[str, int] = {
        "DEFENDER_WON_TRAPPED": 0,
        "DEFENDER_WON_TIMEOUT": 0,
        "ATTACKER_WON_BREACH": 0,
    }
    moving_avg_rewards: List[float] = []
    win_rates: List[float] = []
    loss_history: List[float] = []

    mode_str = "Resumed Training with Fine-Tuning Experience" if is_resumed else "Fresh Training"
    print(f"[*] Starting Double DQN ({mode_str}: {num_episodes} episodes)...")
    start_time = time.time()

    for episode in range(1, num_episodes + 1):
        state = env.reset()
        episode_reward = 0.0
        step_count = 0
        losses = []

        for step in range(max_steps_per_episode):
            step_count += 1
            action, _ = agent.select_action(state, epsilon=epsilon)
            next_state, reward, done, info = env.step(action)

            loss = agent.step(state, action, reward, next_state, done)
            if loss is not None:
                losses.append(loss)

            state = next_state
            episode_reward += reward

            if done:
                break

        # Decay exploration epsilon
        epsilon = max(epsilon_end, epsilon * epsilon_decay)

        # Record metrics
        episode_rewards.append(round(episode_reward, 2))
        episode_lengths.append(step_count)
        result = info.get("result", "UNKNOWN")
        if result in outcomes:
            outcomes[result] += 1

        # Compute moving averages (window = 25)
        window = min(25, len(episode_rewards))
        avg_r = float(np.mean(episode_rewards[-window:]))
        moving_avg_rewards.append(round(avg_r, 2))

        # Win rate (Defender Trapped or Timeout)
        total_played = episode
        wins = outcomes["DEFENDER_WON_TRAPPED"] + outcomes["DEFENDER_WON_TIMEOUT"]
        current_win_rate = round(float(wins / total_played) * 100.0, 1)
        win_rates.append(current_win_rate)

        if losses:
            loss_history.append(round(float(np.mean(losses)), 4))

        if verbose and (episode % 50 == 0 or episode == num_episodes):
            elapsed = time.time() - start_time
            print(
                f"[Episode {episode:03d}/{num_episodes}] "
                f"Reward: {episode_reward:6.1f} | "
                f"Avg(25): {avg_r:6.1f} | "
                f"Epsilon: {epsilon:.3f} | "
                f"Win Rate: {current_win_rate:4.1f}% | "
                f"Breaches: {outcomes['ATTACKER_WON_BREACH']} | "
                f"Trapped: {outcomes['DEFENDER_WON_TRAPPED']} | "
                f"Time: {elapsed:.1f}s"
            )

    # Save model weights and replay buffer
    agent.save_checkpoint(save_path)
    agent.replay_buffer.save_to_disk(replay_path)
    print(f"[✓] Model checkpoint saved to: {save_path}")
    print(f"[✓] Replay memory buffer ({len(agent.replay_buffer)} transitions) saved to: {replay_path}")

    # Prepare summary metrics dictionary (merge if resuming)
    metrics = {
        "num_episodes": num_episodes,
        "final_epsilon": round(epsilon, 4),
        "total_training_time_sec": round(time.time() - start_time, 2),
        "outcomes": outcomes,
        "final_win_rate_pct": win_rates[-1] if win_rates else 0.0,
        "episode_rewards": episode_rewards,
        "moving_avg_rewards": moving_avg_rewards,
        "win_rates": win_rates,
        "episode_lengths": episode_lengths,
        "loss_history": loss_history[-200:],  # Recent loss trend
    }

    if is_resumed and os.path.exists(metrics_path):
        try:
            with open(metrics_path, "r", encoding="utf-8") as f:
                prev_metrics = json.load(f)
            prev_num = prev_metrics.get("num_episodes", 0)
            metrics["num_episodes"] = prev_num + num_episodes
            metrics["outcomes"]["DEFENDER_WON_TRAPPED"] = prev_metrics.get("outcomes", {}).get("DEFENDER_WON_TRAPPED", 0) + outcomes["DEFENDER_WON_TRAPPED"]
            metrics["outcomes"]["DEFENDER_WON_TIMEOUT"] = prev_metrics.get("outcomes", {}).get("DEFENDER_WON_TIMEOUT", 0) + outcomes["DEFENDER_WON_TIMEOUT"]
            metrics["outcomes"]["ATTACKER_WON_BREACH"] = prev_metrics.get("outcomes", {}).get("ATTACKER_WON_BREACH", 0) + outcomes["ATTACKER_WON_BREACH"]
            
            # Combine history arrays
            metrics["episode_rewards"] = prev_metrics.get("episode_rewards", []) + episode_rewards
            metrics["moving_avg_rewards"] = prev_metrics.get("moving_avg_rewards", []) + moving_avg_rewards
            metrics["win_rates"] = prev_metrics.get("win_rates", []) + win_rates
            metrics["episode_lengths"] = prev_metrics.get("episode_lengths", []) + episode_lengths
            metrics["total_training_time_sec"] = round(prev_metrics.get("total_training_time_sec", 0.0) + (time.time() - start_time), 2)
            
            # Overall win rate calculation
            tot_played = metrics["num_episodes"]
            tot_won = metrics["outcomes"]["DEFENDER_WON_TRAPPED"] + metrics["outcomes"]["DEFENDER_WON_TIMEOUT"]
            metrics["final_win_rate_pct"] = round(float(tot_won / tot_played) * 100.0, 1)
        except Exception as e:
            print(f"[!] Note: Could not merge existing metrics ({e}), saving current.")

    os.makedirs(os.path.dirname(metrics_path), exist_ok=True)
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"[✓] Cumulative training metrics saved to: {metrics_path} (Total: {metrics['num_episodes']} episodes)")

    return metrics


if __name__ == "__main__":
    import sys
    fresh_start = "--fresh" in sys.argv
    episodes = 400
    for arg in sys.argv:
        if arg.startswith("--episodes="):
            try:
                episodes = int(arg.split("=")[1])
            except ValueError:
                pass
    train_cyber_defender(num_episodes=episodes, resume=not fresh_start, verbose=True)
