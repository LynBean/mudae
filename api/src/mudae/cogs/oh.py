from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime, timedelta
from random import shuffle
from typing import TYPE_CHECKING, ClassVar, cast

from fastapi import HTTPException, status
from loguru import logger
from selfcord import Button, Message
from selfcord.ext.commands import Context, command
from selfcord.ext.tasks import loop

from src.ext import timeout

if TYPE_CHECKING:
    from src.mudae.client import MudaeClient

from . import MudaeCog


class MudaeOh(MudaeCog):
    SPHERE_RANKING: ClassVar[dict[str, int]] = {
        "spP": 1,
        "spD": 2,
        "spL": 3,
        "spW": 4,
        "spR": 5,
        "spO": 6,
        "spY": 7,
        "spG": 8,
        "spB": 9,
        "spT": 10,
        "spU": 11,
    }

    def __init__(self, client: MudaeClient, /) -> None:
        super().__init__(client)
        self._started: bool = False
        self._next_iteration: datetime | None = None

    @MudaeCog.listener()
    async def on_ready(self) -> None:
        if not self._started:
            self.main.start()
            self._started = True

    @command("oh")
    @timeout(duration=timedelta(minutes=20))
    async def toggle(self, ctx: Context) -> None:
        if self._started:
            self.main.cancel()
            self.main.stop()
            self._started = False
            self._next_iteration = None
            await self.log_message("Stopped ` MudaeOh `")
        else:
            self.main.start()
            self._started = True
            await self.log_message("Started ` MudaeOh `")

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
            for _ in range(16):
                response = await self.send_mudae_command("sphere harvest", input="1")
                message = cast("Message", response.message)

                if message.content.count("You don't have any $oh available!"):
                    self._next_iteration = datetime.now(tz=UTC) + timedelta(hours=2)
                    break

                if message.content.count("wait before the refill"):
                    hours, minutes = self._get_next_oh(message.content)

                    self._next_iteration = datetime.now(tz=UTC) + timedelta(
                        hours=hours,
                        minutes=minutes + 2,
                    )
                    break

                for _ in range(32):
                    with logger.catch():
                        message = await message.fetch()
                        buttons: list[Button] = [
                            child for c in message.components for child in c.children if isinstance(child, Button)
                        ]
                        shuffle(buttons)
                        buttons.sort(
                            key=lambda child: (
                                not child.disabled,
                                -self.SPHERE_RANKING.get(child.emoji.name if child.emoji else "", 0),
                            ),
                        )

                        selected = buttons.pop()
                        if selected.disabled:
                            break

                        await asyncio.sleep(1)
                        await selected.click()

            if self._next_iteration:
                await self.send_mudae_message(
                    f"# 🔮 Next oh scheduled at <t:{int(self._next_iteration.timestamp())}:t> 💫",
                )

    def _get_next_oh(self, text: str, /) -> tuple[int, int]:
        match = re.search(r"Time to wait before the refill: \*\*(\d+)h (\d+)\*\* min\.", text)
        if match:
            return int(match.group(1)), int(match.group(2))

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


async def setup(client: MudaeClient) -> None:
    await client.add_cog(MudaeOh(client))
