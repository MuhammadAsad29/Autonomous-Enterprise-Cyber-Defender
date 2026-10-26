"""
CyberDefenderEnv: Gym-compatible Reinforcement Learning Environment for Blue Team Cyber Defense.
Implements 64-dimensional observation state, 4 core defense actions across hosts, and exact reward metrics.
"""

from typing import Dict, List, Tuple, Any, Optional
import numpy as np
from .topology import EnterpriseTopology, NodeStatus, NodeType, VulnerabilityType
from .attacker import APTAttacker, ThreatLevel, AttackAction


class CyberDefenderEnv:
    """
    Blue Team Autonomous Cyber Defense Environment.
    Observation: 64-dimensional numpy array representing network host status matrix.
    Action: Discrete action in range [0, 39]:
        action_type = action // 10  (0: Isolate Host, 1: Re-image Server, 2: Deploy Decoy, 3: Revoke Token)
        target_node = action % 10   (Node ID 0 to 9)
    """

    ACTION_NAMES = [
        "Isolate Host",
        "Re-image Server",
        "Deploy Decoy Honeypot",
        "Revoke Auth Token",
    ]

    def __init__(self, threat_level: ThreatLevel = ThreatLevel.AGGRESSIVE_APT, max_steps: int = 50):
        self.topology = EnterpriseTopology()
        self.attacker = APTAttacker(self.topology, threat_level=threat_level)
        self.max_steps = max_steps
        self.current_step = 0
        self.action_space_size = 40  # 4 actions * 10 nodes
        self.observation_dim = 64
        self.history: List[Dict[str, Any]] = []
        self.cumulative_downtime_penalty = 0.0

    def reset(self) -> np.ndarray:
        self.topology.reset_all()
        self.attacker.reset()
        self.current_step = 0
        self.history.clear()
        self.cumulative_downtime_penalty = 0.0
        return self._get_observation()

    def set_threat_level(self, level_name: str):
        mapping = {
            "Script Kiddie": ThreatLevel.SCRIPT_KIDDIE,
            "Stealthy Ransomware": ThreatLevel.STEALTHY_RANSOMWARE,
            "Aggressive APT": ThreatLevel.AGGRESSIVE_APT,
        }
        level = mapping.get(level_name, ThreatLevel.AGGRESSIVE_APT)
        self.attacker.set_threat_level(level)

    def _get_observation(self) -> np.ndarray:
        """
        Constructs the 64-dimensional Network Host Status Matrix:
        - 10 nodes x 6 features = 60 dimensions
        - 4 global network telemetry features = 4 dimensions
        Total: 64 dimensions
        """
        obs = np.zeros(64, dtype=np.float32)

        total_compromised = 0
        honeypot_active_any = 0.0

        for i in range(10):
            node = self.topology.nodes[i]
            offset = i * 6

            # Feature 1: Infection status (0.0: Clean, 0.4: Scanned, 0.8: Compromised, 1.0: Owned)
            if node.status == NodeStatus.OWNED:
                obs[offset + 0] = 1.0
                total_compromised += 1
            elif node.status == NodeStatus.COMPROMISED:
                obs[offset + 0] = 0.8
                total_compromised += 1
            elif node.status == NodeStatus.SCANNED or i in self.attacker.discovered_nodes:
                obs[offset + 0] = 0.4
            else:
                obs[offset + 0] = 0.0

            # Feature 2: Compromised auth tokens ratio
            total_stored = len(node.credentials_stored)
            comp_tokens = len(node.compromised_tokens)
            obs[offset + 1] = float(comp_tokens / total_stored) if total_stored > 0 else 0.0

            # Feature 3: Port activity / Alert level (0.0 to 1.0)
            obs[offset + 2] = float(node.alert_level)

            # Feature 4: Isolation status (1.0 if isolated, 0.0 otherwise)
            obs[offset + 3] = 1.0 if node.is_isolated else 0.0

            # Feature 5: Decoy Honeypot flag
            if node.is_decoy or node.status == NodeStatus.HONEYPOT_ACTIVE:
                obs[offset + 4] = 1.0
                honeypot_active_any = 1.0
            else:
                obs[offset + 4] = 0.0

            # Feature 6: Cumulative attacks on host (normalized)
            obs[offset + 5] = min(1.0, float(node.times_attacked) / 5.0)

        # Global Telemetry Features (Indices 60..63)
        # 60: Total infection ratio
        obs[60] = float(total_compromised) / 10.0

        # 61: Decoy triggered / Honeypot active
        obs[61] = 1.0 if self.attacker.trapped_in_honeypot else honeypot_active_any

        # 62: Crown Jewel DB Threat Level (Alert level of Database or direct neighbors)
        db_alert = self.topology.nodes[8].alert_level
        neighbor_alerts = [self.topology.nodes[nbr].alert_level for nbr in self.topology.get_neighbors(8)]
        obs[62] = float(max([db_alert] + neighbor_alerts))

        # 63: Attacker Stage Progress
        if self.attacker.database_exfiltrated:
            stage = 1.0
        elif 8 in self.attacker.discovered_nodes:
            stage = 0.75
        elif any(nid in [6, 7] for nid in self.attacker.compromised_nodes):
            stage = 0.50
        elif any(nid in [3, 4, 5] for nid in self.attacker.compromised_nodes):
            stage = 0.35
        elif any(nid in [1, 2] for nid in self.attacker.compromised_nodes):
            stage = 0.20
        else:
            stage = 0.05
        obs[63] = float(stage)

        return obs

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, Dict[str, Any]]:
        """
        Executes one time step:
        1. Blue Team defender executes defensive action.
        2. Red Team attacker executes attack move.
        3. Rewards and termination conditions are computed.
        """
        self.current_step += 1
        action_type = action // 10
        target_id = action % 10
        target_node = self.topology.nodes[target_id]

        reward = 0.0
        defense_log = ""

        # --- 1. Blue Team Action Execution ---
        if action_type == 0:  # Isolate Host
            if not target_node.is_isolated:
                target_node.is_isolated = True
                if target_id in self.attacker.compromised_nodes or target_node.status == NodeStatus.COMPROMISED:
                    defense_log = f"[DEFENDER] Isolated compromised host: {target_node.name}. Threat contained!"
                    reward += 15.0  # Reward for successfully containing infected node
                else:
                    defense_log = f"[DEFENDER] Isolated clean host: {target_node.name} (Quarantine precaution)."
            else:
                defense_log = f"[DEFENDER] Host {target_node.name} already isolated."

        elif action_type == 1:  # Re-image Server
            if target_node.status in [NodeStatus.COMPROMISED, NodeStatus.OWNED]:
                target_node.status = NodeStatus.CLEAN
                target_node.compromised_tokens.clear()
                target_node.alert_level = 0.0
                if target_id in self.attacker.compromised_nodes:
                    self.attacker.compromised_nodes.remove(target_id)
                if target_id in self.attacker.owned_nodes:
                    self.attacker.owned_nodes.remove(target_id)
                target_node.is_isolated = False
                defense_log = f"[DEFENDER] Re-imaged and restored {target_node.name}. Infection removed!"
                reward += 10.0
            else:
                target_node.is_isolated = False
                defense_log = f"[DEFENDER] Re-imaged clean host {target_node.name}. Restored online."

        elif action_type == 2:  # Deploy Decoy Honeypot
            target_node.status = NodeStatus.HONEYPOT_ACTIVE
            target_node.is_decoy = True
            defense_log = f"[DEFENDER] Deployed active decoy honeypot on {target_node.name}."
            reward += 2.0  # Small incentive for proactive deception

        elif action_type == 3:  # Revoke Auth Token
            if target_node.compromised_tokens:
                stolen_count = len(target_node.compromised_tokens)
                for tok in target_node.compromised_tokens:
                    self.attacker.stolen_credentials.discard(tok)
                target_node.compromised_tokens.clear()
                defense_log = f"[DEFENDER] Revoked {stolen_count} compromised credentials on {target_node.name}."
                reward += 8.0
            else:
                defense_log = f"[DEFENDER] Revoked active session tokens on {target_node.name}."

        # --- 2. Business Downtime Penalty Calculation (-2 per step) ---
        # "−2 for business downtime"
        for nid, node in self.topology.nodes.items():
            if node.is_isolated:
                node.downtime_steps += 1
                # If isolated host was NOT compromised, apply -2 business downtime penalty
                if node.status == NodeStatus.CLEAN and not node.is_crown_jewel:
                    reward -= 2.0
                    self.cumulative_downtime_penalty += 2.0

        # --- 3. Red Team (APT) Attacker Execution ---
        att_action, att_target, att_log, is_honeypot_hit = self.attacker.step()

        # --- 4. Special Milestone Rewards ---
        # "+50 for trapping attacker"
        if is_honeypot_hit or self.attacker.trapped_in_honeypot:
            if not getattr(self, "_trap_rewarded", False):
                reward += 50.0
                self._trap_rewarded = True
                defense_log += " | [TRAPPED] Attacker caught in honeypot decoy! (+50 reward)"

        # "−100 if critical database is exfiltrated"
        if self.attacker.database_exfiltrated:
            if not getattr(self, "_breach_penalized", False):
                reward -= 100.0
                self._breach_penalized = True
                defense_log += " | [BREACH CRITICAL] Crown Jewel DB compromised! (-100 penalty)"

        # Small step survival bonus
        if not self.attacker.database_exfiltrated and not self.attacker.trapped_in_honeypot:
            reward += 1.0

        # --- 5. Termination Check ---
        done = False
        result = "ONGOING"
        if self.attacker.database_exfiltrated:
            done = True
            result = "ATTACKER_WON_BREACH"
        elif self.attacker.trapped_in_honeypot:
            done = True
            result = "DEFENDER_WON_TRAPPED"
        elif self.current_step >= self.max_steps:
            done = True
            result = "DEFENDER_WON_TIMEOUT"

        next_obs = self._get_observation()

        step_info = {
            "step": self.current_step,
            "action_id": action,
            "action_name": self.ACTION_NAMES[action_type],
            "target_node_id": target_id,
            "target_node_name": target_node.name,
            "reward": reward,
            "defense_log": defense_log,
            "attacker_log": att_log,
            "attacker_action": att_action.value if att_action else "None",
            "database_exfiltrated": self.attacker.database_exfiltrated,
            "trapped_in_honeypot": self.attacker.trapped_in_honeypot,
            "result": result,
            "active_infections": sum(1 for n in self.topology.nodes.values() if n.status in [NodeStatus.COMPROMISED, NodeStatus.OWNED]),
            "isolated_hosts": sum(1 for n in self.topology.nodes.values() if n.is_isolated),
        }
        self.history.append(step_info)

        return next_obs, reward, done, step_info

    def get_full_state_dict(self) -> Dict[str, Any]:
        """Returns JSON-serializable network and simulation state for UI."""
        nodes_data = []
        for nid, n in self.topology.nodes.items():
            nodes_data.append({
                "id": n.id,
                "name": n.name,
                "type": n.node_type.value,
                "subnet": n.subnet,
                "ip": n.ip,
                "vulnerability": n.vulnerability.value,
                "ports": n.ports,
                "status": n.status.value,
                "is_isolated": n.is_isolated,
                "is_decoy": n.is_decoy or n.status == NodeStatus.HONEYPOT_ACTIVE,
                "is_crown_jewel": n.is_crown_jewel,
                "alert_level": round(n.alert_level, 2),
                "times_attacked": n.times_attacked,
                "compromised_tokens": list(n.compromised_tokens),
            })

        edges_data = []
        visited = set()
        for u, neighbors in self.topology.adjacency.items():
            for v in neighbors:
                edge_key = tuple(sorted((u, v)))
                if edge_key not in visited:
                    visited.add(edge_key)
                    edges_data.append({"from": u, "to": v})

        return {
            "step": self.current_step,
            "max_steps": self.max_steps,
            "threat_level": self.attacker.threat_level.value,
            "attacker_discovered": list(self.attacker.discovered_nodes),
            "attacker_compromised": list(self.attacker.compromised_nodes),
            "database_exfiltrated": self.attacker.database_exfiltrated,
            "trapped_in_honeypot": self.attacker.trapped_in_honeypot,
            "last_attacker_action": self.attacker.last_action_description,
            "cumulative_downtime_penalty": round(self.cumulative_downtime_penalty, 1),
            "nodes": nodes_data,
            "edges": edges_data,
            "total_stolen_tokens": len(self.attacker.stolen_credentials),
        }
