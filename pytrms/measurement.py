import os.path
import logging
from abc import abstractmethod
from collections.abc import Iterable

from .reader import H5Reader

log = logging.getLogger()


class Measurement(Iterable):
    """Base class for PTRMS-measurements or batch processing.

    Every instance is associated with exactly one `.filename` to a datafile.
    The start time of the measurement is given by `.timezero`.

    A measurement is iterable over the 'rows' of its data. 
    In the online case, this would slowly produce the current trace, one after another.
    In the offline case, this would quickly iterate over the traces in the given
    measurement file.
    """

    def is_local(self):
        return os.path.exists(self.filename)

    def __init__(self, filename):
        self.h5 = H5Reader(filename)

    @property
    def filename(self):
        return self.h5.path
    
    @property
    def timezero(self):
        return self.h5.timezero

    @property
    def traces(self):
        """shortcut for `.get_traces(kind='concentration')`."""
        return self.get_traces(kind='concentration')

    def get_traces(self, kind='raw', index='abs_cycle', force_original=False):
        """Return the timeseries ("traces") of all masses, compounds and settings.

        'kind' is the type of traces and must be one of 'raw', 'concentration' or
        'corrected'.

        'index' specifies the desired index and must be one of 'abs_cycle', 'rel_cycle',
        'abs_time' or 'rel_time'.

        If the traces have been post-processed in the Ionicon Viewer, those will be used,
        unless `force_original=True`.
        """
        return self.h5.get_all(kind, index, force_original)

    def __iter__(self):
        return iter(self.h5)

