"""Script to run the Dirigent backend server."""
import argparse
import sys

import uvicorn

from backend.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Dirigent backend server")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (development only)",
    )
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable auto-reload (production / managed mode)",
    )
    args = parser.parse_args()

    use_reload = args.reload and not args.no_reload

    print(f"Starting Dirigent backend on {settings.api_host}:{settings.api_port}")
    uvicorn.run(
        "backend.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=use_reload,
    )


if __name__ == "__main__":
    main()
