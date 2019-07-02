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

from helpers import Paginator


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
        p = Paginator.Paginator(ctx.bot, ctx.channel, title='Oldest accounts in this guild')
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
