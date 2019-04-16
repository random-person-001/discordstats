import json

import numpy as np
import datetime
from pprint import pprint
import matplotlib.pyplot as plt

import discord
from discord.ext import commands


class Data(commands.Cog):
    """Get stats and data n stuff"""
    def __init__(self, bot):
        self.bot = bot
        self.cache = dict()  # server ids pointing to server data idk
        self.bot.mydatacache = None

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
            data = np.zeros(24*31, dtype=int)  # list of messages in each slot, where each slot is an hour long
            async for msg in channel.history(limit=None, after=begin):
                age = (now - discord.utils.snowflake_time(msg.id)).total_seconds()
                data[int(age/60/60)] += 1
            self.cache[ctx.guild.id].append((channel.id, channel.name, data))
        pprint(self.cache)
        self.bot.mydatacache = self.cache
        await ctx.send(":thumbsup:")
        with open("dump.json", "w") as f:
            f.write(json.dumps(self.cache))



    @commands.command()
    async def graph_data(self, ctx):
        if not self.bot.mydatacache:
            await ctx.invoke("get_data")

        t = np.linspace(0.0, 2.0, 201)
        s = np.sin(2 * np.pi * t)

        # 1) RGB tuple:
        fig, ax = plt.subplots(facecolor=(.18, .31, .31))
        # 2) hex string:
        ax.set_facecolor('#eafff5')
        # 3) gray level string:
        ax.set_title('Voltage vs. time chart', color='0.7')
        # 4) single letter color string
        ax.set_xlabel('time (s)', color='c')
        # 5) a named color:
        ax.set_ylabel('voltage (mV)', color='peachpuff')
        # 6) a named xkcd color:
        ax.plot(t, s, 'xkcd:crimson')
        # 7) Cn notation:
        ax.plot(t, .7 * s, color='C4', linestyle='--')
        # 8) tab notation:
        ax.tick_params(labelcolor='tab:orange')

        plt.show()


def setup(bot):
    bot.add_cog(Data(bot))
