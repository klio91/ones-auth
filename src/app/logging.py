import logging
import sys

from loguru import logger


class InterceptHandler(logging.Handler):
    """stdlib logging을 loguru로 리다이렉트."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging() -> None:
    """loguru 설정 + stdlib logging 인터셉트."""
    import os

    log_level = os.getenv("ONES_AUTH_LOG_LEVEL", "DEBUG").upper()

    logger.remove()
    logger.add(sys.stderr, level=log_level, colorize=True)

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        lg = logging.getLogger(name)
        lg.handlers = [InterceptHandler()]
        lg.propagate = False
