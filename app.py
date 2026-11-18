from flask import Flask
from database import init_db

app= Flask(__name__)

@app.route('/')
def hello():
    return "<p>Hello, World!</p>"

@app.cli.command('init-db')
def init_db_command():
    """Initialize the database."""
    init_db()
    print('Initialized the database.')