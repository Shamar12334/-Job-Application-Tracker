import os

from dotenv import load_dotenv

# Read settings from a .env file in the project folder (see .env.example).
# On a host like Vercel there is no .env file; set these as environment variables instead.
load_dotenv()

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME', 'job_tracker')
