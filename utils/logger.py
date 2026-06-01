from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from core.config import settings


def setup_logger() -> None:
    logger.remove()

    logger.add(
        sys.stderr,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        level=settings.log_level,
        colorize=True,
    )

    log_path = settings.log_file_path
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_path,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level=settings.log_level,
        rotation="00:00",
        retention=settings.log_retention,
        encoding="utf-8",
    )

    logger.info("Logger initialized")
