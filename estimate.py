#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
# "requests",
# ]
# ///
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from common import Client


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def process(client: Client, *, skip: int = 0) -> None:
    items = client.items

    total_length = timedelta()
    oldest = datetime.now(timezone.utc)
    for item in items[skip:]:
        oldest = min(oldest, datetime.fromtimestamp(item.publish_ts, timezone.utc))
        total_length += timedelta(seconds=item.duration)

    logger.info("Oldest episode is %s", oldest.date())
    logger.info("Total backlog length is %s", total_length)

    length = datetime.now(timezone.utc) - oldest

    logger.info(f"Average {total_length / length.days} per day")


def main() -> None:
    c = Client()
    c.login()
    process(c)


if __name__ == "__main__":
    main()
