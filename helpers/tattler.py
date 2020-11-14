import datetime

import discord
from discord.ext import commands


class Tattler(commands.Cog):
    """
    Log when bots go offline or return online, and when members leave
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

        # tell people in verification channel that mee6 is back and they don't have to use dyno any more
        if who.id == self.conf()['mee6']:
            verification = self.bot.get_channel(self.conf()['verification'])
            await verification.send("Ayyy mee6 is back; you can use !verify again :thumbsup: ")

    async def log_leaving(self, who: discord.Member):
        chan = self.bot.get_log_channel(who.guild)
        await chan.send(f'{who} is now offline!')

        # tell people in verification that mee6's !verify won't work and to do dyno instead
        if who.id == self.conf()['mee6']:
            verification = self.bot.get_channel(self.conf()['verification'])
            await verification.send("Hey looks like mee6 is down; in the meantime just use Dyno with ^verify")

    @commands.Cog.listener()
    async def on_member_update(self, old, new):
        await self.check_bot_offlines(old, new)
        await self.check_verified(old, new)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        e = discord.Embed(title=f"{member} left", description=f"User ID: `{member.id}`", color=0x0)
        if member.nick:
            e.add_field(name="Nickname", value=member.nick)
        e.set_thumbnail(url=member.avatar_url)
        e.add_field(name="Joined", value=member.joined_at)
        e.add_field(name="Rolls", value=", ".join(r.mention for r in member.roles))
        await self.bot.get_log_channel(member.guild).send(embed=e)

    async def check_verified(self, old, new):
        """If mee6 is down, look for new members getting stardust and then greet them"""
        mee6 = old.guild.get_member(self.conf()['mee6'])
        if not mee6 or mee6.status != discord.Status.offline:
            return
        stardust = old.guild.get_role(self.bot.config['SHEETS']['basic_roll'])
        if stardust in old.roles or stardust not in new.roles:
            return
        msg = f"Look, everybody! A new star has been discovered! {new.mention}! Enjoy your time looking up!"
        chan = new.guild.get_channel(self.conf()['greeting_channel'])
        await chan.send(msg)

    async def check_bot_offlines(self, old, new):
        """Look for bots going offline, and log them"""
        if not old.bot:
            return
        if old.status == new.status:
            return
        if old.status != discord.Status.offline and new.status != discord.Status.offline:
            return
        if any(new.id == id_ for id_ in self.conf()['dontlog']):
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

    @commands.Cog.listener()
    async def on_member_join(self, noob):
        """When mee6 is down, do its job of welcoming for it"""
        mee6 = noob.guild.get_member(self.conf()['mee6'])
        if not mee6 or mee6.status != discord.Status.offline:
            return
        verification = self.bot.get_channel(self.conf()['verification'])
        msg = f'Welcome {noob.mention}! Read <#391765381645336577>, and type "^verify" in this channel to give ' \
            'yourself the basic role which will let you talk in the rest of the server.'
        await verification.send(msg)

    def conf(self):
        """Convenience method"""
        return self.bot.config['TATTLER']


def setup(bot):
    bot.add_cog(Tattler(bot))
