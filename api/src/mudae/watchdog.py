from __future__ import annotations

import asyncio
import json
import os
import signal
import traceback
from asyncio.tasks import Task
from collections import defaultdict
from types import FrameType
from typing import TYPE_CHECKING, ClassVar, override

from discord import Color, Embed, Intents, Interaction, app_commands
from discord.abc import Messageable
from discord.ext.commands import Bot, Cog, when_mentioned
from fastapi import FastAPI, HTTPException, status
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

if TYPE_CHECKING:
    from loguru import Message as LoguruMessage

    from src.mudae.client import MudaeClient


class Watchdog(Bot):
    def __init__(
        self,
        app: FastAPI,
        *,
        token: str,
        owner_ids: list[int],
        watchdog_channel_id: int,
    ) -> None:
        super().__init__(
            command_prefix=when_mentioned,
            intents=Intents.all(),
            help_command=None,
            owner_ids=set(owner_ids),
        )
        self._app = app
        self._token = token

        self.watchdog_channel_id = watchdog_channel_id

        self._init_loguru_sink()

    def _init_loguru_sink(self) -> None:
        @logger.catch(level="TRACE")
        @retry(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=4, min=2, max=300),
            reraise=True,
        )
        async def sink(message: LoguruMessage) -> None:
            channel = await self.watchdog_channel
            record = message.record
            message = json.loads(message)
            embed = Embed(
                color=Color.brand_red(),
                description=f"```py\n{message['text'][-4048:]}\n```",
                timestamp=record["time"],
            )
            await channel.send(embed=embed)

        logger.add(
            sink,
            level="ERROR",
            format="{message}",
            serialize=True,
            backtrace=False,
            diagnose=False,
        )

    @property
    def mudae_clients(self) -> list[MudaeClient]:
        return self._app.extra["mudae_clients"]

    @override
    async def start(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        await super().login(self._token)
        self._task = asyncio.create_task(super().connect(reconnect=True), name=f"Watchdog-{self._token[:6]}")

    @override
    async def close(self) -> None:
        await super().close()
        if self._task:
            await self._task

    async def on_ready(self) -> None:
        if self.user is None:
            return
        logger.info(f"[{self.user.name}] Successfully logged in")

    async def setup_hook(self) -> None:
        channel = await self.watchdog_channel
        guild = (await channel._get_channel()).guild  # noqa: SLF001
        if not guild:
            return

        await self.add_cog(WatchdogCog(self))
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    @property
    async def watchdog_channel(self) -> Messageable:
        channel = self.get_channel(self.watchdog_channel_id)
        if channel is None:
            channel = await self.fetch_channel(self.watchdog_channel_id)
        if not isinstance(channel, Messageable):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        return channel

    send_message_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    async def send_message(
        self,
        client: MudaeClient,
        *,
        color: Color | None = None,
        title: str | None = None,
        description: str | None = None,
        embed: Embed | None = None,
    ) -> Task:
        @logger.catch
        @retry(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=4, min=2, max=300),
            reraise=True,
        )
        async def main() -> None:
            channel = await self.watchdog_channel
            if not client.user:
                return

            embed_ = embed or Embed(
                color=color,
                title=title,
                description=description,
            )
            embed_.set_author(name=client.user.display_name, icon_url=client.user.display_avatar.url)
            async with self.send_message_lock:
                await channel.send(embed=embed_)

        return asyncio.create_task(main())


class WatchdogCog(Cog):
    mudae = app_commands.Group(
        name="mudae",
        description="Mudae selfbot admin commands",
    )

    def __init__(self, client: Watchdog) -> None:
        super().__init__()
        self.client = client

    @mudae.command(name="reboot", description="Reboot Mudae script")
    async def reboot(self, interaction: Interaction) -> None:
        await interaction.response.send_message(
            embed=Embed(
                color=Color.red(),
                description="Rebooting, this should take a few seconds...",
            ),
        )
        os.kill(os.getpid(), signal.SIGTERM)

    @mudae.command(name="status", description="Mudae selfbots statuses")
    async def status(self, interaction: Interaction) -> None:
        await interaction.response.defer()

        grouped: dict[int, list] = defaultdict(list)

        for client in self.client.mudae_clients:
            grouped[client.mudae_channel_ids[0]].append(client)

        async def format_client(client: MudaeClient) -> str:
            status = await client.get_standing_status()
            return f"- {'🟢' if client.connected else '🔴'} {client.mention} {status['description']}"

        sections = await asyncio.gather(
            *(
                asyncio.gather(
                    *(format_client(client) for client in clients),
                )
                for clients in grouped.values()
            ),
        )

        description = "\n\n".join(
            f"## Instance <#{channel_id}>\n" + "\n".join(lines)
            for (channel_id, _), lines in zip(grouped.items(), sections, strict=True)
        )

        await interaction.followup.send(
            embed=Embed(
                color=Color.yellow(),
                description=description,
            ),
        )

    @mudae.command(name="trace", description="Dump asyncio task stack traces")
    async def trace(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        tasks = sorted(
            asyncio.all_tasks(),
            key=lambda t: t.get_name(),
        )

        async def process_task(task: Task) -> list[Embed]:
            coro = task.get_coro()
            stacks = task.get_stack()

            async def process_stack(stack: FrameType, i: int) -> Embed:
                embed = Embed(
                    color=Color.light_gray(),
                )
                if stack:
                    embed.description = f"```py\n{''.join(traceback.format_stack(stack))[-4048:]}\n```"
                if i == 0:
                    if coro:
                        embed.title = f"` {coro.__name__} `"
                    if task.get_name():
                        embed.set_author(name=task.get_name())
                    if task.done():
                        embed.set_footer(text="Task is done")
                    if task.cancelling():
                        embed.set_footer(text="Task is cancelling")
                    if task.cancelled():
                        embed.set_footer(text="Task is cancelled")

                return embed

            return await asyncio.gather(*[process_stack(stack, i) for i, stack in enumerate(stacks)])

        embeds = [e for li in await asyncio.gather(*[process_task(task) for task in tasks]) for e in li]
        for chunk in [embeds[i : i + 10] for i in range(0, len(embeds), 10)]:
            await interaction.followup.send(embeds=chunk)
