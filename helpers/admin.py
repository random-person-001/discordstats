import re
from datetime import datetime

import discord
from discord.ext import commands


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_update(self, old, new):
        """Log username/nickname changes"""
        if old.nick == new.nick and old.name == new.name:
            return

        print('O.o')
        print(old.id)

        async with self.bot.pool.acquire() as conn:
            await conn.execute(f'CREATE TABLE IF NOT EXISTS nickname{old.id} (' +
                               'name text NOT NULL,'
                               'time timestamp NOT NULL)')
            await conn.execute(f'CREATE TABLE IF NOT EXISTS username{old.id} (' +
                               'name text NOT NULL,'
                               'time timestamp NOT NULL)')
            if old.nick and new.nick != old.nick:
                await conn.execute(f'insert into nickname{old.id} values ($1, $2)',
                                   old.nick, datetime.utcnow())
            elif old.name != new.name:
                await conn.execute(f'insert into username{old.id} values ($1, $2)',
                                   old.name, datetime.utcnow())

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
        3) The message contains any of the words 'porn', 'naked', 'onlyfans', or 'nude'
        """

        # only analyze if the message has a nsfw tinge to it
        bad_words = ('porn', 'naked', 'nude', 'onlyfans')
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
            if msg_count > 2:
                return False
        print('and its like their first message')

        return True

    async def ban_linkbots(self, message):
        """Given that a message was sent by a linkbot, ban them, delete their message, and log it"""
        print(f'yeah ok banhammer time for {message.author}')

        err_channel = self.bot.get_primary_log_channel(message.guild)
        try:
            await message.delete()
        except discord.errors.Forbidden:
            await err_channel.send(f'Insufficient perms to delete message in {message.channel.mention}')
        try:
            banned = message.author
            await message.author.ban(reason='autodetected nsfw bot \N{Pouting Face}')
            log_channel = discord.utils.get(message.guild.channels, name='change-logs')
            msg = f':boom::hammer:  I banned {banned.mention} cuz it was another obnoxious nsfw bot smh\n' + \
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
