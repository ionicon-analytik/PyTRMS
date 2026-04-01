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

# EDIT -------------------------------------------- EDIT
#
# neue IDee: wir haben IMMER eine Url (und ein Ioniconnect)
#
# ~> dies IST der db-synchronisator
# => 
#
#
# EDIT -------------------------------------------- EDIT

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
    #  die sourcefiles werden dann von der API geladen (lazy)
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
        if not len(args):
            raise TypeError(f"{cls.__name__} missing 1 required positional argument: 'api'")
        if len(args) > 1:
            raise TypeError(f"{cls.__name__} expected 1 positional argument, got {len(args)}")

        api = args[0]  # fetch it from first argument passed to __init__
        assert isinstance(api, (_IoniClientBase)) , f"api must implement {type(_IoniClientBase)}"
        assert api.is_connected, f"no connection to {api}"

        id_passed = kwargs.get('id')  # keyword only arg!

        if id_passed is None:
            cls = PreparingMeasurement

        if cls is PreparingMeasurement:
            inst = object.__new__(cls)
            inst._id = None
            return inst

        if cls is not Measurement:
            log.warning(f"direct init of '{cls.__name__}', I hope you know what you're doing!")
            # allow this for debugging, though:
            inst = object.__new__(cls)
            inst._id = id_passed
            return inst

        url_resolved = api.get_location("/api/measurements/" + str(id_passed))  # may throw!

        j = api.get(url_resolved)
        if j["startDateTime"] is None:
            inst = object.__new__(PreparingMeasurement)
            inst._id = j["measurementID"]
            return inst

        if j["stopDateTime"] is None:
            inst = object.__new__(RunningMeasurement)
            inst._id = j["measurementID"]
            return inst

        if True:
            inst = object.__new__(FinishedMeasurement)
            inst._id = j["measurementID"]
            return inst

        raise RuntimeError("invalid program: we should not have come here")

    @property
    def id(self):
        """The unique id for this 'Measurement' on the database."""
        return self._id

    @property
    def url(self):
        """The resource locator for this 'Measurement' on the database."""
        if self._id:
            return "/api/measurements/" + str(self._id)
        return None

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
        if not self.url:
            # while preparing, no sourcefiles can yet have been created:
            return []

        # Note: no caching (yet), because it's rather fast enough..
        j = self.api.get(self.url + "/sourcefiles")
        sf_by_pos = sorted(j["_embedded"]["sourcefiles"], key=itemgetter("measFilePosition"))

        return [sf["path"] for sf in sf_by_pos]

    @property
    def peaktable(self):
        """The peaktable in use by this measurement.

        Note, that the peaktable need not be strictly the same throughout
        a running measurement, because AME allows for the possibility to
        add peaks on-the-fly.

        """

        #        pt = PeakTable.from_file(pt_file)
        # (siehe unten...)
        # Idee ist, dass dies dem .follow_specdata() noch abgenommen wird,
        # was die sache vereinfacht...
        return None


    def __init__(self, api, *, id="last"):
        self.api = api

    def __eq__(self, other):
        return isinstance(other, Measurement) and other._id == self._id

    def __hash__(self):
        return hash(self.url)  # self._id would work, but it's boring (1-based)

    def __repr__(self):
        return f"<{type(self).__name__} @ {self.url}>"


class PreparingMeasurement(Measurement):
    """

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

    """

    def __init__(self, api):
        self.api = api

    def start(self, recipeDirectory, *
              , singleSpecDuration_ms=1000.0
            # , pulsingPeriod_ns=0.0
            # , startDelay_ns=0.0
            # , timebinWidth_ps=0.0
            # , poissonDeadtime_ns=0.0
            # , numberOfTimebins=0.0
              # TODO :: ~> inst_info oder @property info oder so (kann auch api noch anpassen..)
              #  was ist hier ueberhaupt relevant? timebinWidth_ps schon, aber nur read-only ?!
          ):
        """Start a measurement via the AME system.

        Note: This does *not* start the PTR instrument directly, but instead
         signals AME to start a new measurement out of the given `recipeDirectory`.

        Keyword arguments are passed with the payload of the POST request.
        """
        payload = {
            "recipeDirectory": str(recipeDirectory),
            "singleSpecDuration_ms": float(singleSpecDuration_ms),
        }
        # first, set us up to check the correct ordering of events:
        sse = ssevent.SSEventListener(host_url=self.api.url, session=self.api.session)
        sse.subscribe(r'(new|start|stop) measurement')
        event_g = sse.follow_events(timeout_s=10, prime=True)
        e = next(event_g)  # prime the generator..
        assert e.event == "new connection", "invalid program: generator not primed"
        # now, follow the protocol: this will trigger the event: 'new measurement'...
        sc, loc = self.api.post("/api/measurements", payload)
        assert sc == 201, f"unexpected http-status: {sc}"
        self._id = int(loc.split('/')[-1])
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

        assert e.event == "start measurement", "wrong event, got: " + str(e)
        assert e.data == self.url, "wrong event-href, got: " + str(e)

        self._new_state(RunningMeasurement)

        return self


class RunningMeasurement(Measurement):

    def add_sourcefile(self, filename, abs_time=0, abs_cycle=0):
        """Add a sourcefile (.h5 file) to this Measurement's batch.

        The sourcefile will be made persistent in the database.
        If the given filename is already in the batch, this is a no-op
        (in other words, this method is idempotent).

        This may lead to a new peaktable being used if the given filename
        happens to be in a new folder. This will be reflected in the
        `.peaktable` property of this instance.

        Keyword arguments abs_time/abs_cycle are as read from
        `specdata.timecycle` (note, that this might be not correct if
        attaching to running measurement).

        """
        # Note: this will usually only be called by our peakd'ame,
        #  who's following along the IoniTOF's current sourcefile.

        if filename in self.filenames:
            return

        #log.info(("initializing" if last_sourcefile is None else "switching") + " source-file...")
        sc, loc = self.api.post(self.url + "/sourcefiles", data={
            "path": filename,
            "startAbsTime":  abs_time,
            "startAbsCycle": abs_cycle,
        })
        #log.info(f"created 'new sourcefile' ({sourcefile}): {sf_loc}")
        return loc

        # ~~~~~~~~~~~~~~ siehe dieses Monster aus pd~follow_specdata():
        # 1) POST /api/measurements/X/sourcefiles ...
        if sourcefile != last_sourcefile:
            # the source-file has been switched, so wait for the new path:

        # [...]

        # TODO :: damit man DAS testen kann, brauch die API ein result-dir
        #  ~> im test eine mock-pt dort upload'en, dann hier zuruecklsesn:

            if use_local_pt_file:
                log.info(f"loading peaktable from 'recipe-dir'...")
                import platform
                if platform.system() == 'Linux':
                    # Note: this allows us to have a 'D:/AMEData/..' directory placed
                    #  in the current folder (which would otherwise be unaccessible):
                    #
# HACK! weg damit! wir haben inzwischen bessere moeglichkeiten
                    log.warning("looking for relative sourcefile path...")
                    current_recipe = os.path.dirname(sourcefile.replace('\\', os.path.sep))
                else:
                    current_recipe = os.path.dirname(sourcefile)
                pt_file = next_best_file(current_recipe)
                if pt_file is None:
                    raise Exception(f"no peaktable-file found in '{current_recipe}'")

                pt = PeakTable.from_file(pt_file)
                log.debug(f'  |__ success: {pt}')
        last_sourcefile = sourcefile
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def new_folder(self):
        """Prepare a new results-directory for the AME toolchain.

        This creates a new directory and copies all relevant files from
        the recipe-directory. Also, the peaktable found next to the
        sourcefile will be uploaded to the database.

        Returns:
            the filename to be used by IoniTOF
        """
        # Note: this will be called either by the Componist before
        #  starting the measurement or by any action-script with a
        #  'new-folder-action' type.

        #?? A 'new results' event will be emitted on the API.

    #ef maybe_create_folder(action_number, action_cycle):
    # (aus dem actionsetup.py)
    # das gehoert wirklich hierher:
    # action:
    #  m = Measurement(current)  ~> MUSS es geben
    #  m.new_folder()

        if not do_create_folder:
            log.debug("create-folder-action: not requested! skipping...")
            return
    
        if not action_cycle > 0:
            log.warning(f"create-folder-action refused ({action_cycle = })! skipping...")
            return
    
        ## BINGO! das sind wir!!
        j = api.get("/api/measurements/last")
        ## BINGO!! ham wa auch:
        source_recipe_dir  = j["recipeDirectory"]
        ## BINGO!!! das kommt uns auch bekannt vor:
        from pytrms.helpers import setup_measurement_dir
        recipe = setup_measurement_dir(source_recipe_dir, data_root_dir='D:/AMEData',
                suffix=f'_Action{action_number}', date_fmt="%Y_%m_%d__%H_%M_%S")
        log.info("setup new folder.. " + str(recipe.dirname))
        if recipe.pt_file:
            log.info("upload peaks...... " + recipe.pt_file)
            r = api.sync(recipe.pt_file)
            log.info("done sync'ing peaks: " + str(r))
        api.post("/api/alarms/state", { "enabled": False })
        for alarm_file in recipe.alarm_files:
            log.info("upload alarms..... " + alarm_file)
            api.upload("/api/alarms/upload", alarm_file)
        # Note [#3010]: for some reason, IoniTOF will start a new file *after the next*
        #  scheduled cycle, but anyway: we now schedule it 1 cycle prior, such that the
        #  new file is aligned with the AME-numbers:
        ionitof.schedule_filename(recipe.h5_file, action_cycle - 1)
        # nicht BINGO?! Genau hier ^^^^ setzt der Componist (a.k.a. "das AME system") ein!!
        #post(new results) ~> event ~> ? ~> Componist??
        # BZW.. das action-script hat's ja ge-called, also soll's doch scheduln.

    def stop(self):
        """Stop the current measurement via the AME system.

        """
        # first, set us up to check the correct ordering of events:
        sse = ssevent.SSEventListener(host_url=self.api.url, session=self.api.session)
        sse.subscribe(r'(new|start|stop) measurement')
        event_g = sse.follow_events(timeout_s=10, prime=True)
        e = next(event_g)  # prime the generator..
        assert e.event == "new connection", "invalid program: generator not primed"
        log.info(f"stopping measurement '{self.url}'...")
        # now, follow the protocol: this will trigger the event: 'stop measurement'...
        self.api.patch(self.url, { "isRunning": False })
        # ...we back-check it...
        e = next(event_g)
        assert e.event == "stop measurement", "wrong event, got: " + str(e)
        assert e.data == self.url, "wrong event-href, got: " + str(e)

        self._new_state(FinishedMeasurement)

        return self


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

