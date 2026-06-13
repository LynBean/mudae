import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import cast

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from selfcord.ext.commands import when_mentioned_or
from starlette.middleware import _MiddlewareFactory

from src.config import (
    DISCORD_MUDAE_BOT_PREFIX,
    DISCORD_MUDAE_CHANNEL_IDS,
    DISCORD_MUDAE_OWNER_IDS,
    DISCORD_MUDAE_SELFBOT_PREFIX,
    DISCORD_MUDAE_SELFBOT_TOKENS,
    DISCORD_WATCHDOG_BOT_TOKEN,
    DISCORD_WATCHDOG_CHANNEL_ID,
    REDIS_URL,
)
from src.mudae import MudaeClient
from src.mudae.watchdog import Watchdog

"""
window.webpackChunkdiscord_app.push([
	[Symbol()],
	{},
	req => {
		if (!req.c) return;
		for (let m of Object.values(req.c)) {
			try {
				if (!m.exports || m.exports === window) continue;
				if (m.exports?.getToken) return copy(m.exports.getToken());
				for (let ex in m.exports) {
					if (m.exports?.[ex]?.getToken && m.exports[ex][Symbol.toStringTag] !== 'IntlMessagesProxy') return copy(m.exports[ex].getToken());
				}
			} catch {}
		}
	},
]);

window.webpackChunkdiscord_app.pop();
console.log('%cWorked!', 'font-size: 50px');
console.log(`%cYou now have your token in the clipboard!`, 'font-size: 16px');
"""  # noqa: E501


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    app.extra["redis"] = aioredis.from_url(
        REDIS_URL,
        decode_responses=False,
    )

    watchdog = Watchdog(
        app,
        token=DISCORD_WATCHDOG_BOT_TOKEN,
        owner_ids=DISCORD_MUDAE_OWNER_IDS,
        watchdog_channel_id=DISCORD_WATCHDOG_CHANNEL_ID,
    )
    app.extra["watchdog"] = watchdog
    await watchdog.start()
    await watchdog.wait_until_ready()

    mudae_clients: list[MudaeClient] = [
        MudaeClient(
            app=app,
            token=token,
            command_prefix=when_mentioned_or(DISCORD_MUDAE_SELFBOT_PREFIX),
            owner_ids=DISCORD_MUDAE_OWNER_IDS,
            mudae_bot_prefix=DISCORD_MUDAE_BOT_PREFIX,
            mudae_channel_ids=mudae_channel_ids,
        )
        for mudae_channel_ids in DISCORD_MUDAE_CHANNEL_IDS
        for token in DISCORD_MUDAE_SELFBOT_TOKENS
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
