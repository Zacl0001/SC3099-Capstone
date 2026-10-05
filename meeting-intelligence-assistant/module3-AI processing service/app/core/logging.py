"""Central logging setup.

Python's standard "logging" module is used everywhere instead of
print() because it gives you:

  - Levels (DEBUG/INFO/WARNING/ERROR) so you can filter noise
  - Timestamps
  - The module/function that emitted the message (via %(name)s)
"""

import logging

_CONFIGURED = False


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger once per process."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger for a module, e.g. get_logger(__name__)."""
    return logging.getLogger(name)