import datetime
import toml
import io
import sqlite3

import discord
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.path as mpath
import matplotlib.dates as mdates
import matplotlib.colors as colors
import matplotlib.cm as cm
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


def get_min(chans):
    """Fetches the global minimum of a list of channels"""
    # since all our data is timestamps is the past,
    # taking the timestamp of now will be greater than any values we examine
    min_y = datetime.datetime.now().timestamp()
    for channel in chans:
        min_y = min(min_y, min(channel.y))
    return min_y


def sync_db(bot):
    """Write out the current state of the bot db to a persistent file"""
    with open('db.toml', 'w') as f:
        f.write('# This file was automatically generated and will be overwritten when settings are updated\n')
        toml.dump(bot.db, f)


def plot_as_attachment():
    """save image as file-like object and return it as an object ready to be sent in the chat"""
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    return discord.File(buf, filename='channel_activity.png')


def interpolate(x, y, steps=5):
    """Code I stole from SO:
    https://stackoverflow.com/questions/8500700/how-to-plot-a-gradient-color-line-in-matplotlib/25941474#25941474"""
    path = mpath.Path(np.column_stack([x, y]))
    verts = path.interpolated(steps=steps).vertices
    x, y = verts[:, 0], verts[:, 1]
    return x, y


def postplot_styling(chans):
    """Configure the graph style, after calling any plotting functions"""
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


def preplot_styling(ctx, guild_id):
    """Configure the graph style (like the legend), before calling the plot functions"""
    chans = ctx.bot.mydatacache[guild_id][1]

    # Styling
    fig, ax = plt.subplots()
    ax.set_ylabel('Messages per hour')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator())
    ax.set_xlim([datetime.datetime.fromtimestamp(min(chans[0].timestamps)),
                 datetime.datetime.fromtimestamp(max(chans[0].timestamps))])
    for pos in ('top', 'bottom', 'left', 'right'):
        ax.spines[pos].set_visible(False)
    return chans, fig, ax


async def get_guild_id(ctx, guild_id):
    """Convenience method for handling no id, invalid id, and valid id from a parameter"""
    if guild_id is None:
        return ctx.guild.id
    if ctx.bot.get_guild(guild_id) is not None:
        return guild_id
    await ctx.send("Oops that didn't look like the ID of a guild I'm in. "
                   "Try just the command without anything after")
    return None


"""Bot data cache has the following structure:
{
Guild id : (datetime object of start of era covered, [list of unix timestamps of messages in that channel])
}
"""


class Data(commands.Cog):
    """Get stats and data n stuff"""

    def __init__(self, bot):
        self.bot = bot
        # Graph styling
        plt.rcParams['legend.frameon'] = False
        plt.rcParams['figure.figsize'] = [9, 6]
        plt.rcParams['savefig.facecolor'] = '#2C2F33'
        plt.rcParams['axes.facecolor'] = '#2C2F33'
        plt.rcParams['axes.labelcolor'] = '#999999'
        plt.rcParams['xtick.color'] = '#999999'
        plt.rcParams['ytick.color'] = '#999999'
        # message counting
        self.conn = sqlite3.connect('channel_history.db')
        self.last_dump_timestamp = -1
        # message count cache
        self.bins = dict()

    @commands.command(aliases=['exclude'])
    async def ignore(self, ctx, channel: discord.TextChannel):
        """
        Exclude a channel from being graphed

        This will clear any caches that the bot has for this guild.
        """
        ctx.bot.db['ACTIVITY']['excluded_channels'].append(channel.id)
        sync_db(ctx.bot)
        await ctx.invoke(ctx.bot.get_command('clear'), guild_id=ctx.guild.id)

    @commands.command()
    async def unignore(self, ctx, channel: discord.TextChannel):
        """
        Include a channel from being graphed, if it was excluded before

        This will clear any caches that the bot has for this guild.
        """
        if channel.id in ctx.bot.db['ACTIVITY']['excluded_channels']:
            ctx.bot.db['ACTIVITY']['excluded_channels'].remove(channel.id)
            sync_db(ctx.bot)
            await ctx.invoke(ctx.bot.get_command('clear'), guild_id=ctx.guild.id)
        else:
            await ctx.send('That\'s already included; no need to change :thumbsup:')

    @commands.command()
    async def get_data(self, ctx, guild_id: int = None):
        """
        Get the timestamps of all messages by channel, going back a month

        This takes a while.
        """
        guild_id = await get_guild_id(ctx, guild_id)
        if not guild_id:
            return
        print('populating cache...')
        load_msg = None
        try:
            await ctx.message.add_reaction(ctx.bot.config['loadingemoji'])
        except discord.errors.Forbidden:  # if we don't have react perms, send a message instead
            load_msg = await ctx.send('<' + ctx.bot.config['loadingemoji'] + '>')

        now = datetime.datetime.now()
        begin = now - datetime.timedelta(days=30)
        # cache is a list of Channel objects, as defined above
        cache = []
        for channel in ctx.bot.get_guild(guild_id).text_channels:
            if channel.id not in ctx.bot.db['ACTIVITY']['excluded_channels']:
                data = []
                try:
                    async for msg in channel.history(limit=None, after=begin):
                        data.append(discord.utils.snowflake_time(msg.id).timestamp())
                except discord.errors.Forbidden:
                    pass  # silently ignore channels we don't have perms to read
                else:
                    if len(data) > 0:
                        cache.append(Channel(channel.name, data))
        # sort by most total messages first
        cache = sorted(cache, key=lambda c: len(c.timestamps), reverse=True)
        # discard channels with little activity (also we only have so many colormaps)
        colormap_count = len(ctx.bot.config['colormaps'])
        if len(cache) > colormap_count:
            cache = cache[:colormap_count]

        ctx.bot.mydatacache[guild_id] = (begin, cache)
        print("done")
        if load_msg:
            await load_msg.delete()
        else:
            await ctx.message.remove_reaction(ctx.bot.config['loadingemoji'], ctx.me)

    @commands.command()
    async def clear(self, ctx, guild_id: int = None):
        """Ensure next time we graph, we'll go through channels again to get data, rather than using a cached version"""
        guild_id = await get_guild_id(ctx, guild_id)
        if not guild_id:
            return
        if guild_id in ctx.bot.mydatacache:
            ctx.bot.mydatacache.pop(guild_id)
        await ctx.send(":ok_hand:")

    @commands.command(aliases=['magic', 'line'])
    async def pretty_graph(self, ctx, guild_id: int = None):
        """Create a smooth line graph of messages per hour for popular channels"""
        guild_id = await get_guild_id(ctx, guild_id)
        if not guild_id:
            return

        if guild_id not in ctx.bot.mydatacache:
            await ctx.invoke(ctx.bot.get_command('get_data'), guild_id=guild_id)
        else:
            print('cache is already filled')

        chans, fig, ax = preplot_styling(ctx, guild_id)
        bins = np.linspace(min(chans[0].timestamps), max(chans[0].timestamps), int(24 * 30.5))  # leave some fudge space
        # first pass through data, to get smoothed values to plot
        for chan, cmap in zip(chans, ctx.bot.config['colormaps']):
            y = self.get_y(chan, bins, guild_id)
            chan.y = y
            chan.colormap = cmap
        # we need this so that colormaps for each series stretch to the global max, rather than the max of that series
        global_max = get_max(chans)
        # second pass through data, doing interpolation and actually plotting
        for channel in chans:
            # we graph a scatter plot not a line plot, so need to make enough points that it looks continuous
            x, y = interpolate(bins, channel.y)
            # stretch the colormap; we don't use extremes cuz they ugly
            norm = colors.Normalize(vmin=-global_max / 1.5, vmax=global_max * 2.5)
            # boring conversions.  Prob a better way to do this but whatevs
            x = [datetime.datetime.fromtimestamp(t) for t in x]
            plt.scatter(x, y, label=channel.name, c=y, s=10, cmap=channel.colormap, norm=norm)

        postplot_styling(chans)
        await ctx.send(file=plot_as_attachment())

    @commands.command(aliases=['bar'])
    async def rawer_graph(self, ctx, guild_id: int = None):
        """Create a bar chart of messages per hour for popular channels"""
        guild_id = await get_guild_id(ctx, guild_id)
        if not guild_id:
            return
        if guild_id not in ctx.bot.mydatacache:
            await ctx.invoke(ctx.bot.get_command('get_data'), guild_id=guild_id)
        else:
            print('cache is already filled')

        chans, fig, ax = preplot_styling(ctx, guild_id)
        bins = np.linspace(min(chans[0].timestamps), max(chans[0].timestamps), int(24 * 30.5))  # leave some fudge space
        # first pass through data, to get smoothed values to plot
        for chan, cmap in zip(chans, ctx.bot.config['colormaps']):
            y = self.get_y(chan, bins, guild_id, smoothing=0)
            chan.y = y
            chan.colormap = cmap
        # second pass through data, doing interpolation and actually plotting
        for channel in chans:
            # boring conversions.  Prob a better way to do this but whatevs
            x = [datetime.datetime.fromtimestamp(t) for t in bins]
            plt.bar(x, channel.y, .1, label=channel.name, alpha=.3, color=cm.get_cmap(channel.colormap)(.5), )

        postplot_styling(chans)
        await ctx.send(file=plot_as_attachment())

    def get_y(self, channel, bins, guild_id, smoothing=13):
        """For data on a channel, return the smoothed, binned y values to be interpolated and graphed"""
        y = np.zeros(len(bins))
        begin = self.bot.mydatacache[guild_id][0].timestamp()
        for msg_time in channel.timestamps:
            y[int((msg_time - begin) / 3600)] += 1  # change me
        if smoothing > 1:
            return gaussian_filter1d(y, sigma=smoothing)
        return y

    @commands.command()
    @commands.is_owner()
    async def sql(self, ctx, *, query):
        """Run an sql query"""
        c = self.conn.cursor()
        try:
            response = c.execute(query)
        except Exception as e:
            await ctx.send(f'Oh no!  An error! `{e}`')
        else:
            s = "\n".join(str(t) for t in response.fetchall())
            await ctx.send(f'```json\n{s}```')

    @commands.command(hidden=True)
    async def bins(self, ctx):
        """Print out all the bins, for debugging"""
        s = "\n".join('{}: {}'.format(k, self.bins[k]) for k in self.bins)
        await ctx.send(f'```json\n{s}```')

    @commands.Cog.listener()
    async def on_message(self, msg):
        """Keep track of message count as messages come, by channel"""
        # get the timestamp of the beginning of this hour
        d = datetime.datetime.utcnow()
        last_hour = d - datetime.timedelta(minutes=d.minute, seconds=d.second, microseconds=d.microsecond)
        timestamp = int(last_hour.timestamp())

        # if message is in a new hour than recently recorded, dump all contents of self.bins into db and clear it
        if timestamp != self.last_dump_timestamp:
            print(f'dumping!  timestamp is {timestamp}')
            self.last_dump_timestamp = timestamp
            c = self.conn.cursor()
            for chan_id in self.bins:
                # make sure table exists
                c.execute(f'create table if not exists \'{chan_id}\' (timestamp INTEGER, count INTEGER)')
                # dump latest data into the table
                c.execute(f'insert into \'{chan_id}\' values (?, ?)', (timestamp, self.bins[chan_id]))
            # flush memory changes to disk
            self.conn.commit()
            # empty our cache thingy
            self.bins = dict()

        # add to memory bin
        if not msg.author.bot:
            if msg.channel.id not in self.bins:
                self.bins[msg.channel.id] = 0
            self.bins[msg.channel.id] += 1


def setup(bot):
    bot.add_cog(Data(bot))
