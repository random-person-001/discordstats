import datetime
from collections import namedtuple

from discord.ext import commands

MemberData = namedtuple('MemberData', ('username', 'nickname', 'joined', 'xp_roll', 'warnings',
                                       'messages_month', 'messages_total'))


def get_xp_roll(member):
    """Get the english title of the highest xp roll that a given member has"""
    lowest = member.guild.get_role(396440356239048709)
    highest = member.guild.get_role(529851477078835200)
    if not lowest or not highest:
        return 'xp rolls not found!'
    for roll in member.roles[::-1]:
        if lowest <= roll <= highest:
            return roll.name
    stardust = member.guild.get_role(391756481772388352)
    return stardust.name


async def populate(bot, guild):
    """Create and return a sheet data structure that holds all guild data."""
    member_data = dict()
    month_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)

    async with bot.pool.acquire() as conn:
        monthly = await conn.fetch(f" select author, count(*)"
                                   f" from gg{guild.id}"
                                   f" where date > $1"
                                   f" group by author", month_ago)
        totally = await conn.fetch(f" select author, count(*)"
                                   f" from gg{guild.id}"
                                   f" group by author")
        for entry in totally:
            member = guild.get_member(entry['author'])
            if not member:  # ignore users that sent messages but left guild
                continue
            if member.bot:  # ignore all bots
                continue

            month_entry = list(filter(lambda e: e.get('author') == member.id, monthly))
            month_count = month_entry[0]['count'] if month_entry else 0

            t = MemberData(username=str(member), nickname=member.nick, joined=member.joined_at,
                           xp_roll=get_xp_roll(member), warnings=0, messages_month=month_count,
                           messages_total=entry['count'])
            member_data[member.id] = t
    return member_data


class Sheets(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    @commands.cooldown(2, 10)
    async def sheet(self, ctx):
        """Gather stats on the human members of this guild, and upload it to google sheets"""
        from helpers.gsheets_uploader import upload

        # if not ctx.author.top_role >= ctx.guild.
        data = await populate(ctx.bot, ctx.message.guild)
        print('populated')

        await ctx.bot.loop.run_in_executor(None, upload, data, ctx.bot.config['spreadsheet'])
        print('uploaded')
        await ctx.send('done!')


def setup(bot):
    bot.add_cog(Sheets(bot))
