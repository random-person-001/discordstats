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
        self.image_muted_chans = set()  # ids

    @commands.Cog.listener()
    async def on_member_update(self, old, new):
        """Log nickname changes"""
        if old.nick == new.nick:
            return
        async with self.bot.pool.acquire() as conn:
            if old.nick and new.nick != old.nick:
                await conn.execute(f'CREATE TABLE IF NOT EXISTS nickname{old.id} (' +
                                   'name text NOT NULL,'
                                   'time timestamp NOT NULL)')
                await conn.execute(f'insert into nickname{old.id} values ($1, $2)',
                                   old.nick, datetime.utcnow())
                print('yeet inserted into table')

    @commands.Cog.listener()
    async def on_user_update(self, old, new):
        """Log username changes"""
        if old.name == new.name:
            return
        async with self.bot.pool.acquire() as conn:
            if old.name != new.name:
                await conn.execute(f'CREATE TABLE IF NOT EXISTS username{old.id} (' +
                                   'name text NOT NULL,'
                                   'time timestamp NOT NULL)')
                await conn.execute(f'insert into username{old.id} values ($1, $2)',
                                   old.name, datetime.utcnow())
                print('yeet inserted into table')

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
                for row in await conn.fetch(f'select * from username{member.id} order by time desc'):
                    out += '`' + humanize_timedelta(now - row['time']) + ' `  ' + row['name'] + '\n'
            except asyncpg.UndefinedTableError:
                await ctx.send("I don't know of any of their past nicknames.")
                return
            if not out:
                await ctx.send("I don't know of any of their past nicknames.")
            else:
                await ctx.send(embed=
                               discord.Embed(color=0x492045, title=f'Past usernames of {member}',
                                             description=out[:2040]))

    @commands.Cog.listener()
    async def on_message(self, message):
        await self.check_for_naughties(message)
        if await self.is_linkbot(message):
            await self.ban_linkbots(message)

    @commands.Cog.listener()
    async def on_message_edit(self, old, new):
        await self.check_for_naughties(new)

    async def check_for_naughties(self, msg):
        if not msg.author.bot and msg.channel.id in self.image_muted_chans:
            if msg.embeds or msg.attachments:
                log_channel = self.bot.get_secondary_log_channel(msg.guild)
                try:
                    await msg.delete()
                except discord.Forbidden:
                    await log_channel.send(f'Could not do my job of deleting ILLEGAL messages in {msg.channel.mention}')
                except (discord.NotFound, discord.HTTPException):
                    pass
                else:
                    await msg.channel.send(f'{msg.author.mention}, sending images is not allowed rn', delete_after=5)
                    await log_channel.send(f'Deleted message by {msg.author} with attachment/embed '
                                           f'in {msg.channel.mention}')

    @commands.command(aliases=['disallow_images', 'stop_images', 'no_images', 'shutup'])
    async def imageoff(self, ctx, channel: discord.TextChannel = None):
        """Start yeeting any message in the channel that has an embed or attachment"""
        if discord.utils.get(ctx.guild.roles, name='Staff') not in ctx.author.roles:
            await ctx.send('Only staff may use this :sadpluto:')
            return
        if not channel:
            channel = ctx.channel
        if channel.id in self.image_muted_chans:
            await ctx.send("Bruh it's already on the Naughty List")
        else:
            self.image_muted_chans.add(channel.id)
            await ctx.send(f'New messages with attachments or embeds will now be deleted in {channel.mention}\n\n'
                           'To deactivate this, run `=allow_images`')
            await ctx.bot.get_secondary_log_channel(ctx.guild).send(f'{channel.mention} is now on the No Images '
                                                                    f'Naughty List  :eyes:  \n\n'
                                                                    f'Turn this off with `=allow_images`')

    @commands.command(aliases=['allow_images', 'yes_images', 'start_images'])
    async def imageon(self, ctx, channel: discord.TextChannel = None):
        """Stop yeeting any message in the channel that has an embed or attachment"""
        if discord.utils.get(ctx.guild.roles, name='Staff') not in ctx.author.roles:
            await ctx.send('Only staff may use this :sadpluto:')
            return
        if not channel:
            channel = ctx.channel
        if channel.id not in self.image_muted_chans:
            await ctx.send("Bruh it's not on the Naughty List, u dont needta do this")
        else:
            self.image_muted_chans.remove(channel.id)
            await ctx.send('Yeet we gucci')
            await channel.send('Ok yall can post images again, but don\'t go crazy (I still got my eyes on ya)')
            await ctx.bot.get_secondary_log_channel(ctx.guild).send(f'{channel.mention} is no longer on the No Images '
                                                                    f'Naughty List')

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


def setup(bot):
    bot.add_cog(Admin(bot))
