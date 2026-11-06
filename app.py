"""
CyberBattle-RL: Flask WSGI Application
Serves the static UI for GitHub Pages and PythonAnywhere deployment.
The frontend (index.html, static/js, static/css) handles all simulation
logic client-side via the standalone SimEngine.
"""

import os
import json
import numpy as np
from flask import Flask, request, send_from_directory, jsonify

from rl_agent.train import train_cyber_defender

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
DATA_DIR = os.path.join(BASE_DIR, "data")

app = Flask(__name__)

# Serve the main UI
@app.route("/")
def index():
    return send_from_directory(".", "index.html")


# Serve static assets (css, js) for GitHub Pages compatibility
@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)


# API endpoint for current state (optional - for future backend integration)
@app.route("/api/state", methods=["GET"])
def api_state():
    """Return empty state for static mode - client-side SimEngine handles everything."""
    return jsonify({
        "network_state": {
            "nodes": [],
            "edges": [],
            "step": 0,
            "max_steps": 50,
            "active_infections": 0,
            "isolated_hosts": 0,
            "total_stolen_tokens": 0,
            "cumulative_reward": 0.0,
            "database_exfiltrated": False,
            "trapped_in_honeypot": False,
            "threat_level": "Aggressive APT (State-Sponsored)",
            "attacker_stage": "RECON",
        },
        "top_actions": [],
        "status": "success",
    })


# API endpoint for simulation step (optional)
@app.route("/api/step", methods=["POST"])
def api_step():
    """Placeholder step endpoint for static mode."""
    return jsonify({"error": "Use client-side SimEngine for simulation"}), 400


# API endpoint for reset (optional)
@app.route("/api/reset", methods=["POST"])
def api_reset():
    """Placeholder reset endpoint for static mode."""
    return jsonify({"message": "Reset initiated - use client-side controls"}), 200


# API endpoint for configuration (optional)
@app.route("/api/config", methods=["POST"])
def api_config():
    """Placeholder config endpoint for static mode."""
    return jsonify({"message": "Config update - use client-side controls"}), 200


# API endpoint for metrics (optional)
@app.route("/api/metrics", methods=["GET"])
def api_metrics():
    """Return actual training metrics from file for dashboard display."""
    try:
        metrics_path = os.path.join(MODELS_DIR, "training_metrics.json")
        if os.path.exists(metrics_path):
            with open(metrics_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return jsonify(data)
        else:
            return jsonify({
                "num_episodes": 0,
                "final_win_rate_pct": 0.0,
                "recent_batch_win_rate_pct": 0.0,
                "final_epsilon": 0.05,
                "outcomes": {
                    "DEFENDER_WON_TRAPPED": 0,
                    "DEFENDER_WON_TIMEOUT": 0,
                    "ATTACKER_WON_BREACH": 0,
                },
                "loss_history": [],
                "win_rates": [],
                "episode_rewards": [],
                "moving_avg_rewards": [],
            })
    except Exception as e:
        print(f"[!] Error loading metrics: {e}")
        return jsonify({"error": "Could not load metrics"}), 500


# API endpoint for training (optional)
@app.route("/api/train", methods=["POST"])
def api_train():
    """Run fine-tuning in-process and return actual metrics for the UI."""
    try:
        data = request.get_json(silent=True) or {}
        episodes = int(data.get("episodes", 25))
        episodes = max(1, episodes)

        metrics = train_cyber_defender(
            num_episodes=episodes,
            max_steps_per_episode=40,
            save_path=os.path.join(MODELS_DIR, "double_dqn_defender.pth"),
            metrics_path=os.path.join(MODELS_DIR, "training_metrics.json"),
            replay_path=os.path.join(MODELS_DIR, "replay_buffer.pth"),
            verbose=False,
        )

        jsonl_path = os.path.join(DATA_DIR, "fine_tuning_experience.jsonl")
        jsonl_lines = 0
        if os.path.exists(jsonl_path):
            with open(jsonl_path, "r", encoding="utf-8") as f:
                jsonl_lines = sum(1 for _ in f)

        outcome_counts = metrics.get("outcomes", {})
        total_trapped = outcome_counts.get("DEFENDER_WON_TRAPPED", 0)
        overall_win_rate = float(metrics.get("final_win_rate_pct", 0.0))
        batch_win_rate = float(metrics.get("win_rates", [])[-1]) if metrics.get("win_rates") else overall_win_rate
        average_reward = float(np.mean(metrics.get("episode_rewards", []))) if metrics.get("episode_rewards") else 0.0

        response = {
            "status": "success",
            "episodes_trained": episodes,
            "total_episodes": metrics.get("num_episodes", episodes),
            "win_rate": overall_win_rate,
            "overall_win_rate": overall_win_rate,
            "batch_win_rate": batch_win_rate,
            "average_reward": round(average_reward, 1),
            "total_trapped": total_trapped,
            "jsonl_entries": jsonl_lines,
            "output": "",
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# Serve favicon if exists
@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        "static", "favicon.ico", cache_timeout=0
    ) if os.path.exists("static/favicon.ico") else ("", 204)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)