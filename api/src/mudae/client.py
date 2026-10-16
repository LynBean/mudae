from __future__ import annotations

import asyncio
from asyncio import Task
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, TypedDict, cast, override

from discord import Color, Embed
from fastapi import FastAPI, HTTPException, status
from loguru import logger
from selfcord import Guild, Interaction, Member, Message, Reaction, SlashCommand, SubCommand, User
from selfcord.abc import Messageable
from selfcord.ext.commands import Bot, CommandError, Context
from selfcord.http import Route
from selfcord.user import BaseUser

if TYPE_CHECKING:
    from selfcord.ext.commands.bot import PrefixType

from src.mudae.cogs.daily import setup as daily_setup
from src.mudae.cogs.dk import setup as dk_setup
from src.mudae.cogs.give import setup as give_setup
from src.mudae.cogs.givek import setup as givek_setup
from src.mudae.cogs.givesp import setup as givesp_setup
from src.mudae.cogs.kakera_badge import setup as kakera_badge_setup
from src.mudae.cogs.kakera_snipe import setup as kakera_snipe_setup
from src.mudae.cogs.oh import setup as oh_setup
from src.mudae.cogs.roll import setup as roll_setup
from src.mudae.cogs.say import setup as say_setup
from src.mudae.watchdog import Watchdog


class StandingStatus(TypedDict):
    color: Color
    description: str


StandingState = Literal[0, 100, 200, 300, 400, 500]

USER_STANDING_STATUS_MAP: dict[StandingState, StandingStatus] = {
    0: {
        "color": Color.blurple(),
        "description": "Failed to fetch account standing",
    },
    100: {
        "color": Color.brand_green(),
        "description": "Account is in good standing",
    },
    200: {
        "color": Color.orange(),
        "description": "Account is limited",
    },
    300: {
        "color": Color.brand_red(),
        "description": "Account is very limited",
    },
    400: {
        "color": Color.dark_red(),
        "description": "Account is at risk",
    },
    500: {
        "color": Color.dark_gray(),
        "description": "Account is suspended",
    },
}


class MudaeClient(Bot):
    APP_ID = 432610292342587392

    def __init__(
        self,
        app: FastAPI,
        *,
        token: str,
        command_prefix: PrefixType,
        owner_ids: list[int],
        mudae_bot_prefix: str,
        mudae_channel_ids: list[int],
    ) -> None:
        super().__init__(
            afk=True,
            case_insensitive=True,
            chunk_guilds_at_startup=False,
            command_prefix=command_prefix,
            help_command=None,
            idle_since=datetime.now(tz=UTC),
            owner_ids=set(owner_ids),
            strip_after_prefix=True,
            user_bot=True,
        )
        self._app = app
        self._token = token
        self._task: Task | None = None

        self.name = self._token[:6]
        self.mention = self._token[:6]
        self.connected = False

        self.mudae_bot_prefix = mudae_bot_prefix
        self.mudae_channel_ids = mudae_channel_ids

        self.owner_id = owner_ids[0]
        self.owner_ids = set(owner_ids)

    @property
    def watchdog(self) -> Watchdog:
        return self._app.extra["watchdog"]

    @override
    async def start(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        @logger.catch
        def callback(task: Task) -> None:
            task.result()

        self._task = asyncio.create_task(super().start(self._token, reconnect=True), name=f"MudaeClient-{self.name}")
        self._task.add_done_callback(callback)

    @override
    async def close(self) -> None:
        await super().close()
        if self._task:
            await self._task

    @override
    async def setup_hook(self) -> None:
        await daily_setup(self)
        await dk_setup(self)
        await give_setup(self)
        await givek_setup(self)
        await givesp_setup(self)
        await kakera_badge_setup(self)
        await kakera_snipe_setup(self)
        await oh_setup(self)
        await roll_setup(self)
        await say_setup(self)

    @override
    async def _run_event(
        self,
        coro: Callable[..., Coroutine[Any, Any, Any]],
        event_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if event_name == "on_reaction_add" and not await self.is_mudae_channel(cast("Reaction", args[0]).message):
            return
        if event_name == "on_message" and not await self.is_mudae_channel(*args, **kwargs):
            return
        await super()._run_event(coro, event_name, *args, **kwargs)

    async def on_ready(self) -> None:
        if self.user is None:
            return

        self.name = self.user.name
        self.mention = self.user.mention

        logger.info(f"[{self.user.name}] Successfully logged in")
        standing = await self.get_standing_status()
        await self.watchdog.send_message(self, color=standing["color"], description=standing["description"])

    async def on_command(self, ctx: Context, /) -> None:
        if not ctx.command:
            return
        author: User = ctx.author._user if isinstance(ctx.author, Member) else ctx.author  # noqa: SLF001
        embed = Embed(
            description=f"[` {ctx.clean_prefix} {ctx.invoked_with}{f' {ctx.current_argument}' if ctx.current_argument else ''} `]({ctx.message.jump_url})",  # noqa: E501
        )
        embed.set_footer(
            icon_url=author.display_avatar.url,
            text=author.name,
        )
        await self.watchdog.send_message(
            self,
            embed=embed,
        )

    @override
    async def on_command_error(self, ctx: Context, exception: CommandError, /) -> None:
        await self.watchdog.send_message(self, color=Color.red(), description=f"```py\n{exception}\n```")
        await super().on_command_error(ctx, exception)

    @override
    async def process_commands(self, message: Message, /) -> None:
        if not await self.is_mudae_owner(message):
            return
        await super().process_commands(message)

    async def on_connect(self) -> None:
        self.connected = True
        await self.watchdog.send_message(
            self,
            embed=Embed(
                color=Color.teal(),
                description="Connected",
            ),
        )

    async def on_disconnect(self) -> None:
        self.connected = False
        await self.watchdog.send_message(
            self,
            embed=Embed(
                color=Color.red(),
                description="Disconnected",
            ),
        )

    async def on_resumed(self) -> None:
        self.connected = True
        await self.watchdog.send_message(
            self,
            embed=Embed(
                color=Color.teal(),
                description="Connected",
            ),
        )

    async def get_standing_status(self) -> StandingStatus:
        data = await self.http.request(
            Route(
                "GET",
                "/safety-hub/@me",
            ),
        )
        state = data.get("account_standing", {}).get("state", 0)
        return USER_STANDING_STATUS_MAP.get(state, USER_STANDING_STATUS_MAP[0])

    @override
    async def is_owner(self, user: BaseUser, /) -> bool:  # ty:ignore[invalid-method-override]
        if self.owner_id or self.owner_ids:
            return bool(self.owner_id and user.id == self.owner_id) or bool(
                self.owner_ids and user.id in self.owner_ids,
            )

        return await super().is_owner(user)

    async def is_mudae_channel(self, ctx: Context | Message, /) -> bool:
        if not isinstance(ctx, Context | Message):
            return False
        return ctx.channel.id in self.mudae_channel_ids

    async def is_mudae_owner(self, ctx: Context | Message, /) -> bool:
        if not isinstance(ctx, Context | Message):
            return False
        if not isinstance(ctx.author, Member | User):
            return False
        author = ctx.author._user if isinstance(ctx.author, Member) else ctx.author  # noqa: SLF001
        return await self.is_owner(author)

    @property
    async def mudae_channel(self) -> Messageable:
        channel_id = self.mudae_channel_ids[0]
        channel = self.get_channel(channel_id)
        if channel is None:
            channel = await self.fetch_channel(channel_id)
        if not isinstance(channel, Messageable):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        return channel

    @property
    async def mudae_guild(self) -> Guild:
        channel = await self.mudae_channel
        guild = (await channel._get_channel()).guild  # noqa: SLF001
        if not guild:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        return guild

    async def send_mudae_message(self, content: str, /, *, prefix: bool | None = None) -> Message:
        if prefix:
            logger.debug(f"[{self.name}] /{content}")
        channel = await self.mudae_channel
        return await channel.send(f"{self.mudae_bot_prefix if prefix else ''}{content}", silent=True)

    @property
    async def mudae_commands(self) -> list[SlashCommand]:
        channel = await self.mudae_channel
        commands = await channel.application_commands()
        return [c for c in commands if isinstance(c, SlashCommand) and c.application_id == self.APP_ID]

    async def get_mudae_command(self, name: str, /) -> SlashCommand | SubCommand:
        group, name = ([*name.split(maxsplit=1), ""])[:2]

        commands = await self.mudae_commands
        commands = [c for c in commands if c.name == group]
        if name:
            commands = [
                child for c in commands for child in c.children if isinstance(child, SubCommand) and child.name == name
            ]

        if len(commands) < 1:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        return commands.pop()

    async def send_mudae_command(self, name: str, /, **kwargs: str) -> Interaction:
        log_options = " ".join(f"{key}={value}" for key, value in kwargs.items())
        logger.debug(f"[{self.name}] /{name}{f' {log_options}' if log_options else ''}")
        command = await self.get_mudae_command(name)

        if self.user is None:
            msg = "Client user is not available"
            raise RuntimeError(msg)

        top_level_name = command.parent.name if isinstance(command, SubCommand) else command.name
        user_id = self.user.id

        def check(interaction: Interaction) -> bool:
            return interaction.name == top_level_name and interaction.user.id == user_id

        pending_interaction = self.wait_for("interaction", check=check, timeout=15)
        pending_finish = self.wait_for("interaction_finish", check=check, timeout=15)
        await command(**kwargs)

        interaction = await pending_interaction
        finished = await pending_finish
        if not finished.successful:
            msg = f"Interaction /{name} failed"
            raise RuntimeError(msg)

        return interaction
