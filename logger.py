from __future__ import annotations
import logging

_format = "%(levelname)s: %(message)s"
logging.basicConfig(format=_format)

logger = logging.getLogger("abs-client")
logger.setLevel(logging.INFO)
