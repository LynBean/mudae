#!/usr/bin/env python3
import json
import os
from pathlib import Path
from textwrap import dedent

if __name__ == "__main__":
    env = os.getenv("ENV", "production")
    discord_mudae_bot_prefix = os.environ["DISCORD_MUDAE_BOT_PREFIX"]
    discord_mudae_channel_ids = json.loads(os.environ["DISCORD_MUDAE_CHANNEL_IDS"])
    discord_mudae_owner_ids = json.loads(os.environ["DISCORD_MUDAE_OWNER_IDS"])
    discord_mudae_selfbot_prefix = os.environ["DISCORD_MUDAE_SELFBOT_PREFIX"]
    discord_mudae_selfbot_tokens = json.loads(os.environ["DISCORD_MUDAE_SELFBOT_TOKENS"])
    discord_watchdog_bot_token = os.environ["DISCORD_WATCHDOG_BOT_TOKEN"]
    discord_watchdog_channel_id = int(os.environ["DISCORD_WATCHDOG_CHANNEL_ID"])
    redis_url = os.environ["REDIS_URL"]

    config_path = Path(__file__).resolve().parent.parent / "src" / "config.py"
    config_path.write_text(
        dedent(
            f"""
            from typing import Literal

            ENV: Literal["development", "production"] = {env!r}

            REDIS_URL = {redis_url!r}
            DISCORD_WATCHDOG_BOT_TOKEN = {discord_watchdog_bot_token!r}
            DISCORD_MUDAE_OWNER_IDS = {discord_mudae_owner_ids!r}
            DISCORD_WATCHDOG_CHANNEL_ID = {discord_watchdog_channel_id!r}
            DISCORD_MUDAE_SELFBOT_PREFIX = {discord_mudae_selfbot_prefix!r}
            DISCORD_MUDAE_BOT_PREFIX = {discord_mudae_bot_prefix!r}
            DISCORD_MUDAE_CHANNEL_IDS = {discord_mudae_channel_ids!r}
            DISCORD_MUDAE_SELFBOT_TOKENS = {discord_mudae_selfbot_tokens!r}
            """,
        ),
        encoding="utf-8",
    )
