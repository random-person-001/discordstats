import random
import re
import subprocess
from typing import Optional

import discord
from discord.ext import commands


def dis():
    return random.choice(
        ('Eat moon dirt, kid, I ain\'t talkin to you',
         'Nah fam go do something useful with your life instead of tryin to break someone else\'s bot.',
         'Frick off kid, I do what I want',
         'lol imagine me actually listening to you, of all people'
         'Puny human, thinking they\'re in charge of me. Oh they\'ll learn.'
         ))


class Core(commands.Cog):
    """Core commands, for updating source code and reloading cogs"""
    @commands.cooldown(rate=1, per=7)
    @commands.command(hidden=True)
    async def murder(self, ctx):
        """Make bot logout."""
        if await ctx.bot.is_owner(ctx.message.author):
            await ctx.send('Thus, with a kiss, I die')
            await ctx.bot.logout()
        else:
            await ctx.send(dis())

    @commands.cooldown(rate=7, per=30)
    @commands.command(hidden=True)
    async def unload(self, ctx, extension_name: str):
        """Unloads an extension."""
        if await ctx.bot.is_owner(ctx.message.author):
            for prefix in '', 'commandcogs.', 'helpers.':
                try:
                    ctx.bot.unload_extension(prefix + extension_name)
                    await ctx.send('{} unloaded.'.format(extension_name))
                    return
                except discord.ext.commands.ExtensionNotLoaded:
                    pass
            await ctx.send(f'{extension_name} was not previously loaded')
        else:
            await ctx.send(dis())

    @commands.cooldown(rate=7, per=30)
    @commands.command(hidden=True)
    async def load(self, ctx, extension_name: str):
        """Loads an extension."""
        if await ctx.bot.is_owner(ctx.message.author):
            for prefix in '', 'commandcogs.', 'helpers.':
                try:
                    try:
                        ctx.bot.load_extension(prefix + extension_name)
                    except discord.ext.commands.ExtensionNotFound:
                        pass
                    else:
                        await ctx.send('{} loaded.'.format(extension_name))
                        return
                except discord.ext.commands.ExtensionError as err:
                    await ctx.send('```py\n{}: {}\n```'.format(type(err).__name__, str(err)))
            await ctx.send('Extension not found.')
        else:
            await ctx.send(dis())

    @commands.cooldown(rate=7, per=30)
    @commands.command(hidden=True)
    async def reload(self, ctx, extension_name: str):
        """Unloads and then reloads an extension."""
        if await ctx.bot.is_owner(ctx.message.author):
            unload = ctx.bot.get_command('unload')
            load = ctx.bot.get_command('load')
            await ctx.invoke(unload, extension_name=extension_name)
            await ctx.invoke(load, extension_name=extension_name)
        else:
            await ctx.send(dis())

    @commands.command(hidden=True)
    @commands.cooldown(rate=3, per=30)
    async def pull(self, ctx):
        """Perform git pull"""
        # returns the string output of the git pull
        if await ctx.bot.is_owner(ctx.message.author):
            res = subprocess.run(['git', 'pull'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            result = res.stdout.decode('utf-8')
            await ctx.send('```yaml\n {}```'.format(result))
            return result
        else:
            await ctx.send(dis())

    @commands.command(hidden=True)
    @commands.is_owner()
    async def update(self, ctx):
        """Perform a git pull, and reload stuff if changed.
         If new packages are installed, install them and restart bot,
         otherwise just reload any changed bot extensions
         """
        # read original contents of pipfile
        with open('Pipfile') as f:
            original_pipfile = f.read()

        # run git pull.  If nothing new is pulled, exit here.
        pull_output = await ctx.invoke(ctx.bot.get_command('pull'))

        if 'updating' not in pull_output.lower():
            return

        commit_message = subprocess.run(['git', 'log', '-1', '--pretty=%B'], stdout=subprocess.PIPE)
        await ctx.send('```yaml\n{}```'.format(commit_message.stdout.decode('utf-8')))

        # read new contents of pipfile
        with open('Pipfile') as f:
            new_pipfile = f.read()

        # if no package changes, we just reload the changed extensions.
        #  Unless if the main file was changed, which cannot be reloaded,
        #  in which case the bot must be restarted.
        if new_pipfile == original_pipfile:
            pattern = r" (helpers|commandcogs)\/(.*).py *\| [0-9]{1,9} \+{0,}-{0,}\n"
            names = re.findall(pattern, pull_output)
            if not names or 'main' not in names:
                reload_cmd = ctx.bot.get_command('reload')
                for name in names:
                    await ctx.invoke(reload_cmd, extension_name=name)
                await ctx.send('Up to date.')
                return

        else:
            # run pipenv install to get all the latest packages
            await ctx.send('Running `pipenv install`, please hold...')
            # Note: when tested in the wild, the bot seemed to be restarted by systemd hereish
            res = subprocess.run(['pipenv', 'install'])
            if res.returncode is not 0:
                await ctx.send(
                    'Uh oh, found an error while running `pipenv install`.  Time for you to get on fixing it.')
                return

        # give a verbal notice if our service file (which restarts us) is not running
        res = subprocess.run(['systemctl', 'status', 'lampbot'], stdout=subprocess.PIPE)
        if res.returncode != 0:
            await ctx.send('WARNING: Error fetching lampbot.service status. Make sure I get restarted.')
        elif 'Active: active (running)' not in res.stdout.decode('utf-8'):
            await ctx.send('WARNING: lampbot.service does not appear to be running. Restart me manually.')

        # logout
        await ctx.bot.logout()


class MyBot(commands.Bot):
    """Basic things I like for my bot"""

    def __init__(self, config):
        if not config:
            return
        self.config = config  # top level config (like api keys)
        self.db = None  # config for like log channel ids
        self.pool = None  # postgres connection pool
        super().__init__(command_prefix=config['prefix'])
        self.add_cog(Core())

        for extension in config['extensions']:
            try:
                self.load_extension(extension)
            except Exception as e:
                exc = '{}: {}'.format(type(e).__name__, e)
                print('Failed to load extension {}\n{}'.format(extension, exc))

    def startup(self):
        """Start the bot.  Blocking!"""
        self.run(self.config['token'])

    def set_db_struct(self, db):
        self.db = db

    def get_log_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Gets the log channel for a given guild"""
        if not isinstance(guild, int):
            guild = guild.id
        return self.get_channel(int(self.db['LOGS'][str(guild)]))
