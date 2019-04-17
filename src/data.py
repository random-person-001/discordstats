import datetime
from pprint import pprint

import discord
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.path as mpath
import matplotlib.colors as colors
import matplotlib.dates as mdates
from discord.ext import commands
from scipy.ndimage.filters import gaussian_filter1d


class Channel:
    def __init__(self, name, data):
        self.name = name
        self.timestamps = data  # timestamps of all messages sent in last month in channel
        self.y = None  # smoothed and binned timestamps
        self.colormap = None


def get_max(chans):
    """Fetches the global maximum of a list of channels"""
    max_y = 0
    for channel in chans:
        max_y = max(max_y, max(channel.y))
    return max_y


class Data(commands.Cog):
    """Get stats and data n stuff"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def get_data(self, ctx):
        """Get the timestamps of all messages by channel, going back a month"""
        await ctx.message.add_reaction(ctx.bot.config['loadingemoji'])
        now = datetime.datetime.now()
        begin = now - datetime.timedelta(days=30)
        # cache is a list of [custom] Channel objects
        cache = []
        after_boring_stuff = False
        for channel in ctx.bot.get_guild(ctx.bot.config['guildID']).text_channels:
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
                    cache.append(Channel(channel.name, data))
        # sort by most total messages first
        cache = sorted(cache, key=lambda c: len(c.timestamps), reverse=True)
        if len(cache) > 6:  # discard channels with little activity
            cache = cache[:6]
        # pprint(self.cache)
        ctx.bot.mydatacache = {ctx.bot.config['guildID']: cache}
        ctx.bot.mydatacachebegin = begin
        await ctx.message.remove_reaction(ctx.bot.config['loadingemoji'], ctx.me)

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
        # colormaps = ['autumn', 'cool', 'spring', 'winter', 'Wistia', 'summer'] # vibrant-this was just too many colors
        colormaps = ['Reds_r', 'YlOrBr_r', 'Greens_r', 'Blues_r', 'Purples_r', 'cividis']

        # Styling
        plt.style.use('ggplot')
        plt.rcParams['legend.frameon'] = False
        plt.rcParams['savefig.facecolor'] = '#2C2F33'
        plt.rcParams['axes.facecolor'] = '#2C2F33'
        fig, ax = plt.subplots()
        ax.set_xlabel('Time')
        ax.set_ylabel('Messages per hour')

        # custom binning and smoothing
        bins = np.linspace(1552719667, 1555398076, 24*31)
        chans = ctx.bot.mydatacache[ctx.bot.config['guildID']]
        i=0

        for i in range(len(chans)):
            y = self.get_y(chans[i], bins)
            chans[i].y = y
            chans[i].colormap = colormaps[i]
        global_max = get_max(chans)
        for channel in chans:
            x, y = interpolate(bins, channel.y)
            norm = colors.Normalize(vmin=-global_max/1.5, vmax=global_max*1.6)
            plt.scatter(x, y, label=channel.name, c=y, s=10, cmap=channel.colormap, norm=norm)
            i+=1

        # legends and tweaks
        legend = plt.legend(loc='upper left')
        plt.setp(legend.get_texts(), color='#888888')
        plt.grid(True, 'major', 'x', ls=':', lw=.5, c='w', alpha=.2)
        plt.grid(True, 'major', 'y', ls=':', lw=.5, c='w', alpha=.2)

        plt.tight_layout()
        plt.show()

    def get_y(self, channel, bins):
        """For data on a channel, return the smoothed, binned y values to graph"""
        smoothing = 13
        y = np.zeros(len(bins))
        begin = self.bot.mydatacachebegin.timestamp()
        for msgtime in channel.timestamps:
            y[int((msgtime-begin)/3600)] += 1
        ysmoothed = gaussian_filter1d(y, sigma=smoothing)
        return ysmoothed


def interpolate(x, y, steps=6):
    """Code I stole from SO:
    https://stackoverflow.com/questions/8500700/how-to-plot-a-gradient-color-line-in-matplotlib/25941474#25941474"""
    path = mpath.Path(np.column_stack([x, y]))
    verts = path.interpolated(steps=steps).vertices
    x, y = verts[:, 0], verts[:, 1]
    return x, y


def setup(bot):
    bot.add_cog(Data(bot))
