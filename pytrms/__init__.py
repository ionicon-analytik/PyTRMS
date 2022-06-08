_version = '0.2.0'


__all__ = []

from .plotting import plot_marker

__all__ += ['plot_marker']


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

    returns an `Instrument` if connected successfully, `None` if not.
    '''
    from .clients.ioniclient import IoniClient
    from .tracebuffer import TraceBuffer
    from .instrument import Instrument
    from .helpers import PTRConnectionError

    global _client
    global _buffer

    if _client is None:
        _client = IoniClient(host, port)
    if _buffer is None:
        _buffer = TraceBuffer(_client)

    try:
        inst = Instrument(_client, _buffer)
    except PTRConnectionError as exc:
        print(exc)
        inst = None

    return inst

