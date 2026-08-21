"""
Structured logging setup (UPGRADE_PLAN.md D.3). Without this, `logger.error(...)`
calls already present in the science-layer modules (e.g. deep_learning_pipeline.py's
C.2 loud-failure logging) fall back to Python's default bare `LEVEL:name:message`
handler with no timestamp -- fine for a quick script, not for diagnosing a failure
that happened at 3am against a real observing run.
"""
import logging
import sys


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:
        return  # already configured (e.g. re-imported under a test runner)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    ))
    root.addHandler(handler)
    root.setLevel(level)
