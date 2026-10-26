import streamlit as st
import json
import numpy as np
import torch
import os

from rl_agent.double_dqn import DoubleDQNAgent
from rl_agent.train import train_agent
from cyberbattle_env.env import CyberDefenderEnv
from cyberbattle_env.attacker import ThreatLevel

# Page config
st.set_page_config(
    page_title="CyberBattle-RL | Enterprise Cyber Defender",
    page_icon="🛡️",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main { padding: 20px; }
    .stButton > button { width: 100%; margin: 5px 0; }
    .metric-card { background: #0e1626; padding: 15px; border-radius: 10; margin: 10px 0; }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Autonomous Enterprise Cyber Defender")
st.subheader("Double DQN with Experience Replay")

# Sidebar controls
st.sidebar.header("⚙️ Controls")
defense_mode = st.sidebar.radio("Defense Mode", ["Double DQN", "Heuristic", "Random"])
threat_level = st.sidebar.selectbox("Threat Level", ["Aggressive APT", "Stealthy Ransomware", "Script Kiddie"])

# Environment init
@st.cache_resource
def init_env():
    env = CyberDefenderEnv(threat_level=ThreatLevel.AGGRESSIVE_APT, max_steps=50)
    agent = DoubleDQNAgent(state_dim=64, action_dim=40)
    
    model_path = "models/double_dqn_defender.pth"
    if os.path.exists(model_path):
        agent.load_checkpoint(model_path)
    
    return env, env.reset()

env, current_obs = init_env()
cumulative_reward = 0.0
step_count = 0

# Main interface
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("### 📊 Network Topology")
    
    state = env.get_full_state_dict()
    nodes = state.get("nodes", [])
    if nodes:
        for node in nodes[:3]:
            st.markdown(f"- **{node.get('name', 'Unknown')}**: {node.get('status', 'Unknown')}")
    
    if st.button("▶️ Step Forward"):
        action, q_vals = agent.select_action(current_obs, epsilon=0.0)
        next_obs, reward, done, info = env.step(action)
        current_obs = next_obs
        cumulative_reward += reward
        step_count += 1
        st.success(f"Step {step_count} | Reward: +{reward:.1f} | Total: +{cumulative_reward:.1f}")
        
        if done:
            st.error(f"Episode finished: {info.get('result', 'Unknown')}")
            env, current_obs = init_env()
            cumulative_reward = 0.0
            step_count = 0

with col2:
    st.markdown("### 📈 Q-Values Top 5")
    
    action, q_vals = agent.select_action(current_obs, epsilon=0.0)
    sorted_q = sorted(enumerate(q_vals), key=lambda x: x[1], reverse=True)[:5]
    
    for idx, q_val in sorted_q:
        action_type = idx // 10
        target = idx % 10
        st.write(f"**{action_type} → {target}**: Q = {q_val:.2f}")
    
    st.markdown(f"**Cumulative Reward**: +{cumulative_reward:.1f}")
    st.markdown(f"**Step**: {step_count}/50")

# Auto-run section
st.sidebar.markdown("---")
if st.sidebar.button("🚀 Auto Run 10 Steps"):
    for _ in range(10):
        if step_count >= 50:
            break
        action, q_vals = agent.select_action(current_obs, epsilon=0.0)
        next_obs, reward, done, info = env.step(action)
        current_obs = next_obs
        cumulative_reward += reward
        step_count += 1
        if done:
            break
    st.rerun()

# Training section
st.sidebar.markdown("---")
st.sidebar.header("🧠 Training")
if st.sidebar.button("📚 Train Agent (25 ep)"):
    with st.spinner("Training in progress..."):
        rewards = train_agent(episodes=25, env=env)
    st.sidebar.success(f"Training complete! Avg reward: {np.mean(rewards[-5:]):.1f}")

# Footer
st.markdown("---")
st.caption("""📝 **Note**: Model weights `models/double_dqn_defender.pth` required for inference.
🔧 **Train** button uses fine-tuning pipeline. GitHub deploy recommended for full access.""")

# Required at bottom
if __name__ == "__main__":
    import os
    main()