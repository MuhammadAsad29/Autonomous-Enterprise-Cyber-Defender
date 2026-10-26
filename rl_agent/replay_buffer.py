"""
Experience Replay Buffer for Double DQN training.
"""

import random
from collections import deque
from typing import Tuple, List
import numpy as np
import torch


class ReplayBuffer:
    def __init__(self, capacity: int = 50000):
        self.buffer = deque(maxlen=capacity)

    def push(self, state: np.ndarray, action: int, reward: float, next_state: np.ndarray, done: bool):
        self.buffer.append((
            np.array(state, dtype=np.float32),
            int(action),
            float(reward),
            np.array(next_state, dtype=np.float32),
            bool(done)
        ))

    def sample(self, batch_size: int, device: torch.device = torch.device('cpu')) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        batch = random.sample(self.buffer, batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)

        return (
            torch.tensor(np.array(states), dtype=torch.float32, device=device),
            torch.tensor(actions, dtype=torch.int64, device=device).unsqueeze(1),
            torch.tensor(rewards, dtype=torch.float32, device=device).unsqueeze(1),
            torch.tensor(np.array(next_states), dtype=torch.float32, device=device),
            torch.tensor(dones, dtype=torch.float32, device=device).unsqueeze(1)
        )

    def __len__(self) -> int:
        return len(self.buffer)

    def save_to_disk(self, filepath: str):
        """Saves replay buffer transitions to disk."""
        import os
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        torch.save(list(self.buffer), filepath)

    def load_from_disk(self, filepath: str):
        """Loads replay buffer transitions from disk."""
        import os
        if os.path.exists(filepath):
            data = torch.load(filepath, map_location='cpu', weights_only=False)
            self.buffer = deque(data, maxlen=self.buffer.maxlen)
