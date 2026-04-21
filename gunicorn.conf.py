"""
gunicorn.conf.py — reads PORT from environment at runtime
so Railway (and Render/Heroku) don't need shell variable expansion.
"""
import os

bind    = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
workers = 2
timeout = 120
preload_app = True
