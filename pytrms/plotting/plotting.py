# import matplotlib.pyplot as plt  # should be inlined, loads forever!


def plot_marker(signal, marker, **kwargs):
    '''Plot a `signal` and fill the regions where `marker=True`.

    Returns a tuple of `figure, axis`.
    '''
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    if hasattr(signal, 'plot'):
        subplot = signal.plot(ax=ax)
        line, *_ = subplot.get_lines()
    else:
        line, = ax.plot(signal)

    x_ = line.get_xdata()
    lo, hi = ax.get_ylim()
    ax.fill_between(x_, lo, hi, where=marker, color='orange')

    ax.grid(visible=True)
    if hasattr(signal, 'name'):
        ax.set_title(signal.name)

    return fig, ax

