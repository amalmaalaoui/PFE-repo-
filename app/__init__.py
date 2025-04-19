from flask import Flask

app = Flask(__name__)

# Import routes *after* app is created to avoid circular import
from app import routes
