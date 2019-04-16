import datetime
from pprint import pprint

import discord
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from discord.ext import commands
from scipy.ndimage.filters import gaussian_filter1d


SPACECORD = 391743485616717824


class Data(commands.Cog):
    """Get stats and data n stuff"""
    def __init__(self, bot):
        self.bot = bot
        self.cache = dict()  # server ids pointing to server data idk

    def __unload(self):
        pass

    @commands.command()
    async def foo(self, ctx):
        await ctx.send("bar")

    @commands.command()
    async def get_data(self, ctx):
        """Get channel data, going back a month"""
        now = datetime.datetime.now()
        begin = now - datetime.timedelta(days=30)
        # data = [(id, name, [data]), ...]
        # with one tuple per channel, where data is a binned count of messages in that channel by hour
        self.cache[SPACECORD] = []
        after_boring_stuff = False
        for channel in ctx.bot.get_guild(SPACECORD).text_channels:
            if channel.name == 'general-space':
                after_boring_stuff = True
            if after_boring_stuff and not "logs" in channel.name:
                data = []
                try:
                    async for msg in channel.history(limit=None, after=begin):
                        data.append(discord.utils.snowflake_time(msg.id).timestamp())
                except discord.errors.Forbidden:
                    pass
                else:
                    self.cache[SPACECORD].append((channel.id, channel.name, data))
        # sort by most total messages first
        self.cache[SPACECORD] = sorted(self.cache[SPACECORD], key=lambda x: len(x[2]), reverse=True)
        # pprint(self.cache)
        ctx.bot.mydatacache = self.cache
        # await ctx.send(":thumbsup:")

    @commands.command()
    async def clear(self, ctx):
        ctx.bot.mydatacache = None

    @commands.command(aliases=['magic'])
    async def graph_data(self, ctx):
        smoothing = 10
        if not ctx.bot.mydatacache:
            print("populating cache...")
            cmd = ctx.bot.get_command("get_data")
            await ctx.invoke(cmd)
            print("done")
        else:
            print("cache is already filled")

        # Styling
        fig, ax = plt.subplots(1, 1)
        plt.style.use('ggplot')
        plt.rcParams['legend.frameon'] = False
        plt.rcParams['savefig.facecolor'] = '#222222'
        plt.rcParams['axes.facecolor'] = '#222222'
        plt.grid(True, 'major', 'x', ls='--', lw=.5, c='w', alpha=.3)
        plt.grid(True, 'major', 'y', ls='--', lw=.5, c='w', alpha=.1)

        ax.set_xlabel('Time')
        ax.set_ylabel('Messages per hour')
        # ax.set_title('Messages per hour by channel')
        bins = np.linspace(1552719667, 1555398076, 24*31)
        maxY = 0
        for channel in ctx.bot.mydatacache[SPACECORD]:
            if len(channel[2]) > 5:
                # convert the epoch format to matplotlib date format
                #mpl_data = mdates.epoch2num(channel[2])
                # plot it
                y, _, _ = plt.hist(channel[2], bins=bins, alpha=0)
                ysmoothed = gaussian_filter1d(y, sigma=smoothing)
                plt.plot(bins[:-1], ysmoothed, label=channel[1])
                maxY = max(maxY, max(ysmoothed))

        legend = plt.legend(loc='upper left')
        plt.setp(legend.get_texts(), color='#888888')
        plt.ylim(0, maxY*1.05)  # by default it'll scale to show the much higher and invisible bar graph that we don't care about, so manually resize
        plt.tight_layout()

        #ax.xaxis.set_major_locator(mdates.DayLocator())
        #ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%h'))
        plt.show()
        #fig.savefig('whatever.png', facecolor=fig.get_facecolor(), edgecolor='none')




def setup(bot):
    bot.add_cog(Data(bot))
