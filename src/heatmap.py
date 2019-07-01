import datetime
import io

import discord
import matplotlib.pyplot as plt
import numpy as np
from discord.ext import commands


def preplot_styling():
    """Configure the graph style (like splines and labels), before calling the plot functions"""
    # Styling
    fig, ax = plt.subplots()
    for pos in ('top', 'bottom', 'left', 'right'):
        ax.spines[pos].set_visible(False)
    return fig, ax


def plot_as_attachment():
    """Save image as file-like object and return it as an object ready to be sent in the chat"""
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    return discord.File(buf, filename='members.png')


class Heatmap(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def heatmap(self, ctx, weeks: int = None):
        """Graph a heatmap of total server activity over a time period.
        If a number of weeks is not specified, it will be over all time.
        This command is unfinished.
        """
        if not weeks or weeks < 1:
            weeks = 900
        oldest = datetime.datetime.utcnow() - datetime.timedelta(weeks=weeks)
        f = await self.bin(oldest, 391743485616717824)
        await ctx.send(file=f)

    async def bin(self, oldest, guild_id):
        # gather all data, grouped into each bin
        async with self.bot.pool.acquire() as conn:
            results = await conn.fetch(
                """
                select 
                  extract(dow from date) as weekday, 
                  extract(hour from date) as hour, 
                  count(*) from gg{}""".format(guild_id) +
                """
                where date > $1
                group by 
                  extract(dow from date), 
                  extract(hour from date)
                """, oldest)

        data = np.zeros((7, 24), int)
        for point in results:
            data[int(point['weekday'])][int(point['hour'])] = int(point['count'])
        print(data)

        fig, ax = preplot_styling()
        ax.pcolor(data)
        ax.set_title('activity over time in guild')

        fig.tight_layout()
        return plot_as_attachment()


def setup(bot):
    bot.add_cog(Heatmap(bot))
