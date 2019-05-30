import io

import discord
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from discord.ext import commands


def preplot_styling():
    """Configure the graph style (like splines and labels), before calling the plot functions"""
    # Styling
    fig, ax = plt.subplots()
    ax.set_ylabel('Nonbot Members')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    for pos in ('top', 'bottom', 'left', 'right'):
        ax.spines[pos].set_visible(False)
    return ax


def postplot_styling(ax):
    """Various colorings done after plotting data, but before display"""
    # ax.set_ylim(0, ax.get_ylim()[1]) #  don't truncate bottom
    # grid layout
    plt.grid(True, 'major', 'x', ls=':', lw=.5, c='w', alpha=.2)
    plt.grid(True, 'major', 'y', ls=':', lw=.5, c='w', alpha=.2)
    plt.tight_layout()


def plot_as_attachment():
    """Save image as file-like object and return it as an object ready to be sent in the chat"""
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    return discord.File(buf, filename='members.png')


class Members(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Graph styling
        plt.rcParams['legend.frameon'] = False
        plt.rcParams['figure.figsize'] = [9, 6]
        plt.rcParams['savefig.facecolor'] = '#2C2F33'
        plt.rcParams['axes.facecolor'] = '#2C2F33'
        plt.rcParams['axes.labelcolor'] = '#999999'
        plt.rcParams['text.color'] = '#999999'
        plt.rcParams['xtick.color'] = '#999999'
        plt.rcParams['ytick.color'] = '#999999'

    async def get_humans_data(self, guild: discord.Guild):
        """Search through all messages from Dyno responding to `serverinfo` to get human members over time"""
        dyno_id = 155149108183695360
        # subquery returns the union of all text channels
        subquery = '\n                   union all\n                   '.join(
            f'select date, embed, author from cc{chan.id}' for chan in guild.text_channels)
        # query finds all messages by Dyno in response to ^serverinfo, and returns the date and Humans field
        query = """
                select date, embed->'fields'->6->>'value' as members from (
                   {0}
                ) as biggah
                where author = {1}
                and embed->'fields'->6->>'name' = 'Humans'
                order by date asc
                """.format(subquery, dyno_id)
        async with self.bot.pool.acquire() as conn:
            results = await conn.fetch(query)
        # pprint.pprint(results)
        print('Found {} data points'.format(len(results)))
        ax = preplot_styling()
        dates, counts = [], np.zeros(len(results), dtype=int)
        for result, i in zip(results, range(len(results))):
            dates.append(result['date'])
            counts[i] = result['members']
        plt.scatter(dates, counts)
        plt.title(f'Membership over time for {guild.name}')
        postplot_styling(ax)
        return plot_as_attachment()

    @commands.command()
    async def members(self, ctx):
        """Plot a graph of members over all time"""
        guild = ctx.bot.get_guild(391743485616717824)
        f = await self.get_humans_data(guild)
        await ctx.send(file=f)


def setup(bot):
    bot.add_cog(Members(bot))
