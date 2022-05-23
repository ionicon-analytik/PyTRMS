import os.path
import time


class Measurement:
    '''
    Base class for PTRMS measurements or batch processing.

    A Measurement has one unique filename. 

    A Measurement can be preparing, running or finished.

    A prepared Measurement can be started.
    A running Measurement can be stopped.
    A finished Measurement cannot be started again.

    Subclasses of `Process` must implement the `__iter__()` function to guarantee
    the common behaviour for online and offline processing with one or multiple
    datafiles.

    mm = Measurement()
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


class PrepareMeasurement(Measurement):

    @property
    def is_running(self):
        return False

    def start(self):
        if os.path.isdir(self.path):
            basename = time.strftime(Measurement.time_format, time.localtime())
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

