import datetime

import numpy as np
from discord.ext import commands

from helpers import graph_commons


class Activitymap(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def activitymap(self, ctx, weeks: int = None):
        """Graph a activitymap of total server activity over a time period.
        If a number of weeks is not specified, it will be over all time.
        """
        if not weeks or weeks < 1:
            weeks = 900
        oldest = datetime.datetime.utcnow() - datetime.timedelta(weeks=weeks)
        f = await self.bin(oldest, 391743485616717824)
        await ctx.send(file=f)

    async def define_median(self):
        """There is no 'median' builtin command, so we'll make one of our own. From ulib_agg user-defined library."""
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

    async def bin(self, oldest, guild_id):
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
                    where date > $1
                    group by 
                      extract(dow from date), 
                      extract(hour from date),
                      extract(week from date)
                ) t
                group by t.weekday, t.hour
                """, oldest)

        data = np.zeros((7, 24), int)
        for point in results:
            data[int(6 - point['weekday'])][int(point['hour'])] = int(point['median'])
        print(data)

        fig, ax = graph_commons.preplot_styling()
        c = ax.pcolor(data)
        ax.set_xlabel('Time of Day (UTC)')

        ax.set_yticks([float(n) + 0.5 for n in ax.get_yticks()])
        ax.set_yticklabels(['Sun', 'Mon', 'Tues', 'Wed', 'Thurs', 'Fri', 'Sat'][::-1])

        # Hide major tick labels
        ax.set_xticklabels('')
        # Customize minor tick labels to be in the center of their boxes
        ax.set_xticks([0.5 + 4 * x for x in range(6)], minor=True)
        ax.set_xticklabels([4 * x for x in range(6)], minor=True)

        # visually remove all ticks
        ax.xaxis.set_tick_params(length=0)
        ax.yaxis.set_tick_params(length=0)
        ax.tick_params('both', length=0, width=1, which='minor')

        ax.set_title('Activity at Various Times of the Week')
        fig.colorbar(c, ax=ax, orientation='horizontal', drawedges=False).set_label('Median Messages per Hour')

        fig.tight_layout()
        return graph_commons.plot_as_attachment()


def setup(bot):
    bot.add_cog(Activitymap(bot))
