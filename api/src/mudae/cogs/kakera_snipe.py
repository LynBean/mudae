import asyncio
from typing import ClassVar

from selfcord import Button, Emoji, Message, PartialEmoji
from selfcord.ext.commands import Context, command

from src.mudae.client import MudaeClient

from . import MudaeCog


class MudaeKakeraSnipe(MudaeCog):
    WHITELISTED_KAKERA_TYPES: ClassVar[list[str]] = [
        "kakeraP",
        "kakeraT",
        "kakeraG",
        "kakeraY",
        "kakeraO",
        "kakeraR",
        "kakeraW",
        "kakeraL",
        "kakeraD",
        "kakeraC",
    ]

    def __init__(self, client: MudaeClient, /) -> None:
        super().__init__(client)
        self._started: bool = True

    @command("kakerasnipe")
    async def toggle(self, ctx: Context) -> None:
        if self._started:
            self._started = False
            await self.log_message("Stopped ` MudaeKakeraSnipe `")
        else:
            self._started = True
            await self.log_message("Started ` MudaeKakeraSnipe `")

    @MudaeCog.listener("on_message")
    async def on_roll_message(self, message: Message) -> None:
        if not self._started:
            return
        if message.author.id != self.client.APP_ID:
            return

        if not (message.interaction and await self.client.is_owner(message.interaction.user)):
            await asyncio.sleep(40)

        if message.reactions:
            await asyncio.gather(
                *[
                    message.add_reaction(r)
                    for r in message.reactions
                    if (
                        isinstance(r.emoji, Emoji)
                        and any(kakera in r.emoji.name for kakera in self.WHITELISTED_KAKERA_TYPES)
                    )
                ],
            )
        if message.components:
            await asyncio.gather(
                *[
                    child.click()
                    for component in message.components
                    for child in component.children
                    if isinstance(child, Button)
                    and (
                        isinstance(child.emoji, PartialEmoji)
                        and any(kakera in child.emoji.name for kakera in self.WHITELISTED_KAKERA_TYPES)
                    )
                ],
            )


async def setup(client: MudaeClient) -> None:
    await client.add_cog(MudaeKakeraSnipe(client))
