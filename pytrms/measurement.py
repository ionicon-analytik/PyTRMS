"""
@file measurement.py

"""
import time
import logging
from operator import attrgetter
from itertools import chain
from abc import abstractmethod, ABC

from .readers import IoniTOFReader
from .clients import ssevent

log = logging.getLogger(__name__)

__all__ = ['Measurement',
           #'PreparingMeasurement', 'RunningMeasurement', 'FinishedMeasurement']
]


class Measurement(ABC):
    """Class for PTRMS-measurements and batch processing.

    Synchronizes with the database API.

    In the online case, this would slowly produce the current trace, one
    after another.
    In the offline case, this would quickly iterate over the traces in the given
    measurement file.


    """

    # TODO :: ich will hier die API ins Zentrum stellen!
    #  meas hat eine .url, die es identifiziert (s.u.)
    #  die sourcefiles werden dann von der API geladen
    ##  ... bzw. man kann eine neue batch zusammenstellen und hochladen
    #  
    #  wir haben diese __iter__ dinger jetzt im peakdame.helpers !
    #  ..aber unten verweist das eh nur auf reader.iter_specdata() UND 
    #    ausserdem ist das nicht aktuell, weil der kein (file, specdata)
    #    iteriert!! 
    #### ~~> besser in eine separate Funktion oder so (um das "austauschbar" zu haben)
    #  
    #  "backend" (ptr) kommt weg! Dafuer kann man ein Instrument hernehmen.
    #  zum "starten" wird hier NUR auf die API geposted und dann auf AME
    #  GEWARTET dass es aktiv wird: { "isRunning": True }

    #  Der state haengt also ganz klar an der API: 
    #  - es gibt genau 0 oder 1 'current' / RunningMeasurement
    #  - ein PreparingMeasurement kann gestartet werden, genau dann
    #    wenn die API es zulaesst (kein anderes running) ~> POST
    #  - ein FinishedMeasurement laedt seine sourcefiles von der API
    #  - [evtl. auch Funktion, um neue batch zu erstellen, die aber nicht
    #     gestartet wird 
    #         TODOO :: kann die API fordern, dass nur Measurement ohne
    #     #             /sourcefiles gestartet werden koennen)

    # WAS WOLLEN WIR HIER EIGENTLICH??
    # a) diesen praktischen iterator (sourcefile, specdata) erhalten
    # b) start/stop "Protokoll" implementieren (geht schon, s.u.) KANN AUS DB_API.py wieder raus !!
    # c) [future] einen schoenen Zugang zum batch-processing schaffen

    def _new_state(self, newstate):
        # Note: we get ourselves a nifty little state-machine :)
        self.__class__ = newstate

    def __init__(self, instrument, api):
        self.ptr = instrument
        self.api = api

        assert self.ptr.backend.is_connected, "no connection to instrument"
        assert self.api.is_connected, "no connection to database api"

        self.url = ''

    def __eq__(self, other):
        return isinstance(other, Measurement) and other.url == self.url

    def __hash__(self):
        return hash(self.url)


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

    def start(self,
              # timezoneOffset_sec=0,
              # startDateTime=None,
              # stopDateTime=None,
                recipeDirectory='',
                pulsingPeriod_ns=0.0,
                startDelay_ns=0.0,
                singleSpecDuration_ms=1000.0,
                timebinWidth_ps=0.0,
              # poissonDeadtime_ns=0.0,
              # numberOfTimebins=0.0}
          ):
        """Start a measurement on the PTR server.

        """
        #self.ptr.start_measurement(filename)
        #if self.api is not None:
        import requests
        try:
            loc = self.api._get_location('/api/measurements/current')
            assert not len(loc), "measurement running at " + str(loc)
        except requests.exceptions.HTTPError as exc:
            if exc.response and exc.response.status_code == 410:
                pass  # Gone!



        payload = {
            "recipeDirectory": str(recipeDirectory),
            "singleSpecDuration_ms": float(singleSpecDuration_ms),
        }
        sse = ssevent.SSEventListener(session=self.api.session)
        sse.subscribe(r'(new|start) measurement')
        event_g = sse.follow_events(timeout_s=10, prime=True)
        e = next(event_g)
        assert e.event == "new connection", "invalid program: generator not primed"
        # Note: this will trigger the event: 'new measurement'...
        self.url = self.api.post('/api/measurements', payload)
        try:
            e = next(event_g)
            assert e.event == "new measurement", str(e)
            loc = e.data
            print('----', loc)
            log.info(f"waiting for measurement @ {self.url} to be started...")
            # ...and the AME system *should* respond with 'start measurement':
            next(event_g)
        except StopIteration:
            raise TimeoutError("the system didn't respond. make sure AME is running!")

        self._new_state(RunningMeasurement)

        return self

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

    def stop(self):
        """Stop the current measurement on the PTR server."""
        self.ptr.stop_measurement()
        if self.api is not None:
            if self.url is None:
                self.url = self.api.get('/api/measurements/current')
            self.api.put(self.url, { "isRunning": False })

        self._new_state(FinishedMeasurement)

        return self

    def __iter__(self):
        from .clients.mqtt import MqttClient
        if not isinstance(self.ptr.backend, MqttClient):
            raise NotImplementedError("iteration only provided w/ backend 'mqtt'")

        if not self.ptr.backend.is_connected:
            raise Exception("no connection to instrument")

        timeout_s = 15
        ssd_s = 1e-3 * float(self.ptr.get('ACQ_SRV_SpecTime_ms'))
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
        import pandas as pd

        return pd.concat(sf.read_all(kind, index, force_original) for sf in self._readers)

    get_traces = read_traces
    get_traces.__doc__ = read_traces.__doc__ + "\nAlias: 'get_traces'."

    def __iter__(self):
        for reader in self._readers:
            for specdata in reader.iter_specdata():
                yield reader.filename, specdata

