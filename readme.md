# Discord Data bot
Graph stats about channel activity

Built with python 3.7 and discord.py, using matplotlib.

Note that in its current implementation, the graphing occurs in the main bot thread.  This is blocking, and is bad, and the bot will not respond while it occurs.  Eventually I may improve that.

![example output for line command](https://cdn.discordapp.com/attachments/500896262351093761/568268930964127784/channel_activity.png)

![example output for line command](https://cdn.discordapp.com/attachments/500896262351093761/568283419323138068/channel_activity.png)

![example output for bar command](https://media.discordapp.net/attachments/500896262351093761/568284315167883286/channel_activity.png)

## Commands
Remember to put your prefix (default is %) in front of these!

`line` - Show a pretty, smooth line graph of channel activity over time

`bar` - show a nonsmoothed bar chart of channel activity over time


## Installing
This uses [pipenv](https://pipenv.readthedocs.io/en/latest/install/) so make sure you have that installed.
The bot was built for linux, so should work fine there and on macs.  There's a chance that, as ever, making the code run on windows could have some hiccups.

In a terminal, run `git clone https://github.com/random-person-001/discordstats.git && cd discordstats`

You'll need a [discord token](https://github.com/reactiflux/discord-irc/wiki/Creating-a-discord-bot-&-getting-a-token) to get the bot running. Rename `exampleconfig.toml` to `config.toml` and put the token in there.

Then run
`pipenv install` and `pipenv run python src/main.py`

Your bot should hopefully be running!  Invite it somewhere to test with the link https://discordapp.com/api/oauth2/authorize?client_id=LONGNUMBER&scope=bot, replacing `LONGNUMBER` with your bot's discord ID.
