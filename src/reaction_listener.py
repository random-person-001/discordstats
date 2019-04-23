import asyncio
from datetime import datetime, timedelta
from discord.ext import commands
import discord


class ReactionListener(commands.Cog):
    """Log emoji reactions to messages way way back

    When a user reacts to a message that's very old (like to write a hidden message), this will log a link to that
    message, in the configured logging channel.
    """

    def __init__(self, bot):
        self.bot = bot
        # dict of id of message reacted to, pointing towards (time of last reaction, reaction logging message, count)
        self.log_msgs = dict()
        self.max_age = 3  # days

    def cleanup(self):
        """keep self.log_msgs small"""
        old_keys = []
        for key in self.log_msgs:
            if datetime.utcnow() - self.log_msgs[key][0] > timedelta(seconds=120):
                old_keys.append(key)
        for key in old_keys:
            self.log_msgs.pop(key)

    # https://discordpy.readthedocs.io/en/latest/api.html#discord.on_raw_reaction_add
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, event):
        self.cleanup()  # this should be called every so often

        # Logging channels: a dict of server ids pointing to log channel ids
        log_channels = {325354209673216010: 325354209673216010, 391743485616717824: 568975675252408330}
        # only concern ourselves with reactions to ancient posts
        if datetime.utcnow() - discord.utils.snowflake_time(event.message_id) > timedelta(days=self.max_age):
            link = f'https://discordapp.com/channels/{event.guild_id}/{event.channel_id}/{event.message_id}'
            if event.guild_id in log_channels:
                log_chan = self.bot.get_channel(log_channels[event.guild_id])

                # this is the first log for them reacting on this message
                if event.message_id not in self.log_msgs:
                    log_message = await log_chan.send(f'<@{event.user_id}> reacted to the old message {link} (x1)')
                    self.log_msgs[event.message_id] = (datetime.utcnow(), log_message.id, 1)

                # they reacted recently, so don't send a whole new message about this
                else:
                    _, log_message_id, n = self.log_msgs[event.message_id]
                    n += 1
                    self.log_msgs[event.message_id] = (datetime.utcnow(), log_message_id, n)
                    try:
                        log_message = await log_chan.fetch_message(log_message_id)
                    except (discord.errors.NotFound, discord.errors.Forbidden, discord.errors.HTTPException):
                        pass
                    else:
                        await asyncio.sleep(n/5)  # slight delay.  This makes the count accurate for rapid additions
                        await log_message.edit(content=f'<@{event.user_id}> reacted to the old message {link} (x{n})')


def setup(bot):
    bot.add_cog(ReactionListener(bot))
