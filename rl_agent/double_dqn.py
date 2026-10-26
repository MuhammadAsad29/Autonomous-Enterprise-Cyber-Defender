"""
Double Deep Q-Network (Double DQN) Agent with Experience Replay.
Implements decoupled target evaluation to prevent overestimation bias.
"""

import os
from typing import Dict, Any, Tuple, Optional
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from .network import CyberDefenderQNetwork
from .replay_buffer import ReplayBuffer


class DoubleDQNAgent:
    def __init__(
        self,
        state_dim: int = 64,
        action_dim: int = 40,
        lr: float = 5e-4,
        gamma: float = 0.99,
        tau: float = 0.005,
        buffer_size: int = 50000,
        batch_size: int = 64,
        device: Optional[torch.device] = None,
    ):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.tau = tau
        self.batch_size = batch_size
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # 1. Online Q-Network (Used for action selection and policy gradients)
        self.q_online = CyberDefenderQNetwork(state_dim, action_dim).to(self.device)

        # 2. Target Q-Network (Used for stable target evaluations)
        self.q_target = CyberDefenderQNetwork(state_dim, action_dim).to(self.device)
        self.q_target.load_state_dict(self.q_online.state_dict())
        self.q_target.eval()

        # 3. Optimizer & Loss
        self.optimizer = optim.AdamW(self.q_online.parameters(), lr=lr, weight_decay=1e-4)
        self.loss_fn = nn.SmoothL1Loss()  # Huber loss for robust gradient steps

        # 4. Experience Replay Memory
        self.replay_buffer = ReplayBuffer(capacity=buffer_size)

        # 5. Tracking
        self.total_steps = 0
        self.training_losses = []

    def select_action(self, state: np.ndarray, epsilon: float = 0.0) -> Tuple[int, np.ndarray]:
        """
        Select action using Epsilon-Greedy policy.
        Returns:
            action (int): Index of selected action [0, action_dim - 1]
            q_values (np.ndarray): Evaluated Q-values across all candidate actions
        """
        self.q_online.eval()
        with torch.no_grad():
            state_tensor = torch.tensor(state, dtype=torch.float32, device=self.device)
            q_vals = self.q_online(state_tensor).cpu().squeeze(0).numpy()

        if np.random.rand() < epsilon:
            # Explore: random action
            action = int(np.random.randint(self.action_dim))
        else:
            # Exploit: best Q-value
            action = int(np.argmax(q_vals))

        return action, q_vals

    def step(self, state: np.ndarray, action: int, reward: float, next_state: np.ndarray, done: bool) -> Optional[float]:
        """
        Stores experience transition and triggers gradient update if sufficient samples exist.
        """
        self.total_steps += 1
        self.replay_buffer.push(state, action, reward, next_state, done)

        if len(self.replay_buffer) >= self.batch_size:
            loss = self.train_step()
            return loss
        return None

    def train_step(self) -> float:
        """
        Executes one Double DQN gradient update step.
        """
        self.q_online.train()
        states, actions, rewards, next_states, dones = self.replay_buffer.sample(self.batch_size, self.device)

        # Current Q-values from online network for taken actions
        q_current = self.q_online(states).gather(1, actions)

        # Double DQN Decoupled Target Formulation:
        # 1. Action selection using Online network: a* = argmax_a Q_online(s', a)
        with torch.no_grad():
            next_state_online_q = self.q_online(next_states)
            best_next_actions = next_state_online_q.argmax(dim=1, keepdim=True)

            # 2. Action evaluation using Target network: Q_target(s', a*)
            next_state_target_q = self.q_target(next_states)
            q_next = next_state_target_q.gather(1, best_next_actions)

            # Target Q-value: r + gamma * Q_target(s', argmax Q_online) * (1 - done)
            q_target_val = rewards + (self.gamma * q_next * (1.0 - dones))

        # Compute Loss
        loss = self.loss_fn(q_current, q_target_val)

        # Gradient Backpropagation with clipping
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.q_online.parameters(), max_norm=10.0)
        self.optimizer.step()

        # Polyak soft update of Target Network: theta_target = tau * theta_online + (1 - tau) * theta_target
        self._soft_update_target_network()

        loss_val = float(loss.item())
        self.training_losses.append(loss_val)
        return loss_val

    def _soft_update_target_network(self):
        for target_param, online_param in zip(self.q_target.parameters(), self.q_online.parameters()):
            target_param.data.copy_(self.tau * online_param.data + (1.0 - self.tau) * target_param.data)

    def save_checkpoint(self, filepath: str):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        torch.save({
            "total_steps": self.total_steps,
            "q_online_state_dict": self.q_online.state_dict(),
            "q_target_state_dict": self.q_target.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
        }, filepath)

    def load_checkpoint(self, filepath: str):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Checkpoint not found at: {filepath}")
        checkpoint = torch.load(filepath, map_location=self.device)
        self.q_online.load_state_dict(checkpoint["q_online_state_dict"])
        self.q_target.load_state_dict(checkpoint["q_target_state_dict"])
        if "optimizer_state_dict" in checkpoint:
            self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        if "total_steps" in checkpoint:
            self.total_steps = checkpoint["total_steps"]
