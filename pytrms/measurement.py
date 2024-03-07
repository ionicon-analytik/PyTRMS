from glob import glob
from operator import attrgetter
from itertools import chain

from .readers import IoniTOFReader


class Measurement:
    """Class for PTRMS-measurements and batch processing.

    The start time of the measurement is given by `.time_of_meas`.

    A measurement is iterable over the 'rows' of its data. 
    In the online case, this would slowly produce the current trace, one
    after another.
    In the offline case, this would quickly iterate over the traces in the given
    measurement file.
    """
    def _check(self):
        _assumptions = ("incompatible files! "
                "sourcefiles must have the same number-of-timebins and "
                "the same instrument-type to be collected as a batch")

        assert 1 == len(set(sf.inst_type          for sf in self.sourcefiles)), _assumptions
        assert 1 == len(set(sf.number_of_timebins for sf in self.sourcefiles)), _assumptions

    def __init__(self, filenames, _reader=IoniTOFReader):
        if isinstance(filenames, str):
            filenames = glob(filenames)
        if not len(filenames):
            raise ValueError("need at least one filename")

        self.sourcefiles = sorted((_reader(f) for f in filenames), key=attrgetter('time_of_file'))
        self._check()

        self.number_of_timebins      = next(iter(self.sourcefiles)).number_of_timebins
        self.poisson_deadtime_ns     = next(iter(self.sourcefiles)).poisson_deadtime_ns
        self.pulsing_period_ns       = next(iter(self.sourcefiles)).pulsing_period_ns
        self.single_spec_duration_ms = next(iter(self.sourcefiles)).single_spec_duration_ms
        self.start_delay_ns          = next(iter(self.sourcefiles)).start_delay_ns
        self.timebin_width_ps        = next(iter(self.sourcefiles)).timebin_width_ps
        self.time_of_meas            = next(iter(self.sourcefiles)).time_of_meas

    def append(self, filename):
        """Add a sourcefile with the given `filename` to the end of the list."""
        self.sourcefiles.append(_reader(filename))
        self._check()

    def iter_traces(self, kind='raw', index='abs_cycle', force_original=False):
        """Return the timeseries ("traces") of all masses, compounds and settings.

        'kind' is the type of traces and must be one of 'raw', 'concentration' or
        'corrected'.

        'index' specifies the desired index and must be one of 'abs_cycle', 'rel_cycle',
        'abs_time' or 'rel_time'.

        """
        return chain.from_iterable(sf.get_all(kind, index, force_original) for sf in self.sourcefiles)

    def __len__(self):
        return sum(len(sf) for sf in self.sourcefiles)

