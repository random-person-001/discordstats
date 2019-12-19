import platform
import random
import subprocess
import traceback
from datetime import datetime, timedelta
from os import listdir
from os.path import isfile, isdir, join

import discord
import psutil
import toml
from discord.ext import commands

from helpers import Paginator


def item_line_count(path):
    """Functions to get lines of code in a directory from
    https://stackoverflow.com/questions/38543709/count-lines-of-code-in-directory-using-python/49417516#49417516
    """
    if isdir(path):
        return dir_line_count(path)
    elif isfile(path):
        return len(open(path, 'rb').readlines())
    else:
        return 0


def dir_line_count(dir):
    return sum(map(lambda item: item_line_count(join(dir, item)), listdir(dir)))


class Utility(commands.Cog):
    def __init__(self, bot):
        psutil.cpu_percent()  # first time this is run, it returns 0
        self.bot = bot
        self.paginators = []

    @commands.command()
    @commands.cooldown(2, 10)
    async def trivia(self, ctx, participant: discord.Member):
        """Toggles whether the specified member has the Trivia Participant roll.  Usable by trivia hosts and staff."""
        participant_roll = discord.utils.get(ctx.guild.roles, name='Trivia Participant')
        staff_roll = discord.utils.get(ctx.guild.roles, name='Staff')
        host_roll = discord.utils.get(ctx.guild.roles, name='Trivia Host')
        if not all(roll for roll in (participant_roll, staff_roll, host_roll)):
            await ctx.send("Oops I couldn't find all the rolls I expected to here.  Aborting.")
            return
        if ctx.author.top_role < staff_roll and host_roll not in ctx.author.roles:
            await ctx.send('You cannot use this command!')
            return
        if participant_roll in participant.roles:
            await participant.remove_roles(participant_roll)
            await ctx.send('Removed their participant roll :thumbsup: ')
        else:
            await participant.add_roles(participant_roll)
            await ctx.send('Gave them participant roll :thumbsup: ')

    @commands.command()
    async def time(self, ctx, discord_id: int):
        """Extract the utc timestamp that a discord object with the given id was created"""
        await ctx.send(discord.utils.snowflake_time(discord_id))

    @commands.command(hidden=True)
    @commands.is_owner()
    async def say(self, ctx, chan_id: int, *, msg):
        chan = ctx.bot.get_channel(chan_id)
        await chan.send(msg)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def eval(self, ctx, *, code: str):
        """Execute arbitrary python code. Owner only."""
        # noinspection PyBroadException
        try:
            result = eval(code)
        except Exception:
            await ctx.send(traceback.format_exc(chain=False))
        else:
            if len(str(result)) > 2000 - 15:
                result = str(result)[:1985]
            await ctx.send(f'```py\n{result}```')

    @commands.command()
    async def oldies(self, ctx, guild_id: int = None):
        """Show a list of the oldest discord user accounts in this guild"""
        if not guild_id:
            guild_id = ctx.guild.id
        guild = ctx.bot.get_guild(guild_id)
        if not guild:
            await ctx.send(f"I'm not in any guild whose id is {guild_id}")
            return
        members = sorted(guild.members, key=lambda member: member.created_at)
        now = datetime.utcnow()
        p = Paginator.Paginator(ctx.bot, ctx.channel, title='Oldest accounts in this guild')
        for m in members:
            p.add_line("{} days:  {}".format((now - m.created_at).days, m.mention))
        self.paginators.append(p)
        await p.post()

    @commands.command()
    async def members_with(self, ctx, roll: discord.Role):
        """List the nicknames (rather than mentions) of all members with a roll"""
        gang = []
        for member in ctx.guild.members:
            if roll in member.roles:
                gang.append(member)
        e = discord.Embed(title=f"{len(gang)} members with **{roll.name}** roll:", color=0x004a92)
        # description="\n".join(member.display_name for member in gang))
        while gang:
            temp = ""
            for i in range(10):
                if gang:
                    temp += gang.pop(-1).display_name + "\n"
                if not gang:
                    e.add_field(name='_ _', value=temp)
                    break
            if gang:
                e.add_field(name='_ _', value=temp)
        await ctx.send(embed=e)

    @commands.command()
    async def info(self, ctx):
        """Who am I?  What am I doing here?  Where shall I get lunch?"""
        libs = 'Built with the help of the following packages: '
        with open('Pipfile') as f:
            pip_data = toml.load(f)
        libs += ', '.join(pip_data['packages'].keys())

        loc = str(dir_line_count('.'))

        python_version = 'Running python ' + platform.python_version()
        os_info = platform.platform()

        mem = psutil.virtual_memory()
        memory = '{}% - {} free of {} mb'.format(
            mem.percent, round(mem.available / 1_048_576), round(mem.total / 1_048_576))

        cpu = 'CPU: {}%'.format(psutil.cpu_percent())

        p = psutil.Process()
        with p.oneshot():
            cpu_time = str(round(p.cpu_times().user)) + ' seconds'
            start_time = p.create_time()
        # Note: using utcnow() is wrong; we must use now()
        age_seconds = datetime.now().timestamp() - start_time
        age = str(timedelta(seconds=age_seconds))[:-4]

        temp_data = psutil.sensors_temperatures()['coretemp'][0]
        temperature = '{}°C (limit={})'.format(temp_data.current, temp_data.critical)

        proc = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT)
        commit = proc.stdout.decode('utf-8')

        e = discord.Embed(title="About me",
                          description="A general purpose bot for Spacecord, made by Locke.\n\n" + libs,
                          color=0x004a92)
        e.set_thumbnail(url=ctx.bot.user.avatar_url)
        e.add_field(name='CPU', value=cpu)
        e.add_field(name='Memory', value=memory)
        e.add_field(name='Temperature', value=temperature)
        e.add_field(name='Bot uptime', value=age)
        e.add_field(name='CPU Time', value=cpu_time)
        e.add_field(name='Lines of Code', value=loc)
        e.add_field(name='Commands', value=str(len(ctx.bot.commands)))
        e.add_field(name='Commit Hash', value=commit)
        e.add_field(name='Discord.py Version', value=discord.__version__)
        e.set_footer(text=python_version + ' on ' + os_info)
        await ctx.send(embed=e)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        deads = []
        for paginator in self.paginators:
            if paginator.dead:
                deads.append(paginator)
            else:
                await paginator.on_reaction_add(reaction, user)
        for paginator in deads:
            self.paginators.remove(paginator)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def bug(self, ctx):
        """Bug someone to do stuff"""
        bug = ctx.bot.get_user(303770703692562432)
        await bug.send("This is your daily reminder to send Locke stuff :+1:")
        await ctx.send("done")

    @commands.cooldown(4, 15)
    @commands.command()
    async def starwars(self, ctx):
        """Spoiler for the star wars movie!"""
        if ctx.channel.name != 'bot-commands-room':
            await ctx.send('Oops, let\'s head over to the bot room to do this instead of here')
            return
        s = "In this Star Wars movie, our heroes return to take on the First Order and new villain "
        s += random.choice((
            'Kyle Ren',
            'Malloc',
            'Darth Sebelius',
            'Theranos',
            'Lord Juul'
        ))

        s += ' with help from their new friend ' + random.choice((
            'Kim Spacemeasurer',
            'Teen Yoda',
            'Dab Tweetdeck',
            'Yaz Progestin',
            'TI-83'
        ))

        s += '. Rey builds a new lightsaber with a ' + random.choice((
            'beige',
            'ochre',
            'mauve',
            'aquamarine',
            'taupe'
        ))

        s += ' blade, and they head out to confront the First Order\'s new superweapon, the '
        s += random.choice((
            'Sun Obliterator',
            'Moonsquisher',
            'World Eater',
            'Planet Zester',
            'Superconducting Supercollider'
        ))

        s += ', a space station capable of ' + random.choice((
            'blowing up a planet with a bunch of beams of energy that combine into one',
            'blowing up a bunch of planets with one beam of energy that splits into many',
            'cutting a planet in half and smashing the halves together like two cymbals',
            'increasing the CO2 levels in a planet\'s atmosphere, causing rapid heating',
            'triggering the end credits before the movie is done'
        ))

        s += '. They unexpectedly join forces with their old enemy, ' + random.choice((
            'Boba Fett',
            'Salacious Crumb',
            'the Space Slug',
            'the bottom half of Darth Maul',
            'Youtube commenters'
        ))

        s += ', and destroy the superweapon in a battle featuring ' + random.choice((
            'a bow that shoots little lightsaber-headed arrows',
            'X-Wings and TIE fighters dodging the giant letters of the opening crawl',
            'a Sith educational display that uses Force Lightning to demonstrate the dielectric breakdown of air',
            'Kylo Ren putting on another helmet over his smaller one',
            'a Sith car wash where the bristles on the brushes are little lightsabers'
        ))

        s += '.\n\nP.S. Rey\'s parents are...' + random.choice((
            'Luke',
            'Leia',
            'Han',
            'Obi-Wan',
            'a random junk trader'
        ))

        s += ' and ' + random.choice((
            'Poe',
            'BB-8',
            'Amil\'yn Holdo',
            'Laura De\'rn',
            'a random junk trader',
            'that one droid from the Jawa Sandcrawler that says Gonk'
        ))
        await ctx.send('WARNING: STAR WARS EP 9 SPOILER!\n||' + s + '.||')


def setup(bot):
    bot.add_cog(Utility(bot))
