import os
import sys

# Ensure Python can import app.py from the root directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app

# Expose app directly for Vercel's WSGI handler
app = app
