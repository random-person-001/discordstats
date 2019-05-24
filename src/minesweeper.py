import random

import numpy as np
from discord.ext import commands

"""
A discord.py cog for playing minesweeper with spoilers.

Written by John Locke#2742 (275384719024193538) on 1 Feb 2019, released into public domain 
"""


def place_bomb(grid):
    """Places a bomb in a nonoccupied space on the grid"""
    while True:
        x = random.randrange(grid.shape[0])
        y = random.randrange(grid.shape[1])
        if grid[x][y] != -1:
            grid[x][y] = -1
            return


def count_adjacent_bombs(grid, x, y):
    """Get the number of adjacent bombs (including diagonal) to a point"""
    max_x = grid.shape[0]
    max_y = grid.shape[1]
    count = 0
    for dx in range(-1, 2):
        for dy in range(-1, 2):
            if 0 <= x + dx < max_x and 0 <= y + dy < max_y:
                if grid[x + dx][y + dy] == -1:
                    count += 1
    return count


def get_emoji(num):
    """Convert a grid data value into an emoji that will be put in a discord message"""
    mappy = {1: ':one:', 2: ':two:', 3: ':three:', 4: ':four:', 5: ':five:',
             6: ':six:', 7: ':seven:', 8: ':eight:', -1: '💥', 0: '⬜'}
    if num not in mappy:
        return '❓'
    return mappy[num]


def stringify(grid):
    """Get a list of discord message contents representing the grid, given the data grid
    Usually there's just one element, but if the minefield is large and goes over the
    character limit for messages, there'll be more.
    """
    outlist = []
    out = ''
    for row in grid:
        for location in row:
            out += '||' + get_emoji(location) + '|| '
        out += '\n'
        if len(out) + grid.shape[1] * (7 + 5) > 1900:
            outlist.append(out)
            out = ''
    outlist.append(out)
    return outlist


def make_grid(rows=7, cols=7, density=.3):
    """Create a minesweeper data grid and return a list of message contents to post to display it"""
    grid = np.zeros((rows, cols), dtype=int)
    mine_count = int(density * grid.size)
    for i in range(mine_count):
        place_bomb(grid)

    for x in range(rows):
        for y in range(cols):
            if grid[x][y] != -1:
                grid[x][y] = count_adjacent_bombs(grid, x, y)
    print(grid)
    return stringify(grid)


class Minesweeper(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.cooldown(2, 6)
    @commands.command(aliases=['ms'])
    async def minesweeper(self, ctx, rows: int = 8, cols: int = 8, density: int = 15):
        """Play minesweeper in the chat with spoilers!
        The density parameter is the % of mines on the board.  This is usually 10-20%
        """
        if density < 0 or 100 <= density:
            await ctx.send("Woah there, let's try to keep the density between 0 and 100%")
            return
        if max(rows, cols) > 60:
            await ctx.send("Woah there, let's try not to make enormous boards like that.")
            return
        if min(rows, cols) < 1:
            await ctx.send(":thinking: are you alright sir?")
            return
        strlist = make_grid(rows, cols, density / 100.)
        await ctx.send('There are {} mines.  Good luck!'.format(int(density * rows * cols / 100)))
        for part in strlist:
            if len(part) > 0:
                await ctx.send(part)


# add this as a cog to the bot
def setup(bot):
    bot.add_cog(Minesweeper(bot))
