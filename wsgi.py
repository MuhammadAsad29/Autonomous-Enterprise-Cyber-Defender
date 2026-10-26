"""
PythonAnywhere WSGI Configuration File.
Deploy CyberBattle-RL for free with no credit card required.

In the PythonAnywhere 'Web' tab:
1. Set Python version to 3.11.
2. Under 'Code', click 'WSGI configuration file' and point to this file, or paste its contents.
3. Reload web app.
"""

import sys
import os

# Add project root directory to Python path
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Import the Flask application instance
from app import app as application

if __name__ == "__main__":
    application.run()
