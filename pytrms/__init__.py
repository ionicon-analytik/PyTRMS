_version = '0.2.0'


__all__ = []


def load(path):
    '''Open a datafile for post-analysis or batch processing.

    returns a Measurement.
    '''
    from .measurement import OfflineMeasurement
    from .reader import H5Reader

    reader = H5Reader(path)

    return OfflineMeasurement(reader)


_client = None
_buffer = None

def connect(host='localhost', port=8002):
    '''Connect a client to a running measurement server.

    returns an Instrument.
    '''
    from .clients.ioniclient import IoniClient
    from .tracebuffer import TraceBuffer
    from .instrument import Instrument

    global _client
    global _buffer

    if _client is None:
        _client = IoniClient(host, port)
    if _buffer is None:
        _buffer = TraceBuffer(_client)

    return Instrument(_client, _buffer)


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

