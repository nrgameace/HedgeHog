"""Loading `backend/.env` into the process environment.

Deliberately called from the application entry point rather than from the
libraries that read these variables. `client_from_env()` and friends stay pure
`os.getenv` readers, so tests can set and clear variables without a developer's
local `.env` leaking in and making results machine-dependent.

Existing environment variables always win: a real export or a deployment's
injected config is never overridden by the file.
"""

from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_env(path: Path = ENV_FILE) -> bool:
    """Load `.env` if present. Returns whether a file was found; absence is fine."""
    return load_dotenv(path, override=False)
