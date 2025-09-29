"""
@file measurement.py

"""
import time
import json
import logging
from operator import attrgetter, itemgetter
from itertools import chain
from abc import abstractmethod, ABC

from .readers import IoniTOFReader
from .clients import ssevent
from ._base import _IoniClientBase

log = logging.getLogger(__name__)

__all__ = ['Measurement']


class Measurement(ABC):
    """Class for PTRMS-measurements and batch processing.

    Synchronizes with the database API.

    In the online case, this would slowly produce the current trace, one
    after another.
    In the offline case, this would quickly iterate over the traces in the given
    measurement file.

    ???

    # WAS WOLLEN WIR HIER EIGENTLICH??
    # a) diesen praktischen iterator (sourcefile, specdata) erhalten
    # b) start/stop "Protokoll" implementieren (geht schon, s.u.)
    #KANN AUS DB_API.py wieder raus !!
    # c) [future] einen schoenen Zugang zum batch-processing schaffen



        # 4 faelle:
        #  entweder es wird eine URL konkret angegeben:
        #  => dann kennt der user bereits die Messung, sie kann laufen oder nicht
        # oder es wird KEINE Url angegeben,
        # => dann will der user entweder Preparen (noch keine URL) und dann ~> POST
        #    oder er kennt sie noch nicht und will die laufende Messung haben


#       # ~> Was mir *daran* nicht gefaellt ist eben der Error !
#       #  ich will einfach NUR attach'en und dann seh ich ja, was der zustand ist

#       # was WILL man denn? Es gibt doch nur 2 use-cases (weniger als moegliche cases)
#       # a) online: Dann evtl. starten ~~> also NIHCT last, sonder NEU
#       # b) offline/batch processing ~> dann auch NICHT das running/current..
#       # c) neue batch anlegen aus .h5 files
#       # [d) neu starten, aber dann muss man a) auch sehen, was sache ist!]

#       # aber stop ~> wird zum last..
#       # Ja, schon klar, nur will ich ja den JETZT zustand abbilden
#       def attach(api):
#           if api.is_running:
#               loc = api._get_location("/api/measurements/current")
#               return RunningMeasurement(api, loc)
#           else:
#               return PreparingMeasurement(api, '')
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

    def _new_state(self, newstate):
        assert issubclass(newstate, Measurement), "invalid call to _new_state"
        # we get ourselves a nifty little state-machine :)
        self.__class__ = newstate

    def __new__(cls, *args, **kwargs):
        # Note (reminder): If __new__() does not return an instance of cls,
        #  then the new instance’s __init__() method will *not* be invoked!
        #  => OK, but we *always* return an `isinstance(.., Measurement)`
        #     so __init__() will be invoked.
        api = args[0]  # fetch it from first argument passed to __init__
        assert isinstance(api, (_IoniClientBase)), f"api must implement {type(_IoniClientBase)}"
        assert api.is_connected, "no connection to database api"
        assert len({'id', 'url'} & kwargs.keys()) < 2, "kwargs 'id' and 'url' are mutually exclusive"

        fallback = f"/api/measurements/{kwargs['id']}" if 'id' in kwargs else ''
        url_passed = str(kwargs.get('url', fallback))

        if cls is not Measurement:
            log.warning(f"direct init of '{cls.__name__}', I hope you know what you're doing!")
            # allow this for debugging, though:
            inst = object.__new__(cls)
            inst._url = url_passed
            return inst

        if url_passed:
            # id is known ~> do post-processing:
            inst = object.__new__(FinishedMeasurement)
            inst._url = url_passed
            return inst

        if api.is_running:
            # attach!
            inst = object.__new__(RunningMeasurement)
            inst._url = api._get_location("/api/measurements/current")
            return inst

        else:
            # prepare new!
            inst = object.__new__(PreparingMeasurement)
            inst._url = ''
            return inst

        raise RuntimeError("invalid program: we should not have come here")

    @property
    def url(self):
        """The resource locator for this 'Measurement' on the database."""
        return self._url

    @property
    def is_running(self):
        """Returns `True` if this is an instance of a running measurement.

        Note, that it may not reflect the state on the server! See class
        `pytrms.instrument.Instrument` for more direct control.
        """
        return type(self) is RunningMeasurement

    @property
    def info(self):
        j = self.api.get(self.url)
        del j["_links"]
        del j["_embedded"]
        return j

    @property
    def filenames(self):
        j = self.api.get(self.url + "/sourcefiles")
        collection = sorted(j["_embedded"]["sourcefiles"], key=itemgetter("measFilePosition"))
        return [sf["path"] for sf in collection]

    def add_sf(self, filename):
        loc = self.api.post(self.url + "/sourcefiles", payload)
        return loc

    def __init__(self, api, *, url=None, id=None):
        assert self.url is not None, "invalid program: url should have been set in __new__"
        self.api = api

    def __eq__(self, other):
        return isinstance(other, Measurement) and other.url == self.url

    def __hash__(self):
        return hash(self.url)

    def __repr__(self):
        return f"<{type(self)} @ {id(self)}>"


class PreparingMeasurement(Measurement):

    ## TODO :: wer setzt jetzt diese ganzen properties, wenn
    ### wir nur noch die payload POST'en ???
    #
    # da muss "jemand" auf ein 'new measurement' event hoeren..

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

    def start(self, *, recipeDirectory='', singleSpecDuration_ms=1000.0
            # , pulsingPeriod_ns=0.0
            # , startDelay_ns=0.0
            # , timebinWidth_ps=0.0
            # , poissonDeadtime_ns=0.0
            # , numberOfTimebins=0.0
          ):
        """Start a measurement via the AME system.

        This does not start the PTR instrument, but signals AME to start
        a new measurement out of the given `recipeDirectory`.

        Keyword arguments are passed with the payload of the POST request.
        """
        if self.api.is_running:
            # Note: this should only ever happen if a PreparingMeasurement
            #  has been initialized directly (and not via Measurement)!
            current = self.api._get_location('/api/measurements/current')
            raise RuntimeError(f"measurement running at '{current}'")

        payload = {
            "recipeDirectory": str(recipeDirectory),
            "singleSpecDuration_ms": float(singleSpecDuration_ms),
        }
        # first, set us up to check the correct ordering of events:
        sse = ssevent.SSEventListener(session=self.api.session)
        sse.subscribe(r'(new|start|stop) measurement')
        event_g = sse.follow_events(timeout_s=10, prime=True)
        e = next(event_g)  # prime the generator..
        assert e.event == "new connection", "invalid program: generator not primed"
        # now, follow the protocol: this will trigger the event: 'new measurement'...
        self.url = self.api.post('/api/measurements', payload)
        # ...we back-check it...
        e = next(event_g)
        assert e.event == "new measurement", "wrong event, got: " + str(e)
        assert e.data == self.url, "wrong event-href, got: " + str(e)
        log.info(f"starting new measurement '{self.url}'...")
        try:
            # ...and the AME system *should* respond with 'start measurement':
            e = next(event_g)
        except StopIteration:
            raise TimeoutError("the system didn't respond. make sure AME is running!")

        assert e.event == "new measurement", "wrong event, got: " + str(e)
        assert e.data == self.url, "wrong event-href, got: " + str(e)

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
        """Stop the current measurement via the AME system.

        """
        # first, set us up to check the correct ordering of events:
        sse = ssevent.SSEventListener(session=self.api.session)
        sse.subscribe(r'(new|start|stop) measurement')
        event_g = sse.follow_events(timeout_s=10, prime=True)
        e = next(event_g)  # prime the generator..
        assert e.event == "new connection", "invalid program: generator not primed"
        log.info(f"stopping measurement '{self.url}'...")
        # now, follow the protocol: this will trigger the event: 'stop measurement'...
        self.api.put(self.url, { "isRunning": False })
        # ...we back-check it...
        e = next(event_g)
        assert e.event == "stop measurement", "wrong event, got: " + str(e)
        assert e.data == self.url, "wrong event-href, got: " + str(e)

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


class FinishedMeasurement(Measurement):

    @classmethod
    def _check(cls, _readers):
        _assumptions = ("incompatible files! "
                "_readers must have the same number-of-timebins and "
                "the same instrument-type to be collected as a batch")

        assert 1 == len(set(sf.inst_type          for sf in _readers)), _assumptions
        assert 1 == len(set(sf.number_of_timebins for sf in _readers)), _assumptions

    def attach_readers(self, filenames):
        self._readers = sorted((_reader(f) for f in filenames), key=attrgetter('time_of_file'))
        self._check(self._readers)

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

