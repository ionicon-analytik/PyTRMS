import time
from operator import attrgetter
from itertools import chain
from abc import abstractmethod, ABC

import pandas as pd

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

    @property
    def is_running(self):
        return self.__class__ == RunningMeasurement

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

    def __iter__(self):
        from .clients.mqtt import MqttClient
        if not isinstance(self.ptr.backend, MqttClient):
            raise NotImplementedError("iteration only provided w/ backend 'mqtt'")

        print("warning: the measurement needs to be started externally")
        while not self.ptr.backend.is_running:
            time.sleep(50e-3)

        self._new_state(RunningMeasurement)
        yield from iter(self)


class RunningMeasurement(Measurement):

    def __init__(self, instrument):
        self.ptr = instrument

    def stop(self):
        self.ptr.stop_measurement()
        self._new_state(FinishedMeasurement)

    def __iter__(self):
        from .clients.mqtt import MqttClient
        if not isinstance(self.ptr.backend, MqttClient):
            raise NotImplementedError("iteration only provided w/ backend 'mqtt'")

        if not self.ptr.backend.is_connected:
            raise Exception("no connection to instrument")

        timeout_s = 15
        ssd_s = 1e-3 * self.ptr.get('ACQ_SRV_SpecTime_ms')
        last_rel_cycle = -1
        sourcefile = ''
        for specdata in self.ptr.backend.iter_specdata(timeout_s=timeout_s+ssd_s, buffer_size=300):
            if last_rel_cycle == -1 or specdata.timecycle.rel_cycle < last_rel_cycle:
                # the source-file has been switched, so wait for the new path:
                started_at = time.monotonic()
                while time.monotonic() < started_at + timeout_s:
                    candidate = self.ptr.backend.current_sourcefile
                    if candidate and candidate != sourcefile:
                        sourcefile = candidate
                        break

                    time.sleep(10e-3)
                else:
                    raise TimeoutError(f"no new sourcefile after ({timeout_s = })")
            last_rel_cycle = specdata.timecycle.rel_cycle

            yield sourcefile, specdata

        if not self.ptr.backend.is_running:
            self._new_state(FinishedMeasurement)
            ## TODO :: das hier braucht noch seine .sourcefiles !!
            self.sourcefiles = []


class FinishedMeasurement(Measurement):

    @classmethod
    def _check(cls, _readers):
        _assumptions = ("incompatible files! "
                "_readers must have the same number-of-timebins and "
                "the same instrument-type to be collected as a batch")

        assert 1 == len(set(sf.inst_type          for sf in _readers)), _assumptions
        assert 1 == len(set(sf.number_of_timebins for sf in _readers)), _assumptions

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

    def __new__(cls, *args, **kwargs):
        # TODO :: das hier passt mal **ueberhaupt gar nicht** in das "state-machine"-
        ##  schema hinein!! Wie soll man das init-ialisieren, wenn bloss _new_state
        ##  ge-called wird ???!?!?!?!?

        # quick reminder: If __new__() does not return an instance of cls, then the
        # new instance’s __init__() method will *not* be invoked:
        print(*args, **kwargs)

        inst = object.__new__(cls)

        return inst

    def __init__(self, *filenames, _reader=IoniTOFReader):
        if not len(filenames):
            raise ValueError("no filename given")

        self._readers = sorted((_reader(f) for f in filenames), key=attrgetter('time_of_file'))
        self._check(self._readers)

    def read_traces(self, kind='conc', index='abs_cycle', force_original=False):
        """Return the timeseries ("traces") of all masses, compounds and settings.

        'kind' is the type of traces and must be one of 'raw', 'concentration' or
        'corrected'.

        'index' specifies the desired index and must be one of 'abs_cycle', 'rel_cycle',
        'abs_time' or 'rel_time'.

        """
        return pd.concat(sf.read_all(kind, index, force_original) for sf in self._readers)

    def __iter__(self):
        for reader in self._readers:
            for specdata in reader.iter_specdata():
                yield reader.filename, specdata

