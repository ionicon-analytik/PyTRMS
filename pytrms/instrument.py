"""
@file instrument.py

"""
import os.path
import time
import logging
from abc import abstractmethod, ABC

from ._base import _IoniClientBase

log = logging.getLogger(__name__)

__all__ = ['Instrument']


class Instrument(ABC):
    """
    Class for controlling the PTR instrument remotely.

    You should be using the `pytrms.connect()` function, instead of
    instantiating this class directly!

    This is a convenience wrapper around a low-level backend, which
    can be one of MQTT, Modbus or the legacy HTTP-API for IoniTOF 4.2.

    """

    def _new_state(self, newstate):
        # Note: we get ourselves a nifty little state-machine :)
        self.__class__ = newstate

    def __new__(cls, *args, **kwargs):
        # Note (reminder): If __new__() does not return an instance of cls,
        #  then the new instance’s __init__() method will *not* be invoked!

        backend = args[0]  # fetch it from first argument (passed to __init__)
        assert isinstance(backend, (_IoniClientBase)), f"backend must implement {type(_IoniClientBase)}"

        if backend.is_running:
            inst = object.__new__(_RunningInstrument)
        else:
            inst = object.__new__(_IdleInstrument)

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

    def set(self, varname, value):
        """Set a variable to a new value."""
        # TODO :: this is not an interface implementation...
      # return self.backend.set(varname, value, unit='-')
        return self.backend.write(varname, value)

#   def start_measurement(self, filename=''):
#       # this method must be implemented by each state
#       raise RuntimeError("can't start <%s>" % type(self).__name__)

#   def stop_measurement(self):
#       """Stop a running measurement."""
#       # this method must be implemented by each state
#       raise RuntimeError("can't stop <%s>" % type(self).__name__)


class _IdleInstrument(Instrument):

    def start_measurement(self, filename=''):
        """Start a new measurement.

        'filename' is the filename of the datafile to write to. If left blank, start
        a "quick measurement", for which IoniTOF writes to its default folder.

        If pointing to a file and the file exist on the (local) server, this raises
        an exception! To create unique filenames, use placeholders for year (%Y),
        month (%m), and so on, for example `filename=D:/Sauerteig_%Y-%m-%d_%H-%M-%S.h5`.
        The `filename` is passed through `strftime` with the current date and time.

        """
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

    # (appendix to docstring)
    start_measurement.__doc__ += "\nsee also:\n" + time.strftime.__doc__

    def __iter__(self):
        log.warning("waiting for instrument to be started externally")
        while not self.backend.is_running:
            time.sleep(50e-3)

        self._new_state(_RunningInstrument)
        yield from iter(self)


class _RunningInstrument(Instrument):

    def stop_measurement(self):
        """Stop a running measurement."""
        self.backend.stop_measurement()
        self._new_state(_IdleInstrument)

    def __iter__(self):
        if not self.backend.is_connected:
            raise Exception("no connection to instrument")

        timeout_s = 15
        ssd_s = 1e-3 * float(self.get('ACQ_SRV_SpecTime_ms'))
        last_rel_cycle = -1
        sourcefile = ''
        for specdata in self.backend.iter_specdata(timeout_s=timeout_s+ssd_s, buffer_size=300):
            if last_rel_cycle == -1 or specdata.timecycle.rel_cycle < last_rel_cycle:
                # the source-file has been switched, so wait for the new path:
                started_at = time.monotonic()
                while time.monotonic() < started_at + timeout_s:
                    candidate = self.backend.current_sourcefile
                    if candidate and candidate != sourcefile:
                        sourcefile = candidate
                        break

                    time.sleep(10e-3)
                else:
                    raise TimeoutError(f"no new sourcefile after ({timeout_s = })")
            last_rel_cycle = specdata.timecycle.rel_cycle

            yield sourcefile, specdata

        # normal exit:
        self._new_state(_IdleInstrument)

