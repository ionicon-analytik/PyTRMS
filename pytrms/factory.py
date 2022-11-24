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

