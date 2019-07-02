import platform
import subprocess
import traceback
from datetime import datetime, timedelta
from os import listdir
from os.path import isfile, isdir, join

import discord
import psutil
import toml
from discord.ext import commands


def item_line_count(path):
    """Functions to get lines of code in a directory from
    https://stackoverflow.com/questions/38543709/count-lines-of-code-in-directory-using-python/49417516#49417516
    """
    if isdir(path):
        return dir_line_count(path)
    elif isfile(path):
        return len(open(path, 'rb').readlines())
    else:
        return 0


def dir_line_count(dir):
    return sum(map(lambda item: item_line_count(join(dir, item)), listdir(dir)))


class Paginator(discord.ext.commands.Paginator):
    """Usage:
    Instantiate one of these, call add_line() as wanted, then post().
    Hold a list of these in a cog, removing them when `dead`, and passing
    on_reaction_add event to each of these
    """

    def __init__(self, bot, channel: discord.TextChannel, **embed_kwargs):
        """If the footer is empty, it will be set to like 'Page x of X'"""
        super().__init__(prefix='', suffix='', max_size=2048)
        self.dead = False
        self.page_num = 0
        self.channel = channel
        self.bot = bot
        self.msg = None
        self.dynamic_footer = not embed_kwargs or 'footer' not in embed_kwargs
        if not embed_kwargs:
            embed_kwargs = {'footer': discord.Embed.Empty}
        if 'color' not in embed_kwargs:
            embed_kwargs['color'] = 0x004a92
        self.embed_args = embed_kwargs

    def _get_embed(self):
        if self.dynamic_footer:
            self.embed_args['footer'] = f'Page {self.page_num + 1} of {len(self.pages)}'
        if self.pages:
            description = self.pages[self.page_num]
        else:
            description = 'Nothing to see here; move along'
            self.embed_args['footer'] = discord.Embed.Empty
        return discord.Embed(description=description,
                             **self.embed_args).set_footer(text=self.embed_args['footer'])

    async def post(self):
        try:
            self.msg = await self.channel.send(embed=self._get_embed())
            if len(self.pages) > 1:
                await self.msg.add_reaction('\N{BLACK LEFT-POINTING TRIANGLE}')
                await self.msg.add_reaction('\N{BLACK RIGHT-POINTING TRIANGLE}')
        except discord.errors.Forbidden:
            self.dead = True

    async def _refresh(self):
        if not self.dead:
            await self.msg.edit(embed=self._get_embed())
            await self._clear_reactions(leave_mine=True)

    async def _clear_reactions(self, leave_mine=False):
        # the instance of self.msg we have stored will not have any reactions on it
        cached = discord.utils.get(self.bot.cached_messages, id=self.msg.id)
        if not cached:
            cached = await self.msg.channel.fetch_message(self.msg.id)
        for reaction in cached.reactions:
            async for user in reaction.users():
                if not (leave_mine and user.id == self.bot.user.id):
                    try:
                        await reaction.remove(user)
                    except (discord.errors.Forbidden, discord.errors.NotFound, discord.errors.HTTPException):
                        pass

    async def on_reaction_add(self, reaction, user):
        if not discord.utils.get(self.bot.cached_messages, id=self.msg.id):
            print('paginator dropped from cache')
            self.dead = True
            await self._clear_reactions()
        if not self.msg or reaction.message.id != self.msg.id or user.id == self.bot.user.id or self.dead:
            return
        if reaction.emoji == '\N{BLACK LEFT-POINTING TRIANGLE}':
            if self.page_num > 0:
                self.page_num -= 1
                await self._refresh()
        elif reaction.emoji == '\N{BLACK RIGHT-POINTING TRIANGLE}':
            if self.page_num < len(self.pages):
                self.page_num += 1
                await self._refresh()


class Utility(commands.Cog):
    def __init__(self, bot):
        psutil.cpu_percent()  # first time this is run, it returns 0
        self.bot = bot
        self.paginators = []

    @commands.command()
    async def time(self, ctx, discord_id: int):
        """Extract the utc timestamp that a discord object with the given id was created"""
        await ctx.send(discord.utils.snowflake_time(discord_id))

    @commands.command(hidden=True)
    @commands.is_owner()
    async def say(self, ctx, chan_id: int, *, msg):
        chan = ctx.bot.get_channel(chan_id)
        await chan.send(msg)

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

    @commands.command()
    async def oldies(self, ctx, guild_id: int = None):
        """Show a list of the oldest discord user accounts in this guild"""
        if not guild_id:
            guild_id = ctx.guild.id
        guild = ctx.bot.get_guild(guild_id)
        if not guild:
            await ctx.send(f"I'm not in any guild whose id is {guild_id}")
            return
        members = sorted(guild.members, key=lambda member: member.created_at)
        now = datetime.utcnow()
        p = Paginator(ctx.bot, ctx.channel, title='Oldest accounts in this guild')
        for m in members:
            p.add_line("{} days:  {}".format((now - m.created_at).days, m.mention))
        self.paginators.append(p)
        await p.post()

    @commands.command()
    async def info(self, ctx):
        """Who am I?  What am I doing here?  Where shall I get lunch?"""
        libs = 'Built with the help of the following packages: '
        with open('Pipfile') as f:
            pip_data = toml.load(f)
        libs += ', '.join(pip_data['packages'].keys())

        loc = str(dir_line_count('.'))

        python_version = 'Running python ' + platform.python_version()
        os_info = platform.platform()

        mem = psutil.virtual_memory()
        memory = '{}% - {} free of {} mb'.format(
            mem.percent, round(mem.available / 1_048_576), round(mem.total / 1_048_576))

        cpu = 'CPU: {}%'.format(psutil.cpu_percent())

        p = psutil.Process()
        with p.oneshot():
            cpu_time = str(round(p.cpu_times().user)) + ' seconds'
            start_time = p.create_time()
        # Note: using utcnow() is wrong; we must use now()
        age_seconds = datetime.now().timestamp() - start_time
        age = str(timedelta(seconds=age_seconds))[:-4]

        temp_data = psutil.sensors_temperatures()['coretemp'][0]
        temperature = '{}°C (limit={})'.format(temp_data.current, temp_data.critical)

        proc = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT)
        commit = proc.stdout.decode('utf-8')

        e = discord.Embed(title="About me",
                          description="A general purpose bot for Spacecord, made by Locke.\n\n" + libs,
                          color=0x004a92)
        e.set_thumbnail(url=ctx.bot.user.avatar_url)
        e.add_field(name='CPU', value=cpu)
        e.add_field(name='Memory', value=memory)
        e.add_field(name='Temperature', value=temperature)
        e.add_field(name='Bot uptime', value=age)
        e.add_field(name='CPU Time', value=cpu_time)
        e.add_field(name='Lines of Code', value=loc)
        e.add_field(name='Commands', value=str(len(ctx.bot.commands)))
        e.add_field(name='Commit Hash', value=commit)
        e.add_field(name='Discord.py Version', value=discord.__version__)
        e.set_footer(text=python_version + ' on ' + os_info)
        await ctx.send(embed=e)

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


def setup(bot):
    bot.add_cog(Utility(bot))
