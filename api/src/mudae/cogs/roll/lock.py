import asyncio
from typing import ClassVar

from src.mudae.cogs import MudaeLock


class MudaeRTLock(MudaeLock):
    _user_locks: ClassVar[dict[int, asyncio.Lock]] = {}
    _channel_locks: ClassVar[dict[int, asyncio.Lock]] = {}
    _registry_lock: ClassVar[asyncio.Lock] = asyncio.Lock()
