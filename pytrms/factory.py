from functools import lru_cache


@lru_cache
def make_client(host, port, method='webapi'):
    '''Client factory.

    'method' is the preferred connection, either 'webapi' (default) or 'modbus'.
    '''
    from .clients.ioniclient import IoniClient

    if method.lower() != 'webapi':
        raise NotImplementedError(str(method))

    return IoniClient(host, port)


@lru_cache
def make_buffer(host, port, method='webapi'):
    '''TraceBuffer factory.

    'method' is the preferred connection, either 'webapi' (default) or 'modbus'.
    '''
    from .tracebuffer import TraceBuffer

    c = make_client(host, port, method)

    return TraceBuffer(c)

