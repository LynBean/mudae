from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from selfcord.ext.commands import Context, command

if TYPE_CHECKING:
    from src.mudae.client import MudaeClient

from . import MudaeCog


class MudaeKakeraBadge(MudaeCog):
    BADGES: ClassVar[list[str]] = [
        "bronze",
        "silver",
        "gold",
        "sapphire",
        "ruby",
        "emerald",
        "diamond",
    ]

    def __init__(self, client: MudaeClient, /) -> None:
        super().__init__(client)

    @command()
    async def badge(self, ctx: Context) -> None:
        async with self.lock, await ctx.typing():
            if not self.client.user:
                return

            await self.send_mudae_command("modclean kakerarefund", input=f"<@{self.client.user.id}>")
            await self.send_mudae_message("confirm")

            await self.send_mudae_command("kakera bronze", input="2")
            await self.send_mudae_message("yes")
            await self.send_mudae_command("kakera silver", input="2")
            await self.send_mudae_message("yes")
            await self.send_mudae_command("kakera gold", input="2")
            await self.send_mudae_message("yes")
            await self.send_mudae_command("kakera ruby", input="4")
            await self.send_mudae_message("yes")

            for badge in self.BADGES:
                await self.send_mudae_command(f"kakera {badge}", input="4")
                await self.send_mudae_message("yes")


async def setup(client: MudaeClient) -> None:
    await client.add_cog(MudaeKakeraBadge(client))
