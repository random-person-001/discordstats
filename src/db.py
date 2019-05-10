from datetime import datetime
import traceback

import asyncpg
import discord
from discord.ext import commands
from emoji import UNICODE_EMOJI


def is_emoji(s):
    return s in UNICODE_EMOJI


def truncate(s: str, length: int):
    """Truncate and escape a string of certain length"""
    s = s.replace('\n', ' ')
    s = discord.utils.escape_markdown(s).replace('\\_', '_').replace('\\*', '*')
    emoji_so_far = 0
    for i in range(len(s)):
        if is_emoji(s[i]):
            emoji_so_far += 1
            print(s[i] + 'is emoji')
        # emoji are two characters wide
        if i + emoji_so_far >= length:
            s = s[:i]
            break

    # make an attempt to not leave trailing escaping backslashes
    if s.endswith('\\') and not (len(s) > 2 and s[:-2] == '\\'):
        s = s[:-1] + ' '
    return s


def get_channel_widths(res: list):
    """Get a dict of field names : field lengths"""
    default_widths = {'id': 19, 'author': 19, 'content': 20, 'deleted': 1, 'edited_at': 5, 'embed': 1,
              'attachments': 1, 'reactions': 1}
    # if it mostly matches our default data set, return this
    if sum(key in default_widths for key in res[0].keys()) >= len(default_widths)/2:
        print('sim')
        return default_widths
    # else we gotta guess
    maxes = dict()
    for r in res:
        for item in r.items():
            if item[0] not in maxes:
                maxes[item[0]] = 1
            if item[1] and not isinstance(item[1], bool):
                maxes[item[0]] = min(20, max(len(str(item[1])), maxes[item[0]]))
    print(maxes)
    return maxes


def str_chan_res(res: list):
    """Take the result from a channel and stringify it"""
    if len(res) <= 5:
        return '\n'.join(discord.utils.escape_markdown(str(r), as_needed=False, ignore_links=False) for r in res)
    if len(res) > 500:
        res = res[:250].append(*res[:-250])
    # set up buckets
    widths = get_channel_widths(res)
    out = '(╯°□°）╯︵ ┻━┻\n<Fields:'
    for key in res[0].keys():
        out += ' ' + key
    for r in res:
        out += '\n|'
        for item in r.items():
            if item[0] in widths:
                width = widths[item[0]]
            else:
                width = 1
            val = str(item[1])
            if not item[1]:
                val = ''
            out += truncate(val.ljust(width), width) + '|'
    return out


class DB(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.connect())

    def cog_unload(self):
        self.bot.loop.create_task(self.disconnect())

    async def connect(self):
        if not self.bot.pool or self.bot.pool._closed:
            self.bot.pool = await asyncpg.create_pool(user=self.bot.config['postgresuser'],
                                                      password=self.bot.config['postgrespwd'],
                                                      database='discord', host='127.0.0.1', loop=self.bot.loop)
            print('db pool initialized')
        print('db connected!')

    async def disconnect(self):
        await self.bot.pool.close()

    async def create_chan_table(self, chan):
        async with self.bot.pool.acquire() as conn:
            if isinstance(chan, discord.TextChannel):  # and chan.permissions_for(self.bot.me).read_messages:
                await conn.execute(f'CREATE TABLE IF NOT EXISTS c{chan.id} (' + '''
                      id int8 PRIMARY KEY,
                      author int8 NOT NULL,
                      content varchar(2000),
                      deleted bool NOT NULL default 'f',
                      edited_at timestamp DEFAULT NULL,
                      embed json DEFAULT NULL,
                      attachments json DEFAULT NULL,
                      reactions json DEFAULT NULL
                )
                ''')

    @commands.command()
    @commands.is_owner()
    async def post(self, ctx, *, query):
        """Run an sql query"""
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
        for chan in self.bot.get_all_channels():
            await self.create_chan_table(chan)
        await ctx.send('done')

    @commands.Cog.listener()
    async def on_message(self, msg: discord.message):
        embeds = None
        if msg.embeds:
            if msg.embeds[0].type == 'rich':
                embeds = msg.embeds[0].to_dict()
        async with self.bot.pool.acquire() as conn:
            await conn.execute(f'insert into c{msg.channel.id} values ($1, $2, $3)', msg.id, msg.author.id, msg.content)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        chan_id = payload.data['channel_id']
        if hasattr(payload, 'cached_message'):
            timestamp = payload.cached_message.edited_at
        else:
            timestamp = datetime.utcnow()
        async with self.bot.pool.acquire() as conn:
            await conn.execute(f'update c{chan_id} set edited_at = $1 where id = $2', timestamp, payload.message_id)
            # todo: content update

    @commands.Cog.listener()
    async def on_raw_message_delete(self, event):
        async with self.bot.pool.acquire() as conn:
            await conn.execute(f'update c{event.channel_id} set deleted = t where id = $2', event.message_id)

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, event):
        async with self.bot.pool.acquire() as conn:
            for msg_id in event.message_ids:
                await conn.execute(f'update c{event.channel_id} set deleted = t where id = $1', msg_id)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, chan):
        await self.create_chan_table(chan)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        for chan in guild.text_channels:
            await self.create_chan_table(chan)


def setup(bot):
    bot.add_cog(DB(bot))
