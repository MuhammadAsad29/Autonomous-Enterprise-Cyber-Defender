"""
Enterprise Network Topology for CyberBattle-RL
Modeled after Microsoft CyberBattleSim enterprise scenarios.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Optional


class NodeType(Enum):
    GATEWAY = "Gateway"
    WEB_SERVER = "DMZ Web Server"
    WORKSTATION = "Workstation"
    DOMAIN_CONTROLLER = "Domain Controller"
    FILE_SERVER = "File Server"
    DATABASE = "Crown Jewel DB"
    HONEYPOT = "Decoy Honeypot"


class NodeStatus(Enum):
    CLEAN = "Clean"
    SCANNED = "Scanned"
    COMPROMISED = "Compromised"
    OWNED = "Owned (Admin)"
    ISOLATED = "Isolated"
    HONEYPOT_ACTIVE = "Honeypot Active"


class VulnerabilityType(Enum):
    NONE = "None"
    APACHE_STRUTS = "CVE-2017-5638 (Apache Struts RCE)"
    SSH_WEAK_AUTH = "CWE-307 (SSH Weak Credentials)"
    SMB_REMOTE_EXEC = "CVE-2017-0144 (SMB EternalBlue RCE)"
    SQL_INJECTION = "CWE-89 (Database SQL Injection)"


@dataclass
class NetworkNode:
    id: int
    name: str
    node_type: NodeType
    subnet: str
    ip: str
    vulnerability: VulnerabilityType
    ports: List[int]
    credentials_stored: List[str]
    status: NodeStatus = NodeStatus.CLEAN
    is_isolated: bool = False
    is_decoy: bool = False
    is_crown_jewel: bool = False
    compromised_tokens: List[str] = field(default_factory=list)
    times_attacked: int = 0
    downtime_steps: int = 0
    alert_level: float = 0.0  # 0.0 to 1.0 based on suspicious telemetry

    def reset(self):
        self.status = NodeStatus.CLEAN
        self.is_isolated = False
        self.is_decoy = False
        self.compromised_tokens.clear()
        self.times_attacked = 0
        self.downtime_steps = 0
        self.alert_level = 0.0


class EnterpriseTopology:
    """
    Graph topology representing the corporate enterprise network.
    Includes DMZ, Internal Corporate Network, Infrastructure, and Crown Jewel Database.
    """

    def __init__(self):
        self.nodes: Dict[int, NetworkNode] = {}
        self.adjacency: Dict[int, Set[int]] = {}
        self._build_topology()

    def _build_topology(self):
        # 1. Gateway (Entry Router)
        self.nodes[0] = NetworkNode(
            id=0,
            name="Edge-Firewall-Gateway",
            node_type=NodeType.GATEWAY,
            subnet="Perimeter",
            ip="10.0.0.1",
            vulnerability=VulnerabilityType.NONE,
            ports=[80, 443, 22],
            credentials_stored=["token_gw_vpn"],
        )

        # 2. DMZ Web Servers (Apache Struts RCE)
        self.nodes[1] = NetworkNode(
            id=1,
            name="DMZ-Web-App-01",
            node_type=NodeType.WEB_SERVER,
            subnet="DMZ",
            ip="192.168.1.10",
            vulnerability=VulnerabilityType.APACHE_STRUTS,
            ports=[80, 8080],
            credentials_stored=["token_web_db_ro", "ssh_user_dev"],
        )

        self.nodes[2] = NetworkNode(
            id=2,
            name="DMZ-API-Gateway",
            node_type=NodeType.WEB_SERVER,
            subnet="DMZ",
            ip="192.168.1.20",
            vulnerability=VulnerabilityType.APACHE_STRUTS,
            ports=[443, 8443],
            credentials_stored=["token_api_internal"],
        )

        # 3. Workstations (SSH Weak Credentials & Token Theft)
        self.nodes[3] = NetworkNode(
            id=3,
            name="WS-Dev-01",
            node_type=NodeType.WORKSTATION,
            subnet="Corporate-Dev",
            ip="172.16.10.15",
            vulnerability=VulnerabilityType.SSH_WEAK_AUTH,
            ports=[22, 3389],
            credentials_stored=["token_smb_share", "token_dc_user"],
        )

        self.nodes[4] = NetworkNode(
            id=4,
            name="WS-Finance-02",
            node_type=NodeType.WORKSTATION,
            subnet="Corporate-Finance",
            ip="172.16.20.44",
            vulnerability=VulnerabilityType.SSH_WEAK_AUTH,
            ports=[22, 445],
            credentials_stored=["token_finance_analyst"],
        )

        self.nodes[5] = NetworkNode(
            id=5,
            name="WS-HR-03",
            node_type=NodeType.WORKSTATION,
            subnet="Corporate-HR",
            ip="172.16.30.12",
            vulnerability=VulnerabilityType.SSH_WEAK_AUTH,
            ports=[22, 80],
            credentials_stored=["token_hr_portal"],
        )

        # 4. Infrastructure (Domain Controller & SMB File Server EternalBlue)
        self.nodes[6] = NetworkNode(
            id=6,
            name="File-Server-SMB",
            node_type=NodeType.FILE_SERVER,
            subnet="Infrastructure",
            ip="172.16.50.5",
            vulnerability=VulnerabilityType.SMB_REMOTE_EXEC,
            ports=[445, 139],
            credentials_stored=["token_db_admin", "token_backup_svc"],
        )

        self.nodes[7] = NetworkNode(
            id=7,
            name="Domain-Controller",
            node_type=NodeType.DOMAIN_CONTROLLER,
            subnet="Infrastructure",
            ip="172.16.50.2",
            vulnerability=VulnerabilityType.NONE,
            ports=[88, 389, 636],
            credentials_stored=["token_domain_admin", "token_crown_root"],
        )

        # 5. Crown Jewel Database (High-value Target)
        self.nodes[8] = NetworkNode(
            id=8,
            name="Crown-Jewel-Customer-DB",
            node_type=NodeType.DATABASE,
            subnet="Secure-Vault",
            ip="10.100.1.50",
            vulnerability=VulnerabilityType.SQL_INJECTION,
            ports=[1433, 5432],
            credentials_stored=["root_db_master_key"],
            is_crown_jewel=True,
        )

        # 6. Decoy Honeypot Slot
        self.nodes[9] = NetworkNode(
            id=9,
            name="Decoy-Honeypot-Alpha",
            node_type=NodeType.HONEYPOT,
            subnet="Deception-Grid",
            ip="172.16.99.99",
            vulnerability=VulnerabilityType.APACHE_STRUTS,
            ports=[80, 22, 445],
            credentials_stored=["honey_token_canary"],
            is_decoy=True,
        )

        # Initialize Adjacency list
        for nid in self.nodes:
            self.adjacency[nid] = set()

        # Connect network paths (Lateral Movement graph)
        # Gateway -> DMZ
        self._add_edge(0, 1)
        self._add_edge(0, 2)

        # DMZ Web -> Internal Workstations (via compromised jump-box / VPN)
        self._add_edge(1, 3)
        self._add_edge(1, 4)
        self._add_edge(2, 3)
        self._add_edge(2, 5)

        # Workstations cross-talk (Corporate LAN)
        self._add_edge(3, 4)
        self._add_edge(4, 5)

        # Workstations -> File Server & Domain Controller
        self._add_edge(3, 6)
        self._add_edge(4, 6)
        self._add_edge(3, 7)
        self._add_edge(5, 7)

        # Infrastructure -> Crown Jewel Database
        self._add_edge(6, 8)
        self._add_edge(7, 8)

        # Decoy Honeypot is reachable from Corporate Workstations & DMZ
        self._add_edge(1, 9)
        self._add_edge(3, 9)
        self._add_edge(6, 9)

    def _add_edge(self, u: int, v: int):
        self.adjacency[u].add(v)
        self.adjacency[v].add(u)

    def get_neighbors(self, node_id: int) -> Set[int]:
        return self.adjacency.get(node_id, set())

    def reset_all(self):
        for node in self.nodes.values():
            node.reset()
            if node.id == 9:
                node.is_decoy = True
                node.status = NodeStatus.CLEAN
