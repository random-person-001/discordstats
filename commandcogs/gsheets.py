import datetime
from collections import namedtuple

import discord
from discord.ext import commands

# the data for one row in the spreadsheet (except for the user id)
MemberData = namedtuple('MemberData', ('username', 'nickname', 'xp_roll', 'warnings', 'joined',
                                       'messages_month', 'messages_total', 'messages_offtopic', 'xp_roll_pos'))


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

    async def populate(self, guild: discord.Guild):
        """Create and return a sheet data structure that holds all guild data."""
        member_data = dict()
        month_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)

        # build a subquery to get all the author messages in offtopic channels
        lowest_on_topic = guild.get_channel(self.bot.config['SHEETS']['lowest_on_topic'])
        off_topics = (chan.id for chan in guild.text_channels if chan.position > lowest_on_topic.position)
        off_topic_subquery = ' union all '.join(f'( select author from c{id} )' for id in off_topics)

        async with self.bot.pool.acquire() as conn:
            message_counts = await conn.fetch(f" select t1.author, monthly, total, offtopic, warns"
                                              f" from ("
                                              f"     select author, count(*) as monthly"
                                              f"     from gg{guild.id}"
                                              f"     where date > $1"
                                              f"     group by author"
                                              f" )   as t1"
                                              f" left join ("
                                              f"     select author, count(*) as total"
                                              f"     from gg{guild.id}"
                                              f"     group by author"
                                              f" )   as t2"
                                              f" on t1.author = t2.author"
                                              f" left join ("
                                              f"     select author, count(*) as offtopic"
                                              f"     from ( {off_topic_subquery} ) as foo"
                                              f"     group by author"
                                              f" ) as t3"
                                              f" on t1.author = t3.author"
                                              f" left join ("
                                              f"     select victim, warns from warns{guild.id}"
                                              f" ) as t4 on t1.author = t4.victim", month_ago)

            for entry in message_counts:
                member = guild.get_member(entry['author'])
                if not member:  # ignore users that sent messages but left guild
                    continue
                if member.bot:  # ignore bots
                    continue
                xp_roll = self.get_xp_roll(member)

                warnings = entry['warns'] if entry['warns'] else 0

                member_data[member.id] = MemberData(username=str(member), nickname=member.nick,
                                                    joined=str(member.joined_at),
                                                    xp_roll=xp_roll.name, warnings=warnings,
                                                    messages_month=entry['monthly'], messages_total=entry['total'],
                                                    messages_offtopic=entry['offtopic'], xp_roll_pos=xp_roll.position)
        return member_data

    def get_xp_roll(self, member):
        """Get the highest xp roll that a given member has"""
        lowest = member.guild.get_role(self.bot.config['SHEETS']['lowest_xp_roll'])
        highest = member.guild.get_role(self.bot.config['SHEETS']['highest_xp_roll'])
        if not lowest or not highest:
            return 'xp rolls not found!'
        for roll in member.roles[::-1]:
            if lowest <= roll <= highest:
                return roll
        stardust = member.guild.get_role(self.bot.config['SHEETS']['basic_roll'])
        return stardust


def setup(bot):
    bot.add_cog(Sheets(bot))
