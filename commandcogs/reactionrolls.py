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
        self.region_roll_names = {'Africa', 'Asia', 'Europe', 'North America', 'Oceania', 'South America'}

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, event):
        if str(event.message_id) not in self.bot.db['REACTION_ROLLS']:  # no reaction rolls configured for this msg
            return
        mapping = self.bot.db['REACTION_ROLLS'][str(event.message_id)]
        print('i has mapping')
        if str(event.emoji) in mapping:
            print('i has place 2')
            print(mapping)
            guild = self.bot.get_guild(event.guild_id)
            print(guild)
            print(mapping[str(event.emoji)])
            roll = discord.utils.get(guild.roles, id=int(mapping[str(event.emoji)]))
            user = discord.utils.get(guild.members, id=event.user_id)
            if not user.bot:
                if roll.name not in self.region_roll_names and roll not in user.roles:
                    roll_list = user.roles
                    roll_list.append(roll)
                    await user.edit(roles=roll_list, reason='reaction rolls')
                else:
                    # get all reactions to this message and remove all from that person but the one that was just added
                    msg = await self.bot.get_channel(event.channel_id).fetch_message(event.message_id)
                    for previous_reaction in msg.reactions:
                        users = await previous_reaction.users().flatten()
                        # sometimes a fetched reaction is only a str, sometimes partial emoji, sometimes emoji
                        # so we just compare the str() versions instead
                        if msg.author in users and str(previous_reaction.emoji) != str(event.emoji):
                            await previous_reaction.remove(msg.author)

                    # rolls
                    roll_list = user.roles
                    for roll_name in self.region_roll_names:
                        r = discord.utils.get(guild.roles, name=roll_name)
                        try:
                            roll_list.remove(r)
                        except ValueError:
                            pass
                    if roll not in roll_list:
                        roll_list.append(roll)
                        await user.edit(roles=roll_list, reason='Only one region at a time bruh')

        else:
            print(f'user {event.user_id} posted an unconfigured reaction ({event.emoji}) to the message')
            print(mapping)
            print(event.emoji)
            # try to get rid of it
            msg = await self.bot.get_channel(event.channel_id).fetch_message(event.message_id)
            user = discord.utils.get(self.bot.users, id=event.user_id)
            try:
                await msg.reactions[-1].remove(user)
            except:
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, event):
        if str(event.message_id) not in self.bot.db['REACTION_ROLLS']:
            return
        mappy = self.bot.db['REACTION_ROLLS'][str(event.message_id)]
        if str(event.emoji) in mappy:
            guild = self.bot.get_guild(event.guild_id)
            roll = discord.utils.get(guild.roles, id=mappy[str(event.emoji)])
            user = discord.utils.get(guild.members, id=event.user_id)
            if not user.bot and roll in user.roles:
                roll_list = user.roles
                roll_list.remove(roll)
                await user.edit(roles=roll_list, reason='reaction rolls')
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
        self.bot.db['REACTION_ROLLS'][msg_id] = dict()
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
                self.bot.db['REACTION_ROLLS'][msg_id][emoji] = roll.id
                write_db(self.bot)
                await primary_msg.add_reaction(emoji)
        await ctx.send('cool bye')


def setup(bot):
    bot.add_cog(ReactionRickRoller(bot))
