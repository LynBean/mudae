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


class MudaeGiveSp(MudaeCog):
    def __init__(self, client: MudaeClient, /) -> None:
        super().__init__(client)
        self._started: bool = False
        self._next_iteration: datetime | None = None

    @MudaeCog.listener()
    async def on_ready(self) -> None:
        if self.client.user and self.client.user.id and self.client.user.id == self.client.owner_id:
            return
        if not self._started:
            self.main.start()
            self._started = True

    @command("givesp")
    @timeout(duration=timedelta(minutes=20))
    async def toggle(self, ctx: Context) -> None:
        if self._started:
            self.main.cancel()
            self.main.stop()
            self._started = False
            self._next_iteration = None
            await self.log_message("Stopped ` MudaeGiveSp `")
        else:
            self.main.start()
            self._started = True
            await self.log_message("Started ` MudaeGiveSp `")

    @loop(minutes=2)
    @logger.catch
    @timeout(duration=timedelta(minutes=20))
    async def main(self) -> None:
        if not self._started:
            return
        if not self.client.is_ready():
            return
        if self.client.user and self.client.user.id and self.client.user.id == self.client.owner_id:
            return
        if self._next_iteration and datetime.now(tz=UTC).timestamp() <= self._next_iteration.timestamp():
            return

        async with self.lock, await self.typing():
            response = await self.send_mudae_command("sphere timer")
            message = cast("Message", response.message)

            sphere = self._get_sphere_values(message.content)
            if sphere > 0:
                await self.send_mudae_command("sphere give", input=f"<@{self.client.owner_id}> {sphere}")
                await self.send_mudae_message("yes")

            self._next_iteration = datetime.now(tz=UTC) + timedelta(hours=12)

            if self._next_iteration:
                await self.send_mudae_message(
                    f"# ❤️‍🔥 Next givesp scheduled at <t:{int(self._next_iteration.timestamp())}:t> 💫",
                )

    def _get_sphere_values(self, text: str, /) -> int:
        match = re.search(r"Stock:\s*\*\*([\d,]+)\*\*", text)
        if match:
            return int(match.group(1).replace(",", ""))

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


async def setup(client: MudaeClient) -> None:
    await client.add_cog(MudaeGiveSp(client))
