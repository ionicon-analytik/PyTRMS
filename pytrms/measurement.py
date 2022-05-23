import os.path
import time
import datetime as dt

import h5py


class Measurement:
    '''
    Base class for PTRMS measurements or batch processing.

    A Measurement has one unique filename. 

    A Measurement can be preparing, running or finished.

    A prepared Measurement can be started.
    A running Measurement can be stopped.
    A finished Measurement cannot be started again.

    CAUTION: Attaching to an already running measurement is not
    explicitly supported and may cause errors or weird behaviour.
    Automation using scripts should therefore not be mixed with
    other means of experiment control.
    '''
    time_format = "%Y-%m-%d_%H-%M-%S"
    prefix = ''

    _lock = object()

    def _new_state(self, newstate):
        if issubclass(newstate, RunningMeasurement):
            if isinstance(Measurement._lock, Measurement):
                raise RuntimeError(f'running measurement locked by {Measurement._lock}')
            Measurement._lock = self
        if issubclass(self.__class__, RunningMeasurement):
            Measurement._lock = object()  # clear lock
        self.__class__ = newstate

    def __init__(self, path, client=None):
        if client is None and os.path.isfile(path):
            self._new_state(FinishedMeasurement)
        elif client is not None:
            # TODO :: this is a bit weary if a measurement is already running. in that
            # case we would have to attach to the current measurement and override the
            # path. however, there is no means of testing this without making a
            # web-request in the constructor! instead, we never attach to a running
            # measurement. people should not mix scripting and device operation.
            self._new_state(PrepareMeasurement)
        else:
            raise Exception('no client and path does not exist')

        if not len(path):
            path = os.getcwd()
        home = os.path.dirname(path)
        os.makedirs(home, exist_ok=True)
        self.path = os.path.abspath(path)
        self.client = client

    def wait(self, seconds, reason=''):
        if reason:
            print(reason)
        time.sleep(seconds)

    @property
    def is_running(self):
        raise NotImplementedError()

    @property
    def timezero(self):
        raise NotImplementedError()

    @property
    def datafile(self):
        raise NotImplementedError()

    def start(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def set(self, varname, value):
        raise NotImplementedError()

    def find(self, needle):
        raise NotImplementedError()

    def iterrows(self):
        raise NotImplementedError()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, tb):
        self.stop()


class PrepareMeasurement(Measurement):

    @property
    def is_running(self):
        return False

    @property
    def timezero(self):
        return dt.datetime(dt.MAXYEAR, 1, 1)  # some day, but definitely in the future

    @property
    def datafile(self):
        raise RuntimeError('no datafile has been written')

    def start(self):
        self._timestamp = time.localtime()
        if os.path.isdir(self.path):
            basename = time.strftime(Measurement.time_format, self._timestamp)
            basename = Measurement.prefix + basename + '.h5'
            self.path = os.path.join(self.path, basename)

        if os.path.exists(self.path):
            raise RuntimeError(f'{self.path} exists and cannot be overwritten')

        self.client.start_measurement(self.path)
        print(f'started measurement in {self.path}')
        self._new_state(RunningMeasurement)

    def stop(self):
        raise RuntimeError('measurement has not been started')

    def set(self, varname, value):
        self.client.set(varname, value)

    def find(self, needle):
        raise RuntimeError('measurement has not been started')

    def iterrows(self):
        raise RuntimeError('measurement has not been started')


class RunningMeasurement(Measurement):

    @property
    def is_running(self):
        return False

    @property
    def timezero(self):
        return dt.fromtimestamp(self._timestamp)

    @property
    def datafile(self):
        raise RuntimeError('cannot access datafile of a running measurement')

    def start(self):
        raise RuntimeError('measurement has already started')

    def stop(self):
        self.client.stop_measurement()
        print(f'stopped measurement at {time.localtime()}')
        self._new_state(FinishedMeasurement)

    def set(self, varname, value):
        self.client.set(varname, value)

    def find(self, needle):
        self.client.get_traces()

    def iterrows(self):
        return PollingIterator(self.client)


class FinishedMeasurement(Measurement):

    @property
    def is_running(self):
        return False

    @property
    def timezero(self):
        return self.datafile.get_timezero()

    @property
    def datafile(self):
        return h5py.File(self.path, 'r')

    def start(self):
        raise RuntimeError('measurement has finished and cannot be restarted')

    def stop(self):
        raise RuntimeError('measurement has already been stopped')

    def set(self, varname, value):
        raise RuntimeError('measurement has already been stopped')

    def find(self, needle):
        self.client.get_traces()

    def iterrows(self):
        return PollingIterator(self.client)


class PollingIterator:  # TODO :: in etwa so, nur anders

    def __init__(self, client):
        self.client = client

    def __iter__(self):
        return self

    def __next__(self):
        if not False: #self.client.measuring:
            raise StopIteration

        time.sleep(1)
        return self.client

