import datetime
import json
from typing import List

import discord
import matplotlib.colors as colors
import matplotlib.path as mpath
import matplotlib.pyplot as plt
import numpy as np
from discord.ext import commands
from scipy.ndimage.filters import gaussian_filter1d

from helpers import graph_commons


class ChannelData:
    def __init__(self, x, y, chan):
        self.x = x
        self.y = y
        self.chan = chan
        self.count = sum(y)
        self.max = max(y)
        self.colormap = None  # set later


def sync_db(bot):
    """Write out the current state of the bot db to a persistent file"""
    with open('conf/db.json', 'w') as f:
        json.dump(bot.db, f)


def interpolate(x_list: List[datetime.datetime], y_nums, steps=5):
    """Code I stole from SO:
    https://stackoverflow.com/questions/8500700/how-to-plot-a-gradient-color-line-in-matplotlib/25941474#25941474"""
    x_nums = [x.timestamp() for x in x_list]
    path = mpath.Path(np.column_stack([x_nums, y_nums]))
    verts = path.interpolated(steps=steps).vertices
    x_nums, y_nums = verts[:, 0], verts[:, 1]
    return [datetime.datetime.fromtimestamp(x) for x in x_nums], y_nums


async def get_guild(ctx, guild_id):
    """Convenience method for handling no id, invalid id, and valid id from a parameter"""
    if not guild_id:
        return ctx.guild
    guild = ctx.bot.get_guild(guild_id)
    if not guild:
        await ctx.send("Oops that didn't look like the ID of a guild I'm in. "
                       "Try just the command without anything after")
        return None
    return guild


def hours(dt: datetime.timedelta) -> int:
    """Get total hours in a timedelta"""
    return int(dt.total_seconds() / 3600)


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
        ctx.bot.db['ACTIVITY_EXCLUDED_CHANNELS'].append(channel.id)
        sync_db(ctx.bot)

    @commands.command()
    async def unignore(self, ctx, channel: discord.TextChannel):
        """
        Include a channel from being graphed, if it was excluded before

        This will clear any caches that the bot has for this guild.
        """
        if channel.id in ctx.bot.db['ACTIVITY_EXCLUDED_CHANNELS']:
            ctx.bot.db['ACTIVITY_EXCLUDED_CHANNELS'].remove(channel.id)
            sync_db(ctx.bot)
        else:
            await ctx.send('That\'s already included; no need to change :thumbsup:')

    async def get_channel_data(self, chan: discord.TextChannel, earliest: datetime.datetime, smoothing):
        """Generate a ChannelData object for a channel"""
        async with self.bot.pool.acquire() as conn:
            results = await conn.fetch("  SELECT count(*), date_trunc('hour', date) AS date" +
                                       f" FROM cc{chan.id}"
                                       "  WHERE date > $1"
                                       "  GROUP BY date_trunc('hour', date)"
                                       "  ORDER BY date_trunc('hour', date) ASC", earliest)
            raw_y = np.zeros(24 * 30)
            for record in results:
                raw_y[hours(record['date'] - earliest)] = record['count']

        if smoothing > 0:
            raw_y = gaussian_filter1d(raw_y, sigma=smoothing)
        raw_x = [earliest + i * datetime.timedelta(hours=1) for i in range(24 * 30)]
        return ChannelData(raw_x, raw_y, chan)

    async def get_all_channel_data(self, guild: discord.Guild, start, smoothing=13):
        """Generate a list of the top five channel classes.  Descending order."""
        chans = []
        for chan in guild.text_channels:
            if chan.id not in self.bot.db['ACTIVITY_EXCLUDED_CHANNELS']:
                chan_data = await self.get_channel_data(chan, start, smoothing)
                if chan_data.max > 0:
                    chans.append(chan_data)
        # only return the top five channels by total count.  Or, if there are less than five, all that there are.
        n = min((5, len(chans)))
        return sorted(chans, key=lambda c: c.count, reverse=True)[:n]

    @commands.command(aliases=['magic', 'line'])
    async def graph(self, ctx, guild_id: int = None):
        """Create a smooth line graph of messages per hour for popular channels"""
        duration = 29  # days

        guild = await get_guild(ctx, guild_id)
        if not guild:
            return
        earliest = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=duration)
        graph_commons.preplot_styling_dates(earliest)

        chans = await self.get_all_channel_data(guild, earliest)

        for i in range(len(chans)):
            chans[i].colormap = ctx.bot.config['colormaps'][i]

        # we need this so that colormaps for each series stretch to the global max, rather than the max of that series
        global_max = chans[0].max

        # second pass through data, doing interpolation and actually plotting
        for channel in chans:
            # we graph a scatter plot not a line plot, so need to make enough points that it looks continuous
            x, y = interpolate(channel.x, channel.y)
            # stretch the colormap; we don't use extremes cuz they ugly
            norm = colors.Normalize(vmin=-global_max / 1.5, vmax=global_max * 2.5)
            # boring conversions.  Prob a better way to do this but whatevs
            print(channel.chan.name)
            plt.scatter(x, y, label=channel.chan.name, c=y, s=10, cmap=channel.colormap, norm=norm)

        graph_commons.postplot_styling_fancy(chans)
        await ctx.send(file=graph_commons.plot_as_attachment())

    @commands.command()
    async def scatter(self, ctx, weeks: float = 4):
        """Create a scatter plot of messages per hour for popular channels"""
        duration = weeks * 7  # days
        earliest = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=duration)
        graph_commons.preplot_styling_dates(earliest)

        chans = await self.get_all_channel_data(ctx.guild, earliest, smoothing=0)

        for i in range(len(chans)):
            chans[i].colormap = ctx.bot.config['colormaps'][len(chans) - i]

        # we need this so that colormaps for each series stretch to the global max, rather than the max of that series
        global_max = chans[0].max

        # second pass through data, doing interpolation and actually plotting
        for channel in chans:
            # stretch the colormap; we don't use extremes cuz they ugly
            norm = colors.Normalize(vmin=-global_max / 2.5, vmax=global_max * 1.5)
            # boring conversions.  Prob a better way to do this but whatevs
            print(channel.chan.name)
            plt.scatter(channel.x, channel.y, label=channel.chan.name, c=channel.y, s=10, cmap=channel.colormap,
                        norm=norm)

        graph_commons.postplot_styling_fancy(chans)
        await ctx.send(file=graph_commons.plot_as_attachment())


def setup(bot):
    bot.add_cog(Data(bot))
