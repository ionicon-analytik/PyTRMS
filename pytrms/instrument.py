import os.path
import time
from abc import abstractmethod, ABC

from .measurement import *


class Instrument(ABC):
    '''
    Class for controlling the PTR instrument remotely.

    This class reflects the states of the actual instrument, which can be currently idle
    or running a measurement. An idle instrument can start a measurement. A running
    instrument can be stopped. But trying to start a measurement twice will raise an
    exception (RuntimeError).

    Note, that for every client PTR instrument there is only one instance of this class.
    This is to prevent different instances to be in other states than the instrument.
    '''
    __instance = None

    def _new_state(self, newstate):
        # Note: we get ourselves a nifty little state-machine :)
        self.__class__ = newstate

    def __new__(cls, backend):
        # make this class a singleton..
        if cls._Instrument__instance is not None:
            # quick reminder: If __new__() does not return an instance of cls, then the
            # new instance’s __init__() method will *not* be invoked:
            return cls._Instrument__instance

        # ..that is synchronized with the PTR-instrument state:
        if backend.is_running:
            cls = RunningInstrument
        else:
            cls = IdleInstrument

        inst = object.__new__(cls)
        Instrument._Instrument__instance = inst

        return inst

    def __init__(self, backend):
        # dispatch all blocking calls to the client
        self.backend = backend

    @property
    def is_local(self):
        """Returns True if files are written to the local machine."""
        host = str(self.backend.host)
        return 'localhost' in host or '127.0.0.1' in host

    def get(self, varname):
        """Get the current value of a setting."""
        # TODO :: this is not an interface implementation
        raw = self.backend.get(varname)
        if not isinstance(self.backend, MqttClient):
            import json
            jobj = json.loads(raw)

            return jobj[0]['Act']['Real']

        ## how it should be:
        return raw

    def set(self, varname, value, unit='-'):
        """Set a variable to a new value."""
        return self.backend.set(varname, value, unit='-')

    _current_sourcefile = ''

    def start_measurement(self, filename=''):
        # this method must be implemented by each state
        raise RuntimeError("can't start %s" % self.__class__)

    def stop_measurement(self):
        # this method must be implemented by each state
        raise RuntimeError("can't stop %s" % self.__class__)


class IdleInstrument(Instrument):

    def start_measurement(self, filename=''):
        dirname = os.path.dirname(filename)
        if dirname and self.is_local:
            # Note: if we send a filepath to the server that does not exist there, the
            #  server will open a dialog and "hang" (which I'd very much like to avoid).
            #  the safest way is to not send a path at all and start a 'Quick' measurement.
            #  but if the server is the local machine, we do our best to verify the path:
            os.makedirs(dirname, exist_ok=True)

        if filename:
            basename = os.path.basename(filename)
            # this may very well be a directory to record a filename into:
            if not basename:
                basename = '%Y-%m-%d_%H-%M-%S.h5'
                filename = os.path.join(dirname, basename)
            # finally, pass everything through strftime...
            filename = time.strftime(filename)
            if os.path.exists(filename):
                raise RuntimeError(f'filename exists and cannot be overwritten')

        self.backend.start_measurement(filename)
        self._current_sourcefile = filename
        self._new_state(RunningInstrument)

        return RunningMeasurement(self)


class RunningInstrument(Instrument):

    def stop_measurement(self):
        self.backend.stop_measurement()
        self._new_state(IdleInstrument)

        # TODO :: this catches only one sourcefile.. it'll do for simple cases:
        return FinishedMeasurement(_current_sourcefile)

