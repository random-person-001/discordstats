import datetime

from discord.ext import commands


class MemberData:
    """Data holding structure for a row in a sheet"""

    def __init__(self):
        self.username = None
        self.nickname = None
        self.joined = None
        self.xp_roll = None
        self.warnings = None
        self.messages_month = None
        self.messages_total = None


class Sheet:
    """Data holding structure for everything we want to send to google sheets"""

    def __init__(self):
        self.members = dict()

    def ensure_indexed(self, who):
        if who.id not in self.members:
            self.members[who.id] = MemberData()

    def add_names(self, who, username, nickname):
        self.ensure_indexed(who)
        self.members[who.id].username = username
        self.members[who.id].nickname = nickname

    def add_joined(self, who, joined):
        self.ensure_indexed(who)
        self.members[who.id].joined = joined

    def add_xp_roll(self, who, xp_roll):
        self.ensure_indexed(who)
        self.members[who.id].xp_roll = xp_roll

    def add_messages(self, who, month, total):
        self.ensure_indexed(who)
        self.members[who.id].messages_month = month
        self.members[who.id].messages_total = total

    def add_warnings(self, who, count):
        self.ensure_indexed(who)
        self.members[who.id].warnings = count


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
    sheet = Sheet()
    month_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    for member in guild.members:
        if member.bot:  # ignore all bots
            continue
        #  print(member)
        #  print(member.id)

        async with bot.pool.acquire() as conn:
            sheet.add_names(member, str(member), member.nickname if hasattr(member, 'nickname') else None)

            sheet.add_joined(member, member.joined_at)

            month_count = await conn.fetchval(f" select count(*) "
                                              f" from gg{guild.id} "
                                              f" where author = {member.id} "
                                              f" and date > $1", month_ago)
            total_count = await conn.fetchval(f" select count(*) "
                                              f" from gg{guild.id} "
                                              f" where author = {member.id} ")
            if month_count:
                sheet.add_messages(member, month_count, total_count)

            # xp roll
            sheet.add_xp_roll(member, get_xp_roll(member))

            # warnings
            sheet.add_warnings(member, 0)
    return sheet


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

        await ctx.bot.loop.run_in_executor(None, upload, data, ctx.bot.config['spreadsheet'])
        await ctx.send('done!')


def setup(bot):
    bot.add_cog(Sheets(bot))
