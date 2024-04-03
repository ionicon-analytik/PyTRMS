import time
from glob import glob
from operator import attrgetter
from itertools import chain
from abc import abstractmethod, ABC

from .readers import IoniTOFReader

__all__ = ['Measurement', 'PreparingMeasurement', 'RunningMeasurement', 'FinishedMeasurement']


class Measurement(ABC):
    """Class for PTRMS-measurements and batch processing.

    The start time of the measurement is given by `.time_of_meas`.

    A measurement is iterable over the 'rows' of its data. 
    In the online case, this would slowly produce the current trace, one
    after another.
    In the offline case, this would quickly iterate over the traces in the given
    measurement file.
    """

    def _new_state(self, newstate):
        # Note: we get ourselves a nifty little state-machine :)
        self.__class__ = newstate

    def start(self, filename=''):
        """Start a measurement on the PTR server.

        'filename' is the filename of the datafile to write to. 
        If left blank, start a "quick measurement".

        If pointing to a file and the file exist on the (local) server, this raises an exception.
        To create unique filenames, use placeholders for year (%Y), month (%m), and so on,
        for example `filename=C:/Ionicon/Data/Sauerteig_%Y-%m-%d_%H-%M-%S.h5`.

        see also:
        """
        # this method must be implemented by each state
        raise RuntimeError("can't start %s" % self.__class__)

    # (see also: this docstring)
    start.__doc__ += time.strftime.__doc__

    def stop(self):
        """Stop the current measurement on the PTR server."""
        raise RuntimeError("can't stop %s" % self.__class__)

    @abstractmethod
    def __len__(self):
        pass


class PreparingMeasurement(Measurement):

    @property
    def single_spec_duration_ms(self):
        return self.ptr.get('ACQ_SRV_SpecTime_ms')

    @single_spec_duration_ms.setter
    def single_spec_duration_ms(self, value):
        self.ptr.set('ACQ_SRV_SpecTime_ms', int(value), unit='ms')

    @property
    def extraction_time_us(self):
        return self.ptr.get('ACQ_SRV_ExtractTime')

    @extraction_time_us.setter
    def extraction_time_us(self, value):
        self.ptr.set('ACQ_SRV_ExtractTime', int(value), unit='us')

    @property
    def max_flight_time_us(self):
        return self.ptr.get('ACQ_SRV_MaxFlighttime')

    @max_flight_time_us.setter
    def max_flight_time_us(self, value):
        self.ptr.set('ACQ_SRV_MaxFlighttime', int(value), unit='us')

    @property
    def expected_mass_range_amu(self):
        return self.ptr.get('ACQ_SRV_ExpectMRange')

    @expected_mass_range_amu.setter
    def expected_mass_range_amu(self, value):
        self.ptr.set('ACQ_SRV_ExpectMRange', int(value), unit='amu')

    def __init__(self, instrument):
        self.ptr = instrument

    def start(self, filename=''):
        self.ptr.start_measurement(filename)
        self._new_state(RunningMeasurement)

    def __len__(self):
        return 0


class RunningMeasurement(Measurement):

    def __init__(self, instrument):
        self.ptr = instrument

    def stop(self):
        self.ptr.stop_measurement()
        self._new_state(FinishedMeasurement)

    def __len__(self):
        return -1


class FinishedMeasurement(Measurement):

    @classmethod
    def _check(cls, sourcefiles):
        _assumptions = ("incompatible files! "
                "sourcefiles must have the same number-of-timebins and "
                "the same instrument-type to be collected as a batch")

        assert 1 == len(set(sf.inst_type          for sf in sourcefiles)), _assumptions
        assert 1 == len(set(sf.number_of_timebins for sf in sourcefiles)), _assumptions

    @property
    def number_of_timebins(self):
        return next(iter(self.sourcefiles)).number_of_timebins

    @property
    def poisson_deadtime_ns(self):
        return next(iter(self.sourcefiles)).poisson_deadtime_ns

    @property
    def pulsing_period_ns(self):
        return next(iter(self.sourcefiles)).pulsing_period_ns

    @property
    def single_spec_duration_ms(self):
        return next(iter(self.sourcefiles)).single_spec_duration_ms

    @property
    def start_delay_ns(self):
        return next(iter(self.sourcefiles)).start_delay_ns

    @property
    def timebin_width_ps(self):
        return next(iter(self.sourcefiles)).timebin_width_ps

    def __init__(self, filenames, _reader=IoniTOFReader):
        if isinstance(filenames, str):
            filenames = glob(filenames)
        if not len(filenames):
            raise ValueError("file not found or empty glob expression")

        self.sourcefiles = sorted((_reader(f) for f in filenames), key=attrgetter('time_of_file'))
        self._check(self.sourcefiles)

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

