import discord
from discord.ext import commands


def print_why_rethinkdb():
    print("Rethinkdb is used for storing locations that users specify, so that w|a results are localized to users them."
          "  The bot will still work, but the `,set_location` command won't work and results won't be localized.")


try:
    import rethinkdb as r
except ImportError:
    print("Oops, couldn't import the rethinkdb module.  If you want it, run `pip install rethinkdb`")
    print_why_rethinkdb()
    r = None

RETHINKDB_PORT = 28015
DEFAULT_LOCATION = "washington dc"


class Registration:

    def __init__(self, bot: discord.ext.commands.Bot):
        self.conn = None
        self.bot = bot
        self.conn_task = self.bot.loop.create_task(self.connect_to_rethinkdb())

    def disconnect(self):
        if self.conn is not None:
            self.bot.loop.create_task(self.conn.close())

    async def connect_to_rethinkdb(self):
        """Create our connection to rethinkdb.  This is what we use for storing user locations.
        This will create the table and stuff if necessary"""
        if r is not None:
            r.set_loop_type("asyncio")
        print("connecting to rethinkdb....")
        if 'rethinkdb' not in self.bot.api_keys:
            print("Looks like you don't have a rethinkdb password specified in the api key file.")
            print_why_rethinkdb()
        print("Good, had password in api key file")
        self.conn = await r.connect("localhost", RETHINKDB_PORT, user='admin', password=self.bot.api_keys['rethinkdb'])
        print("Connected to rethinkdb")

        try:
            tables = await r.db("lamp").table_list().run(self.conn)
        except r.errors.ReqlOpFailedError:
            await r.db_create("lamp").run(self.conn)
            await r.db("lamp").table_create("user_locations").run(self.conn)
            print("Created db and table for lamp user location registration")
        else:
            if "user_locations" not in tables:
                await r.db("lamp").table_create("user_locations").run(self.conn)
                print("Created table for lamp user location registration")

    async def set_location(self, ctx, location: str):
        """Sets a location to localize your wolfram alpha queries to.  You only have to do this once."""
        user = ctx.message.author
        cursor = await r.db('lamp').table("user_locations").filter(r.row["user"] == str(user.id)).run(self.conn)

        # check to see if already registered first
        while await cursor.fetch_next():
            c = await cursor.next()
            try:
                await ctx.send(f"Unregistering you from previous location {c['location']}")
                res = await r.db('lamp').table("user_locations").get(c['id']).delete().run(self.conn)
                print(res)
            except KeyError:
                pass

        await r.db('lamp').table("user_locations").insert({"user": str(user.id), "location": location}).run(self.conn)
        await ctx.send(f'`{user.name}`\'s results will now be localized to the place `{location}`')

    async def unset_location(self, ctx):
        """Unsets your remembered location"""
        user = ctx.message.author
        cursor = await r.db('lamp').table("user_locations").filter(r.row["user"] == str(user.id)).run(self.conn)
        found = False

        while await cursor.fetch_next():
            c = await cursor.next()
            try:
                await ctx.send(f"Unregistering you from previous location of {c['location']}")
                res = await r.db('lamp').table("user_locations").get(c['id']).delete().run(self.conn)
                print(res)
                found = True
            except KeyError:
                pass

        if not found:
            await ctx.send("It didn't look like you were registered")

    async def get_location(self, ctx, silent=True):
        """
        Gets the location of the user who sent the message in ctx.
        If they aren't registered to a location, return DEFAULT_LOCATION
        The silent option specifies whether the command should say the result in the chat.
        """
        user = ctx.message.author
        if self.conn is None:
            return 'washington dc'
        try:
            cursor = await r.db('lamp').table("user_locations").filter(r.row["user"] == str(user.id)).run(self.conn)
        except r.errors.ReqlDriverError:
            print("No connection to rethinkdb!")
            return 'washington dc'

        # check to see if already registered first
        while await cursor.fetch_next():
            c = await cursor.next()
            if 'location' in c:
                print(c['location'])
                if not silent:
                    await ctx.send(f"{user.name} is registered to the location `{c['location']}`")
                return c['location']
        if not silent:
            await ctx.send(f"{user.name} is not registered any location yet.  Type `,help set_location` for more")
        return DEFAULT_LOCATION
