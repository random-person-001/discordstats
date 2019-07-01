import datetime
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


def rc_styling():
    """One-off stylistic settings"""
    plt.rcParams['legend.frameon'] = False
    plt.rcParams['figure.figsize'] = [9, 6]
    plt.rcParams['savefig.facecolor'] = '#2C2F33'
    plt.rcParams['axes.facecolor'] = '#2C2F33'
    plt.rcParams['axes.labelcolor'] = '#999999'
    plt.rcParams['text.color'] = '#999999'
    plt.rcParams['xtick.color'] = '#999999'
    plt.rcParams['ytick.color'] = '#999999'


def blocking_graph(guild, results):
    """Build a matplotlib graph of the data"""
    ax = preplot_styling()
    dates, counts = [], np.zeros(len(results), dtype=int)
    for result, i in zip(results, range(len(results))):
        dates.append(result['date'])
        counts[i] = result['members']
    plt.scatter(dates, counts)
    plt.title(f'{guild.name} membership over time')
    postplot_styling(ax)
    return plot_as_attachment()


class Members(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        rc_styling()

    async def get_humans_data(self, guild: discord.Guild, weeks: float):
        """Search through all messages from Dyno responding to `serverinfo` to get human members over the
        last `weeks` (or all time if None)"""
        dyno_id = 155149108183695360
        if not weeks or weeks < 1:
            earliest = datetime.datetime.min
        else:
            earliest = datetime.datetime.utcnow() - datetime.timedelta(weeks=weeks)

        # query finds all messages by Dyno in response to ^serverinfo, and returns the date and Humans field
        async with self.bot.pool.acquire() as conn:
            results = await conn.fetch(
                f"select date, embed->'fields'->6->>'value' as members from gg{guild.id} "
                """where author = $1
                and date > $2
                and embed->'fields'->6->>'name' = 'Humans'
                order by date asc
                """, dyno_id, earliest)
        # pprint.pprint(results)
        if len(results) < 1:
            ax = preplot_styling()
            ax.xaxis_date()
            plt.title(f'No data during the last {weeks} weeks')
            return plot_as_attachment()
        return await self.bot.loop.run_in_executor(None, blocking_graph, guild, results)

    @commands.command()
    @commands.cooldown(2, 30)
    @commands.guild_only()
    async def members(self, ctx, weeks: float = None, guild_id: int = None):
        """Plot a graph of (human) members over all time
        If the number of weeks is not specified, it will count for all time
        This works by searching through messages from Dyno as a response to ^serverinfo"""
        if not guild_id:
            guild_id = ctx.guild.id
        f = await self.get_humans_data(ctx.bot.get_guild(guild_id), weeks)
        await ctx.send(file=f)


def setup(bot):
    bot.add_cog(Members(bot))
