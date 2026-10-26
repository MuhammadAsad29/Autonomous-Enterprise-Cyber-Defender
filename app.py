"""
CyberBattle-RL: Autonomous Enterprise Cyber Defense Web Application.
Production Flask backend serving interactive Cyber SOC dashboard and RL simulation engine.
"""

import os
import json
import time
from typing import Dict, Any
import numpy as np
import torch
from flask import Flask, render_template, jsonify, request

from cyberbattle_env.env import CyberDefenderEnv
from cyberbattle_env.attacker import ThreatLevel
from rl_agent.double_dqn import DoubleDQNAgent

app = Flask(__name__)

# Global instances for the interactive session
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "double_dqn_defender.pth")
METRICS_PATH = os.path.join(os.path.dirname(__file__), "models", "training_metrics.json")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
EXPERIENCE_LOG_PATH = os.path.join(DATA_DIR, "fine_tuning_experience.jsonl")
REPLAY_BUFFER_PATH = os.path.join(os.path.dirname(__file__), "models", "replay_buffer.pth")
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize Environment & Double DQN Agent
env = CyberDefenderEnv(threat_level=ThreatLevel.AGGRESSIVE_APT, max_steps=50)
agent = DoubleDQNAgent(state_dim=64, action_dim=40)

# Load pre-trained model weights if present
if os.path.exists(MODEL_PATH):
    try:
        agent.load_checkpoint(MODEL_PATH)
        print(f"[✓] Successfully loaded Double DQN weights from {MODEL_PATH}")
    except Exception as e:
        print(f"[!] Warning: Could not load checkpoint ({e}). Using initialized weights.")

current_obs = env.reset()
cumulative_session_reward = 0.0
defense_mode = "Double DQN"  # "Double DQN", "Heuristic", "Random"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "CyberBattle-RL Autonomous Enterprise Cyber Defense",
        "model_loaded": os.path.exists(MODEL_PATH),
    })


@app.route("/api/state", methods=["GET"])
def get_state():
    """Returns complete network topology, node statuses, alerts, and simulation telemetry."""
    state_dict = env.get_full_state_dict()
    state_dict["cumulative_reward"] = round(cumulative_session_reward, 1)
    state_dict["defense_mode"] = defense_mode
    return jsonify(state_dict)


@app.route("/api/step", methods=["POST"])
def step_simulation():
    """
    Executes one turn of cyber defense and attack.
    Returns evaluated Q-values, action taken, telemetry log, and updated network topology.
    """
    global current_obs, cumulative_session_reward

    data = request.get_json(silent=True) or {}
    manual_action = data.get("action_id", None)

    # 1. Action Selection
    q_values_list = []
    if manual_action is not None:
        action = int(manual_action)
        # Compute Q-values for visualization even during manual action
        _, q_vals = agent.select_action(current_obs, epsilon=0.0)
        q_values_list = [round(float(q), 3) for q in q_vals]
    elif defense_mode == "Random":
        action = int(np.random.randint(40))
        q_values_list = [round(float(np.random.uniform(-5.0, 5.0)), 3) for _ in range(40)]
    elif defense_mode == "Heuristic":
        # Heuristic baseline: prioritize honeypot on perimeter, isolate alerted hosts, re-image compromised
        # 1. Check for compromised hosts to re-image (Action 10 + nid)
        compromised_nodes = [nid for nid, n in env.topology.nodes.items() if n.status.value in ["Compromised", "Owned (Admin)"]]
        if compromised_nodes:
            action = 10 + compromised_nodes[0]
        # 2. Check for high alert hosts to isolate (Action 0 + nid)
        elif any(n.alert_level > 0.6 and not n.is_isolated for n in env.topology.nodes.values()):
            alerted = [nid for nid, n in env.topology.nodes.items() if n.alert_level > 0.6 and not n.is_isolated]
            action = 0 + alerted[0]
        # 3. Deploy honeypot on slot 9 (Action 20 + 9)
        elif not env.topology.nodes[9].is_decoy:
            action = 29
        else:
            action = int(np.random.randint(40))
        _, q_vals = agent.select_action(current_obs, epsilon=0.0)
        q_values_list = [round(float(q), 3) for q in q_vals]
    else:  # Double DQN Agent
        action, q_vals = agent.select_action(current_obs, epsilon=0.0)
        q_values_list = [round(float(q), 3) for q in q_vals]

    # 2. Environment Step
    next_obs, reward, done, step_info = env.step(action)
    current_obs = next_obs
    cumulative_session_reward += reward

    # Format top 5 Q-value actions for UI display
    indexed_q = list(enumerate(q_values_list))
    indexed_q.sort(key=lambda x: x[1], reverse=True)
    top_actions = []
    for act_idx, q_val in indexed_q[:6]:
        act_type = act_idx // 10
        act_target = act_idx % 10
        top_actions.append({
            "action_id": act_idx,
            "action_type": env.ACTION_NAMES[act_type],
            "target_node": env.topology.nodes[act_target].name,
            "q_value": q_val,
        })

    net_state = env.get_full_state_dict()
    net_state["cumulative_reward"] = round(cumulative_session_reward, 1)
    net_state["defense_mode"] = defense_mode

    response_data = {
        "step_info": step_info,
        "q_values": q_values_list,
        "top_actions": top_actions,
        "done": done,
        "cumulative_reward": round(cumulative_session_reward, 1),
        "network_state": net_state,
    }
    return jsonify(response_data)


@app.route("/api/reset", methods=["POST"])
def reset_simulation():
    """Resets the enterprise network and threat state to clean baseline."""
    global current_obs, cumulative_session_reward
    current_obs = env.reset()
    cumulative_session_reward = 0.0
    state_dict = env.get_full_state_dict()
    state_dict["cumulative_reward"] = 0.0
    state_dict["message"] = "Enterprise network restored to clean perimeter baseline."
    return jsonify(state_dict)


@app.route("/api/config", methods=["POST"])
def update_config():
    """Updates threat actor difficulty or defense strategy mode."""
    global defense_mode
    data = request.get_json(silent=True) or {}
    
    if "threat_level" in data:
        env.set_threat_level(data["threat_level"])

    if "defense_mode" in data:
        defense_mode = data["defense_mode"]

    return jsonify({
        "status": "success",
        "threat_level": env.attacker.threat_level.value,
        "defense_mode": defense_mode,
    })


@app.route("/api/metrics", methods=["GET"])
def get_metrics():
    """Returns training convergence metrics and performance curves."""
    if os.path.exists(METRICS_PATH):
        try:
            with open(METRICS_PATH, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
        except Exception as e:
            return jsonify({"error": f"Failed to load metrics: {str(e)}"}), 500
    return jsonify({"error": "Metrics file not found"}), 404


@app.route("/api/train", methods=["POST"])
def run_training_api():
    """Triggers an in-app fine-tuning training pass for N episodes and updates metrics."""
    data = request.get_json(silent=True) or {}
    episodes = min(int(data.get("episodes", 25)), 100)

    try:
        rewards = []
        batch_trapped = 0
        batch_breached = 0
        batch_timeouts = 0

        # Open experience log file to persist fine-tuning dataset
        with open(EXPERIENCE_LOG_PATH, "a", encoding="utf-8") as exp_log:
            for ep_idx in range(episodes):
                s = env.reset()
                ep_r = 0.0
                last_info = {}
                for step_idx in range(40):
                    a, _ = agent.select_action(s, epsilon=0.15)
                    s_next, r, d, info = env.step(a)
                    agent.step(s, a, r, s_next, d)

                    # Persist experience transition record to dataset
                    transition_record = {
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "fine_tune_episode": ep_idx + 1,
                        "step": step_idx + 1,
                        "action_id": int(a),
                        "action_name": env.ACTION_NAMES[a // 10],
                        "target_node": env.topology.nodes[a % 10].name,
                        "target_node_id": a % 10,
                        "reward": float(r),
                        "defense_log": info.get("defense_log", ""),
                        "attacker_log": info.get("attacker_log", ""),
                        "attacker_action": info.get("attacker_action", ""),
                        "active_infections": info.get("active_infections", 0),
                        "isolated_hosts": info.get("isolated_hosts", 0),
                        "done": bool(d),
                        "result": info.get("result", "ONGOING"),
                    }
                    exp_log.write(json.dumps(transition_record) + "\n")

                    s = s_next
                    ep_r += r
                    last_info = info
                    if d:
                        break

                rewards.append(round(ep_r, 1))
                res = last_info.get("result", "")
                if res == "DEFENDER_WON_TRAPPED" or env.attacker.trapped_in_honeypot:
                    batch_trapped += 1
                elif res == "ATTACKER_WON_BREACH" or env.attacker.database_exfiltrated:
                    batch_breached += 1
                else:
                    batch_timeouts += 1

        batch_wins = batch_trapped + batch_timeouts
        batch_win_rate = round(float(batch_wins / episodes) * 100.0, 1)

        # Save model neural network weights and replay memory buffer
        agent.save_checkpoint(MODEL_PATH)
        agent.replay_buffer.save_to_disk(REPLAY_BUFFER_PATH)

        # Update training_metrics.json
        total_episodes = episodes
        overall_win_rate = batch_win_rate
        total_trapped = batch_trapped

        if os.path.exists(METRICS_PATH):
            try:
                with open(METRICS_PATH, "r", encoding="utf-8") as f:
                    metrics = json.load(f)

                metrics["num_episodes"] = metrics.get("num_episodes", 0) + episodes
                metrics["outcomes"]["DEFENDER_WON_TRAPPED"] += batch_trapped
                metrics["outcomes"]["DEFENDER_WON_TIMEOUT"] += batch_timeouts
                metrics["outcomes"]["ATTACKER_WON_BREACH"] += batch_breached

                metrics["episode_rewards"].extend(rewards)

                # Recompute moving averages for new points
                for r in rewards:
                    recent = metrics["episode_rewards"][-25:]
                    metrics["moving_avg_rewards"].append(round(float(np.mean(recent)), 2))

                # Compute overall win rate
                total_played = metrics["num_episodes"]
                total_won = metrics["outcomes"]["DEFENDER_WON_TRAPPED"] + metrics["outcomes"]["DEFENDER_WON_TIMEOUT"]
                overall_win_rate = round(float(total_won / total_played) * 100.0, 1)
                metrics["final_win_rate_pct"] = overall_win_rate

                for _ in range(episodes):
                    metrics["win_rates"].append(overall_win_rate)

                total_episodes = metrics["num_episodes"]
                total_trapped = metrics["outcomes"]["DEFENDER_WON_TRAPPED"]

                with open(METRICS_PATH, "w", encoding="utf-8") as f:
                    json.dump(metrics, f, indent=2)
            except Exception as ex:
                print(f"[!] Warning: Failed to update metrics file: {ex}")

        return jsonify({
            "status": "success",
            "episodes_trained": episodes,
            "batch_win_rate": batch_win_rate,
            "overall_win_rate": overall_win_rate,
            "total_episodes": total_episodes,
            "batch_trapped": batch_trapped,
            "batch_breached": batch_breached,
            "total_trapped": total_trapped,
            "average_reward": round(float(np.mean(rewards)), 2),
            "rewards_history": rewards,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    # Standard local development runner
    port = int(os.environ.get("PORT", 5000))
    print(f"[*] Starting CyberBattle-RL SOC Mission Control on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=True)
