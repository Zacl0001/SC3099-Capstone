# Central configuration.
#
# Reads:
#
# DATABASE_URL
# AI_SERVICE_URL
# KNOWLEDGE_SERVICE_URL
#
# Values come from module2-backend/.env (loaded here and in db/database.py),
# falling back to the local development defaults below.

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://meeting_app:meeting_local_dev@127.0.0.1:5432/meeting_intelligence",
)

# Downstream services (see docs/testing-guide.md).
AI_SERVICE_URL = os.environ.get("AI_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/")
KNOWLEDGE_SERVICE_URL = os.environ.get(
    "KNOWLEDGE_SERVICE_URL", "http://127.0.0.1:8002"
).rstrip("/")

# LLM calls on CPU can take over a minute; embedding a whole transcript can
# take a couple of minutes.
AI_TIMEOUT_SECONDS = float(os.environ.get("AI_TIMEOUT_SECONDS", "240"))
KNOWLEDGE_TIMEOUT_SECONDS = float(os.environ.get("KNOWLEDGE_TIMEOUT_SECONDS", "120"))
