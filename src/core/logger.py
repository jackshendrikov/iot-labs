import logging
import sys
from typing import ClassVar

from core.config import settings


class _ColorFormatter(logging.Formatter):
    """Форматувальник із підсвічуванням рівнів повідомлень кольорами ANSI."""

    _LEVEL_COLORS: ClassVar[dict[int, str]] = {
        logging.DEBUG: "\033[36m",  # Блакитний
        logging.INFO: "\033[32m",  # Зелений
        logging.WARNING: "\033[33m",  # Жовтий
        logging.ERROR: "\033[31m",  # Червоний
        logging.CRITICAL: "\033[35m",  # Пурпуровий
    }
    _RESET: ClassVar[str] = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Форматує запис, додаючи кольори до рівня повідомлення."""
        color = self._LEVEL_COLORS.get(record.levelno, "")
        message = super().format(record)
        return f"{color}{message}{self._RESET}" if color else message


class ProjectLogger:
    """Обгортка над стандартним логером із відкладеною ініціалізацією."""

    _LOG_FORMAT: ClassVar[str] = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    _DATE_FORMAT: ClassVar[str] = "%Y-%m-%d %H:%M:%S"

    def __init__(self, name: str) -> None:
        self.name = name
        self._logger: logging.Logger | None = None

    def __call__(self) -> logging.Logger:
        return self.logger

    @property
    def logger(self) -> logging.Logger:
        """Повертає логер, створюючи його лише при першому зверненні."""
        if self._logger is None:
            self._logger = self._build_logger()
        return self._logger

    def _build_logger(self) -> logging.Logger:
        """Налаштовує логер згідно з параметрами конфігурації."""
        logger = logging.getLogger(self.name)

        level_name = (settings.log_level or "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
        logger.setLevel(level)
        logger.propagate = False

        # Очищаємо попередні обробники, щоб уникнути дублювання
        logger.handlers.clear()

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(_ColorFormatter(self._LOG_FORMAT, self._DATE_FORMAT))
        logger.addHandler(handler)

        return logger


logger = ProjectLogger(name="road-vision-agent")()
