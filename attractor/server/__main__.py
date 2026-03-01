"""Entry point: python -m attractor.server"""

import argparse

import uvicorn

from attractor.server.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Attractor Pipeline Server"
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Bind host"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Bind port"
    )
    parser.add_argument(
        "--reload", action="store_true", help="Auto-reload on changes"
    )
    args = parser.parse_args()

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
