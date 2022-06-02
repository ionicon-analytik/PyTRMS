import os.path
import ntpath
import time
import datetime as dt

import h5py

#from .tracebuffer import TraceBuffer


class Instrument:
    '''
    Base class for PTRMS instruments or batch processing.

    A Instrument has one unique filename. 

    A Instrument can be preparing, running or finished.

    A prepared Instrument can be started.
    A running Instrument can be stopped.
    A finished Instrument cannot be started again.

    CAUTION: Attaching to an already running instrument is not
    explicitly supported and may cause errors or weird behaviour.
    Automation using scripts should therefore not be mixed with
    other means of experiment control.
    '''
    time_format = "%Y-%m-%d_%H-%M-%S"
    prefix = ''

    __instance = None

    def _new_state(self, newstate):
        self.__class__ = newstate
        print(self)

    def __new__(cls, client):
        # make this class a singleton
        if cls._Instrument__instance is not None:
            # If __new__() does not return an instance of cls, then the new instance’s
            # __init__() method will not be invoked:
            #return cls._Instrument__instance  # TODO :: to raise or not to raise..?
            raise Exception('the Instrument class can only have one instance')

        inst = object.__new__(cls)
        cls._Instrument__instance = inst

        return inst

    def __init__(self, client):
        print('run init')
        self.client = client

        # TODO :: das funzt natuerlich nicht, wenn man an den server connected...
        
        # if not len(path):
        #     path = os.getcwd()
        # home = os.path.dirname(path)
        # os.makedirs(home, exist_ok=True)
        #self.path = ntpath.normpath(path)

    @property
    def is_remote(self):
        host = self.client.host
        return host == 'localhost' or host == '127.0.0.1'

    def wait(self, seconds, reason=''):
        if reason:
            print(reason)
        time.sleep(seconds)

    def set(self, varname, value):
        self.client.set(varname, value)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, tb):
        self.stop()

    def start(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()


class IdleInstrument(Instrument):

    def start(self):
        self._timestamp = time.localtime()
        if os.path.isdir(self.path):
            basename = time.strftime(instrument.time_format, self._timestamp)
            basename = instrument.prefix + basename + '.h5'
            self.path = os.path.join(self.path, basename)

        if os.path.exists(self.path):
            raise RuntimeError(f'{self.path} exists and cannot be overwritten')

        self._new_state(BusyInstrument)
        print(f'started instrument in {self.path}')
        self.client.start_measurement(self.path)
        self._new_state(RunningInstrument)

    def stop(self):
        raise RuntimeError('instrument is not running')


class RunningInstrument(Instrument):

    def start(self):
        raise RuntimeError('instrument is already running')

    def stop(self):
        self._new_state(BusyInstrument)
        self.client.stop_measurement()
        self._new_state(IdleInstrument)


class BusyInstrument(Instrument):

    def start(self):
        raise RuntimeError('instrument is busy')

    def stop(self):
        raise RuntimeError('instrument is busy')

