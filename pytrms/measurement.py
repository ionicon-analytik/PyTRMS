"""
@file measurement.py

"""
import time
import logging
from collections import defaultdict
from operator import attrgetter, itemgetter
from abc import abstractmethod, ABC

from .clients import ssevent
from ._base import _IoniConnectBase

log = logging.getLogger(__name__)

__all__ = ['Measurement']


class Measurement(ABC):
    """Class for AME-measurements and batch (post)-processing.

    Synchronizes with the database API to conduct new measurements.

    The following shows some example outputs of attaching to a
    measurement on the database API that we need to connect to:
    >>> api = pytrms.clients.db_api.IoniConnect()           # doctest: +SKIP

    The keyword argument must be one of `id` (defaults to 'last')...
    >>> Measurement(api)                                    # doctest: +SKIP
    <PendingMeasurement ...>
    >>> Measurement(api, id=5)                              # doctest: +SKIP
    <StoppedMeasurement [id=5] @ 'uno'>
    >>> Measurement(api, id='current')                      # doctest: +SKIP
    <RunningMeasurement ...>
    >>> Measurement(api, id='last')                         # doctest: +SKIP
    <StoppedMeasurement ...>

    ...or `recipe` for a new measurement that has not been started:
    >>> Measurement(api, recipe='uno')                      # doctest: +SKIP
    <PendingMeasurement [id=??] @ 'uno'>

    A `PendingMeasurement` has no url and no filenames, because
    it does not yet exist on the API. But it can be started and
    made to change its state in sync with the AME system:
    >>> m = Measurement(api, recipe='my_recipe')            # doctest: +SKIP
    >>> m.start(singleSpecDuration_ms=3000.0)               # doctest: +SKIP
    >>> m                                                   # doctest: +SKIP
    <RunningMeasurement ...>
    >>> m.url                                               # doctest: +SKIP
    /api/measurements/6

    The sourcefiles will be synchronized with the API and be
    made available for batch processing:
    >>> batch = Measurement(api, id='last?stopped=true')    # doctest: +SKIP
    <StoppedMeasurement ...>
    >>> batch.filenames                                     # doctest: +SKIP
    ["D:/AMEData/yesterday/one.h5, ... ]

    """

    # TODO :: 
    # - [x] ich will hier die API ins Zentrum stellen!
    # - [ ] meas hat eine .url, die es identifiziert (s.u.)
    # - [ ] die sourcefiles werden dann von der API geladen (lazy)
    # - [ ]  ... bzw. man kann eine neue batch zusammenstellen und hochladen
    #  
    # - [ ] wir haben diese __iter__ dinger jetzt im peakdame.helpers !
    #  ..aber unten verweist das eh nur auf reader.iter_specdata() UND 
    #    ausserdem ist das nicht aktuell, weil der kein (file, specdata)
    #    iteriert!! 
    #### ~~> besser in eine separate Funktion oder so (um das "austauschbar" zu haben)
    #  
    # - [x] "backend" (ptr) kommt weg! Dafuer kann man ein Instrument hernehmen.
    # - [x] zum "starten" wird hier NUR auf die API geposted und dann auf AME
    #       GEWARTET dass es aktiv wird: { "isRunning": True }

    #  - [x] Der state haengt also ganz klar an der API: 
    #  - [x] es gibt genau 0 oder 1 'current' / RunningMeasurement
    #  - [x] ein PendingMeasurement kann gestartet werden, genau dann
    #        wenn die API es zulaesst (kein anderes running) ~> POST
    #  - [x] ein StoppedMeasurement laedt seine sourcefiles von der API
    #  - [ ] [evtl. auch Funktion, um neue batch zu erstellen, die aber nicht
    #         gestartet wird 

    def _new_state(self, newstate):
        assert issubclass(newstate, Measurement), "invalid call to _new_state"
        # we get ourselves a nifty little state-machine :)
        self.__class__ = newstate

    def __new__(cls, *args, **kwargs):
        # Note (reminder): If __new__() does not return an instance of cls,
        #  then the new instance’s __init__() method will *not* be invoked!
        #  => OK, but we *always* return an `isinstance(.., Measurement)`
        #     so __init__() *will* be invoked: That's why the subclasses
        #     should not define their own, unless the arguments really match!
        if not len(args):
            raise TypeError(f"{cls.__name__} missing 1 required positional argument: 'api'")
        if len(args) > 1:
            raise TypeError(f"{cls.__name__} expected 1 positional argument, got {len(args)}")

        api = args[0]  # fetch it from first argument passed to __init__
        assert isinstance(api, (_IoniConnectBase)) , f"api must implement {type(_IoniConnectBase)}"
        assert api.is_connected, f"no connection to {api}"

        if 'id' in kwargs and 'recipe' in kwargs:
            raise TypeError("keyword arguments 'id' and 'recipe' are mutually exclusive")

        if 'recipe' in kwargs:
            inst = object.__new__(PendingMeasurement)
            inst._id = None
            inst._recipe = str(kwargs['recipe'])

            api.get_location("/api/recipes/" + inst._recipe)  # may throw!

            return inst

        id_passed = kwargs.get('id', "last")

        if cls is not Measurement:
            log.warning(f"direct init of '{cls.__name__}', I hope you know what you're doing!")
            # allow this for debugging, though:
            inst = object.__new__(cls)
            inst._id = id_passed
            return inst

        mep = "/api/measurements/"
        url = str(id_passed) if id_passed.startswith(mep) else mep + str(id_passed)
        url_resolved = api.get_location(url)  # may throw!

        j = api.get(url_resolved)
        if j["startTimestamp_UTC"] is None:
            inst = object.__new__(PendingMeasurement)
            inst._id = j["measurementID"]
            inst._recipe = j["recipeDirectory"]
            return inst

        if j["stopTimestamp_UTC"] is None:
            inst = object.__new__(RunningMeasurement)
            inst._id = j["measurementID"]
            inst._recipe = j["recipeDirectory"]
            return inst

        if True:
            inst = object.__new__(StoppedMeasurement)
            inst._id = j["measurementID"]
            inst._recipe = j["recipeDirectory"]
            return inst

        raise RuntimeError("invalid program: we should never have come here")

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


    _id = None
    _recipe = None
    _known_etags = dict()

    def __init__(self, api, *, id=None, recipe=None):
        self.api = api

    def new_folder(self, suffix=""):
        """Prepare a new results-directory for the AME toolchain.

        This creates a new directory and copies all relevant files from
        the recipe-directory. Also, the peaktable found next to the
        sourcefile will be uploaded to the database.

        A 'new results' event will be emitted on the API.

        Arguments:
        - suffix: a string appended to the folder name

        Returns:
            the full path to the new folder
        """
        st, href = self.api.post(self.url + "/results", data={ }, params={ "suffix": str(suffix) })
        assert st in [201, 204], "unexpected status code: " + st

        fe = defaultdict(list)
        j = self.api.get(self.url)
        files_ep = j["_links"]["describedby"]["href"] + "/files"
        j = self.api.get(files_ep)
        for f in j["_embedded"]["files"]:
            name = f["name"]
            etag = f["etag"]
            if etag == self._known_etags.get(name):
                log.warning("skipping unchanged file: " + name)
            else:
                ext = f["extension"]
                fe[ext].append((name, etag))

        for pt_file, etag in sorted(fe[".ionipt"]):
            log.info("upload peaks...... " + pt_file)
            content = self.api.get(files_ep + "/content", params={ "name": pt_file})
            # TODO ::
            # - api.get doesn't want this (octet-stream)
            # - broken: takes filename!
            r = self.api.sync(content)
            log.info("done sync'ing peaks: " + str(r))
            self._known_etags[pt_file] = etag

        self.api.post("/api/alarms/state", { "enabled": False })
        for alarm_file, etag in sorted(fe[".alm"]):
            log.info("upload alarms..... " + alarm_file)
            content = self.api.get(files_ep + "/content", params={ "name": alarm_file})
            # TODO ::
            # - api.get doesn't want this (octet-stream)
            # - broken: takes filename!
            self.api.upload("/api/alarms/upload", content)
            self._known_etags[alarm_file] = etag

        return self.api.get(href)["path"]

    def __eq__(self, other):
        return isinstance(other, Measurement) and hash(other) == hash(self)

    def __hash__(self):
        return hash(self._recipe + str(self._id)) if self._id else hash(self._recipe)

    def __repr__(self):
        return f"<{type(self).__name__} [id={self._id if self._id else '??'}] @ '{self._recipe}'>"


class PendingMeasurement(Measurement):

    def start(self, *, singleSpecDuration_ms=1000.0):
        """Start a measurement via the AME system.

        The `recipeDirectory` must be the name of a valid (master) recipe,
        which is usually found in `C:/Ionicon/AME/Recipes`.

        Keyword arguments are passed with the payload of the POST request.

        Note: This does *not* start the PTR instrument directly, but instead
         signals AME to start a new measurement out of the given `recipeDirectory`.

        """
        payload = {
            "recipeDirectory": self._recipe,
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

        result_dir = self.new_folder(suffix="")
        log.info(f"created new folder at '{result_dir}'...")
        e = next(event_g)
        assert e.event == "new result", "wrong event, got: " + str(e)

        log.info(f"starting new measurement '{self.url}'...")
        try:
            # ...and the AME system *should* respond with 'start measurement':
            e = next(event_g)
            assert e.event == "start measurement", "wrong event, got: " + str(e)
            assert e.data == self.url, "wrong event-href, got: " + str(e)
        except StopIteration:
            raise TimeoutError("the system didn't respond. make sure AME is running!")

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
        # Note: this will usually only be called by our peakd'AME,
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

        self._new_state(StoppedMeasurement)

        return self


class StoppedMeasurement(Measurement):

    # TODO :: this should just be an interface to sync with the API
    #  all file-processing should happen in a 'batch' that may be
    #  initialized w/o running an API..
    pass

