_version = '0.1.1'


__all__ = []


_client = None
_buffer = None

def load(path):
    '''Open a datafile for a quick view on it.

    returns a measurement.
    '''
    from .measurement import Measurement

    return Measurement(path)


def connect(host='localhost', port=8002):
    '''Connect a client to a running measurement server.

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

