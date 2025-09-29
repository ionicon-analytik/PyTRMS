"""
@file instrument.py

"""
import os.path
import time
from abc import abstractmethod, ABC

from ._base import _IoniClientBase

__all__ = ['Instrument']


class Instrument(ABC):
    '''
    Class for controlling the PTR instrument remotely.

    This class reflects the states of the actual instrument, which can be currently
    either idle or running. A idle instrument can start a measurement. A running
    instrument can be stopped.

    The `Instrument` class wraps a `backend`. For testing purposes, we use a mock:
    >>> from pytrms.clients import dummy
    >>> backend = dummy.IoniDummy()

    Note, that for every client PTR instrument there is only one instance of this class
     (this is to prevent different instances to be in other states than the instrument).

    >>> ptr = Instrument(backend)
    >>> ptr
    <_IdleInstrument [<IoniDummy @ 127.0.0.1[:1234]>]>

    >>> id(ptr) == id(Instrument(dummy.IoniDummy()))  # singleton ID is always the same
    True

    Trying to start an instrument twice will raise a RuntimeError!

    >>> ptr.start_measurement(filename='foo %y %M')
    >>> ptr.is_running
    True

    >>> ptr.start_measurement()
    Traceback (most recent call last):
        ...
    RuntimeError: can't start <_RunningInstrument>

    '''
    __instance = None

    def _new_state(self, newstate):
        # Note: we get ourselves a nifty little state-machine :)
        self.__class__ = newstate

    def __new__(cls, *args, **kwargs):
        # Note (reminder): If __new__() does not return an instance of cls,
        #  then the new instance’s __init__() method will *not* be invoked!
        #
        # This aside, we override the __new__ method to make this class a
        #  singleton that reflects the PTR-instrument state and dispatches
        #  to one of its subclass implementations.
        if cls._Instrument__instance is not None:
            return cls._Instrument__instance

        backend = args[0]  # fetch it from first argument (passed to __init__)
        assert isinstance(backend, (_IoniClientBase)), f"backend must implement {type(_IoniClientBase)}"

        if backend.is_running:
            inst = object.__new__(_RunningInstrument)
        else:
            inst = object.__new__(_IdleInstrument)

        Instrument._Instrument__instance = inst

        return inst

    @property
    def is_running(self):
        return type(self) is _RunningInstrument

    @property
    def is_local(self):
        """Returns True if files are written to the local machine."""
        host = str(self.backend.host)
        return 'localhost' in host or '127.0.0.1' in host

    def __init__(self, backend):
        # Note: this will be called *once* per Python process! see __new__() method.
        self.backend = backend

    def __repr__(self):
        return f'<{self.__class__.__name__} [{self.backend}]>'

    def get(self, varname):
        """Get the current value of a setting."""
        # TODO :: this is not an interface implementation...
        raw = self.backend.get(varname)

        from .clients.mqtt import MqttClient
        if not isinstance(self.backend, MqttClient):
            import json
            jobj = json.loads(raw)

            return jobj[0]['Act']['Real']

        ## ...how it should be: just:
        return raw

    def set(self, varname, value, unit='-'):
        """Set a variable to a new value."""
        return self.backend.set(varname, value, unit='-')

    def start_measurement(self, filename=''):
        """Start a new measurement.

        'filename' is the filename of the datafile to write to. If left blank, start
        a "quick measurement", for which IoniTOF writes to its default folder.

        If pointing to a file and the file exist on the (local) server, this raises
        an exception! To create unique filenames, use placeholders for year (%Y),
        month (%m), and so on, for example `filename=D:/Sauerteig_%Y-%m-%d_%H-%M-%S.h5`.
        The `filename` is passed through `strftime` with the current date and time.

        see also:
        """
        # this method must be implemented by each state
        raise RuntimeError("can't start <%s>" % type(self).__name__)

    # (see also: this docstring)
    start_measurement.__doc__ += time.strftime.__doc__

    def stop_measurement(self):
        """Stop a running measurement."""
        # this method must be implemented by each state
        raise RuntimeError("can't stop <%s>" % type(self).__name__)


class _IdleInstrument(Instrument):

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
        self._new_state(_RunningInstrument)


class _RunningInstrument(Instrument):

    def stop_measurement(self):
        self.backend.stop_measurement()
        self._new_state(_IdleInstrument)

