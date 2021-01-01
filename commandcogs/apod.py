import asyncio
import datetime
import json
import re
import traceback

import aiohttp
import async_timeout
import discord
import time
from discord.ext import tasks, commands


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
                await asyncio.sleep(125 / retries ** 3)  # geometric delay for retries
                return fetch_url(url, retries - 1)


class Apod(commands.Cog):
    """Fetches Nasa's Astronomy Picture of the Day
    This supports non-images.

    Code adapted from https://github.com/TheDevFreak/NasaBot/
    """

    def __init__(self, bot):
        self.bot = bot
        self.nasa_key = self.bot.config['APOD']['nasatoken']
        self.last_checked = ''  # stringified version of when we last fetched the apod
        self.last_url = None  # url of the image we got, none if it wasn't an image
        self.last_json = None
        self.apod_bg.start()

    def truncate_explanation(self):
        """Truncate the explanation, and add a [more] to the end
         with a link to that day's apod page

        The description field in a discord embed is limited to
        2048 characters, which truncate to.

        'date' is an exactly six digit string of year, month, day format.
        """
        s = self.last_json['explanation']
        # Here we handle obnoxious addendums like on
        # 2019-05-15  2019-04-28  2017-03-20  2017-03-07 2017-03-01  2012-12-30 etc
        # which are returned in the api's description field mrrg _even though_ the website has a <p> separator
        # in the html, the api just breezes through that
        #
        # Try looking for `sentence end, then spaces, then up to six words, then a colon, then an arbitrary amount
        #  of words but no periods, then perhaps sentence end punctuation, then end of input` because the
        #  annoying addendums seem to follow that pattern
        #
        addendum = r"([.!?])( +[\w,()+<>=]+){1,6}:( +[^.!?]+)+\W?\Z"
        split = re.split(addendum, s)
        s = split[0]
        # add back punctuation before the addendum
        if len(split) > 1:
            s += split[1]
        # don't go over discord's embed field length
        if 1993 <= len(s):
            s = s[:1990] + '...'
            s += '[[more]]({})'.format(self.last_json['permalink'])
        self.last_json['explanation'] = s

    async def update_image(self):
        """Update internal state to make sure we have the latest
        and greatest data
        """
        today = time.strftime("%Y-%m-%d")
        self.last_checked = today
        apod_json = await fetch_url(f'https://api.nasa.gov/planetary/apod?date={today}&api_key={self.nasa_key}')
        self.last_json = json.loads(apod_json)
        smol_date = time.strftime('%y%m%d')
        self.last_json['permalink'] = f'https://apod.nasa.gov/apod/ap{smol_date}.html'
        self.truncate_explanation()
        if self.last_json['media_type'] == 'image':
            if 'hdurl' in self.last_json:
                self.last_url = self.last_json['hdurl']
            else:
                self.last_url = self.last_json['url']
        else:
            self.last_url = None
            # kinda handle obnoxious unclickable urls
            # (like returned on 2019-04-28)
            if self.last_json['url'].startswith('//'):
                self.last_json['url'] = 'https:' + self.last_json['url']

    def get_texty(self):
        out = f'__**{self.last_json["title"]}**__\n\\> ' + self.last_json['explanation']
        if 'copyright' in self.last_json:
            out += '   ***Image credit & copyright: ' + self.last_json['copyright'] + '***\n '
        out = out.replace('*', '\\*').replace('_', '\\_')
        out += self.last_json['url']
        return out

    async def get_embed(self):
        """Build the discord.Embed object to send to the chat"""
        await self.update_image()
        apod_url = self.last_json['permalink']
        if self.last_json is None:
            return discord.Embed(title='Error fetching APOD', color=0x992222, url=apod_url,
                                 description='Maybe try again in a bit?')
        if self.last_json['service_version'] != 'v1':
            return discord.Embed(title='Looks like the APOD format has changed to an unsupported version',
                                 color=0x5b000a, url=apod_url)
        embed = discord.Embed(
            title='Astronomy Picture Of The Day - ' + self.last_json['title'],
            color=0x123e57, url=apod_url,
            description=self.last_json['explanation']
        )

        # self.last_url is None if the image is not an
        # actual image (like some youtube vid or something)
        if self.last_url:
            embed.set_image(url=self.last_url)
        else:
            embed.add_field(name='Link', value=self.last_json['url'])

        nasa_raster_icon = 'http://www.laboiteverte.fr/wp-content/uploads/2015/09/nasa-logo.png'
        return embed.set_footer(text=self.last_checked, icon_url=nasa_raster_icon)

    @commands.command(hidden=True)
    @commands.guild_only()
    async def apod(self, ctx):
        """Post NASA's Astronomy Picture of the Day here"""
        await ctx.send(embed=await self.get_embed())

    @commands.command(hidden=True)
    async def oapod(self, ctx):
        """Get a copy/pastable apod post"""
        await self.update_image()
        await ctx.send(self.get_texty())

    @tasks.loop(hours=23.9)
    async def apod_bg(self):
        apod_channel = self.bot.get_channel(self.bot.config['APOD']['apod_channel'])
        apod_err_channel = self.bot.get_channel(self.bot.config['APOD']['apod_err_channel'])
        # noinspection PyBroadException
        try:
            embed = await self.get_embed()
        except TimeoutError:
            traceback.print_exc()  # log to stderr
            await apod_err_channel.send(
                'Yo uh kinda awkward but my background task had '
                'problems fetching the apod from nasa; would some '
                'human mind trying to make stuff work?')
        except Exception:
            # ooh boy something went real wrong
            traceback.print_exc()  # log to stderr
            tb = traceback.format_exc()
            await apod_err_channel.send(
                'Yo uh I had a big ol whoopsies while trying to post '
                "the apod here... here's the traceback so mebbe it "
                'gets fixed:\n\n```arm\n' + tb + '```')
        else:
            await apod_channel.send(embed=embed)

    @apod_bg.before_loop
    async def before_apod_bg(self):
        print('waiting...')
        await self.bot.wait_until_ready()
        # wait until, say 4am before beginning the task
        # (which repeats every 24 hrs after)
        now = datetime.datetime.utcnow()
        hr = self.bot.config['APOD']['apod_post_hour']
        if now.hour < hr:
            dt = datetime.datetime(now.year, now.month, now.day, hour=hr) - now
            print(f'waiting {dt} to start apod')
            await asyncio.sleep(dt.total_seconds())
        else:
            dt = datetime.datetime(now.year, now.month, now.day + 1, hour=hr) - now
            print(f'waiting {dt} to start apod tomorrow')
            await asyncio.sleep(dt.total_seconds())


def setup(bot):
    bot.add_cog(Apod(bot))
