"""
Convert JSONL fine-tuning experience to PyTorch Replay Buffer format.

This script reads data/fine_tuning_experience.jsonl and converts it
into models/replay_buffer.pth format that train.py can use for fine-tuning.

JSONL format expected (based on existing data):
{
    "timestamp": str,
    "fine_tune_episode": int,
    "step": int,
    "action_id": int,
    "action_name": str,
    "target_node": str,
    "reward": float,
    "defense_log": str,
    "attacker_log": str,
    "attacker_action": str,
    "active_infections": int,
    "isolated_hosts": int,
    "done": bool,
    "result": str
}
"""

import json
import os
import numpy as np
import torch
from rl_agent.replay_buffer import ReplayBuffer


def convert_jsonl_to_replay_buffer(
    jsonl_path: str = "data/fine_tuning_experience.jsonl",
    buffer_path: str = "models/replay_buffer.pth",
    buffer_capacity: int = 50000,
    state_dim: int = 64,
):
    """
    Convert JSONL experience file to PyTorch replay buffer.
    
    Note: The JSONL file contains transition metadata but NOT the actual
    state vectors. This script creates placeholder state vectors based
    on the transition data. For real use, you should have state data 
    embedded in your JSONL or generate it from the environment.
    """
    
    print(f"[*] Reading JSONL from: {jsonl_path}")
    
    # Count transitions first
    total_transitions = 0
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                json.loads(line)  # validate
                total_transitions += 1
    
    print(f"[*] Found {total_transitions} transitions in JSONL")
    
    if total_transitions == 0:
        print("[!] No transitions found in JSONL file. Exiting.")
        return
    
    # Create replay buffer
    buffer = ReplayBuffer(capacity=buffer_capacity)
    
    # Read and convert each transition
    print(f"[*] Converting transitions...")
    converted = 0
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            try:
                transition = json.loads(line)
                
                # Extract fields
                action_id = transition.get("action_id", 0)
                reward = transition.get("reward", 0.0)
                done = transition.get("done", False)
                
                # --- STATE EXTRACTION ---
                # The JSONL doesn't contain raw state vectors.
                # We need to reconstruct or placeholder the states.
                # Option 1: Use target_node as state index
                # Option 2: Create zero/identity vectors
                # Option 3: Expect state data in JSONL (not present in current format)
                
                target_node = transition.get("target_node", "Unknown")
                
                # Create placeholder state vector
                # In a real scenario, you would have the actual network state
                # We'll use a hash-based approach or node-index based vector
                node_to_idx = {
                    "Edge-Firewall-Gateway": 0,
                    "DMZ-Web-App-01": 1,
                    "DMZ-API-Gateway": 2,
                    "WS-Dev-01": 3,
                    "WS-Finance-02": 4,
                    "WS-HR-03": 5,
                    "File-Server-SMB": 6,
                    "Domain-Controller": 7,
                    "Crown-Jewel-Customer-DB": 8,
                    "Decoy-Honeypot-Alpha": 9,
                }
                
                target_node_name = transition.get("target_node", "")
                target_idx = node_to_idx.get(target_node_name, 0)
                
                # Create state vector: one-hot encoding of target node + some features
                state = np.zeros(state_dim, dtype=np.float32)
                if target_idx < state_dim:
                    state[target_idx] = 1.0  # One-hot encode the target node
                    # Add some additional features
                    state[state_dim - 1] = 0.5  # bias term
                
                # Create next_state (same structure, could be slightly different)
                # For simplicity, use same state structure
                next_state = np.zeros(state_dim, dtype=np.float32)
                if target_idx < state_dim:
                    next_state[target_idx] = 1.0
                    next_state[state_dim - 1] = 0.5
                
                # Push to buffer
                buffer.push(state, action_id, reward, next_state, done)
                converted += 1
                
                if converted % 100 == 0:
                    print(f"[*] Converted {converted}/{total_transitions}...")
                    
            except json.JSONDecodeError as e:
                print(f"[!] JSON parse error on line: {e}")
                continue
    
    print(f"[+] Converted {converted} transitions successfully")
    
    # Save to disk
    print(f"[*] Saving replay buffer to: {buffer_path}")
    os.makedirs(os.path.dirname(buffer_path), exist_ok=True)
    
    # Save in the format train.py expects: list of buffer transitions
    torch.save(list(buffer.buffer), buffer_path)
    
    print("[+] Complete! Buffer contains", len(buffer.buffer), "transitions")
    print(f"[✓] Saved to: {buffer_path}")
    
    return buffer


if __name__ == "__main__":
    import sys
    
    jsonl_path = sys.argv[1] if len(sys.argv) > 1 else "data/fine_tuning_experience.jsonl"
    buffer_path = sys.argv[2] if len(sys.argv) > 2 else "models/replay_buffer.pth"
    
    convert_jsonl_to_replay_buffer(jsonl_path, buffer_path)