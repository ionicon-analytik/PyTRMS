import time
import os.path


class Instrument:
    '''
    Class for controlling the PTR instrument remotely.

    This class reflects the states of the actual instrument, which can be currently idle
    or running a measurement. An idle instrument can start a measurement. A running
    instrument can be stopped. But trying to start a measurement twice will raise an
    exception (RuntimeError).

    This is a singleton class, i.e. it is only instanciated once per script.
    '''

    __instance = None

    def _new_state(self, newstate):
        self.__class__ = newstate
        print(self)

    def __new__(cls, client, buffer):
        # make this class a singleton
        if cls._Instrument__instance is not None:
            # quick reminder: If __new__() does not return an instance of cls, then the
            # new instance’s __init__() method will *not* be invoked:
            return cls._Instrument__instance
            #raise Exception('the Instrument class can only have one instance')

        inst = object.__new__(cls)
        cls._Instrument__instance = inst

        # launch the buffer's thread..
        if not buffer.is_alive():
            buffer.daemon = True
            buffer.start()
        # ..and synchronize the PTR-instrument state with this Python object:
        Instrument._new_state(inst, BusyInstrument)
        try:
            buffer.wait_for_connection(timeout=3)  # may raise PTRConnectionError!
        except:
            cls._Instrument__instance = None
            raise

        if buffer.is_idle():
            Instrument._new_state(inst, IdleInstrument)
        else:
            Instrument._new_state(inst, RunningInstrument)

        return inst

    def __init__(self, client, buffer):
        # dispatch all blocking calls to the client
        # and fetch current data from the buffer!
        self._client = client
        self._buffer = buffer

    def is_local(self):
        """Returns True if files are written to the local machine."""
        host = self._client.host
        return host == 'localhost' or host == '127.0.0.1'

    def wait(self, seconds, reason=''):
        if reason:
            print(reason)
        time.sleep(seconds)

    def get(self, varname):
        """Get the current value of a setting."""
        return self._client.get(varname)

    def set(self, varname, value):
        """Set a variable to a new value."""
        return self._client.set(varname, value)

    def __enter__(self):
        # TODO :: implement proper context with dict of settings...
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, tb):
        self.stop()

    def start(self, path=''):
        """Start a measurement on the PTR server.

        'path' is the filename of the datafile to write to. 
        If left blank, start a "quick measurement".

        If pointing to a file and the file exist on the (local) server, this raises an exception.
        To create unique filenames, use placeholders for year (%Y), month (%m), and so on,
        for example `path=C:/Ionicon/Data/Sauerteig_%Y-%m-%d_%H-%M-%S.h5`.

        see also:
        """
        # this method must be implemented by each state
        raise NotImplementedError()

    start.__doc__ += time.strftime.__doc__

    def stop(self):
        """Stop the current measurement on the PTR server."""
        # this method must be implemented by each state
        raise NotImplementedError()

    def get_traces(self, kind='raw', index='abs_cycle'):
        """Return the timeseries ("traces") of all masses, compounds and settings.

        This will grow with time if a measurement is currently running and stop growing
        once the measurement has been stopped. The tracedata is cleared, when a new
        measurement is started.

        'kind' is the type of traces and must be one of 'raw', 'concentration' or 'corrected'.

        'index' specifies the desired index and must be one of 'abs_cycle', 'rel_cycle',
        'abs_time' or 'rel_time'.
        """
        # TODO :: this method must be implemented by each state
        raise NotImplementedError()

    def follow(self, kind='raw'):
        """Returns an iterator over the timeseries ("traces") of all masses, compounds and settings.

        'kind' is the type of traces and must be one of 'raw', 'concentration' or 'corrected'.
        """
        # TODO :: this method must be implemented by each state
        raise NotImplementedError()


class IdleInstrument(Instrument):

    def start(self, path=''):
        # if we send a filepath to the server that does not exist there, the server will
        # open a dialog and "hang" (which I'd very much like to avoid).
        # the safest way is to not send a path at all and start a 'Quick' measurement.
        # but if the server is the local machine, we do our best to verify the path:
        if path and self.is_local():
            home = os.path.dirname(path)
            os.makedirs(home, exist_ok=True)
            base = os.path.basename(path)
            if not base:
                base = '%Y-%m-%d_%H-%M-%S.h5'
            base = time.strftime(base)
            path = os.path.join(home, base)
            if os.path.exists(path):
                raise RuntimeError(f'path exists and cannot be overwritten')

        self._new_state(BusyInstrument)
        self._client.start_measurement(path)
        self.start(path)

    def stop(self):
        raise RuntimeError('instrument is not running')


class RunningInstrument(Instrument):

    def start(self, path=''):
        raise RuntimeError('instrument is already running')

    def stop(self):
        self._new_state(BusyInstrument)
        self._client.stop_measurement()
        self.stop()


class BusyInstrument(Instrument):

    def start(self, path=''):
        while self._buffer.is_idle:
            time.sleep(0.01)
        self._new_state(RunningInstrument)

    def stop(self):
        while not self._buffer.is_idle:
            time.sleep(0.01)
        self._new_state(IdleInstrument)

