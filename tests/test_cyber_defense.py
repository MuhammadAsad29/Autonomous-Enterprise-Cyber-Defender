"""
Comprehensive Unit and Integration Test Suite for CyberBattle-RL.
Validates Environment, Red Team Attacker, PyTorch Double DQN Network, and Flask APIs.
"""

import os
import unittest
import numpy as np
import torch

from cyberbattle_env.topology import EnterpriseTopology, NodeStatus, VulnerabilityType
from cyberbattle_env.attacker import APTAttacker, ThreatLevel, AttackAction
from cyberbattle_env.env import CyberDefenderEnv
from rl_agent.network import CyberDefenderQNetwork
from rl_agent.replay_buffer import ReplayBuffer
from rl_agent.double_dqn import DoubleDQNAgent
from app import app


class TestEnterpriseTopology(unittest.TestCase):
    def setUp(self):
        self.topology = EnterpriseTopology()

    def test_node_count_and_types(self):
        self.assertEqual(len(self.topology.nodes), 10)
        # Node 8 is Crown Jewel Database
        self.assertTrue(self.topology.nodes[8].is_crown_jewel)
        # Node 1 has Apache Struts
        self.assertEqual(self.topology.nodes[1].vulnerability, VulnerabilityType.APACHE_STRUTS)
        # Node 6 has SMB RCE
        self.assertEqual(self.topology.nodes[6].vulnerability, VulnerabilityType.SMB_REMOTE_EXEC)
        # Node 9 is Honeypot Decoy
        self.assertTrue(self.topology.nodes[9].is_decoy)

    def test_lateral_movement_paths(self):
        # Gateway connects to DMZ
        self.assertIn(1, self.topology.get_neighbors(0))
        # DMZ connects to Workstations
        self.assertIn(3, self.topology.get_neighbors(1))
        # Infrastructure connects to Crown Jewel DB
        self.assertIn(8, self.topology.get_neighbors(6))


class TestCyberDefenderEnv(unittest.TestCase):
    def setUp(self):
        self.env = CyberDefenderEnv(threat_level=ThreatLevel.AGGRESSIVE_APT, max_steps=30)

    def test_observation_dimensions(self):
        obs = self.env.reset()
        self.assertIsInstance(obs, np.ndarray)
        self.assertEqual(obs.shape, (64,))
        self.assertEqual(obs.dtype, np.float32)

    def test_actions_and_transitions(self):
        self.env.reset()
        # Action 0: Isolate Host 0
        next_obs, reward, done, info = self.env.step(0)
        self.assertEqual(next_obs.shape, (64,))
        self.assertIn("Isolate Host", info["action_name"])
        self.assertTrue(self.env.topology.nodes[0].is_isolated)

        # Action 29: Deploy Honeypot on Node 9
        next_obs, reward, done, info = self.env.step(29)
        self.assertEqual(info["action_name"], "Deploy Decoy Honeypot")
        self.assertEqual(self.env.topology.nodes[9].status, NodeStatus.HONEYPOT_ACTIVE)

    def test_business_downtime_penalty(self):
        self.env.reset()
        # Isolate clean node 3 (Workstation Dev)
        _, reward1, _, _ = self.env.step(3)  # Isolate Node 3
        # In the next step, node 3 is isolated while clean -> triggers -2 downtime penalty
        _, reward2, _, _ = self.env.step(1)  # Re-image or do other action
        self.assertTrue(self.env.topology.nodes[3].downtime_steps >= 1)

    def test_honeypot_trap_reward(self):
        self.env.reset()
        # Force honeypot trigger
        self.env.attacker.trapped_in_honeypot = True
        _, reward, done, info = self.env.step(0)
        self.assertTrue(done)
        self.assertEqual(info["result"], "DEFENDER_WON_TRAPPED")


class TestDoubleDQNAgent(unittest.TestCase):
    def setUp(self):
        self.agent = DoubleDQNAgent(state_dim=64, action_dim=40, batch_size=8)

    def test_network_forward_pass(self):
        dummy_state = np.zeros(64, dtype=np.float32)
        action, q_values = self.agent.select_action(dummy_state, epsilon=0.0)
        self.assertIsInstance(action, int)
        self.assertTrue(0 <= action < 40)
        self.assertEqual(len(q_values), 40)

    def test_replay_buffer(self):
        buf = ReplayBuffer(capacity=100)
        s = np.zeros(64, dtype=np.float32)
        buf.push(s, 5, 10.0, s, False)
        self.assertEqual(len(buf), 1)

        for i in range(10):
            buf.push(s, i, float(i), s, False)

        states, actions, rewards, next_states, dones = buf.sample(batch_size=4)
        self.assertEqual(states.shape, (4, 64))
        self.assertEqual(actions.shape, (4, 1))

    def test_training_gradient_step(self):
        s = np.random.randn(64).astype(np.float32)
        for i in range(16):
            self.agent.step(s, i % 40, 1.0, s, False)
        self.assertTrue(len(self.agent.training_losses) > 0)


class TestFlaskServerAPI(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_health_endpoint(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "healthy")

    def test_get_state(self):
        res = self.client.get("/api/state")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("nodes", data)
        self.assertEqual(len(data["nodes"]), 10)
        self.assertIn("edges", data)

    def test_step_endpoint(self):
        res = self.client.post("/api/step", json={"action_id": 5})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("step_info", data)
        self.assertIn("q_values", data)
        self.assertEqual(len(data["q_values"]), 40)

    def test_reset_endpoint(self):
        res = self.client.post("/api/reset")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["step"], 0)

    def test_metrics_endpoint(self):
        res = self.client.get("/api/metrics")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("num_episodes", data)
        self.assertIn("episode_rewards", data)


if __name__ == "__main__":
    unittest.main()
