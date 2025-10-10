from __future__ import annotations
import logging

logger = logging.getLogger("abs-client")
_format = "%(levelname)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=_format)
