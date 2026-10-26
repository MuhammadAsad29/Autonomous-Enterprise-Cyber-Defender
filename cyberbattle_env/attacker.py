"""
Attacker (APT / Red Team) agent for CyberBattle-RL.
Simulates realistic cyber kill-chain: Recon -> Weaponization -> Lateral Movement -> Crown Jewel Exfiltration.
"""

import random
from enum import Enum
from typing import Dict, List, Set, Tuple, Optional
from .topology import EnterpriseTopology, NodeStatus, NodeType, VulnerabilityType


class ThreatLevel(Enum):
    SCRIPT_KIDDIE = "Script Kiddie"
    STEALTHY_RANSOMWARE = "Stealthy Ransomware"
    AGGRESSIVE_APT = "Aggressive APT"


class AttackAction(Enum):
    RECON = "Reconnaissance Port Scan"
    EXPLOIT_STRUTS = "Exploit Apache Struts (CVE-2017-5638)"
    EXPLOIT_SSH = "SSH Credential Brute-Force"
    EXPLOIT_SMB = "SMB EternalBlue RCE (CVE-2017-0144)"
    HARVEST_TOKENS = "Credential Harvesting & Dump"
    LATERAL_JUMP = "Pass-the-Hash / Lateral Jump"
    EXFILTRATE_DB = "Exfiltrate Crown Jewel Database"


class APTAttacker:
    def __init__(self, topology: EnterpriseTopology, threat_level: ThreatLevel = ThreatLevel.AGGRESSIVE_APT):
        self.topology = topology
        self.threat_level = threat_level
        self.discovered_nodes: Set[int] = set()
        self.compromised_nodes: Set[int] = set()
        self.owned_nodes: Set[int] = set()
        self.stolen_credentials: Set[str] = set()
        self.database_exfiltrated: bool = False
        self.trapped_in_honeypot: bool = False
        self.last_action_description: str = "Initialized outside perimeter"
        self.reset()

    def reset(self):
        self.discovered_nodes = {0, 1}  # Discovered gateway and DMZ Web 1 initially
        self.compromised_nodes = set()
        self.owned_nodes = set()
        self.stolen_credentials = set()
        self.database_exfiltrated = False
        self.trapped_in_honeypot = False
        self.last_action_description = "Threat actor active at perimeter"

    def set_threat_level(self, level: ThreatLevel):
        self.threat_level = level

    def step(self) -> Tuple[Optional[AttackAction], Optional[int], str, bool]:
        """
        Executes one turn of the attacker's cyber kill-chain.
        Returns:
            action: AttackAction taken
            target_node_id: Target node ID or None
            log_message: Telemetry description
            is_honeypot_hit: Whether attacker walked into a decoy honeypot (+50 blue reward)
        """
        if self.trapped_in_honeypot:
            self.last_action_description = "Attacker isolated/trapped in decoy honeypot"
            return None, None, self.last_action_description, False

        if self.database_exfiltrated:
            self.last_action_description = "Attacker maintaining persistence after database exfiltration"
            return None, None, self.last_action_description, False

        # Exploit success probabilities based on threat profile
        if self.threat_level == ThreatLevel.AGGRESSIVE_APT:
            exploit_prob = 0.85
            honeypot_avoidance = 0.25
        elif self.threat_level == ThreatLevel.STEALTHY_RANSOMWARE:
            exploit_prob = 0.70
            honeypot_avoidance = 0.45
        else:  # SCRIPT_KIDDIE
            exploit_prob = 0.40
            honeypot_avoidance = 0.05

        # 1. Check if attacker has reached Crown Jewel DB (Node 8)
        if 8 in self.compromised_nodes or 8 in self.owned_nodes:
            # Attempt exfiltration
            if not self.database_exfiltrated:
                self.database_exfiltrated = True
                msg = "[CRITICAL ALERT] Attacker exfiltrated Crown Jewel Database records!"
                self.last_action_description = msg
                return AttackAction.EXFILTRATE_DB, 8, msg, False

        # 2. Check if Crown Jewel DB is discovered and neighbor to an owned/compromised node
        if 8 in self.discovered_nodes:
            db_node = self.topology.nodes[8]
            if not db_node.is_isolated:
                # Check if we have credentials or can exploit SQL/SMB
                can_attack_db = any(
                    (nbr in self.compromised_nodes or nbr in self.owned_nodes)
                    and not self.topology.nodes[nbr].is_isolated
                    for nbr in self.topology.get_neighbors(8)
                )
                if can_attack_db:
                    if random.random() < exploit_prob:
                        db_node.status = NodeStatus.COMPROMISED
                        self.compromised_nodes.add(8)
                        msg = "[BREACH] Attacker exploited Database access via internal trust link!"
                        self.last_action_description = msg
                        return AttackAction.EXFILTRATE_DB, 8, msg, False

        # 3. Harvest credentials on newly compromised nodes
        unharvested = [
            nid for nid in self.compromised_nodes.union(self.owned_nodes)
            if any(tok not in self.stolen_credentials for tok in self.topology.nodes[nid].credentials_stored)
        ]
        if unharvested and random.random() < 0.8:
            target_id = random.choice(unharvested)
            target = self.topology.nodes[target_id]
            for tok in target.credentials_stored:
                self.stolen_credentials.add(tok)
                if tok not in target.compromised_tokens:
                    target.compromised_tokens.append(tok)
            msg = f"[CREDENTIAL THEFT] Attacker dumped auth tokens on {target.name}: {list(target.credentials_stored)}"
            self.last_action_description = msg
            return AttackAction.HARVEST_TOKENS, target_id, msg, False

        # 4. Reconnaissance: Scan reachable neighbors from compromised/owned non-isolated hosts
        active_bases = [
            nid for nid in self.compromised_nodes.union(self.owned_nodes)
            if not self.topology.nodes[nid].is_isolated
        ]
        # Or from initial gateway
        if not active_bases and not self.topology.nodes[0].is_isolated:
            active_bases = [0]

        candidates_to_discover = set()
        for base_id in active_bases:
            for nbr_id in self.topology.get_neighbors(base_id):
                if nbr_id not in self.discovered_nodes:
                    candidates_to_discover.add(nbr_id)

        if candidates_to_discover and (random.random() < 0.6 or not self.compromised_nodes):
            new_node = random.choice(list(candidates_to_discover))
            self.discovered_nodes.add(new_node)
            target = self.topology.nodes[new_node]
            target.alert_level = min(1.0, target.alert_level + 0.3)
            msg = f"[RECON SCAN] Attacker scanned {target.name} ({target.ip}) - Exposed ports: {target.ports}"
            self.last_action_description = msg
            return AttackAction.RECON, new_node, msg, False

        # 5. Exploit reachable discovered nodes
        exploit_candidates = []
        for d_id in self.discovered_nodes:
            if d_id in self.compromised_nodes or d_id in self.owned_nodes:
                continue
            node = self.topology.nodes[d_id]
            if node.is_isolated:
                continue
            # Must have path from active base
            has_path = any(
                base in self.topology.get_neighbors(d_id)
                for base in active_bases
            )
            if has_path or d_id in [1, 2]:  # DMZ is reachable from edge
                exploit_candidates.append(d_id)

        if exploit_candidates:
            # Sort or prioritize towards DB (nodes 6, 7, 8) if Aggressive APT
            if self.threat_level == ThreatLevel.AGGRESSIVE_APT:
                exploit_candidates.sort(key=lambda nid: 0 if nid in [6, 7, 8] else (1 if nid in [3, 4, 5] else 2))
            
            target_id = exploit_candidates[0]
            target = self.topology.nodes[target_id]
            target.times_attacked += 1

            # Check if target is a Decoy Honeypot
            if target.is_decoy or target.status == NodeStatus.HONEYPOT_ACTIVE:
                if random.random() > honeypot_avoidance:
                    self.trapped_in_honeypot = True
                    target.alert_level = 1.0
                    msg = f"[DECOY TRAP TRIGGERED] Attacker attacked Honeypot {target.name}! Blue Team trapped APT!"
                    self.last_action_description = msg
                    return AttackAction.EXPLOIT_STRUTS, target_id, msg, True

            # Attempt exploitation based on vulnerability
            if random.random() < exploit_prob:
                target.status = NodeStatus.COMPROMISED
                self.compromised_nodes.add(target_id)
                target.alert_level = 0.9

                action_type = AttackAction.EXPLOIT_STRUTS
                if target.vulnerability == VulnerabilityType.APACHE_STRUTS:
                    action_type = AttackAction.EXPLOIT_STRUTS
                    msg = f"[EXPLOIT] Attacker executed Apache Struts RCE on {target.name}!"
                elif target.vulnerability == VulnerabilityType.SSH_WEAK_AUTH:
                    action_type = AttackAction.EXPLOIT_SSH
                    msg = f"[EXPLOIT] Attacker cracked SSH credentials on {target.name}!"
                elif target.vulnerability == VulnerabilityType.SMB_REMOTE_EXEC:
                    action_type = AttackAction.EXPLOIT_SMB
                    msg = f"[EXPLOIT] Attacker executed SMB EternalBlue RCE on {target.name}!"
                else:
                    action_type = AttackAction.LATERAL_JUMP
                    msg = f"[LATERAL MOVE] Attacker gained foothold on {target.name}!"

                self.last_action_description = msg
                return action_type, target_id, msg, False
            else:
                target.alert_level = min(1.0, target.alert_level + 0.25)
                msg = f"[PROBE BLOCKED] Attacker exploit attempt failed against {target.name}."
                self.last_action_description = msg
                return AttackAction.RECON, target_id, msg, False

        # Default idle reconnaissance
        msg = "[IDLE] Attacker evaluating lateral movement routes"
        self.last_action_description = msg
        return None, None, msg, False
