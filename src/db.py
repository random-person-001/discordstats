import json
from datetime import datetime
import traceback
from typing import List

import asyncpg
import discord
from discord.ext import commands
from emoji import UNICODE_EMOJI


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

    # else we gotta guess
    widths = dict()
    for r in res:
        for (field, value) in r.items():
            if field not in widths:
                widths[field] = 1
            if value and not isinstance(value, bool):
                widths[field] = min(20, max(len(str(value)), widths[field]))
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
    out = '(╯°□°）╯︵ ┻━┻\n<Fields:'
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
    # this code is untested.
    out = []
    for reaction in reactions:
        emoji_str = reaction.emoji  # this will be unicode if standard emoji
        if reaction.custom_emoji:
            emoji_str = ('<a:' if reaction.emoji.animated else '<:') \
                   + f'{reaction.emoji.name}:{reaction.emoji.id}>'
        users = (user.id for user in await reaction.users().flatten())
        out.append({'emoji': emoji_str, 'count': reaction.count, 'users': users})
    return json.dumps(out)


def add_reaction_to_json(event: discord.RawReactionActionEvent, prev):
    """Adjust for a new reaction added to a message,
    given a previous reaction representation,
    and return the new suitable json representation
    """
    # Sample representation of the data structure here:
    # [{'emoji': '\ud83d\udc40👍', 'count': 2, 'users': [23456, 23456]},
    #  {'emoji': '<a:trash:234567>', 'count': 3, 'users': [654, 3456, 567]}]

    if event.emoji.is_custom_emoji():
        emoji_str = ('<a:' if event.emoji.animated else '<:')
        emoji_str += f'{event.emoji.name}:{event.emoji.id}>'
    else:
        emoji_str = event.emoji.name  # this will be unicode
    is_new_reaction = True
    print(prev)
    print(type(prev))
    if prev:
        prev = json.loads(prev)
        for reaction in prev:
            if reaction['emoji'] == emoji_str:
                reaction['count'] += 1
                reaction['users'].append(event.user_id)
                is_new_reaction = False
    else:
        prev = list()
    if is_new_reaction:
        prev.append({'emoji': emoji_str, 'count': 1, 'users': [event.user_id]})
    return json.dumps(prev)


async def init_connection(conn):
    """Set json data that we get from the db to be parsed
    into a python data structure for us, and write that way too
    """
    await conn.set_type_codec('json',
                              encoder=json.dumps,
                              decoder=json.loads,
                              schema='pg_catalog'
                              )


class DB(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.connect())
        self.markov_model = None

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
        async with self.bot.pool.acquire() as conn:
            if isinstance(chan, discord.TextChannel):
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
    async def eval(self, ctx, *, code: str):
        """Execute arbitrary python code. Owner only."""
        # noinspection PyBroadException
        try:
            result = eval(code)
        except Exception:
            await ctx.send(traceback.format_exc(chain=False))
        else:
            if len(str(result)) > 2000 - 15:
                result = str(result)[:1985]
            await ctx.send(f'```py\n{result}```')

    @commands.command(hidden=True)
    @commands.is_owner()
    async def create_tables(self, ctx):
        """Create activity tables for all channels I can see.
        This should only be run once, on setup.
        """
        for chan in self.bot.get_all_channels():
            await self.create_chan_table(chan)
        await ctx.send('done')

    @commands.command()
    @commands.is_owner()
    async def log_back(self, ctx, chan_id: int, n: int):
        """Ensure we have the last `n` messages sent
        from a channel in our local db
        """
        chan = discord.utils.get(ctx.bot.get_all_channels(), id=chan_id)
        async for message in chan.history(limit=n):
            await self.on_message(message)
        await ctx.send('done')

    @commands.command(hidden=True)
    @commands.is_owner()
    async def drop_pg_tables(self, ctx):
        async with self.bot.pool.acquire() as conn:
            for chan in self.bot.get_all_channels():
                if isinstance(chan, discord.TextChannel):
                    await conn.execute(f'DROP TABLE IF EXISTS c{chan.id}')
        await ctx.send('done')

    @commands.Cog.listener()
    async def on_message(self, msg: discord.message):
        async with self.bot.pool.acquire() as conn:
            if not msg.content:
                msg.content = ''
            embeds = None
            attachment = None

            if msg.attachments:
                # since I always assume there's max of 1
                # attachment per message, tell me if this is ever wrong
                if len(msg.attachments) > 1:
                    print('\n\nMESSAGE WITH MULTIPLE EMBEDS: ' + msg.jump_url)
                    locke = discord.utils.get(self.bot.users, id=275384719024193538)
                    await locke.send('Yo this message has more than '
                                     'one attachment, fix yo code: ' + msg.jump_url)
                attachment = msg.attachments[0].url

            if msg.embeds:
                if msg.embeds[0].type == 'rich':
                    embeds = msg.embeds[0].to_dict()
                await conn.set_type_codec(
                    'json',
                    encoder=json.dumps,
                    decoder=json.loads,
                    schema='pg_catalog'
                )

            try:
                await conn.execute(f"insert into c{msg.channel.id} values "
                                   f"($1, $2, $3, $4, 'f', NULL, $5, $6)",
                                   msg.id, msg.author.id, msg.author.bot,
                                   msg.content, attachment, embeds)
            except asyncpg.exceptions.UniqueViolationError:
                # this method is called for fetching historical records,
                # so we occasionally fetch something already in the db
                pass

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        chan_id = payload.data['channel_id']
        if hasattr(payload, 'cached_message'):
            timestamp = payload.cached_message.edited_at
        else:
            timestamp = datetime.utcnow()
        async with self.bot.pool.acquire() as conn:
            await conn.set_type_codec(
                'json',
                encoder=json.dumps,
                decoder=json.loads,
                schema='pg_catalog'
            )
            prev = await conn.fetchrow(f'select * from c{chan_id} where id = $1', payload.message_id)
            content = payload.data['content'] if 'content' in payload.data else prev['content']
            embed = prev['embed']
            if 'embeds' in payload.data and payload.data['embeds'] and payload.data['embeds'][0]['type'] == 'rich':
                embed = payload.data['embeds'][0]
            await conn.execute(f'update c{chan_id} set edited_at = $1, content = $2, embed = $3 where id = $4',
                               timestamp, content, embed, payload.message_id)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, event):
        print(event)
        async with self.bot.pool.acquire() as conn:
            prev = await conn.fetchval(f"select reactions from c{event.channel_id} where id = $1", event.message_id)
            print(prev)
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
