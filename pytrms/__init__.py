_version = '0.2.1'


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


def connect(host='localhost', method='webAPI', port=None):
    '''Connect a client to a running measurement server.

    returns an `Instrument` if connected successfully, `None` if not.
    '''
    from .factory import make_client, make_buffer
    from .instrument import Instrument
    from .helpers import PTRConnectionError

    _buffer = make_buffer(host, port, method='webAPI')

    try:
        inst = Instrument(_buffer)
    except PTRConnectionError as exc:
        print(exc)
        inst = None

    return inst

