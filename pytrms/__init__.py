from .__version__ import version as _version

__all__ = []


from .measurement import Measurement

__all__ += ['Measurement']


def open(path):
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
    '''
    from .ioniclient import IoniClient

    return IoniClient(host, port)

