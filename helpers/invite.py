import re

import discord
from discord.ext import commands


class InviteWacher(commands.Cog):
    """
    Log invites that are posted
    """

    def __init__(self, bot):
        self.bot = bot
        self.regex = r"discord\.gg\/(\w{4,})\b"

    async def log(self, invite_code, msg):
        chan = self.bot.get_log_channel(msg.guild.id)
        changes = self.bot.get_channel(401172732856762370)
        try:
            invite = await self.bot.fetch_invite(invite_code)
        except discord.NotFound:
            await chan.send(f'An invalid/expired invite was posted in {msg.channel.mention} by {msg.author}.')
            return

        e = discord.Embed(title="Some sneaky user posted an invite! grrrr",
                          description=f"Inviter was {invite.inviter} ({invite.inviter.id})", color=0x993322)
        e.add_field(name='Guild name', value=invite.guild.name)
        e.add_field(name='Guild id', value=invite.guild.id)
        e.add_field(name='Channel name', value=invite.channel.name)
        e.add_field(name='Total members', value=invite.approximate_member_count)
        e.add_field(name='Online members', value=invite.approximate_presence_count)
        e.set_thumbnail(url=invite.guild.icon_url)
        await chan.send(embed=e)

        try:
            await msg.delete()
        except discord.Forbidden:
            await chan.send("(I wouldda deleted it but I was just hiding my powers)")
        else:
            await changes.send(f'- deleted an invite by {msg.author} in {msg.channel.mention}')

        staff_bot_room = self.bot.get_channel(395649976048287758)
        welcome_rules = self.bot.get_channel(391765381645336577)
        retort = await msg.channel.send(f'Hey {msg.author.mention} please note that the rules here don\'t '
                                        f'allow posting invites. It may serve you well to review {welcome_rules.mention} again.')
        await staff_bot_room.send(f'hey yo please warn user {msg.author.id} - {retort.jump_url}')

    @commands.Cog.listener()
    async def on_message(self, msg):
        results = re.findall(self.regex, msg.content, re.I)
        for res in results:
            await self.log(res, msg)


def setup(bot):
    bot.add_cog(InviteWacher(bot))
