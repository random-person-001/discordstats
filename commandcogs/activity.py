import datetime
import os

import asyncpg
import matplotlib.pyplot as plt
import numpy as np
from discord import File
from discord.ext import commands

from helpers import graph_commons


class Activity(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def activitymap(self, ctx, weeks: int = 26):
        """Graph a activitymap of total server activity over a time period.
        If a number of weeks is not specified, it will be over the past 6 months.
        """
        if not weeks or weeks < 1:
            weeks = 900
        now = datetime.datetime.utcnow()
        oldest = now - datetime.timedelta(weeks=weeks)
        await self.bin(oldest, now, ctx.guild.id)
        await ctx.send(file=graph_commons.plot_as_attachment())

    @commands.command()
    async def activitygif(self, ctx, weeks: int = 26, normalize: bool = False):
        """Create a gif of channel activity activitymaps over the past many weeks.
        Todo: make nonblocking"""
        if weeks > 34:
            await ctx.send("nah that looks like too much work, miss me with that")
            return
        status = await ctx.send('building plots...')
        guild_id = ctx.guild.id
        now = datetime.datetime.utcnow()
        oldest = now - datetime.timedelta(weeks=weeks)
        # find the absolute max in the data we'll be graphing.  We do this so that all frames have the same scale.
        async with self.bot.pool.acquire() as conn:
            max_val = await conn.fetchval(
                """
                select max(count)
                from (
                    select   
                      count(*) from gg{}""".format(guild_id) + """
                    where date > $1
                    group by 
                      extract(dow from date),
                      extract(hour from date),
                      extract(week from date)
                ) t
                """, oldest)
        # create images for each of the gif frames
        for i in range(weeks):
            c, fig = await self.bin(now - datetime.timedelta(weeks=i + 1), now - datetime.timedelta(weeks=i), guild_id)
            if not normalize:
                c.set_clim(0, max_val)
            plt.gca().annotate(f'{i} weeks ago', xy=(10, 10), xycoords='figure pixels')
            fig.tight_layout()
            # we save files with letter ordering instead of number, because that way they get mixed up less
            plt.savefig(f'tmp/activity {chr(65 + weeks - 1 - i)}.png', format='png')
            plt.close()
        await status.edit(content='creating gif...')
        # use imagemagick to convert frames into a gif
        os.system('convert -delay 40 -loop 0 tmp/*.png tmp/activity.gif && rm tmp/*.png')
        await ctx.send(file=File('tmp/activity.gif'))
        await status.edit(content='Done!')

    async def define_median(self):
        """There is no 'median' builtin command, so we'll make one of our own. From ulib_agg user-defined library."""
        try:
            async with self.bot.pool.acquire() as conn:
                await conn.execute("""
                    CREATE OR REPLACE FUNCTION _final_median(NUMERIC[])
                       RETURNS NUMERIC AS
                    $$
                       SELECT AVG(val)
                       FROM (
                         SELECT val
                         FROM unnest($1) val
                         ORDER BY 1
                         LIMIT  2 - MOD(array_upper($1, 1), 2)
                         OFFSET CEIL(array_upper($1, 1) / 2.0) - 1
                       ) sub;
                    $$
                    LANGUAGE 'sql' IMMUTABLE;
                     
                    CREATE AGGREGATE median(NUMERIC) (
                      SFUNC=array_append,
                      STYPE=NUMERIC[],
                      FINALFUNC=_final_median,
                      INITCOND='{}'
                    );    
                """)
        except asyncpg.exceptions.DuplicateFunctionError:
            # we only need to define it once
            pass

    async def bin(self, oldest, newest, guild_id):
        await self.define_median()
        # gather all data, grouped into each bin
        async with self.bot.pool.acquire() as conn:
            results = await conn.fetch(
                """
                select t.weekday, t.hour, median(count) as median
                from (
                    select 
                      extract(dow from date)-1 as weekday, 
                      extract(hour from date) as hour, 
                      count(*) from gg{}""".format(guild_id) + """
                    where date > $1 and
                          date < $2
                    group by 
                      extract(dow from date), 
                      extract(hour from date),
                      extract(week from date)
                ) t
                group by t.weekday, t.hour
                """, oldest, newest)

        data = np.zeros((7, 24), int)
        for point in results:
            if point['weekday'] == -1:  # put sunday at the end of the week
                data[0][int(point['hour'])] = int(point['median'])
            else:
                data[int(6 - point['weekday'])][int(point['hour'])] = int(point['median'])
        print(data)

        fig, ax = graph_commons.preplot_styling()
        c = ax.pcolor(data)
        ax.set_xlabel('Time of Day (UTC)')

        ax.set_yticks([float(n) + 0.5 for n in ax.get_yticks()])
        ax.set_yticklabels(['Mon', 'Tues', 'Wed', 'Thurs', 'Fri', 'Sat', 'Sun'][::-1])

        # Customize tick labels to be in the center of their boxes
        ax.set_xticks([0.5 + 4 * x for x in range(6)])
        ax.set_xticklabels([4 * x for x in range(6)])

        # visually remove all ticks
        ax.tick_params('both', length=0, width=1)

        ax.set_title('Activity at Various Times of the Week')
        cb = fig.colorbar(c, ax=ax, orientation='horizontal', drawedges=False)
        cb.set_label('Median Messages per Hour')
        fig.tight_layout()
        return c, fig


def setup(bot):
    bot.add_cog(Activity(bot))
