from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast

from discord import Color
from fastapi import HTTPException, status
from loguru import logger
from selfcord import Button, Emoji, Member, Message, PartialEmoji, Reaction, User
from selfcord.ext.commands import Context, command
from selfcord.ext.tasks import loop

from src.ext import timeout
from src.mudae.cogs import MudaeCog

if TYPE_CHECKING:
    from src.mudae.client import MudaeClient

from .lock import MudaeRTLock


class MudaeRoll(MudaeCog):
    REACT_EMOJI = "❤️"
    REACT_TRIGGER_EMOJI = "👍"

    def __init__(self, client: MudaeClient, /) -> None:
        super().__init__(client)
        self._rt_lock = MudaeRTLock(client)

        self._started: bool = False
        self._next_iteration: datetime | None = None

    @MudaeCog.listener()
    async def on_ready(self) -> None:
        if not self._started:
            self.main.start()
            self._started = True

    @command("roll")
    @timeout(duration=timedelta(minutes=20))
    async def toggle(self, ctx: Context) -> None:
        if self._started:
            self.main.cancel()
            self.main.stop()
            self._started = False
            self._next_iteration = None
            await self.log_message("Stopped ` MudaeRoll `")
        else:
            self.main.start()
            self._started = True
            await self.log_message("Started ` MudaeRoll `")

    @command()
    @timeout(duration=timedelta(minutes=20))
    async def rolls(self, ctx: Context) -> None:
        async with self.lock, await self.typing():
            await self.send_mudae_command("rolls")

        self._next_iteration = None
        await self.main()

    @MudaeCog.listener("on_message")
    @timeout(duration=timedelta(minutes=20))
    async def on_roll_message(self, message: Message) -> None:
        if not self._started:
            return
        if message.author.id != self.client.APP_ID:
            return
        if message.interaction and self.client.user and message.interaction.user.id == self.client.user.id:
            return
        if not (message.interaction and await self.client.is_owner(message.interaction.user)):
            await asyncio.sleep(40)

        await self._process_roll_message(message)

    @MudaeCog.listener("on_reaction_add")
    @timeout(duration=timedelta(minutes=20))
    async def on_roll_reaction_add(self, reaction: Reaction, user: Member | User) -> None:
        message = reaction.message
        if message.author.id != self.client.APP_ID:
            return
        if reaction.emoji != self.REACT_TRIGGER_EMOJI:
            return
        if user.id != self.client.owner_id:
            return

        await self._procedure_react_roll_message(message)

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
            for _ in range(64):
                response = await self.send_mudae_command("ma")
                message = cast("Message", response.message)
                if len(message.embeds) < 1:
                    message = await message.fetch()

                if message.content.count("the roulette is limited to"):
                    match = re.search(r"\*\*(\d+)\*\*\s*min left", message.content)
                    if match is None:
                        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

                    self._next_iteration = datetime.now(tz=UTC) + timedelta(
                        minutes=int(match.group(1)) + 2,
                    )
                    break

                await self._process_roll_message(message)

        if self._next_iteration:
            await self.send_mudae_message(
                f"# ✨ Next roll scheduled at <t:{int(self._next_iteration.timestamp())}:t> 💫",
            )

    @property
    async def _kakera_threshold(self) -> int:
        mudae_channel = await (await self.client.mudae_channel)._get_channel()  # noqa: SLF001

        cache_key = f"kakera_threshold:{mudae_channel.id}"
        cache = await self.redis.get(cache_key)
        if cache:
            return int(cache)

        interaction = await self.send_mudae_command("top", input="#2000")
        message = cast("Message", interaction.message)
        match = re.search(r"#.*?-\s*(.+?)\*\*", message.content)
        if not match:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        character_name = match.group(1)
        interaction = await self.send_mudae_command("im", input=character_name)
        message = cast("Message", interaction.message)
        if len(message.embeds) < 1:
            message = await message.fetch()

        text = message.embeds.pop().description
        if not text:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        match = re.search(r"\**\s*(\d+)\s*<:kakera:", text)
        if not match:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        kakera = int(match.group(1))
        await self.redis.setex(cache_key, timedelta(weeks=2), kakera)
        await self.client.watchdog.send_message(
            self.client,
            color=Color.blurple(),
            description=f"Channel [{mudae_channel.id}]({mudae_channel.jump_url}) has updated its kakera threshold to {kakera}",  # noqa: E501
        )
        return kakera

    async def _process_roll_message(self, message: Message, /) -> None:
        embed = message.embeds.pop()
        if embed.footer and embed.footer.text and embed.footer.text.count("Belongs to"):
            return
        if not embed.description:
            return
        if not (embed.image and embed.image.url):
            return

        if not message.content.count("Wished by"):
            kakeras = self._get_kakera_values(embed.description)
            if kakeras < await self._kakera_threshold:
                return

        await self._procedure_react_roll_message(message)

    async def _procedure_react_roll_message(self, message: Message, /) -> None:
        await self._react_roll_message(message)

        async with self._rt_lock:
            await asyncio.sleep(2)
            message = await message.fetch()
            embed = message.embeds.pop()
            if embed.footer and embed.footer.text and embed.footer.text.count("Belongs to"):
                return

            if not self.client.user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

            await message.remove_reaction(self.REACT_EMOJI, self.client.user)
            await self.send_mudae_command("rollsutil resetclaimtimer")
            await self._react_roll_message(message)

    async def _react_roll_message(self, message: Message, /) -> None:
        if message.components:
            await asyncio.gather(
                *[
                    child.click()
                    for component in message.components
                    for child in component.children
                    if isinstance(child, Button)
                    and not (isinstance(child.emoji, PartialEmoji) and child.emoji.name.count("kakera"))
                ],
            )
        elif message.reactions:
            await asyncio.gather(
                *[
                    message.add_reaction(r)
                    for r in message.reactions
                    if not (isinstance(r.emoji, Emoji) and r.emoji.name.count("kakera"))
                ],
            )
        else:
            await message.add_reaction(self.REACT_EMOJI)

    def _get_kakera_values(self, text: str, /) -> int:
        match = re.search(r"\*\*\s*(\d+)\s*\*\*\s*<:kakera:", text)
        if match:
            return int(match.group(1))

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


async def setup(client: MudaeClient) -> None:
    await client.add_cog(MudaeRoll(client))
