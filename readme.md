# Discord Data bot
Graph stats about channel activity

Built with python 3.7 and discord.py, using matplotlib.

Note that in its current implementation, the graphing occurs in the main bot thread.  This is blocking, and is bad, and the bot will not respond while it occurs.  Eventually I may improve that.

![example output](https://i.imgur.com/6xwWrom.png)

## Commands
Remember to put your prefix (default is %) in front of these!

`line` - Show a pretty, smooth line graph of channel activity over time

`bar` - show a nonsmoothed bar chart of channel activity over time


## Installing
In a terminal, run `git clone https://github.com/random-person-001/discordstats.git && cd discordstats`

You'll need a discord token to get the bot running. Rename `exampleconfig.toml` to `config.toml` and put the token in there.

Then run
`pipenv install` and then `pipenv run python src/main.py`

Your bot should hopefully be running!  Invite it somewhere to test with the link https://discordapp.com/api/oauth2/authorize?client_id=LONGNUMBER&scope=bot, replacing `LONGNUMBER` with your bot's discord ID.