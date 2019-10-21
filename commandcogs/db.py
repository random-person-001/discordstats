import json
from datetime import datetime, timedelta
from typing import List

import asyncpg
import discord
from discord.ext import commands
from emoji import UNICODE_EMOJI

from helpers import Paginator


def is_emoji(s):
    return s in UNICODE_EMOJI


def truncate(s: str, length: int):
    """Truncate and escape a string to certain length"""
    s = s.replace('\n', ' ').replace('`', '\\`')
    emoji_so_far = 0
    for i in range(len(s)):
        if is_emoji(s[i]) or s[i] == '︵':
            emoji_so_far += 1
        # emoji are (about) two characters wide
        if i + emoji_so_far >= length:
            s = s[:i]
            break

    # make an attempt to not leave trailing escaping backslashes
    if s.endswith('\\') and not (len(s) > 2 and s[:-2] == '\\'):
        s = s[:-1] + ' '
    return s


def get_channel_widths(res: list):
    """Get a dict of field names : field lengths"""
    default_widths = {'id': 19, 'author': 19, 'bot': 1,
                      'content': 20, 'deleted': 1, 'edited_at': 5,
                      'embed': 1, 'attachment': 6, 'reactions': 1}

    # if it mostly matches our default data set, return this
    similarities = sum(key in default_widths for key in res[0].keys())
    if similarities >= len(default_widths) / 2:
        return default_widths

    # allow extra wide columns when there are few of them
    max_width = max((20, int(90 / len(res[0]) - len(res[0]))))

    # else we gotta guess
    widths = dict()
    for r in res:
        for (field, value) in r.items():
            if field not in widths:
                widths[field] = 1
            if value and not isinstance(value, bool):
                widths[field] = min(max_width, max(len(str(value)), widths[field]))
    print(widths)
    return widths


def str_chan_res(res: list):
    """stringify a asyncpg.Result list for sending in chat"""
    if len(res) <= 5:
        return '\n'.join((str(r)) for r in res).replace('`', '\\`')
    if len(res) > 100:
        res2 = res[:50]
        res2.extend(res[:-50])
        res = res2

    widths = get_channel_widths(res)
    out = '(╯°□°）╯︵ ┻━┻\n<Fields: '
    out += ' '.join(key for key in res[0].keys())

    for r in res:
        out += '\n|'
        for item in r.items():
            width = widths[item[0]] if item[0] in widths else 1
            val = str(item[1]) if item[1] else ''
            out += truncate(val.ljust(width), width) + '|'
    return out


async def reactions_to_json(reactions: List[discord.Reaction]):
    """Given a list of Reactions to a message,
    return a suitable json representation of them
    """
    out = dict()
    for reaction in reactions:
        emoji_str = reaction.emoji  # this will be unicode if standard emoji
        if reaction.custom_emoji:
            emoji_str = ('<a:' if reaction.emoji.animated else '<:') \
                        + f'{reaction.emoji.name}:{reaction.emoji.id}>'
        users = list(user.id for user in await reaction.users().flatten())
        out[emoji_str] = users
    if not out:
        return None
    return out


def add_reaction_to_json(event: discord.RawReactionActionEvent, prev):
    """Adjust for a new reaction added to a message,
    given a previous reaction representation,
    and return the new suitable json representation
    """
    #  Sample representation of the data structure here:
    #  {'\ud83d\udc40👍': [23456, 23456]}, '<a:trash:234567>': [654, 3456, 567]}

    if event.emoji.is_custom_emoji():
        emoji_str = ('<a:' if event.emoji.animated else '<:')
        emoji_str += f'{event.emoji.name}:{event.emoji.id}>'
    else:
        emoji_str = event.emoji.name  # this will be unicode
    if not prev:
        prev = dict()

    if emoji_str in prev:
        prev[emoji_str].append(event.user_id)
    else:
        prev[emoji_str] = [event.user_id]
    return prev


def json_dumps_unicode(data):
    return json.dumps(data, ensure_ascii=False)


async def init_connection(conn):
    """Set json data that we get from the db to be parsed
    into a python data structure for us, and write that way too
    """
    await conn.set_type_codec('json',
                              encoder=json_dumps_unicode,
                              decoder=json.loads,
                              schema='pg_catalog'
                              )


class DB(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.connect())
        self.markov_model = None
        self.paginators = []

    def cog_unload(self):
        self.bot.loop.create_task(self.disconnect())

    async def connect(self):
        if not self.bot.pool or self.bot.pool._closed:
            args = {'user': self.bot.config['postgresuser'],
                    'password': self.bot.config['postgrespwd'],
                    'database': 'discord',
                    'host': '127.0.0.1',
                    'loop': self.bot.loop,
                    'init': init_connection}
            self.bot.pool = await asyncpg.create_pool(**args)
            print('db pool initialized')
        print('db connected!')

    async def disconnect(self):
        await self.bot.pool.close()

    async def create_chan_table(self, chan):
        """Create a db table for a given channel.  This also updates all relevant views"""
        if not isinstance(chan, discord.TextChannel):
            return
        async with self.bot.pool.acquire() as conn:
            await conn.execute(
                f'CREATE TABLE IF NOT EXISTS c{chan.id} (' + '''
                  id int8 PRIMARY KEY,
                  author int8 NOT NULL,
                  bot bool NOT NULL default 'f',
                  content varchar(2000) NOT NULL,
                  del bool NOT NULL default 'f',
                  edited_at timestamp DEFAULT NULL,
                  attachment varchar(500) DEFAULT NULL,
                  embed json DEFAULT NULL,
                  reactions json DEFAULT NULL
            )
            ''')
            # we have a view (titled the same as the table, but with an extra c in front)
            # of every table that includes the date at which the message was sent
            await conn.execute(
                f' create or replace view cc{chan.id}' +
                '  as select *, to_timestamp(((id >> 22) + 1420070400000) / 1000) as date' +
                f' from c{chan.id}'
            )
            # update our view of all the messages in the guild
            u = ' union all '.join(' select * from cc' + str(c.id) for c in chan.guild.text_channels)
            try:
                await conn.execute(f' create or replace view gg{chan.guild.id} as {u}')
            except asyncpg.exceptions.UndefinedTableError:
                pass

    @commands.command()
    @commands.is_owner()
    async def post(self, ctx, *, query):
        """Run a postgres sql query"""
        async with self.bot.pool.acquire() as conn:
            try:
                response = await conn.fetch(query)
            except Exception as e:
                await ctx.send(f'Oh no!  An error! `{e}`')
            else:
                if not response:
                    await ctx.send('```toml\n[nothing returned]```')
                else:
                    s = str_chan_res(response)
                    if (len(s)) > 1985:
                        s = s[:1985]
                    await ctx.send(f'```xml\n{s}```')

    @commands.command(hidden=True)
    @commands.is_owner()
    async def create_tables(self, ctx):
        """Create activity tables for all channels I can see.
        This should only be run once, on setup.
        """
        for chan in self.bot.get_all_channels():
            await self.create_chan_table(chan)
        await ctx.send('done')

    @commands.command(hidden=True)
    @commands.is_owner()
    async def make_warns_view(self, ctx, warns_channel: discord.TextChannel):
        """Create a table view that has all warns.
        This works by parsing messages from dyno and mee6 about warns."""
        async with ctx.bot.pool.acquire() as conn:
            await conn.execute(f'create or replace view warns{ctx.guild.id} as '
                               ' select victim, count(*) as warns from ('
                               " select author, ("
                               "    SELECT regexp_matches("
                               "        embed->'fields'->0->>'value', "
                               "        '<@!?(\\d*)>'))[1]::int8 "
                               "    as victim "
                               f"FROM c{warns_channel.id}"
                               " where embed->'author'->>'name' ilike '%warn%'"
                               " ) as t"
                               " group by victim")
        await ctx.send('done')

    @commands.command()
    @commands.is_owner()
    async def avg_warns(self, ctx):
        """Calculate the average warns for each xp level"""
        import collections
        xp_levels = collections.OrderedDict(
            zip(('Stardust', 'Meteoroid', 'Asteroid', 'Dwarf Planet', 'Rocky Planet', 'Gas Giant', 'Brown Dwarf',
                 'Main Sequence Star', 'Giant Star', 'Supergiant Star', 'Open Cluster', 'Globular Cluster'),
                [[0, 0]] * 13
                ))
        table_name = f'warns{ctx.guild.id}'
        xp_rolls = [discord.utils.get(ctx.guild.roles, name=level) for level in xp_levels]
        async with ctx.bot.pool.acquire() as conn:
            for member in ctx.guild.members:
                # get how many warns they have
                warns = await conn.fetchval(f'select warns from {table_name} where victim = {member.id}')
                # incrament xp roll count
                for roll in xp_rolls:
                    if roll in member.roles:
                        xp_levels[roll.name][1] += 1
                        if warns:
                            xp_levels[roll.name][0] += warns
                        break
            print(xp_levels)
            await ctx.send('\n'.join([f'{level}: \t {xp_levels[level]}' for level in xp_levels]))

    @commands.command()
    @commands.is_owner()
    async def log_back(self, ctx, chan_id: int, n: int):
        """Ensure we have the last `n` messages sent
        from a channel in our local db
        """
        chan = discord.utils.get(ctx.bot.get_all_channels(), id=chan_id)
        if not chan:
            await ctx.send('channel not found sorry')
        try:
            async for message in chan.history(limit=n):
                await self.on_message(message)
            await ctx.send('done')
        except discord.errors.Forbidden:
            await ctx.send('_need...\nmoar...\nperms..._')

    @commands.command(hidden=True)
    @commands.is_owner()
    async def much_downtime(self, ctx, days: float, guild: int = None):
        """Ensure we have all messages in the last `n` days sent
        in our local db
        if no guild id is specified, it will go through all guilds.
        """
        oldest = datetime.utcnow() - timedelta(days=days)
        guilds = [guild] if guild else ctx.bot.guilds
        for guild in guilds:
            for chan in guild.text_channels:
                try:
                    async for message in chan.history(after=oldest, limit=None):
                        await self.on_message(message)
                    print(f"Logged {days} days of #{chan.name}")
                except discord.errors.Forbidden:
                    print(f"Can't see history of #{chan.name}")
        await ctx.send("All caught up!")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def show_cache_by_channel(self, ctx):
        msg = 'Count of cached messages for each channel:\n'
        async with ctx.bot.pool.acquire() as conn:
            for chan in ctx.guild.text_channels:
                count = await conn.fetchval(f'select count(*) from c{chan.id} where not del')
                msg += chan.mention + str(count) + '\n'
        await ctx.send(msg)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def drop_pg_tables(self, ctx):
        async with self.bot.pool.acquire() as conn:
            for chan in self.bot.get_all_channels():
                if isinstance(chan, discord.TextChannel):
                    await conn.execute(f'DROP TABLE IF EXISTS c{chan.id}')
        await ctx.send('done')

    @commands.command()
    async def puns(self, ctx, channel: discord.TextChannel = None):
        """Output a score ranking of puns"""
        if not channel:
            channel = ctx.channel
        query = u" select author, reactions, id" \
            f" from cc{channel.id}" \
                "  where reactions::json->>'\U0001F345'" \
                "  is not null" \
                "  order by date desc"
        async with self.bot.pool.acquire() as conn:
            res = await conn.fetch(query)
        paginator = Paginator.Paginator(self.bot, ctx.channel, title='Puns in #' + channel.name, color=0x123e57)
        for row in res:
            author = ctx.guild.get_member(row['author'])
            author = 'Gone' if author is None else author.display_name
            emojis = " ".join(emoji + ' ' + str(len(row['reactions'][emoji])) for emoji in row['reactions'])
            link = f'https://discordapp.com/channels/{channel.guild.id}/{channel.id}/{row["id"]}'
            paginator.add_line(f'[{emojis} - {author}]({link})')
        self.paginators.append(paginator)
        await paginator.post()

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        deads = []
        for paginator in self.paginators:
            if paginator.dead:
                deads.append(paginator)
            else:
                await paginator.on_reaction_add(reaction, user)
        for paginator in deads:
            self.paginators.remove(paginator)

    @commands.Cog.listener()
    async def on_message(self, msg: discord.message):
        async with self.bot.pool.acquire() as conn:
            if not msg.content:
                msg.content = ''
            embeds = None
            attachment = None

            if msg.attachments:
                # Except for uploads on mobiles, there is only 1 per message.  I ignore subsequent ones
                """
                if len(msg.attachments) > 1:
                    print('\n\nMESSAGE WITH MULTIPLE EMBEDS: ' + msg.jump_url)
                    locke = discord.utils.get(self.bot.users, id=275384719024193538)
                    await locke.send('Yo this message has more than '
                                     'one attachment, fix yo code: ' + msg.jump_url)
                 """
                attachment = msg.attachments[0].url

            if msg.embeds:
                if msg.embeds[0].type == 'rich':
                    embeds = msg.embeds[0].to_dict()

            # For logging messages sent previously, this add their reactions in.
            # New messages won't have reactions, so this just returns null then
            reactions = await reactions_to_json(msg.reactions)

            # edited timestamp is included in case we're logging historical messages
            try:
                await conn.execute(f"insert into c{msg.channel.id} values "
                                   f"($1, $2, $3, $4, 'f', $5, $6, $7, $8)",
                                   msg.id, msg.author.id, msg.author.bot,
                                   msg.content, msg.edited_at, attachment,
                                   embeds, reactions)
            except asyncpg.exceptions.UniqueViolationError:
                # this method is called for fetching historical records,
                # so we occasionally fetch something already in the db
                pass
            except asyncpg.exceptions.UndefinedTableError:
                # this can happen when the bot has just been installed and
                # tables are not yet configured.
                # Thus we automatically do the configuration.
                for chan in self.bot.get_all_channels():
                    await self.create_chan_table(chan)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        chan_id = payload.data['channel_id']
        if hasattr(payload, 'cached_message') and payload.cached_message is not None:
            timestamp = payload.cached_message.edited_at
        else:
            timestamp = datetime.utcnow()
        async with self.bot.pool.acquire() as conn:
            prev = await conn.fetchrow(f'select * from c{chan_id} where id = $1', payload.message_id)
            if not prev:
                # the message being edited has not been recorded by us
                return
            content = payload.data['content'] if 'content' in payload.data else prev['content']
            embed = prev['embed']
            if 'embeds' in payload.data and payload.data['embeds'] and payload.data['embeds'][0]['type'] == 'rich':
                embed = payload.data['embeds'][0]
            await conn.execute(f'update c{chan_id} set edited_at = $1, content = $2, embed = $3 where id = $4',
                               timestamp, content, embed, payload.message_id)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, event):
        async with self.bot.pool.acquire() as conn:
            prev = await conn.fetchval(f"select reactions from c{event.channel_id} where id = $1", event.message_id)
            new_val = add_reaction_to_json(event, prev)
            await conn.execute(f"update c{event.channel_id} set reactions = $1 where id = $2",
                               new_val, event.message_id)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, event):
        async with self.bot.pool.acquire() as conn:
            await conn.execute(f"update c{event.channel_id} set del = 't' where id = $1", event.message_id)

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, event):
        async with self.bot.pool.acquire() as conn:
            for msg_id in event.message_ids:
                await conn.execute(f"update c{event.channel_id} set del = 't' where id = $1", msg_id)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, chan):
        await self.create_chan_table(chan)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        for chan in guild.text_channels:
            await self.create_chan_table(chan)


def setup(bot):
    bot.add_cog(DB(bot))
