_version = '0.2.1'


import logging

#logging.basicConfig(#)
log = logging.getLogger()

__all__ = ['log']

from .plotting import plot_marker

__all__ += ['plot_marker']


from functools import lru_cache

@lru_cache
def make_client(host, port=None, method='webapi'):
    '''Client factory.

    'method' is the preferred connection, either 'webapi' (default) or 'modbus'.
    '''
    if method.lower() == 'webapi':
        from .clients.ioniclient import IoniClient
        if port is not None:
            return IoniClient(host, port)
        return IoniClient(host)

    if method.lower() == 'modbus':
        from .modbus import IoniconModbus
        if port is not None:
            return IoniconModbus(host, port)
        return IoniconModbus(host)

    raise NotImplementedError(str(method))

@lru_cache
def make_buffer(host, port=None, method='webapi'):
    '''TraceBuffer factory.

    'method' is the preferred connection, either 'webapi' (default) or 'modbus'.
    '''
    from .tracebuffer import TraceBuffer

    c = make_client(host, port, method)

    return TraceBuffer(c)


def load(path):
    '''Open a datafile for post-analysis or batch processing.

    returns a `Measurement`.
    '''
    from .measurement import OfflineMeasurement
    from .reader import H5Reader

    reader = H5Reader(path)

    return OfflineMeasurement(reader)


def connect(host='localhost', method='webAPI', port=None):
    '''Connect a client to a running measurement server.

    returns an `Instrument` if connected successfully.
    '''
    from .factory import make_client, make_buffer
    from .instrument import Instrument
    from .helpers import PTRConnectionError

    _buffer = make_buffer(host, port, method='webAPI')

    try:
        inst = Instrument(_buffer)
    except PTRConnectionError as exc:
        log.error(exc)
        raise

    return inst


__all__ += ['load', 'connect']

