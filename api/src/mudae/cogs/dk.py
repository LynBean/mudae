from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast

from fastapi import HTTPException, status
from loguru import logger
from selfcord import Message
from selfcord.ext.commands import Context, command
from selfcord.ext.tasks import loop

from src.ext import timeout

if TYPE_CHECKING:
    from src.mudae.client import MudaeClient

from . import MudaeCog


class MudaeDk(MudaeCog):
    def __init__(self, client: MudaeClient, /) -> None:
        super().__init__(client)
        self._started: bool = False
        self._next_iteration: datetime | None = None

    @MudaeCog.listener()
    async def on_ready(self) -> None:
        if not self._started:
            self.main.start()
            self._started = True

    @command("dk")
    @timeout(duration=timedelta(minutes=20))
    async def toggle(self, ctx: Context) -> None:
        if self._started:
            self.main.cancel()
            self.main.stop()
            self._started = False
            self._next_iteration = None
            await self.log_message("Stopped ` MudaeDk `")
        else:
            self.main.start()
            self._started = True
            await self.log_message("Started ` MudaeDk `")

    @loop(minutes=2)
    @logger.catch
    @timeout(duration=timedelta(minutes=20))
    async def main(self) -> None:
        if not self._started:
            return
        if not self.client.is_ready():
            return
        if self._next_iteration and datetime.now(tz=UTC).timestamp() <= self._next_iteration.timestamp():
            return

        async with self.lock, await self.typing():
            for _ in range(4):
                response = await self.send_mudae_command("dk")
                message = cast("Message", response.message)
                if message.content.count("Next $dk in"):
                    hours, minutes = self._get_next_dk(message.content)

                    self._next_iteration = datetime.now(tz=UTC) + timedelta(
                        hours=hours,
                        minutes=minutes + 2,
                    )
                    break

                await self.send_mudae_message("yes")

            if self._next_iteration:
                await self.send_mudae_message(
                    f"# ☪️ Next dk scheduled at <t:{int(self._next_iteration.timestamp())}:t> 💫",
                )

    def _get_next_dk(self, text: str, /) -> tuple[int, int]:
        match = re.search(r"Next \$dk in \*\*(?:(\d+)h )?(\d+)\*\* min\.", text)
        if match:
            hours = int(match.group(1)) if match.group(1) is not None else 0
            minutes = int(match.group(2))
            return hours, minutes

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


async def setup(client: MudaeClient) -> None:
    await client.add_cog(MudaeDk(client))
