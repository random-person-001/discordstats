import datetime
import io

import discord
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.path as mpath
import matplotlib.colors as colors
import matplotlib.dates as mdates
import matplotlib.cm as cm
import toml
from discord.ext import commands
from scipy.ndimage.filters import gaussian_filter1d


class Channel:
    """Data struct for the things I care about in a channel"""
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


def sync_db(bot):
    """Write out the current state of the bot db to a persistent file"""
    with open("db.toml", "w") as f:
        f.write("# This file was automatically generated and will be overwritten when settings are updated\n")
        toml.dump(bot.db, f)


class Data(commands.Cog):
    """Get stats and data n stuff"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['exclude'])
    async def ignore(self, ctx, channel: discord.TextChannel):
        """
        Exclude a channel from being graphed

        This will clear any caches that the bot has for this guild.
        """
        ctx.bot.db['excluded_channels'].append(channel.id)
        sync_db(ctx.bot)
        await ctx.invoke(ctx.bot.get_command('clear'))

    @commands.command()
    async def unignore(self, ctx, channel: discord.TextChannel):
        """
        Include a channel from being graphed, if it was excluded before

        This will clear any caches that the bot has for this guild.
        """
        if channel.id in ctx.bot.db['excluded_channels']:
            ctx.bot.db['excluded_channels'].remove(channel.id)
            sync_db(ctx.bot)
            await ctx.invoke(ctx.bot.get_command('clear'))
        else:
            await ctx.send('That\'s already included no need to change :thumbs_up:')

    @commands.command()
    async def get_data(self, ctx):
        """
        Get the timestamps of all messages by channel, going back a month

        This takes a while.
        """
        print("populating cache...")
        await ctx.message.add_reaction(ctx.bot.config['loadingemoji'])
        now = datetime.datetime.now()
        begin = now - datetime.timedelta(days=30)
        # cache is a list of Channel objects, as defined above
        cache = []
        for channel in ctx.bot.get_guild(ctx.bot.config['guildID']).text_channels:
            if channel.id not in ctx.bot.db['excluded_channels']:
                data = []
                try:
                    async for msg in channel.history(limit=None, after=begin):
                        data.append(discord.utils.snowflake_time(msg.id).timestamp())
                except discord.errors.Forbidden:
                    pass  # silently ignore channels we don't have perms to read
                else:
                    cache.append(Channel(channel.name, data))
        # sort by most total messages first
        cache = sorted(cache, key=lambda c: len(c.timestamps), reverse=True)
        # discard channels with little activity (also we only have so many colormaps)
        colormap_count = len(ctx.bot.config['colormaps'])
        if len(cache) > colormap_count:
            cache = cache[:colormap_count]
        # pprint(self.cache)
        ctx.bot.mydatacache = {ctx.bot.config['guildID']: cache}
        ctx.bot.mydatacachebegin = begin
        print("done")
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
            await ctx.invoke(ctx.bot.get_command("get_data"))
        else:
            print("cache is already filled")

        # custom binning, rather than using the (slow) default histogram function and hiding it
        chans = ctx.bot.mydatacache[ctx.bot.config['guildID']]
        bins = np.linspace(min(chans[0].timestamps), max(chans[0].timestamps), int(24*30.5))  # leave some fudge space

        # Styling
        plt.style.use('ggplot')
        plt.rcParams['legend.frameon'] = False
        plt.rcParams["figure.figsize"] = [9, 6]
        plt.rcParams['savefig.facecolor'] = '#2C2F33'
        plt.rcParams['axes.facecolor'] = '#2C2F33'
        plt.rcParams['axes.labelcolor'] = '#999999'
        plt.rcParams['xtick.color'] = '#999999'
        plt.rcParams['ytick.color'] = '#999999'
        fig, ax = plt.subplots()
        ax.set_ylabel('Messages per hour')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator())
        ax.set_xlim([datetime.datetime.fromtimestamp(bins[0]), datetime.datetime.fromtimestamp(bins[-1])])
        for pos in ('top', 'bottom', 'left', 'right'):
            ax.spines[pos].set_visible(False)

        # first pass through data, to get smoothed values to plot
        for chan, cmap in zip(chans, ctx.bot.config['colormaps']):
            y = self.get_y(chan, bins)
            chan.y = y
            chan.colormap = cmap
        # we need this so that colormaps for each series stretch to the global max, rather than the max of that series
        global_max = get_max(chans)
        # second pass through data, doing interpolation and actually plotting
        for channel in chans:
            # we graph a scatter plot not a line plot, so need to make enough points that it looks continuous
            x, y = interpolate(bins, channel.y)
            # stretch the colormap; we don't use extremes cuz they ugly
            norm = colors.Normalize(vmin=-global_max/1.5, vmax=global_max*2.5)
            # boring conversions.  Prob a better way to do this but whatevs
            x = [datetime.datetime.fromtimestamp(t) for t in x]
            plt.scatter(x, y, label=''+channel.name, c=y, s=10, cmap=channel.colormap, norm=norm)

        # legends and tweaks
        legend = plt.legend(loc='upper left', prop={'size': 13}, handlelength=0)
        # set legend labels to the right color
        for text, chan in zip(legend.get_texts(), chans):
            text.set_color(cm.get_cmap(chan.colormap)(.5))
        # get rid of the (usually colored) dots next to the text entries in the legend
        for item in legend.legendHandles:
            item.set_visible(False)
        # grid layout
        plt.grid(True, 'major', 'x', ls=':', lw=.5, c='w', alpha=.2)
        plt.grid(True, 'major', 'y', ls=':', lw=.5, c='w', alpha=.2)
        plt.tight_layout()

        # save image as file-like object and upload as a message attachment
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        disfile = discord.File(buf, filename='channel_activity.png')
        await ctx.send(file=disfile)

    def get_y(self, channel, bins, smoothing=13):
        """For data on a channel, return the smoothed, binned y values to graph"""
        y = np.zeros(len(bins))
        begin = self.bot.mydatacachebegin.timestamp()
        for msgtime in channel.timestamps:
            y[int((msgtime-begin)/3600)] += 1
        ysmoothed = gaussian_filter1d(y, sigma=smoothing)
        return ysmoothed


def interpolate(x, y, steps=5):
    """Code I stole from SO:
    https://stackoverflow.com/questions/8500700/how-to-plot-a-gradient-color-line-in-matplotlib/25941474#25941474"""
    path = mpath.Path(np.column_stack([x, y]))
    verts = path.interpolated(steps=steps).vertices
    x, y = verts[:, 0], verts[:, 1]
    return x, y


def setup(bot):
    bot.add_cog(Data(bot))
