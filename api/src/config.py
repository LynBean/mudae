import json
import os
from typing import Literal, cast

ENV: Literal["development", "production"] = cast(
    "Literal['development', 'production']",
    os.getenv("ENV", "development"),
)

REDIS_URL = os.environ["REDIS_URL"]
DISCORD_WATCHDOG_BOT_TOKEN = os.environ["DISCORD_WATCHDOG_BOT_TOKEN"]
DISCORD_MUDAE_OWNER_IDS = json.loads(os.environ["DISCORD_MUDAE_OWNER_IDS"])
DISCORD_WATCHDOG_CHANNEL_ID = int(os.environ["DISCORD_WATCHDOG_CHANNEL_ID"])
DISCORD_MUDAE_SELFBOT_PREFIX = os.environ["DISCORD_MUDAE_SELFBOT_PREFIX"]
DISCORD_MUDAE_BOT_PREFIX = os.environ["DISCORD_MUDAE_BOT_PREFIX"]
DISCORD_MUDAE_CHANNEL_IDS = json.loads(os.environ["DISCORD_MUDAE_CHANNEL_IDS"])
DISCORD_MUDAE_SELFBOT_TOKENS = json.loads(os.environ["DISCORD_MUDAE_SELFBOT_TOKENS"])
