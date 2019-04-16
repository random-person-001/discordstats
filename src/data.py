import json
import datetime
from pprint import pprint

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import discord
from discord.ext import commands


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
        self.cache[ctx.guild.id] = []
        for channel in ctx.guild.text_channels:
            data = []
            async for msg in channel.history(limit=None, after=begin):
                data.append(discord.utils.snowflake_time(msg.id).timestamp())
            self.cache[ctx.guild.id].append((channel.id, channel.name, data))
        #  pprint(self.cache)
        ctx.bot.mydatacache = self.cache
        await ctx.send(":thumbsup:")
        with open("dump.json", "w") as f:
            f.write(json.dumps(self.cache))

    @commands.command()
    async def graph_data(self, ctx):
        num_bins = 10
        if not ctx.bot.mydatacache:
            print("populating cache")
            cmd = ctx.bot.get_command("get_data")
            await ctx.invoke(cmd)
        else:
            print("cache is already filled")

        #fig, ax = plt.subplots(1, 1)
        for channel in ctx.bot.mydatacache[ctx.guild.id]:
            if len(channel[2]) > 2:
                # convert the epoch format to matplotlib date format
                mpl_data = mdates.epoch2num(channel[2])
                # plot it
                n, x, _ = plt.hist(mpl_data, bins=num_bins, histtype='step', align='mid')
                bin_centers = 0.5 * (x[1:] + x[:-1])
                plt.plot(bin_centers, n, color='brown')  ## using bin_centers rather than edges
                plt.show()
        #ax.xaxis.set_major_locator(mdates.DayLocator())
        ##ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%h'))
        #plt.show()


def setup(bot):
    bot.add_cog(Data(bot))
