from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from dashboard.config import get_settings

LOG_LINE_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\s+\|\s+(\w+)\s+\|\s+(.*)$"
)


def get_log_file_path(date_str: str) -> Path:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Invalid date format: {date_str}") from exc

    log_dir = Path(get_settings().log_dir).resolve()
    log_file = (log_dir / f"poster_bot_{date_str}.log").resolve()

    try:
        log_file.relative_to(log_dir)
    except ValueError as exc:
        raise ValueError("Path traversal detected") from exc

    return log_file


def read_log_lines(
    date_str: str,
    keyword: str = "",
    level: str = "",
    tail: int = 0,
) -> list[dict]:
    log_file = get_log_file_path(date_str)
    if not log_file.exists():
        return []

    lines = log_file.read_text(encoding="utf-8").splitlines()
    parsed = []
    for index, line in enumerate(lines, 1):
        match = LOG_LINE_PATTERN.match(line)
        if match:
            entry = {
                "line_number": index,
                "timestamp": match.group(1),
                "level": match.group(2),
                "message": match.group(3),
            }
        else:
            entry = {
                "line_number": index,
                "timestamp": "",
                "level": "",
                "message": line,
            }

        if level and entry["level"] and entry["level"] != level.upper():
            continue
        if keyword and keyword.lower() not in entry["message"].lower():
            continue

        parsed.append(entry)

    if tail > 0:
        parsed = parsed[-tail:]

    return parsed
