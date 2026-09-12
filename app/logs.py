import json
import logging
import os
import sys
import time

ENV_VAR = "LOG_LEVEL"
DEFAULT_LEVEL = "INFO"

# Attributes LogRecord always carries. Anything else was passed via `extra=`
# and belongs in the JSON output.
_BUILTIN = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _BUILTIN:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def _requested_level() -> tuple[int, str | None]:
    name = os.environ.get(ENV_VAR, DEFAULT_LEVEL).strip().upper()
    resolved = logging.getLevelNamesMapping().get(name)
    if resolved is None:
        return logging.INFO, name
    return resolved, None


def configure() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    level, unknown = _requested_level()
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
        logger.setLevel(logging.NOTSET)

    if unknown is not None:
        logging.getLogger(__name__).warning(
            "unknown %s, defaulting to INFO", ENV_VAR, extra={"requested": unknown}
        )
