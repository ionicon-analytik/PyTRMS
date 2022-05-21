from .__version__ import version as _version

__all__ = []


from .measurement import Measurement

__all__ += ['Measurement']


def open(path):
    '''Open a datafile for a quick view on it.
    '''
    return Measurement(path)

def connect(host='localhost', port=8002):
    '''Factory function.
    '''
    from .ioniclient import IoniClient

    return IoniClient(host, port)

