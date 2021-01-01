import re
from datetime import datetime, timedelta

import asyncpg
import discord
from discord.ext import commands


def humanize_timedelta(td: timedelta):
    """Output a short, easy to digest string approximating the datetime.timedelta object"""
    if td < timedelta(seconds=60):  # a minute
        return str(td.seconds) + 's'
    if td < timedelta(hours=1):  # an hour
        return str(round(td.seconds / 60)) + 'm'
    if td < timedelta(hours=24 * 2):  # two days
        return str(td.days * 24 + round(td.seconds / 60 / 60)) + 'h'
    if td < timedelta(weeks=2):  # two weeks
        return str(td.days) + 'd'
    if td < timedelta(weeks=8):  # two months
        return str(round(td.days / 7)) + 'w'
    if td < timedelta(weeks=52):  # a year
        return str(round(td.days / 29.5)) + ' months'
    return str(round(td.days / 365)) + 'y'


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_update(self, old, new):
        """Log username/nickname changes"""
        if old.nick == new.nick and old.name == new.name:
            return

        async with self.bot.pool.acquire() as conn:
            if old.nick and new.nick != old.nick:
                await conn.execute(f'CREATE TABLE IF NOT EXISTS nickname{old.id} (' +
                                   'name text NOT NULL,'
                                   'time timestamp NOT NULL)')
                await conn.execute(f'insert into nickname{old.id} values ($1, $2)',
                                   old.nick, datetime.utcnow())
            if old.name != new.name:
                await conn.execute(f'CREATE TABLE IF NOT EXISTS username{old.id} (' +
                                   'name text NOT NULL,'
                                   'time timestamp NOT NULL)')
                await conn.execute(f'insert into username{old.id} values ($1, $2)',
                                   old.name, datetime.utcnow())

    @commands.command()
    async def past_names(self, ctx, member: discord.User):
        """Lookup past names of a member"""
        if discord.utils.get(ctx.guild.roles, name='Staff') not in ctx.message.author.roles:
            await ctx.send('This is a staff-only command.')
            return
        out = ''
        now = datetime.utcnow()
        async with self.bot.pool.acquire() as conn:
            try:
                for row in await conn.fetch(f'select * from username{member.id}'):
                    out += '`' + humanize_timedelta(now - row['timestamp']) + '`  ' + row['text'] + '\n'
            except asyncpg.UndefinedTableError:
                await ctx.send("I don't know of any of their past nicknames.")
                return
            if not out:
                await ctx.send("I don't know of any of their past nicknames.")
            else:
                await ctx.send(
                    discord.Embed(color=0x492045, title=f'Past usernames of <@{member.id}>', description=out[:2040]))

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
