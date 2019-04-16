import datetime
from pprint import pprint

import discord
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from discord.ext import commands
from scipy.ndimage.filters import gaussian_filter1d


SPACECORD = 391743485616717824
LOADING = "a:loading:567758532875911169"


class Data(commands.Cog):
    """Get stats and data n stuff"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def get_data(self, ctx):
        """Get the timestamps of all messages by channel, going back a month"""
        await ctx.message.add_reaction(LOADING)
        now = datetime.datetime.now()
        begin = now - datetime.timedelta(days=30)
        # cache = [(id, name, [data]), ...]
        # with one tuple per channel, where data is a binned count of messages in that channel by hour
        cache = []
        after_boring_stuff = False
        for channel in ctx.bot.get_guild(SPACECORD).text_channels:
            if channel.name == 'general-space':
                after_boring_stuff = True
            if (after_boring_stuff and not "logs" in channel.name) or channel.name == 'staff-room':
                data = []
                try:
                    async for msg in channel.history(limit=None, after=begin):
                        data.append(discord.utils.snowflake_time(msg.id).timestamp())
                except discord.errors.Forbidden:
                    pass
                else:
                    cache.append((channel.id, channel.name, data))
        # sort by most total messages first
        cache = sorted(cache, key=lambda x: len(x[2]), reverse=True)
        if len(cache) > 7:  # discard channels with little activity
            cache = cache[:7]
        # pprint(self.cache)
        ctx.bot.mydatacache = {SPACECORD: cache}
        ctx.bot.mydatacachebegin = begin
        await ctx.message.remove_reaction(LOADING, ctx.me)

    @commands.command()
    async def clear(self, ctx):
        """Ensure next time we graph, we'll go through channels again to get data, rather than using a cached version"""
        ctx.bot.mydatacache = None
        await ctx.send(":ok_hand:")

    @commands.command(aliases=['magic'])
    async def graph_data(self, ctx):
        """Create a smooth line graph of messages per hour for popular channels"""
        if not ctx.bot.mydatacache:
            print("populating cache...")
            await ctx.invoke(ctx.bot.get_command("get_data"))
            print("done")
        else:
            print("cache is already filled")

        # Styling
        plt.style.use('ggplot')
        plt.rcParams['legend.frameon'] = False
        plt.rcParams['savefig.facecolor'] = '#222222'
        plt.rcParams['axes.facecolor'] = '#222222'
        fig, ax = plt.subplots()
        ax.set_xlabel('Time')
        ax.set_ylabel('Messages per hour')

        # custom binning and smoothing
        bins = np.linspace(1552719667, 1555398076, 24*31)
        for channel in ctx.bot.mydatacache[SPACECORD]:
            y = self.get_y(channel, bins)
            plt.plot(bins, y, label=channel[1], drawstyle='default')

        # legends and tweaks
        legend = plt.legend(loc='upper left')
        plt.setp(legend.get_texts(), color='#888888')
        plt.grid(True, 'major', 'x', ls='--', lw=.5, c='w', alpha=.1)
        plt.grid(True, 'major', 'y', ls='--', lw=.5, c='w', alpha=.1)

        plt.tight_layout()
        plt.show()

    def get_y(self, channel, bins):
        """For data on a channel, return the smoothed, binned """
        smoothing = 13
        y = np.zeros(len(bins))
        begin = self.bot.mydatacachebegin.timestamp()
        for msgtime in channel[2]:
            y[int((msgtime-begin)/3600)] += 1
        ysmoothed = gaussian_filter1d(y, sigma=smoothing)
        pprint(ysmoothed)
        return ysmoothed


def setup(bot):
    bot.add_cog(Data(bot))
