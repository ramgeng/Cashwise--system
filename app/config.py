"""Central settings, read from the .env file in the project root."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"

# SQLite by default (a single file, nothing to install).
# To switch to PostgreSQL later, set DATABASE_URL in .env, e.g.
# DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/cashwise
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'cashwise.db'}")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HINDSIGHT_URL = os.getenv("HINDSIGHT_URL", "https://api.hindsight.vectorize.io")
HINDSIGHT_API_KEY = os.getenv("HINDSIGHT_API_KEY")

# One memory bank per business, so data never mixes.
BANK_ID = os.getenv("HINDSIGHT_BANK_ID", "malabar-electronics")
BUSINESS_NAME = "Malabar Electronics Distributors"
