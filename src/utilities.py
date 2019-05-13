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


class Utility(commands.Cog):
    def __init__(self, bot):
        psutil.cpu_percent()  # first time this is run, it returns 0
        self.bot = bot

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
    async def info(self, ctx):
        """Who am I?  What am I doing here?  Where shall I get lunch?"""
        libs = 'Built with the help of the following packages: '
        with open('Pipfile') as f:
            pip_data = toml.load(f)
        libs += ', '.join(pip_data['packages'].keys())

        loc = str(dir_line_count('./src'))

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


def setup(bot):
    bot.add_cog(Utility(bot))
