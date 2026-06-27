"""
@file batch.py

"""
import time
import logging
from operator import attrgetter, itemgetter
from abc import abstractmethod, ABC

from .readers.ionitof_reader import IoniTOFReader

log = logging.getLogger(__name__)

__all__ = ['Batch']


class Batch:

    # TODO :: this should just be an interface to sync with the API
    #  all file-processing should happen in a 'batch' that may be
    #  initialized w/o running an API..

    @classmethod
    def _check(cls, _readers):
        _assumptions = ("incompatible files! "
                "_readers must have the same number-of-timebins and "
                "the same instrument-type to be collected as a batch")

        assert 1 == len(set(sf.inst_type          for sf in _readers)), _assumptions
        assert 1 == len(set(sf.number_of_timebins for sf in _readers)), _assumptions

    def attach_readers(self, filenames):
        self._readers = sorted((IoniTOFReader(f) for f in filenames), key=attrgetter('time_of_file'))
        assert len(self._readers) > 0, "empty list of filenames given"
        self._check(self._readers)

    def __init__(self, filenames):
        if isinstance(filenames, str):
            self.attach_readers([filenames])
        else:
            self.attach_readers(filenames)

    @property
    def number_of_timebins(self):
        return next(iter(self._readers)).number_of_timebins

    @property
    def poisson_deadtime_ns(self):
        return next(iter(self._readers)).poisson_deadtime_ns

    @property
    def pulsing_period_ns(self):
        return next(iter(self._readers)).pulsing_period_ns

    @property
    def single_spec_duration_ms(self):
        return next(iter(self._readers)).single_spec_duration_ms

    @property
    def start_delay_ns(self):
        return next(iter(self._readers)).start_delay_ns

    @property
    def timebin_width_ps(self):
        return next(iter(self._readers)).timebin_width_ps

    def read_traces(self, kind='conc', index='abs_cycle', force_original=False):
        """Return the timeseries ("traces") of all masses, compounds and settings.

        'kind' is the type of traces and must be one of 'raw', 'concentration' or
        'corrected'.

        'index' specifies the desired index and must be one of 'abs_cycle', 'rel_cycle',
        'abs_time' or 'rel_time'.

        """
        import pandas as pd

        return pd.concat(sf.read_all(kind, index, force_original) for sf in self._readers)

    get_traces = read_traces
    get_traces.__doc__ = read_traces.__doc__ + "\nAlias: 'get_traces'."

    def __iter__(self):
        for reader in self._readers:
            for specdata in reader.iter_specdata():
                yield reader.filename, specdata

