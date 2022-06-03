import os.path
from abc import abstractmethod
from collections.abc import Iterable


class Measurement(Iterable):
    """Base class for PTRMS-measurements or batch processing.

    Every instance is associated with exactly one `.filename` to a datafile.
    The start time of the measurement is given by `.timezero`.

    A measurement is iterable over the 'rows' of its data. 
    In the online case, this would slowly produce the current trace, one after another.
    In the offline case, this would quickly iterate over the traces in the given
    measurement file.
    """

    def is_local(self):
        return os.path.exists(self.filename)

    def __init__(self, filename):
        self._filename = filename

    @property
    def filename(self):
        return self._filename
    
    @property
    @abstractmethod
    def timezero(self):
        raise NotImplementedError()


class OnlineMeasurement(Measurement):

    def __init__(self, instrument):
        super().__init__(filename)
        self.instrument = instrument

    @property
    def timezero(self):
        return dt.fromtimestamp(self._timestamp)


    def __iter__(self):
        buf = TraceBuffer(self.client)
        buf.start()
        try:
            while issubclass(self.__class__, RunningMeasurement):
                yield buf.queue.get()

        finally:
            buf.stop_producing()
            buf.join()


class OfflineMeasurement(Measurement):

    def __init__(self, h5reader):
        super().__init__(h5reader.path)
        self.hr = h5reader

    @property
    def timezero(self):
        return self.hr.timezero

    def __iter__(self):
        return iter(self.hr)

