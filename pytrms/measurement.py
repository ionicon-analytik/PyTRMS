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

    @property
    @abstractmethod
    def traces(self):
        raise NotImplementedError()


class OnlineMeasurement(Measurement):

    # TODO :: ausbauen oder abreissen....
    def __init__(self, instrument):
        super().__init__(filename)
        self.instrument = instrument

    @property
    def timezero(self):
        return 0

    @property
    def traces(self):
        pass

    def __iter__(self):
        while issubclass(self.__class__, RunningMeasurement):
            yield self.instrument.buffer.queue.get()


class OfflineMeasurement(Measurement):

    def __init__(self, h5reader):
        super().__init__(h5reader.path)
        self.hr = h5reader

    @property
    def timezero(self):
        return self.hr.timezero

    @property
    def traces(self):
        """shortcut for `.get_traces(kind='concentration')`."""
        return self.get_traces(kind='concentration')

    def get_traces(self, kind='raw', index='abs_cycle', force_original=False):
        """Return the timeseries ("traces") of all masses, compounds and settings.

        'kind' is the type of traces and must be one of 'raw', 'concentration' or
        'corrected'.

        'index' specifies the desired index and must be one of 'abs_cycle', 'rel_cycle',
        'abs_time' or 'rel_time'.

        If the traces have been post-processed in the Ionicon Viewer, those will be used,
        unless `force_original=True`.
        """
        return self.hr.get_all(kind, index, force_original)

    def __iter__(self):
        return iter(self.hr)

