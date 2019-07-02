import datetime

import discord
from discord.ext import commands


class Tattler(commands.Cog):
    """
    Log when bots go offline or return online.
    """

    def __init__(self, bot):
        self.bot = bot
        # dict of (bot) members pointing to datetimes that they were last online
        self.last_onlines = []

    def get_log_channel(self, guild):
        return self.bot.db['CHANNEL_REARRANGING']['log_channels'][guild]

    async def log_returning(self, who: discord.Member, last_online_time: datetime.datetime):
        chan = self.get_log_channel(who.guild)
        if last_online_time:
            duration = last_online_time - datetime.datetime.utcnow()
        else:
            duration = 'idk how long really'
        await chan.send(f'{who} is back online! (down for {duration})')

    async def log_leaving(self, who: discord.Member):
        chan = self.get_log_channel(who.guild)
        await chan.send(f'{who} is now offline!')

    @commands.Cog.listener()
    async def on_member_update(self, old, new):
        if not old.bot:
            return
        if old.status == new.status:
            return
        if old.status != discord.Status.offline and new.status != discord.Status.offline:
            return

        if new.status == discord.Status.offline:
            # they just dropped offline
            self.last_onlines[new] = datetime.datetime.utcnow()
            await self.log_leaving(new)
        else:
            # they just returned from online
            if new not in self.last_onlines:
                self.last_onlines[new] = None
            await self.log_returning(new, self.last_onlines[new])
