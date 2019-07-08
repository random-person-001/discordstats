import datetime
import io

import discord
import matplotlib.cm as cm
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


def postplot_styling_fancy(chans):
    """Configure the graph style, after calling any plotting functions"""
    # legends and tweaks
    legend = plt.legend(loc='upper left', prop={'size': 13}, handlelength=0)
    # set legend labels to the right color
    for text, chan in zip(legend.get_texts(), chans):
        text.set_color(cm.get_cmap(chan.colormap)(.5))
    # get rid of the (usually colored) dots next to the text entries in the legend
    for item in legend.legendHandles:
        item.set_visible(False)
    postplot_styling()


def postplot_styling():
    """Various colorings done after plotting data, but before display"""
    # grid layout
    plt.grid(True, 'major', 'x', ls=':', lw=.5, c='w', alpha=.2)
    plt.grid(True, 'major', 'y', ls=':', lw=.5, c='w', alpha=.2)
    plt.tight_layout()


def preplot_styling_dates(earliest):
    """Configure the graph style (like the legend), before calling the plot functions"""
    # Styling
    fig, ax = preplot_styling()
    ax.set_ylabel('Messages per hour')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator())
    ax.set_xlim(earliest, datetime.datetime.utcnow())


def preplot_styling():
    """Configure the graph style (like splines and labels), before calling the plot functions"""
    # Styling
    fig, ax = plt.subplots()
    for pos in ('top', 'bottom', 'left', 'right'):
        ax.spines[pos].set_visible(False)
    return fig, ax


def plot_as_attachment():
    """Save image as file-like object and return it as an object ready to be sent in the chat"""
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close()  # plots are not closed automatically
    buf.seek(0)
    return discord.File(buf, filename='plot.png')


def rc_styling():
    """One-off stylistic settings"""
    plt.rcParams['legend.frameon'] = False
    plt.rcParams['figure.figsize'] = [9, 6]
    plt.rcParams['savefig.facecolor'] = '#2C2F33'
    plt.rcParams['axes.facecolor'] = '#2C2F33'
    plt.rcParams['axes.labelcolor'] = '#999999'
    plt.rcParams['text.color'] = '#999999'
    plt.rcParams['xtick.color'] = '#999999'
    plt.rcParams['ytick.color'] = '#999999'


# we want this done no matter what.
rc_styling()
