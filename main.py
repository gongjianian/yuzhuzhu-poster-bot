from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

load_dotenv()


def setup_logging() -> None:
    Path("logs").mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(
        "logs/poster_bot_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        encoding="utf-8",
        level="DEBUG",
    )


def main() -> None:
    setup_logging()

    import uvicorn
    from dashboard.app import create_app

    app = create_app()
    port = int(os.getenv("DASHBOARD_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
