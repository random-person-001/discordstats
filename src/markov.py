import functools
import random
import re
from datetime import datetime
from typing import Dict

import discord
from discord.ext import commands
import markovify
import spacy

nlp = spacy.load("en_core_web_sm")


class POSifiedText(markovify.Text):
    """Markov chaining but aware of parts of speech"""

    def word_split(self, sentence):
        return ["::".join((word.orth_, word.pos_)) for word in nlp(sentence)]

    def word_join(self, words):
        sentence = " ".join(word.split("::")[0] for word in words)
        return sentence

    def sentence_split(self, text):
        return re.split(r"\s*\n\s*", text)


class MarkovChannel:
    def __init__(self, bot, channel_id):
        self.bot = bot
        self.channel_id = channel_id
        self.updated_at = None
        self.bot_model = None
        self.human_model = None
        self.bot_users = dict()
        self.human_users = dict()

    def prettify(self, text: str) -> str:
        """Remove spaces before punctuation, and transform mentions to be nice
        Also combine n't and nt onto their previous words
        This is a hacky solution to me not understanding spacy code.
        For instance,
        Right now I 'm thinking about this , no
        becomes
        Right now I'm thinking about this, no
        """
        # todo: this regex works great except for the
        #  n't and 's sequences, which are hackily added at the end.
        #  Make that more elegant.
        # https://regexper.com/ is a nice regex visualization tool.

        # get rid of weird spaces
        text = re.sub(r" ([',.!?;]|n't|nt|'s)", r"\1", text)

        # replace mentions with their user names
        def convert_mentions(match):
            print('Match!:  ' + match[0] + '\nid=' + match.group('id') + ' prefix=' + match[1])
            if '&' in match[1]:  # roll mentions
                try:
                    return self._id_to_roll(int(match.group('id')))
                except ValueError:
                    print("uh oh, couldn't be converted to int.  "
                          "Current type is " + type(match.group('id')))
                    return '????'
            elif '@' in match[1]:  # user mentions
                try:
                    name = self._id_to_name(int(match.group('id')))
                    print(name)
                    return f'**{name}**'
                except ValueError:
                    print("uh oh, couldn't be converted to int.  "
                          "Current type is " + type(match.group('id')))
                    return '???'
            elif match[1] == '#':  # channel mentions
                return '<#{}>'.format(match.group('id'))
            return '???????'

        text = re.sub(r"< ?(@|#|@&) ?!? ?(?P<id>[0-9]{17,21}) ?>", convert_mentions, text)

        def convert_emojis(match) -> str:
            return f'<:{match[1]}>'

        text = re.sub(r"< ? ?(.*:[0-9]{17,21}) ? ?>", convert_emojis, text)

        # later I should probably move this to a regex or something
        return text.replace('you re', 'youre').replace('gon na', 'gonna').replace(' i m', ' im') \
            .replace(" 's", "'s").replace(" n't", "n't")

    def _id_to_name(self, user_id: int):
        """Map a user id to a string display name for a user"""
        guild = self.bot.get_channel(self.channel_id).guild
        member = guild.get_member(user_id)
        if not member:
            user = discord.utils.get(self.bot.users, id=user_id)
            if not user:
                return 'Left guild'
            return discord.utils.escape_markdown(user.name)
        return discord.utils.escape_markdown(member.display_name)

    def _id_to_roll(self, roll_id: int) -> str:
        """Get a roll name, or 'deleted-roll' if it isn't found"""
        guild = self.bot.get_channel(self.channel_id).guild
        roll = guild.get_role(roll_id)
        if roll:
            return f'**@{roll.name}**'
        return '**@deleted-roll**'

    def _get_name(self, frequencies: Dict[int, int]) -> str:
        """Get a bolded name of a user, from a dict of
        user ids pointing to their frequencies
        """
        user_id = random.choices(tuple(frequencies.keys()),
                                 tuple(frequencies.values()))[0]
        return self._id_to_name(user_id)

    def _model(self, text, bot: bool):
        """Train a model based on inputted text"""
        if bot:
            self.bot_model = POSifiedText(text, state_size=2)
        else:
            self.human_model = POSifiedText(text, state_size=2)

    async def ensure_ready(self):
        """Ensure that the models are initialized"""
        if not self.bot_model:
            await self.populate()

    async def populate(self):
        """Generate markov models"""
        self.updated_at = datetime.utcnow()
        bot_text_training_set = ''
        human_text_training_set = ''
        async with self.bot.pool.acquire() as conn:
            me = self.bot.user.id
            bot_data = await conn.fetch(f'SELECT author, content FROM c{self.channel_id} '
                                        f'WHERE bot AND NOT del AND NOT id = {me}')
            for record in bot_data:
                user_id = record[0]
                if user_id in self.bot_users:
                    self.bot_users[user_id] += 1
                else:
                    self.bot_users[user_id] = 1
                bot_text_training_set += record.get('content') + '\n'
            human_data = await conn.fetch(f'SELECT author, content FROM c{self.channel_id} '
                                          f'WHERE NOT bot AND NOT del AND NOT id = {me}')
            for record in human_data:
                user_id = record[0]
                if user_id in self.human_users:
                    self.human_users[user_id] += 1
                else:
                    self.human_users[user_id] = 1
                human_text_training_set += record.get('content') + '\n'
        await self.bot.loop.run_in_executor(None, functools.partial(
            self._model, text=bot_text_training_set, bot=True))
        await self.bot.loop.run_in_executor(None, functools.partial(
            self._model, text=human_text_training_set, bot=False))

    def _get_bot_user(self) -> str:
        """Gets the name of a random bot who has spoken here"""
        return "**" + self._get_name(self.bot_users) + "**:   "

    def _get_human_user(self) -> str:
        """Gets the name of a random human who has spoken here"""
        return "**" + self._get_name(self.human_users) + "**:   "

    def _make_sentence(self, model) -> str:
        """Get the next sentence for a model"""
        sentence = model.make_sentence(tries=20)
        if sentence:
            return self.prettify(sentence)
        return 'not enough variety in this channel :cry:'

    def get_next(self) -> str:
        """Generate a message sent in this channel"""
        if not self.bot_model:
            raise ValueError("You must call `ensure_ready()` before fetching sentences")
        percent_bots = len(self.bot_users) / (len(self.human_users) + len(self.bot_users))
        bot = random.random() < percent_bots
        if bot:
            return self._get_bot_user() + self._make_sentence(self.bot_model)
        else:
            return self._get_human_user() + self._make_sentence(self.human_model)


class Markov(commands.Cog):
    def __init__(self, bot):
        self.channel_models = dict()
        self.bot = bot

    async def next_from(self, channel_id: int) -> str:
        """Ensure we have a model of the channel stored, and then
        return its next generated message
        """
        # we could use locks here but I doubt we'll get to the scale that's necessary
        if channel_id not in self.channel_models:
            print('building model...')
            markov_channel = MarkovChannel(self.bot, channel_id)
            self.channel_models[channel_id] = markov_channel
            await markov_channel.ensure_ready()
            print('...model built!')
        else:
            markov_channel = self.channel_models[channel_id]
        return markov_channel.get_next()

    @commands.command()
    @commands.cooldown(5, 5)
    async def mark(self, ctx, channel: discord.TextChannel = None):
        """Generate message from this channel, or another channel if specified"""
        if not channel:
            channel = ctx.channel
        elif not channel.permissions_for(ctx.author).read_message_history:
            await ctx.send("Nope, you can't see there so I ain't doing that")
            return
        await ctx.send(await self.next_from(channel.id))

    @commands.command()
    @commands.is_owner()
    async def manymark(self, ctx, channel_id: int = 391757407493029890):
        for _ in range(15):
            await ctx.send(await self.next_from(channel_id))


def setup(bot):
    bot.add_cog(Markov(bot))
