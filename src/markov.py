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
    def word_split(self, sentence):
        return ["::".join((word.orth_, word.pos_)) for word in nlp(sentence)]

    def word_join(self, words):
        sentence = " ".join(word.split("::")[0] for word in words)
        return sentence

    def sentence_split(self, text):
        return re.split(r"\s*[\n.!?]\s*", text)


def prettify(text: str) -> str:
    """Remove spaces before punctuation
    Also combine n't and nt onto their previous words
    This is a hacky solution to me not understanding spacy code.
    For instance,
    Right now I 'm thinking about this , no
    becomes
    Right now I'm thinking about this, no
    """
    # todo: this works great except for the n't and 's sequences. Fix 'em
    text = re.sub(r" ([',.!?]|n't|nt|'s)", r"\1", text)
    return discord.utils.escape_mentions(text)


class MarkovChannel:
    def __init__(self, bot, channel_id):
        self.bot = bot
        self.channel_id = channel_id
        self.updated_at = None
        self.bot_model = None
        self.human_model = None
        self.bot_users = dict()
        self.human_users = dict()

    def get_name(self, frequencies: Dict[str, int]) -> str:
        """Get a bolded name of a user, from a dict of
        usernames pointing to their frequencies
        """
        user_id = random.choices(tuple(frequencies.keys()),
                                 tuple(frequencies.values()))[0]
        user = discord.utils.get(self.bot.users, id=user_id)
        if not user:
            return '**Left guild**:  '
        return f'**{user.name}**:  '

    def model(self, text, bot: bool):
        """Train a model based on inputted text"""
        if bot:
            self.bot_model = POSifiedText(text)
        else:
            self.human_model = POSifiedText(text)

    async def ensure_ready(self):
        """Ensure that the models are initialized"""
        if not self.bot_model:
            await self.populate()

    async def populate(self):
        """Generate markov models"""
        # todo: ignore messages sent by itself
        self.updated_at = datetime.utcnow()
        bot_text_training_set = ''
        human_text_training_set = ''
        async with self.bot.pool.acquire() as conn:
            bot_data = await conn.fetch(f'SELECT author, content FROM c{self.channel_id} WHERE bot')
            for record in bot_data:
                # print(record)
                user_id = record[0]
                if user_id in self.bot_users:
                    self.bot_users[user_id] += 1
                else:
                    self.bot_users[user_id] = 1
                bot_text_training_set += record.get('content') + '.\n'
            human_data = await conn.fetch(f'SELECT author, content FROM c{self.channel_id} WHERE not bot')
            for record in human_data:
                user_id = record[0]
                if user_id in self.human_users:
                    self.human_users[user_id] += 1
                else:
                    self.human_users[user_id] = 1
                human_text_training_set += record.get('content') + '.\n'
        await self.bot.loop.run_in_executor(None, functools.partial(
            self.model, text=bot_text_training_set, bot=True))
        await self.bot.loop.run_in_executor(None, functools.partial(
            self.model, text=human_text_training_set, bot=False))

    def get_bot_user(self) -> str:
        """Gets the name of a random bot who has spoken here"""
        return self.get_name(self.bot_users)

    def get_human_user(self) -> str:
        """Gets the name of a random human who has spoken here"""
        return self.get_name(self.human_users)

    def make_sentence(self, model) -> str:
        """Get the next sentence for a model"""
        sentence = model.make_sentence()
        # todo: replace escaped mentions with bolded usernames
        if sentence:
            return discord.utils.escape_mentions(prettify(sentence))
        return 'not enough variety in this channel :cry:'

    def get_next(self) -> str:
        """Generate a message sent in this channel"""
        percent_bots = len(self.bot_users) / (len(self.human_users) + len(self.bot_users))
        bot = random.random() < percent_bots
        if bot:
            return self.get_bot_user() + self.make_sentence(self.bot_model)
        else:
            return self.get_human_user() + self.make_sentence(self.human_model)


class Markov(commands.Cog):
    def __init__(self, bot):
        self.channel_models = dict()
        self.bot = bot

    async def next_from(self, channel_id: int):
        """Ensure we have a model of the channel stored, and then
        return its next generated message
        """
        if channel_id not in self.channel_models:
            markov_channel = MarkovChannel(self.bot, channel_id)
            self.channel_models[channel_id] = markov_channel
        else:
            markov_channel = self.channel_models[channel_id]
        await markov_channel.ensure_ready()
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
    async def manymark(self, ctx, channel_id: int):
        for _ in range(15):
            await ctx.send(await self.next_from(channel_id))


def setup(bot):
    bot.add_cog(Markov(bot))
