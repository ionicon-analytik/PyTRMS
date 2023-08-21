_version = '0.2.1'

import logging

logging.TRACE = 0  # overwrites logging.NOTSET
logging.basicConfig(format='[%(levelname)s]\t%(message)s')


from .plotting import plot_marker

__all__ = ['plot_marker', 'load', 'connect']


def load(path):
    '''Open a datafile for post-analysis or batch processing.

    returns a `Measurement`.
    '''
    from .measurement import OfflineMeasurement
    from .reader import H5Reader

    reader = H5Reader(path)

    return OfflineMeasurement(reader)


def connect(host=None, method='webapi'):
    '''Connect a client to a running measurement server.

    'method' is the preferred connection, either 'webapi' (default) or 'modbus'.

    returns an `Instrument` if connected successfully.
    '''
    from .instrument import Instrument
    from .helpers import PTRConnectionError

    if method.lower() == 'webapi':
        from .clients.ioniclient import IoniClient
        return IoniClient(host)

    if method.lower() == 'modbus':
        from .modbus import IoniconModbus
        return IoniconModbus(host)

    raise NotImplementedError(str(method))


    #try:
    #    inst = Instrument(_buffer)
    #except PTRConnectionError as exc:
    #    log = logging.getLogger('pytrms')
    #    log.error(exc)
    #    raise

    #return inst


