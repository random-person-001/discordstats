import json
import os
import random
import re
import subprocess

import discord
import toml
from discord.ext import commands


def write_db():
    """Write out a db file with default settings"""
    print('Didn\'t find a db file, so creating a new one with default settings')
    data = {'ACTIVITY': {
        'excluded_channels': []
    }, 'CHANNEL_REARRANGING': {
        'log_channels': {
            325354209673216010: 325354209673216010,
            391743485616717824: 568975675252408330
        }
    }, 'ALARM': {
        'err_channels': {
            325354209673216010: 325354209673216010,
            391743485616717824: 568975675252408330
        }
    }, 'APOD':  {
        'channel': {
            325354209673216010: 325354209673216010,
            391743485616717824: 395649976048287758
        }
    }, 'REACTION': {
        'max_age': 3,  # days
        'log_channels': {
            325354209673216010: 325354209673216010,
            391743485616717824: 568975675252408330
        }
    }
    }
    with open("db.json", "w") as f:
        json.dump(data, f)
    return data


def get_db():
    """Get the persistent settings for the bot. You shouldn't need to worry about this"""
    try:
        with open('db.json') as f:
            return json.load(f)
    except:
        return write_db()


def prep():
    """Make sure the environment and config stuff is set up right, giving hopefully helpful messages if not"""
    if discord.__version__[0] != '1':  # async is about 0.16, rewrite is 1.0+
        print("Looks like you're using the old async discord.py library. This is written in rewrite. "
              "You should really run this with pipenv instead of on your system environment... see the readme.md")
        return
    try:
        config = toml.load("config.toml")
    except (TypeError, toml.TomlDecodeError):
        print("Oy, it looks like your `config.toml` file is incorrectly formatted")
        return
    except FileNotFoundError:
        print("Oops, couldn't find a config file. Try renaming `exampleconfig.toml` to `config.toml` "
              "(more help can be found in the file `readme.md`)")
        return
    else:
        if not os.path.exists('logs'):  # make sure we have a place to log errors if we encounter them
            os.mkdir('logs')
        for key in ('token', 'prefix', 'extensions', 'loadingemoji', 'colormaps'):
            if key not in config:
                print('Oof, looks like you\'re missing the entry for `{}` in the config.toml file. '
                      'Perhaps reference `exampleconfig.toml`?'.format(key))
                return
        return config


config = prep()
bot = commands.Bot(command_prefix=config['prefix'])
disses = ('Eat moon dirt, kid, I ain\'t talkin to you',
          'Nah fam go do something useful with your life instead of tryin to break someone else\'s bot.',
          'Frick off kid, I do what I want',
          'lol imagine me actually listening to you, of all people'
          'Puny human, thinking they\'re in charge of me. Oh they\'ll learn.'
          )


@commands.cooldown(rate=1, per=7)
@bot.command(hidden=True)
async def murder(ctx):
    """Make bot logout."""
    if await bot.is_owner(ctx.message.author):
        await ctx.send('Thus, with a kiss, I die')
        await bot.logout()
    else:
        await ctx.send(random.choice(disses))


@commands.cooldown(rate=7, per=30)
@bot.command(hidden=True)
async def unload(ctx, extension_name: str):
    """Unloads an extension."""
    if await bot.is_owner(ctx.message.author):
        bot.unload_extension(extension_name)
        await ctx.send('{} unloaded.'.format(extension_name))
    else:
        await ctx.send(random.choice(disses))


@commands.cooldown(rate=7, per=30)
@bot.command(hidden=True)
async def load(ctx, extension_name: str):
    """Loads an extension."""
    if await bot.is_owner(ctx.message.author):
        try:
            bot.load_extension(extension_name)
        except (AttributeError, ImportError) as err:
            await ctx.send('```py\n{}: {}\n```'.format(type(err).__name__, str(err)))
            return
        await ctx.send('{} loaded.'.format(extension_name))
    else:
        await ctx.send(random.choice(disses))


@commands.cooldown(rate=7, per=30)
@bot.command(hidden=True)
async def reload(ctx, extension_name: str):
    """Unloads and then reloads an extension."""
    if await bot.is_owner(ctx.message.author):
        try:
            bot.unload_extension(extension_name)
            await ctx.send('{} unloaded.'.format(extension_name))
        except discord.ext.commands.errors.ExtensionNotLoaded:
            pass
        try:
            bot.load_extension(extension_name)
        except (AttributeError, ImportError, discord.ext.commands.errors.ExtensionNotFound) as err:
            await ctx.send('```py\n{}: {}\n```'.format(type(err).__name__, str(err)))
            return
        await ctx.send('{} loaded.'.format(extension_name))
    else:
        await ctx.send(random.choice(disses))


@bot.command(hidden=True)
@commands.is_owner()
@commands.cooldown(rate=3, per=30)
async def pull(ctx):
    """Perform git pull"""
    # returns the string output of the git pull
    if await bot.is_owner(ctx.message.author):
        res = subprocess.run(['git', 'pull', 'origin', 'master'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        result = res.stdout.decode('utf-8')
        await ctx.send('```yaml\n {}```'.format(result))
        return result
    else:
        await ctx.send(random.choice(disses))


@bot.command(hidden=True)
@commands.is_owner()
async def update(ctx):
    """Perform a git pull, and reload stuff if changed.
     If new packages are installed, install them and restart bot,
     otherwise just reload any changed bot extensions
     """
    # read original contents of pipfile
    with open('Pipfile') as f:
        original_pipfile = f.read()

    # run git pull.  If nothing new is pulled, exit here.
    pull_output = ctx.invoke(ctx.bot.get_command('pull'))
    if 'Already up to date.' in pull_output:
        return

    # read new contents of pipfile
    with open('Pipfile') as f:
        new_pipfile = f.read()

    # if no package changes, we just reload the changed extensions.
    #  Unless if the main file was changed, which cannot be reloaded,
    #  in which case the bot must be restarted.
    if new_pipfile == original_pipfile:
        pattern = r" src/(.*).py *\| [0-9]{1,9} \+{0,}-{0,}\n"
        names = re.findall(pattern, pull_output)
        if 'main' not in names:
            reload_cmd = ctx.bot.get_command('reload')
            for name in names:
                await ctx.invoke(reload_cmd, extension_name=name)
            await ctx.send('Up to date.')
            return

    else:
        # run pipenv install to get all the latest packages
        await ctx.send('Running `pipenv install`, please hold...')
        res = subprocess.run(['pipenv', 'install'])
        if res.returncode is not 0:
            await ctx.send('Uh oh, found an error while running `pipenv install`.  Time for you to get on fixing it.')
            return

    # give a verbal notice if our service file (which restarts us) is not running
    res = subprocess.run(['systemctl', 'status', 'lampbot'], stdout=subprocess.PIPE)
    if res.returncode != 0:
        await ctx.send('WARNING: Error fetching lampbot.service status. Make sure I get restarted.')
    elif 'Active: active (running)' not in res.stdout.decode('utf-8'):
        await ctx.send('WARNING: lampbot.service does not appear to be running. Restart me manually.')

    # logout
    await bot.logout()


if __name__ == '__main__':
    if config:
        bot.config = config
        bot.db = get_db()  # load the db file. User doesn't have to touch this
        bot.mydatacache = dict()  # for caching data for graphing
        bot.pool = None  # postgres connection pool
        for extension in config['extensions']:
            try:
                bot.load_extension(extension)
            except Exception as e:
                exc = '{}: {}'.format(type(e).__name__, e)
                print('Failed to load extension {}\n{}'.format(extension, exc))
        bot.run(bot.config['token'])
