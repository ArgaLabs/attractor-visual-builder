"""Entry point: python -m attractor.server"""

import argparse
import os
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent


def _load_dotenv() -> None:
    """Load .env from repo root into os.environ without requiring python-dotenv."""
    env_path = _ROOT / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


# Load .env BEFORE importing app so _make_backend() sees the keys
_load_dotenv()

import uvicorn  # noqa: E402

from attractor.server.app import create_app  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Attractor Pipeline Server"
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Bind host"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Bind port"
    )
    parser.add_argument(
        "--reload", action="store_true", help="Auto-reload on changes"
    )
    args = parser.parse_args()

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
