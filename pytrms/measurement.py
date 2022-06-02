import abc


class Measurement(abc.Iterable):
    """Base class for PTRMS-measurements or batch processing.

    A measurement is iterable over the 'rows' of its data. 
    In the online case, this would slowly produce the current trace, one after another.
    In the offline case, this would quickly iterate over the traces in the given
    measurement file.
    """

    @property
    @abc.abstractmethod
    def timezero(self):
        raise NotImplementedError()

    #@abc.abstractmethod
    def iterwindow(self, width):
        """window function

        give the last n datapoints

        also quickly realized with a deque
        """
        raise NotImplementedError()



class OnlineMeasurement(Measurement):

    def __init__(self, instrument):
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

    def __init__(self, path):
        #self.hf = somereader(path)
        pass

    @property
    def timezero(self):
        return self.datafile.get_timezero()

    def __iter__(self):
        pass

