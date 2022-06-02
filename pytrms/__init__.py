_version = '0.1.1'


__all__ = []


from .measurement import Measurement

__all__ += ['Measurement']


def load(path):
    '''Open a datafile for a quick view on it.
    '''
    return Measurement(path)


def measure(filename='', host='localhost', port=8002):
    '''Prepare a measurement.
    '''
    client = connect(host, port)

    return Measurement(filename, client)


def connect(host='localhost', port=8002):
    '''Connect a client to a running measurement server.

    makes connection via modbus or webapi or whatnot
    tests connection
    returns an instrument.


    '''
    from .clients.ioniclient import IoniClient
    from .tracebuffer import TraceBuffer

    global _client
    global _buffer

    if _client is None:
        _client = IoniClient(host, port)
    if _buffer is None:
        _buffer = TraceBuffer(_client)

    return Instrument(_client, _buffer)


_client = None
_buffer = None

