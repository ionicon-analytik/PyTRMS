import time
import os.path
#import ntpath
#import datetime as dt


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
        if buffer.is_idle:
            Instrument._new_state(inst, IdleInstrument)
        else:
            Instrument._new_state(inst, RunningInstrument)

        return inst

    def __init__(self, client, buffer):
        # dispatch all blocking calls to the client
        # and fetch current data from the buffer!
        self._client = client
        self._buffer = buffer

    prefix = ''

    @property
    def time_format(self):
        """Set the time format for the filename of quick measurements.

        Use placeholders according to 
        """
        return self._time_format

    _time_format = "%Y-%m-%d_%H-%M-%S"
    time_format.__doc__ += time.strftime.__doc__

    def is_local(self):
        """Returns True if files are written to the local machine."""
        host = self._client.host
        return host == 'localhost' or host == '127.0.0.1'

    def wait(self, seconds, reason=''):
        if reason:
            print(reason)
        time.sleep(seconds)

    def get(self, varname):
        return self._client.get(varname)

    get.__doc__ = IoniClient.get.__doc__

    def set(self, varname, value):
        return self._client.set(varname, value)

    def __enter__(self):
        # TODO :: implement proper context with dict of settings...
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, tb):
        self.stop()

    def start(self):
        # this method must be implemented by each state
        raise NotImplementedError()

    def stop(self):
        # this method must be implemented by each state
        raise NotImplementedError()


class IdleInstrument(Instrument):

    def start(self):
        # _client.is_local ??  --> Pfade setzen..

        # TODO :: das funzt natuerlich nicht, wenn man an den server connected...
        
        # if not len(path):
        #     path = os.getcwd()
        # home = os.path.dirname(path)
        # os.makedirs(home, exist_ok=True)
        #self.path = ntpath.normpath(path)
        self._timestamp = time.localtime()
        #if os.path.isdir(self.path):
        #    basename = time.strftime(instrument.time_format, self._timestamp)
        #    basename = instrument.prefix + basename + '.h5'
        #    self.path = os.path.join(self.path, basename)

        #if os.path.exists(self.path):
        #    raise RuntimeError(f'{self.path} exists and cannot be overwritten')

        self._new_state(BusyInstrument)
        self._client.start_measurement()#self.path)
        self.start()

    def stop(self):
        raise RuntimeError('instrument is not running')


class RunningInstrument(Instrument):

    def start(self):
        raise RuntimeError('instrument is already running')

    def stop(self):
        self._new_state(BusyInstrument)
        self._client.stop_measurement()
        self.stop()


class BusyInstrument(Instrument):

    def start(self):
        while self._buffer.is_idle:
            time.sleep(0.01)
        self._new_state(RunningInstrument)

    def stop(self):
        while not self._buffer.is_idle:
            time.sleep(0.01)
        self._new_state(IdleInstrument)

