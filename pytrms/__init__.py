_version = '0.9.4'

__all__ = ['load', 'connect']


def load(path):
    '''Open a datafile for post-analysis or batch processing.

    `path` may be a glob-expression to collect a whole batch.

    returns a `Measurement` instance.
    '''
    import glob
    from .measurement import FinishedMeasurement

    files = glob.glob(path)

    return FinishedMeasurement(*files)


def connect(host='localhost', port=None, method='mqtt'):
    '''Connect a client to a running measurement server.

    'method' is the preferred connection, either 'mqtt' (default), 'webapi' or 'modbus'.

    returns an `Instrument` if connected successfully.
    '''
    from .instrument import Instrument

    if method.lower() == 'mqtt':
        from .clients.mqtt import MqttClient as _client
    elif method.lower() == 'webapi':
        from .clients.ioniclient import IoniClient as _client
    elif method.lower() == 'modbus':
        from .modbus import IoniconModbus as _client
    else:
        raise NotImplementedError(str(method))

    backend = _client(host, port) if port is not None else _client(host)

    return Instrument(backend)

