import re

import discord
from discord.ext import commands


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    async def verify(self, ctx):
        """Become verified in the server
        This is a feature pending support in the server
        """
        roll_id = 339136164533501983  # todo: replace me when actual roll made
        roll = ctx.guild.get_role(roll_id)
        if roll not in ctx.author.roles:
            await ctx.author.add_roles(roll, reason='Self verified \N{White Heavy Check Mark}')
            await ctx.message.add_reaction('\N{White Heavy Check Mark}')
        else:
            await ctx.send("No need; you're already verified \N{Thumbs Up Sign}")

    async def is_linkbot(self, message):
        """
        Test if all of the following conditions are met:
        1) The user's message has a clickable link in it
        2) This is the user's first message
        3) The message contains any of the words 'porn' or 'naked'
        """

        # only analyze if the message has a nsfw tinge to it
        bad_words = ('porn', 'naked', 'nude')
        if not any(bad_word in message.content for bad_word in bad_words):
            return False
        print('ono it has bad words')

        # only analyze if the message has a clickable link in it
        if not re.search('https?://', message.content):
            return False
        print('and it has a link')

        # only analyze if this is their first message
        # this uses the bot's local message db to reduce load and increase speed
        async with self.bot.pool.acquire() as conn:
            msg_count = await conn.fetch(f'select count(*) from gg{message.guild.id}'
                                         f' where author = $1', message.author.id)['count']
            if msg_count > 1:
                return False
        print('and its like their first message')

        return True

    async def ban_linkbots(self, message):
        """Given that a message was sent by a linkbot, ban them, delete their message, and log it"""
        print(f'yeah ok banhammer time for {message.author}')

        log_channels = self.bot.db['CHANNEL_REARRANGING']['log_channels']
        # todo: change that to a more legit setting
        #  ... that probably involves redoing the local settings ug
        err_channel = self.bot.get_channel(log_channels[str(message.guild.id)])
        try:
            await message.delete()
        except discord.errors.Forbidden:
            await err_channel.send(f'Insufficient perms to delete message in {message.channel.mention}')
        try:
            banned = message.author
            await message.author.ban(reason='autodetected nsfw bot \N{Pouting Face}')
            log_channel = discord.utils.get(message.guild.channels, name='change-logs')
            msg = f':boom::hammer:  Banned {banned.mention} cuz it was another obnoxious nsfw bot smh\n' + \
                  f'(aka {banned}, {banned.id})'
            await log_channel.send(msg)
        except discord.errors.Forbidden:
            await err_channel.send(f'Autobanning of bot {message.author} failed cuz I need moar perms')

    @commands.Cog.listener()
    async def on_message(self, message):
        if await self.is_linkbot(message):
            await self.ban_linkbots(message)


def setup(bot):
    bot.add_cog(Admin(bot))
