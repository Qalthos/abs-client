#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
# "requests",
# ]
# ///
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from common import Client
from logger import logger


def process(client: Client) -> None:
    total_length = timedelta()
    oldest = datetime.now(timezone.utc)
    items = client.items
    for item in items:
        oldest = min(oldest, datetime.fromtimestamp(item.publish_ts, timezone.utc))
        total_length += timedelta(seconds=int(item.duration))
    length = datetime.now(timezone.utc) - oldest

    logger.info("Oldest episode is %s (%s days!)", oldest.date(), length.days)
    logger.info("Total backlog length is %s (%d episodes)", total_length, len(items))

    # Switch to all episodes
    total_length = timedelta()
    oldest = datetime.now(timezone.utc)
    items = client.all_episodes
    for item in items:
        oldest = min(oldest, datetime.fromtimestamp(item.publish_ts, timezone.utc))
        total_length += timedelta(seconds=int(item.duration))
    length = datetime.now(timezone.utc) - oldest

    logger.info(
        "Average %d minutes per day (%.2f episodes per day)",
        (total_length / length.days).total_seconds() // 60,
        len(items) / length.days,
    )


def main() -> None:
    c = Client()
    c.login()
    process(c)


if __name__ == "__main__":
    main()
