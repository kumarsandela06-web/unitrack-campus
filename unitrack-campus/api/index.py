import os
import sys

# Add root folder to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app as flask_app

# WSGI Middleware to strip /api prefix and restore proper PATH_INFO
class PathFixer:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        if path.startswith('/api/index'):
            environ['PATH_INFO'] = path.replace('/api/index', '', 1) or '/'
        elif path.startswith('/api'):
            environ['PATH_INFO'] = path.replace('/api', '', 1) or '/'
        return self.app(environ, start_response)

app = PathFixer(flask_app)
