import asyncio

from selfcord.ext.commands import Context, command

from src.mudae.client import MudaeClient
from src.mudae.cogs import MudaeCog

from .lock import MUDAE_SAY_LOCK


class MudaeSay(MudaeCog):
    def __init__(self, client: MudaeClient, /) -> None:
        super().__init__(client)

    @command()
    async def say(self, ctx: Context, *, message: str) -> None:
        async with MUDAE_SAY_LOCK, await ctx.typing():
            await asyncio.sleep(1)
            await ctx.send(message)


async def setup(client: MudaeClient) -> None:
    await client.add_cog(MudaeSay(client))
