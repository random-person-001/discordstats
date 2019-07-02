import discord
from discord.ext import commands


class Paginator(commands.Paginator):
    """Usage:
    Instantiate one of these, call add_line() as wanted, then post().
    Hold a list of these in a cog, removing them when `dead`, and passing
    on_reaction_add event to each of these
    """

    def __init__(self, bot, channel: discord.TextChannel, **embed_kwargs):
        """If the footer is empty, it will be set to like 'Page x of X'"""
        super().__init__(prefix='', suffix='', max_size=2048)
        self.dead = False
        self.page_num = 0
        self.channel = channel
        self.bot = bot
        self.msg = None
        self.dynamic_footer = not embed_kwargs or 'footer' not in embed_kwargs
        if not embed_kwargs:
            embed_kwargs = {'footer': discord.Embed.Empty}
        if 'color' not in embed_kwargs:
            embed_kwargs['color'] = 0x004a92
        self.embed_args = embed_kwargs

    def _get_embed(self):
        if self.dynamic_footer:
            self.embed_args['footer'] = f'Page {self.page_num + 1} of {len(self.pages)}'
        if self.pages:
            description = self.pages[self.page_num]
        else:
            description = 'Nothing to see here; move along'
            self.embed_args['footer'] = discord.Embed.Empty
        return discord.Embed(description=description,
                             **self.embed_args).set_footer(text=self.embed_args['footer'])

    async def post(self):
        try:
            self.msg = await self.channel.send(embed=self._get_embed())
            if len(self.pages) > 1:
                await self.msg.add_reaction('\N{BLACK LEFT-POINTING TRIANGLE}')
                await self.msg.add_reaction('\N{BLACK RIGHT-POINTING TRIANGLE}')
        except discord.errors.Forbidden:
            self.dead = True

    async def _refresh(self):
        if not self.dead:
            await self.msg.edit(embed=self._get_embed())
            await self._clear_reactions(leave_mine=True)

    async def _clear_reactions(self, leave_mine=False):
        # the instance of self.msg we have stored will not have any reactions on it
        cached = discord.utils.get(self.bot.cached_messages, id=self.msg.id)
        if not cached:
            cached = await self.msg.channel.fetch_message(self.msg.id)
        for reaction in cached.reactions:
            async for user in reaction.users():
                if not (leave_mine and user.id == self.bot.user.id):
                    try:
                        await reaction.remove(user)
                    except (discord.errors.Forbidden, discord.errors.NotFound, discord.errors.HTTPException):
                        pass

    async def on_reaction_add(self, reaction, user):
        if not discord.utils.get(self.bot.cached_messages, id=self.msg.id):
            print('paginator dropped from cache')
            self.dead = True
            await self._clear_reactions()
        if not self.msg or reaction.message.id != self.msg.id or user.id == self.bot.user.id or self.dead:
            return
        if reaction.emoji == '\N{BLACK LEFT-POINTING TRIANGLE}':
            if self.page_num > 0:
                self.page_num -= 1
                await self._refresh()
        elif reaction.emoji == '\N{BLACK RIGHT-POINTING TRIANGLE}':
            if self.page_num < len(self.pages):
                self.page_num += 1
                await self._refresh()
