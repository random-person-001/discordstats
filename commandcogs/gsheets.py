import datetime
from collections import namedtuple

from discord.ext import commands

# the data for one row in the spreadsheet (except for the user id)
MemberData = namedtuple('MemberData', ('username', 'nickname', 'joined', 'xp_roll', 'warnings',
                                       'messages_month', 'messages_total'))


class Sheets(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    @commands.cooldown(2, 20)
    async def sheet(self, ctx):
        """Gather stats on the human members of this guild, and upload it to google sheets"""
        # this import is here because of problems loading the cog when it's at the top.
        from helpers.gsheets_uploader import upload

        if ctx.author.top_role < ctx.guild.get_role(self.bot.config['SHEETS']['staff']):
            await ctx.send('bro this command takes a lot of resources so only staff can run it. '
                           ' You could ask to do that for you tho.')
            return
        data = await self.populate(ctx.message.guild)
        print('populated')

        await ctx.bot.loop.run_in_executor(None, upload, data, ctx.bot.config['SHEETS']['spreadsheet'])
        print('uploaded')
        await ctx.send('done!')

    async def populate(self, guild):
        """Create and return a sheet data structure that holds all guild data."""
        member_data = dict()
        month_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)

        async with self.bot.pool.acquire() as conn:
            message_counts = await conn.fetch(f" select t1.author, t1.monthcount, t2.totalcount"
                                              f" from ("
                                              f"     select author, count(*) as monthcount"
                                              f"     from gg{guild.id}"
                                              f"     where date > $1"
                                              f"     group by author"
                                              f" )   as t1"
                                              f" left join ("
                                              f"     select author, count(*) as totalcount"
                                              f"     from gg{guild.id}"
                                              f"     group by author"
                                              f" )   as t2"
                                              f" on t1.author = t2.author", month_ago)

            for entry in message_counts:
                member = guild.get_member(entry['author'])
                if not member:  # ignore users that sent messages but left guild
                    continue
                if member.bot:  # ignore bots
                    continue

                month_count = entry['monthcount']
                if not month_count:
                    month_count = 0

                member_data[member.id] = MemberData(username=str(member), nickname=member.nick, joined=member.joined_at,
                                                    xp_roll=self.get_xp_roll(member), warnings=0,
                                                    messages_month=month_count, messages_total=entry['totalcount'])
        return member_data

    def get_xp_roll(self, member):
        """Get the english title of the highest xp roll that a given member has"""
        lowest = member.guild.get_role(self.bot.config['SHEETS']['lowest_xp_roll'])
        highest = member.guild.get_role(self.bot.config['SHEETS']['highest_xp_roll'])
        if not lowest or not highest:
            return 'xp rolls not found!'
        for roll in member.roles[::-1]:
            if lowest <= roll <= highest:
                return roll.name
        stardust = member.guild.get_role(self.bot.config['SHEETS']['basic_roll'])
        return stardust.name


def setup(bot):
    bot.add_cog(Sheets(bot))
