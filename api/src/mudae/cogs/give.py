from __future__ import annotations

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


class MudaeGive(MudaeCog):
    def __init__(self, client: MudaeClient, /) -> None:
        super().__init__(client)
        self._started: bool = False
        self._next_iteration: datetime | None = None

    @MudaeCog.listener()
    async def on_ready(self) -> None:
        if not self._started and self.client.user and self.client.user.id != self.client.owner_id:
            self.main.start()
            self._started = True

    @command("give")
    @timeout(duration=timedelta(minutes=20))
    async def toggle(self, ctx: Context) -> None:
        if self._started:
            self.main.cancel()
            self.main.stop()
            self._started = False
            self._next_iteration = None
            await self.log_message("Stopped ` MudaeGive `")
        elif self.client.user and self.client.user.id != self.client.owner_id:
            self.main.start()
            self._started = True
            await self.log_message("Started ` MudaeGive `")

    @MudaeCog.listener("on_message")
    @timeout(duration=timedelta(minutes=20))
    async def on_receive_message(self, message: Message) -> None:
        if message.author.id != self.client.APP_ID:
            return
        if not (
            self.client.user
            and message.content.startswith(f"<@{self.client.user.id}>")
            and message.content.count("wants to give you")
        ):
            return

        await message.reply("yes", silent=True)

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
        if self.client.user and self.client.user.id == self.client.owner_id:
            return

        async with self.lock, await self.typing():
            for _ in range(16):
                response = await self.send_mudae_command("mm")
                message = cast("Message", response.message)
                if len(message.embeds) < 1:
                    message = await message.fetch()

                text = message.embeds.pop().description
                if text is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

                text = text.replace("\u200b", "").strip()

                if text.count("(No results)"):
                    break

                # This is broken, Mudae won't send response back for some reason
                # await self.send_mudae_command(
                #     "collection give",
                #     input=f"<@{self.client.owner_id}> {'$'.join(text.splitlines())}",
                # )
                await self.send_mudae_message(
                    f"give <@{self.client.owner_id}> {'$'.join(text.splitlines())}",
                    prefix=True,
                )

            self._next_iteration = datetime.now(tz=UTC) + timedelta(hours=12)

            if self._next_iteration:
                await self.send_mudae_message(
                    f"# 🎁 Next give scheduled at <t:{int(self._next_iteration.timestamp())}:t> 💫",
                )


async def setup(client: MudaeClient) -> None:
    await client.add_cog(MudaeGive(client))
