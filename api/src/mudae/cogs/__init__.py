from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, ClassVar, Self

from fastapi import HTTPException, status
from redis.asyncio import Redis
from selfcord import Interaction, Message
from selfcord.context_managers import Typing
from selfcord.ext.commands import Cog

if TYPE_CHECKING:
    from src.mudae import MudaeClient


class MudaeLock:
    _user_locks: ClassVar[dict[int, asyncio.Lock]] = {}
    _channel_locks: ClassVar[dict[int, asyncio.Lock]] = {}
    _registry_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __init__(self, client: MudaeClient) -> None:
        self.client = client
        self._channel_id = client.mudae_channel_ids[0]
        self._user_lock: asyncio.Lock | None = None
        self._channel_lock: asyncio.Lock | None = None

    @property
    def _user_id(self) -> int:
        if self.client.user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return self.client.user.id

    @classmethod
    async def _get_locks(cls, user_id: int, channel_id: int) -> tuple[asyncio.Lock, asyncio.Lock]:
        async with cls._registry_lock:
            return (
                cls._user_locks.setdefault(user_id, asyncio.Lock()),
                cls._channel_locks.setdefault(channel_id, asyncio.Lock()),
            )

    async def __aenter__(self) -> Self:
        user_lock, channel_lock = await self._get_locks(
            self._user_id,
            self._channel_id,
        )

        while True:
            await user_lock.acquire()

            try:
                try:
                    await asyncio.wait_for(
                        channel_lock.acquire(),
                        timeout=0.02,
                    )
                except TimeoutError:
                    pass
                else:
                    self._user_lock = user_lock
                    self._channel_lock = channel_lock
                    return self

            finally:
                if self._channel_lock is None:
                    user_lock.release()

            await asyncio.sleep(0.2)

    async def __aexit__(self, *exc_info: object) -> None:
        await asyncio.sleep(1)
        if self._channel_lock is not None:
            self._channel_lock.release()
            self._channel_lock = None

        if self._user_lock is not None:
            self._user_lock.release()
            self._user_lock = None


class MudaeCog(Cog):
    def __init__(self, client: MudaeClient, /) -> None:
        self.client: MudaeClient = client
        self.lock = MudaeLock(client)

    @property
    def redis(self) -> Redis:
        return self.client._app.extra["redis"]  # noqa: SLF001

    async def send_mudae_message(self, content: str, /, *, prefix: bool | None = None) -> Message:
        return await self.client.send_mudae_message(content, prefix=prefix)

    async def send_mudae_command(self, name: str, /, **kwargs: str) -> Interaction:
        return await self.client.send_mudae_command(name, **kwargs)

    async def typing(self) -> Typing:
        channel = await self.client.mudae_channel
        return channel.typing()

    async def log_message(self, content: str, /) -> None:
        await self.client.watchdog.send_message(self.client, description=content)
