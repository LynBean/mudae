import asyncio
import json
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Literal, cast

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from selfcord.ext.commands import when_mentioned_or
from starlette.middleware import _MiddlewareFactory

from src.mudae import MudaeClient
from src.mudae.watchdog import Watchdog

ENV: Literal["development", "production"] = cast(
    "Literal['development', 'production']",
    os.getenv("ENV", "development"),
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    app.extra["redis"] = aioredis.from_url(
        os.environ["REDIS_URL"],
        decode_responses=False,
    )

    watchdog = Watchdog(
        app,
        token=os.environ["DISCORD_WATCHDOG_BOT_TOKEN"],
        owner_ids=json.loads(os.environ["DISCORD_MUDAE_OWNER_IDS"]),
        watchdog_channel_id=int(os.environ["DISCORD_WATCHDOG_CHANNEL_ID"]),
    )
    app.extra["watchdog"] = watchdog
    await watchdog.start()
    await watchdog.wait_until_ready()

    mudae_clients: list[MudaeClient] = [
        MudaeClient(
            app=app,
            token=token,
            command_prefix=when_mentioned_or(os.environ["DISCORD_MUDAE_SELFBOT_PREFIX"]),
            owner_ids=json.loads(os.environ["DISCORD_MUDAE_OWNER_IDS"]),
            mudae_bot_prefix=os.environ["DISCORD_MUDAE_BOT_PREFIX"],
            mudae_channel_ids=mudae_channel_ids,
        )
        for mudae_channel_ids in json.loads(os.environ["DISCORD_MUDAE_CHANNEL_IDS"])
        for token in json.loads(os.environ["DISCORD_MUDAE_SELFBOT_TOKENS"])
    ]
    app.extra["mudae_clients"] = mudae_clients
    await asyncio.gather(*[c.start() for c in mudae_clients])

    yield

    await asyncio.gather(*[c.close() for c in mudae_clients])
    await watchdog.close()
    await app.extra["redis"].aclose(close_connection_pool=True)


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    middleware_class=cast("_MiddlewareFactory", CORSMiddleware),
    allow_credentials=True,
    allow_headers=[
        "Authorization",
        "Content-Type",
    ],
    allow_methods=[
        "*",
    ],
    allow_origins=["*"],
)

app.add_api_route(
    path="/health",
    endpoint=lambda: (
        {"status": "healthy"} if all(c.connected for c in app.extra["mudae_clients"]) else {"status": "unhealthy"}
    ),
)
