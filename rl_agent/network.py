"""
PyTorch Neural Network for Double DQN Cyber Defender Agent.
Architecture:
Input (64 dimensions) -> Dense(64, 256, LeakyReLU) -> Dense(256, 128, LeakyReLU) -> Output(num_actions, Q-Values)
"""

import torch
import torch.nn as nn


class CyberDefenderQNetwork(nn.Module):
    def __init__(self, state_dim: int = 64, action_dim: int = 40):
        super(CyberDefenderQNetwork, self).__init__()
        self.state_dim = state_dim
        self.action_dim = action_dim

        # Exact layers requested:
        # Dense(64 -> 256, LeakyReLU) -> Dense(256 -> 128, LeakyReLU) -> Output(Q-values)
        self.fc1 = nn.Linear(state_dim, 256)
        self.act1 = nn.LeakyReLU(negative_slope=0.01)
        self.fc2 = nn.Linear(256, 128)
        self.act2 = nn.LeakyReLU(negative_slope=0.01)
        self.out = nn.Linear(128, action_dim)

        self._init_weights()

    def _init_weights(self):
        # Kaiming normal initialization suitable for LeakyReLU
        for layer in [self.fc1, self.fc2]:
            nn.init.kaiming_normal_(layer.weight, nonlinearity='leaky_relu')
            nn.init.constant_(layer.bias, 0.0)
        # Output layer initialized with small weights for stable Q-values
        nn.init.xavier_uniform_(self.out.weight)
        nn.init.constant_(self.out.bias, 0.0)

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """
        Forward pass computing Q-values for all candidate actions.
        Args:
            state: Tensor of shape (batch_size, 64) or (64,)
        Returns:
            q_values: Tensor of shape (batch_size, 40)
        """
        if state.dim() == 1:
            state = state.unsqueeze(0)
        x = self.act1(self.fc1(state))
        x = self.act2(self.fc2(x))
        q_values = self.out(x)
        return q_values
