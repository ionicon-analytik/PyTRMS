_version = '0.9.1'

__all__ = ['load', 'connect']


def load(path):
    '''Open a datafile for post-analysis or batch processing.

    returns a `Measurement`.
    '''
    from .measurement import OfflineMeasurement
    from .readers import IoniTOFReader

    reader = IoniTOFReader(path)

    return OfflineMeasurement(reader)

def connect(host=None, method='webapi'):
    '''Connect a client to a running measurement server.

    'method' is the preferred connection, either 'webapi' (default) or 'modbus'.

    returns an `Instrument` if connected successfully.
    '''
    from .instrument import Instrument

    if method.lower() == 'webapi':
        from .clients.ioniclient import IoniClient
        return IoniClient(host)

    if method.lower() == 'modbus':
        from .modbus import IoniconModbus
        return IoniconModbus(host)

    raise NotImplementedError(str(method))

