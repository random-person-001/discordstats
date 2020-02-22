import json

import discord
from discord.ext import commands


def write_db(bot):
    with open("config/db.json", "w") as f:
        json.dump(bot.db, f)


def check_db(bot, guild):
    if 'REACTION_ROLLS' not in bot.db:
        bot.db['REACTION_ROLLS'] = dict()
    if str(guild.id) not in bot.db['REACTION_ROLLS']:
        bot.db['REACTION_ROLLS'][str(guild.id)] = dict()
    write_db(bot)


class ReactionRickRoller(commands.Cog):
    """
    A system of using reactions to a message to toggle one's rolls
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, event):
        try:
            mappy = self.bot.db['REACTION_ROLLS'][str(event.guild_id)]
        except KeyError:  # no reaction rolls configured for this guild
            return
        if event.message_id != mappy['message_id']:
            return
        if str(event.emoji) in mappy:
            guild = self.bot.get_guild(event.guild_id)
            roll = discord.utils.get(guild.roles, id=mappy[str(event.emoji)])
            user = discord.utils.get(guild.members, id=event.user_id)
            if not user.bot:
                await user.add_roles(roll, reason='reaction rolls')
        else:
            print(f'user {event.user_id} posted an unconfigured reaction ({event.emoji}) to the message')
            print(mappy)
            print(event.emoji)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, event):
        try:
            mappy = self.bot.db['REACTION_ROLLS'][str(event.guild_id)]
        except KeyError:  # no reaction rolls configured for this guild
            return
        if event.message_id != mappy['message_id']:
            return
        if str(event.emoji) in mappy:
            guild = self.bot.get_guild(event.guild_id)
            roll = discord.utils.get(guild.roles, id=mappy[str(event.emoji)])
            user = discord.utils.get(guild.members, id=event.user_id)
            if not user.bot:
                await user.remove_roles(roll, reason='reaction rolls')
        else:
            print(f'user {event.user_id} removed an unconfigured reaction ({event.emoji}) to the message')
            print(mappy)
            print(event.emoji)

    @commands.command()
    async def conf(self, ctx, msg_id: int):
        """Configure reaction rolls to listen to a specific message in this channel, given by its ID

        This will overwrite previous reaction roll setups for the server."""

        #  sassily reject anyone who tries to use this without enough perms
        if not ctx.message.author.guild_permissions.administrator:
            await ctx.send('smh get out you pleb, you have no power over me')
            return

        await ctx.send(f'yoooooo ok set the message that I listen to as https://discordapp.com/channels/'
                       f'{ctx.guild.id}/{ctx.channel.id}/{msg_id}  type done instead of an emoji to exit.')
        check_db(self.bot, ctx.guild)
        self.bot.db['REACTION_ROLLS'][str(ctx.guild.id)] = {'message_id': msg_id}
        primary_msg = await ctx.channel.fetch_message(msg_id)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        while True:
            await ctx.send('ok post an emoji that\'ll correspond to a roll')
            msg = await ctx.bot.wait_for('message', check=check)
            if 'done' in msg.content.lower():
                break
            print(msg.content)
            emoji = msg.content  # what could possibly go wrong
            await ctx.send('Now write the name of that roll, getting the capitalization right')
            msg = await ctx.bot.wait_for('message', check=check)
            roll = discord.utils.get(ctx.guild.roles, name=msg.content)
            if not roll:
                await ctx.send('shucks.  That roll wasn\'t found.')
            else:
                self.bot.db['REACTION_ROLLS'][str(ctx.guild.id)][emoji] = roll.id
                write_db(self.bot)
                await primary_msg.add_reaction(emoji)
        await ctx.send('cool bye')


def setup(bot):
    bot.add_cog(ReactionRickRoller(bot))