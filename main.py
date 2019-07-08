import json
import logging
import os

import discord
import toml

from helpers.mybot import MyBot

# set up logging
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='logs/discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


def write_db():
    """Write out a db file with default settings"""
    print('Didn\'t find a db file, so creating a new one with default settings')
    data = {'REACTION_MAX_AGE': 3,  # days
            'LOGS': {
                325354209673216010: 325354209673216010,  # guild id: log channel id
                391743485616717824: 568975675252408330
            },
            'ACTIVITY_EXCLUDED_CHANNELS': []
            }
    with open("config/db.json", "w") as f:
        json.dump(data, f)
    return data


def get_db():
    """Get the persistent settings for the bot. You shouldn't need to worry about this"""
    # noinspection PyBroadException
    try:
        with open('config/db.json') as f:
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
        config = toml.load("config/config.toml")
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
        for key in ('token', 'prefix', 'extensions'):
            if key not in config:
                print('Oof, looks like you\'re missing the entry for `{}` in the config.toml file. '
                      'Perhaps reference `exampleconfig.toml`?'.format(key))
                return
        return config


config = prep()
bot = MyBot(config)

if __name__ == '__main__':
    if config:
        bot.set_db_struct(get_db())  # load the db file. User doesn't have to touch this
        bot.startup()
