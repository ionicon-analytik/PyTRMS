from .__version__ import version as _version

__all__ = []


from .measurement import Measurement

__all__ += ['Measurement']


from .sources.h5source import H5Source

def open(path):
    '''Open a datafile for a quick view on it.
    '''
    return H5Source(path)

