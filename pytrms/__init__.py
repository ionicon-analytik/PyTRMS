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


def connect(host='localhost', port=8002):
    '''Connect a client to a running measurement server.

    returns an `Instrument` if connected successfully, `None` if not.
    '''
    from .factory import *
    from .instrument import Instrument
    from .helpers import PTRConnectionError

    _client = make_client(host, port, method='webAPI')
    _buffer = make_buffer(host, port, method='webAPI')

    try:
        inst = Instrument(_client, _buffer)
    except PTRConnectionError as exc:
        print(exc)
        inst = None

    return inst

