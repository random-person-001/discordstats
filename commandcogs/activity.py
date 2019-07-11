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
    async def activitygif(self, ctx, weeks: int = 26, normalize: bool = False, fast: bool = False):
        """Create a gif of channel activity activitymaps over the past many weeks.
        If `normalize` is set to True, the range is rescaled on every frame to the local maximum.
        Otherwise, the scale defaults to staying constant through the entire gif, between global extrema.
        `fast` should be True if you want the gif to go zoom; the default is False.
        Todo: make nonblocking"""
        if weeks > 34:
            await ctx.send("nah that looks like too much work, miss me with that")
            return
        status = await ctx.send('building plots...')
        guild_id = ctx.guild.id
        now = datetime.datetime.utcnow()
        oldest = now - datetime.timedelta(weeks=weeks)
        # find the absolute max in the data we'll be graphing.  We do this so that all frames have the same scale.
        #  This will only be used if `normalize` is False
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
            c, fig, cb = await self.bin(now - datetime.timedelta(weeks=i + 1), now - datetime.timedelta(weeks=i),
                                        guild_id)
            if not normalize:
                c.set_clim(0, max_val)
            plt.gca().annotate(f'{i} weeks ago', xy=(10, 10), xycoords='figure pixels')
            cb.set_label('Messages per Hour')
            fig.tight_layout()
            # we save files with letter ordering instead of number, because that way they get mixed up less
            # we also are reversing the order, so that going alphabetically means moving forward in time.
            plt.savefig(f'tmp/activity {chr(65 + weeks - 1 - i)}.png', format='png')
            # plots don't automatically close, which can lead to memory leaks.  So we manually do it.
            plt.close()
        await status.edit(content='creating gif...')
        # use imagemagick to convert frames into a gif.  Then cleanup when done
        #  The cleanup is important because next time we may generate fewer frames, but these leftovers wouldn't be
        #  overwritten
        speed = 0 if fast else 40
        os.system(f'convert -delay {speed} -loop 0 tmp/*.png tmp/activity.gif && rm tmp/*.png')
        await status.edit(content='uploading...')
        await ctx.send(file=File('tmp/activity.gif'))
        await status.edit(content='Done!')

    async def bin(self, oldest, newest, guild_id):
        # ensure that the median function is defined
        await self.define_median()
        # gather all data, grouped into each bin
        async with self.bot.pool.acquire() as conn:
            results = await conn.fetch(
                """
                select t.weekday, t.hour, median(count) as median
                from (
                    select 
                      extract(dow from date) as weekday, 
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
            if point['weekday'] == 0:  # put sunday at the end of the week
                data[6 - 6][int(point['hour'])] = int(point['median'])
            else:
                data[int(6 - point['weekday']) - 1][int(point['hour'])] = int(point['median'])
        print(data)

        fig, ax = graph_commons.preplot_styling()
        c = ax.pcolor(data)
        ax.set_xlabel('Time of Day (UTC)')

        # shift the labels to be visually in the center of their buckets
        ax.set_yticks([float(n) + 0.5 for n in ax.get_yticks()])
        ax.set_yticklabels(['Mon', 'Tues', 'Wed', 'Thurs', 'Fri', 'Sat', 'Sun'][::-1])

        # same for x axis
        ax.set_xticks([0.5 + 4 * x for x in range(6)])
        ax.set_xticklabels([4 * x for x in range(6)])

        # visually remove all ticks, leaving just the labels
        ax.tick_params('both', length=0, width=1)

        ax.set_title('Activity at Various Times of the Week')
        cb = fig.colorbar(c, ax=ax, orientation='horizontal', drawedges=False)
        cb.set_label('Median Messages per Hour')
        fig.tight_layout()

        # Return various components in case we want to work with the graph more (ex to make a gif of multiple)
        return c, fig, cb

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


def setup(bot):
    bot.add_cog(Activity(bot))
