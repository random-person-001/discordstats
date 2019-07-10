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
        self.last_onlines = dict()

    async def log_returning(self, who: discord.Member, last_online_time: datetime.datetime):
        chan = self.bot.get_log_channel(who.guild)
        if last_online_time:
            duration = datetime.datetime.utcnow() - last_online_time
        else:
            duration = 'idk how long really'
        await chan.send(f'{who} is back online! (down for {duration})')

    async def log_leaving(self, who: discord.Member):
        chan = self.bot.get_log_channel(who.guild)
        await chan.send(f'{who} is now offline!')

    @commands.Cog.listener()
    async def on_member_update(self, old, new):
        if not old.bot:
            return
        if old.status == new.status:
            return
        if old.status != discord.Status.offline and new.status != discord.Status.offline:
            return
        if any(old.id is id for id in self.bot.config['TATTLER']['dontlog']):
            return

        if new.status == discord.Status.offline:
            # they just dropped offline
            self.last_onlines[new.id] = datetime.datetime.utcnow()
            await self.log_leaving(new)
        else:
            # they just returned from online
            if new.id not in self.last_onlines:
                self.last_onlines[new.id] = None
            await self.log_returning(new, self.last_onlines[new.id])


def setup(bot):
    bot.add_cog(Tattler(bot))
