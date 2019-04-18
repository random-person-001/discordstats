import discord
import toml
from discord.ext import commands


def write_db():
    """Write out a db file with default settings"""
    print('Didn\'t find a db file, so creating a new one with default settings')
    data = {
        'excluded_channels': []
    }
    with open("db.toml", "w") as f:
        f.write("# This file was automatically generated and will be overwritten when settings are updated\n")
        toml.dump(data, f)
    return data


def get_db():
    """Get the persistent settings for the bot. The bot owner shouldn't need to worry about this"""
    try:
        return toml.load("db.toml")
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
        for key in ("token", "prefix", "extensions"):
            if key not in config:
                print("Oof, looks like you're missing the entry for `{}` in the config.toml file. "
                      "Perhaps reference `exampleconfig.toml`?".format(key))
                return
        return config


config = prep()
bot = commands.Bot(command_prefix=config['prefix'])


@commands.cooldown(rate=1, per=7)
@bot.command(hidden=True)
async def murder(ctx):
    """Make bot logout."""
    if await bot.is_owner(ctx.message.author):
        await ctx.send("Thus, with a kiss, I die")
        await bot.logout()
    else:
        await ctx.send("Eat moon dirt, kid, I ain't talkin to you")


@commands.cooldown(rate=7, per=30)
@bot.command(hidden=True)
async def reload(ctx, extension_name: str):
    """Unloads and then reloads an extension."""
    if await bot.is_owner(ctx.message.author):
        bot.unload_extension(extension_name)
        await ctx.send("{} unloaded.".format(extension_name))
        try:
            bot.load_extension(extension_name)
        except (AttributeError, ImportError) as err:
            await ctx.send("```py\n{}: {}\n```".format(type(err).__name__, str(err)))
            return
        await ctx.send("{} loaded.".format(extension_name))
    else:
        await ctx.send(
            "This is what you call sarcasm, isn't it? Cuz I'm a free bot and do what I want, not what you tell me to.")


if __name__ == "__main__":
    if config:
        bot.config = config
        bot.db = get_db()  # load the db file. User doesn't have to touch this
        bot.mydatacache = dict()  # for caching data for graphing
        for extension in config['extensions']:
            try:
                bot.load_extension(extension)
            except Exception as e:
                exc = '{}: {}'.format(type(e).__name__, e)
                print('Failed to load extension {}\n{}'.format(extension, exc))
        bot.run(bot.config['token'])

