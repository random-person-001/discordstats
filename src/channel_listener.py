import pprint
import asyncio
import traceback
from datetime import datetime, timedelta

from discord.ext import commands


class ChannelListener(commands.Cog):
    """Log channel rearrangement events"""

    def __init__(self, bot):
        self.bot = bot
        self.chan_changes = dict()
        self.task = self.bot.loop.create_task(self.listener())

    def cog_unload(self):
        if self.task is not None:
            self.task.cancel()
            print('cancelled task')

    # https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_update
    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        """Listen for channel update events, and record them

        This stores data in a temporary place, to be looked at by a background task, rather than analyzing it itself.
        This is because if channel #2 is dragged after channel #5, this method will be called for channels 2, 3, 4, & 5
        (as each one is decremented except for #2), and we only want to send one message rather than four
        """
        if before.position != after.position:
            print('#{} moved from position {} to {}'.format(before.name, before.position, after.position))
            if before.guild.id not in self.chan_changes:
                self.chan_changes[before.guild.id] = []
            self.chan_changes[before.guild.id].append((datetime.now(), before, after))

            print(self.chan_changes)

    async def listener(self):
        """A background task that monitors the recently-changed channels, and tells about it in a channel"""
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            self.chan_changes[guild.id] = []  # init stuff
        # Logging channels: a dict of server ids pointing to log channel ids
        log_channels = {325354209673216010: 325354209673216010, 391743485616717824:568975675252408330}
        print('listener task begun')
        while True:
            log_channels = self.bot.db['CHANNEL_REARRANGING']['log_channels']
            await asyncio.sleep(1)
            for guild in self.bot.guilds:
                changes = self.chan_changes[guild.id] if guild.id in self.chan_changes else []
                if len(changes) > 0:
                    # wrap all the useful stuff in try-catch so we don't silently and permanently fail on error
                    try:
                        latest_change = max([chan[0] for chan in changes])
                        # wait for everything to calm down before complaining.  Don't wanna log something if ongoing
                        if (datetime.now() - latest_change) > timedelta(seconds=.3):
                            print('channels moved!')
                            log_chan = self.bot.get_channel(log_channels[str(guild.id)])
                            # the `changes` list, but sorted from top to bottom as seen before the drag event
                            sorted_begins = sorted(changes, key=lambda chan: chan[1].position)
                            if len(changes) < 2:
                                await log_chan.send('I\'m really unsure what just happened.')
                            elif sorted_begins[-1][1].position - sorted_begins[0][1].position is 1:
                                await log_chan.send('<#{}> swapped with <#{}>'.format(changes[0][1].id, changes[1][1].id))
                            else:
                                # a channel was dragged far above or far below where it was previously

                                # the before and after version of the channel that someone dragged
                                dragged_chan = [chan[1:3] for chan in changes if 1<abs(chan[1].position-chan[2].position)][0]

                                # print the of the dragged channel's name (before-version, technically)
                                print(dragged_chan[0].name)

                                # case: channel was dragged far upward
                                if dragged_chan[0].position > dragged_chan[1].position:
                                    start_after_chan = sorted_begins[-2][1]
                                    end_above_chan = sorted_begins[0][1]
                                    await log_chan.send('<#{}> was dragged from after <#{}> to above <#{}>'.format(
                                        dragged_chan[0].id, start_after_chan.id, end_above_chan.id))

                                # case: channel was dragged far downward
                                else:
                                    start_after_chan_pos = sorted_begins[0][1].position - 1
                                    end_above_chan = sorted_begins[-1][1]

                                    if start_after_chan_pos < 0:
                                        await log_chan.send('<#{}> was dragged from the top to after <#{}>'.format(
                                            dragged_chan[0].id, end_above_chan.id))

                                    else:
                                        start_after_chan = self.bot.get_guild(guild.id).text_channels[start_after_chan_pos]
                                        await log_chan.send('<#{}> was dragged from after <#{}> to after <#{}>'.format(
                                            dragged_chan[0].id, start_after_chan.id, end_above_chan.id))

                            # clear our cache of channel changes.  Don't wanna double-report stuff
                            self.chan_changes[guild.id] = []

                    # We don't want to silently crash if we somehow encounter an error in this.
                    # Thus, we implement our own error catcher
                    except Exception as e:
                        # windows doesn't like colons, so replace them
                        now_str = datetime.utcnow().isoformat().replace(':', '_').replace('-', '_')
                        with open(f'logs/channel_listener_error_dump_{now_str}.txt', 'w') as f:
                            f.write('Contents of self.chan_changes: \n\n')
                            f.write(pprint.pformat(self.chan_changes))
                            f.write('\n\nTraceback:\n\n')
                            f.write(traceback.format_exc())
                        self.chan_changes = dict()  # needs to be cleared or we'll keep throwing the same error
                        try:
                            log_chan = self.bot.get_channel(log_channels[str(guild.id)])
                            await log_chan.send("Oy, some channels moved but I had problems understanding what "
                                                "happened.  I got an error like `{}`.".format(e))
                            ids = {chan[1].id for chan in changes}  # eliminate repeated elements by using set
                            outs = "<#" + ">, <#".join(str(e) for e in ids) + ">"
                            await log_chan.send("It involved these channels: " + outs)
                        except Exception:
                            traceback.print_exc()


def setup(bot):
    bot.add_cog(ChannelListener(bot))
