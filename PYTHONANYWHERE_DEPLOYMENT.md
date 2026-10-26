# PythonAnywhere Free Tier Deployment Guide (No Credit Card Required)

This guide walks you through deploying **CyberBattle-RL (Autonomous Enterprise Cyber Defense)** to **PythonAnywhere** for free with interactive dashboards and zero credit card needed.

---

## Prerequisites
1. A free PythonAnywhere account at [pythonanywhere.com](https://www.pythonanywhere.com).

---

## Step 1: Open a Bash Console
1. Log in to your PythonAnywhere dashboard.
2. Click on the **Consoles** tab.
3. Click on **Bash** to launch a terminal.

---

## Step 2: Upload or Clone the Project
In the Bash console, clone your GitHub repository or create the project folder:
```bash
git clone https://github.com/<your-username>/Enterprise-Cyber-Defender.git
cd "Enterprise-Cyber-Defender"
```
*(Or upload the zip archive via the PythonAnywhere **Files** tab and extract it with `unzip project.zip`).*

---

## Step 3: Create a Virtual Environment with Python 3.11
Run the following in the Bash console:
```bash
mkvirtualenv --python=/usr/bin/python3.11 cyber-env
pip install --upgrade pip
pip install -r requirements.txt
```

> [!TIP]
> On PythonAnywhere, CPU-only PyTorch will be installed automatically by `pip install torch` without needing CUDA drivers.

---

## Step 4: Configure the Web App
1. Navigate to the **Web** tab in PythonAnywhere.
2. Click **Add a new web app**.
3. Choose your domain (e.g., `yourusername.pythonanywhere.com`).
4. Select **Manual configuration** (do NOT pick Django or Flask wizard).
5. Select **Python 3.11**.
6. Click Next until the web app is created.

---

## Step 5: Configure Virtualenv & WSGI File
1. Scroll down to the **Virtualenv** section on the Web tab.
2. Enter the path to your virtual environment:
   ```text
   /home/<your-username>/.virtualenvs/cyber-env
   ```
3. Scroll up to the **Code** section:
   - Set **Source code**:
     ```text
     /home/<your-username>/Enterprise-Cyber-Defender
     ```
   - Set **Working directory**:
     ```text
     /home/<your-username>/Enterprise-Cyber-Defender
     ```
4. Click on the **WSGI configuration file** link (e.g. `/var/www/yourusername_pythonanywhere_com_wsgi.py`).
5. Replace everything in that file with:
   ```python
   import sys
   import os

   project_home = '/home/<your-username>/Enterprise-Cyber-Defender'
   if project_home not in sys.path:
       sys.path.insert(0, project_home)

   from app import app as application
   ```
   *(Be sure to replace `<your-username>` with your actual PythonAnywhere username)*.
6. Click **Save** in the top-right.

---

## Step 6: Reload and Launch!
1. Return to the **Web** tab.
2. Click the green **Reload yourusername.pythonanywhere.com** button.
3. Click your live site link (`https://yourusername.pythonanywhere.com`).

Your Cyber SOC interactive mission control is now live on the internet! 🛡️
