import os.path
from abc import abstractmethod
from collections.abc import Iterable


class Measurement(Iterable):
    """Base class for PTRMS-measurements or batch processing.

    ---------- OLD ideas ------------

    Every instance is associated with exactly one `.filename` to a datafile.
    The start time of the measurement is given by `.timezero`.

    A measurement is iterable over the 'rows' of its data. 
    In the online case, this would slowly produce the current trace, one after another.
    In the offline case, this would quickly iterate over the traces in the given
    measurement file.

    ---------- NEW ideas ------------

    A 'Measurement'...
    - comprises of one or more consecutive datafiles (i.e. there is no gap in time).
    - is in one of three states: Preparing, Running, Finished.
    - can be scripted while preparing, but cannot be changed once running (compare this
      to an 'Instrument', which remains in control as long as the connection is upheld).
    - only one 'Measurement' can run on one 'Instrument' at a time (but several can be
      queued).


    >>> ptr = connect('localhost')
    >>> m = Measurement(ptr)  # no!
    >>> m = Measurement()

    >>> m.run(ptr)  # ?
    >>> ptr.run(m)  # !

    >>> ptr.run_repeated(m, 5)
    >>> ptr.run([m, m2, meas, Measurement()])
    >>> ptr.run()
    >>> ptr.run_quick()


    >>> m.datafiles
    []

    >>> m.current_file  # not accessible...
    >>> ptr.current_file
    None

    >>> m.wait()  # doesn't make sense
    AttributeError

    >>> ptr.wait_until(cycle=123)  # blocks until cycle 123 comes along (raise if that's not going to happen)
    ...
    >>> ptr.wait_for(cycles=123)  # blocks for 123 cycles...
    ...

    >>> m.schedule({'DPS_Udrift': 432}, cycle=15, repeat_every=15, repeat_until=60 [,repeat_for=4])
    >>> m.generate_schedule()
    <generator>

    >>> list(m.generate_schedule())
    {'cycle': 15, 'updates': {'DPS_Udrift': 432}}
    {'cycle': 30, 'updates': {'DPS_Udrift': 432}}
    {'cycle': 45, 'updates': {'DPS_Udrift': 432}}
    {'cycle': 60, 'updates': {'DPS_Udrift': 432}}

    When the measurement has been prepared, let the measurement run. This will
    block the execution of the script at this point! Internally, the control is
    given to the 'Instrument':

    >>> m.run_forever()  # call this only when the measurement has been prepared
    ...
    >>> m.run()  # this implies that the Measurement is predefined
    >>> m  # the Instrument is not Busy, the Measurement is!!
    Running
    >>> m.run_for(seconds=120)  # blocks for two minutes!
    ...

    # ..  or the measurementwas stopped for some reason


    >>> ptr.get_schedule()  # same in green, but read out the instrument buffer

    >>> m.blocks(marker='AddData/PTR_Instrument/DPS_Udrift')  # every set of instrument parameters forms a 'block', until any parameter changes
    <generator>

    >>> m.blocks(marker=pytrms.markers.Periodic(20))
    <generator>

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

