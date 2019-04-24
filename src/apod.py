import asyncio

import discord
from discord.ext import commands
import json
import aiohttp
import async_timeout
import time


async def fetch_url(url, retries=10):
    """Async url fetch.  By default, it will retry up to 10 times, with a geometric wait"""
    if retries is 0:
        raise TimeoutError(f'Failed to fetch the url {url} too many times')
    async with aiohttp.ClientSession() as session:
        with async_timeout.timeout(10):
            try:
                async with session.get(url) as response:
                    return await response.text()
            except aiohttp.ClientError:
                await asyncio.sleep(125/retries**3)  # geometric delay for retries
                return fetch_url(url, retries-1)


class Apod(commands.Cog):
    """Fetches Nasa's Astronomy Picture of the Day
    This supports non-images.

    Code adapted from https://github.com/TheDevFreak/NasaBot/
    """

    def __init__(self, bot):
        self.bot = bot
        self.nasa_key = self.bot.config['nasatoken']
        self.last_checked = ''  # stringified version of when we last fetched the apod
        self.last_url = None  # url of the image we got, none if it wasn't an image
        self.last_json = None

    def truncate_explanation(self, date: str):
        """The description field in a discord embed is limited to 2048 characters.
        Truncate the explanation to fit, and add a [more] to the end with a link to that day's apod page
        'date' is an exactly six digit string of year, month, day format.
        """
        if 1990 > len(self.last_json['explanation']):
            self.last_json['explanation'] = self.last_json['explanation'][:1990] + '...'
        self.last_json['explanation'] += f'[[more]](https://apod.nasa.gov/apod/ap{date}.html)'

    async def update_image(self):
        """Update internal state to make sure we have the latest and greatest data"""
        today = time.strftime("%Y-%m-%d")
        if today != self.last_checked:
            self.last_checked = today
            apod_json = await fetch_url(f'https://api.nasa.gov/planetary/apod?date={today}&api_key={self.nasa_key}')
            self.last_json = json.loads(apod_json)
            self.truncate_explanation(time.strftime('%y%m%d'))
            if self.last_json['media_type'] == 'image':
                if 'hdurl' in self.last_json:
                    self.last_url = self.last_json['hdurl']
                else:
                    self.last_url = self.last_json['url']
            else:
                self.last_url = None

    async def get_embed(self):
        """Build the discord.Embed object to send to the chat"""
        apod_url = 'https://apod.nasa.gov/'
        await self.update_image()
        if self.last_json is None:
            return discord.Embed(title='Error fetching APOD', color=0x992222, url=apod_url,
                                 description='Maybe try again in a bit?')
        if self.last_json['service_version'] != 'v1':
            return discord.Embed(title='Looks like the APOD format has changed to an unsupported version',
                                 color=0x5b000a, url=apod_url)
        embed = discord.Embed(
            title='Astronomy Picture Of The Day - ' + self.last_json['title'],
            color=0x123e57,
            description=self.last_json['explanation']
        )
        if self.last_url:  # this is None if the image is not an actual image (like some youtube vid or something)
            embed.set_image(url=self.last_url)
        else:
            embed.add_field(name='Link', value=self.last_json['url'])

        nasa_raster_icon = 'http://www.laboiteverte.fr/wp-content/uploads/2015/09/nasa-logo.png'
        return embed.set_footer(text=self.last_checked, icon_url=nasa_raster_icon)

    @commands.command()
    async def apod(self, ctx):
        await ctx.send(embed=await self.get_embed())


def setup(bot):
    bot.add_cog(Apod(bot))
