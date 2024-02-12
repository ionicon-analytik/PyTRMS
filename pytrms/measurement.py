import os.path
import logging
from abc import abstractmethod
from collections.abc import Iterable

from .reader import H5Reader

log = logging.getLogger()


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
    - ..comprises of one or more consecutive datafiles (i.e. there is no gap in time).
    - ..is in one of three states: Preparing, Running, Finished.
    - ..can be scripted while preparing, but cannot be changed once running (compare this
      to an 'Instrument', which remains in control as long as the connection is upheld).
    - Only one 'Measurement' can run on one 'Instrument' at a time (but several can be
      queued).
    - ..generates a schedule of parameter changes.


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

    >>> m.schedule({'DPS_Udrift': 432}, cycle=0, repeat_every=15, repeat_until=60 [,repeat_for=4])  # example...
    >>> m.generate_schedule()
    <generator>

    >>> list(m.generate_schedule())
    {'cycle': 15, 'updates': {'DPS_Udrift': 432}, 'block': 1}
    {'cycle': 30, 'updates': {'DPS_Udrift': 432}, 'block': 1}
    {'cycle': 45, 'updates': {'DPS_Udrift': 432}, 'block': 1}
    {'cycle': 60, 'updates': {'DPS_Udrift': 432}, 'block': 1}

    # clear schedule(?) makes no sense!

    >>> m.schedule({'DPS_Udrift': 600}, cycle= 0, repeat_every=20)
    >>> m.schedule({'DPS_Udrift': 300}, cycle=10, repeat_every=20, tag='H3O+')
    >>> list(take(4, m.generate_schedule()))
    {'cycle':  0, 'updates': {'DPS_Udrift': 600}, 'block': 1}
    {'cycle': 10, 'updates': {'DPS_Udrift': 300}, 'block': 'H3O+'}
    {'cycle': 20, 'updates': {'DPS_Udrift': 600}, 'block': 1}
    {'cycle': 30, 'updates': {'DPS_Udrift': 300}, 'block': 'H3O+'}
    ...

    [given a schedule like this, the 'Instrument' can already do its thing!]

    >>> m.blocks()
    [<Block 1>, <Block 'H3O+'>]

    # the following has the same effect, but requires less brain damage to grasp:

    >>> block1 = pytrms.tools.Block({'DPS_Udrift': 600}, duration=10, tag=1)
    >>> block2 = pytrms.tools.Block({'DPS_Udrift': 300}, duration=10, tag='H3O+')
    >>> m.schedule(block1)
    >>> m.schedule(block2)  # just override the above definitions

    this restarts the schedule as defined up to this point
    >>> m.repeat_forever()  # no! -> see ptr.run(..) instead
    >>> m.repeat(5)  # no!

    instead:
    >>> for i in range(5):
    >>>     m.schedule(block1)
    >>>     m.schedule(block2)

    [rough idea]
      Blocks will be averaged automatically by "some server". But this is the other
    side of the lawn, the 'E' part, whereas we are at the 'A' part and the 
    'Instrument' connects to the 'M' part. In fact, the 'Instrument' (or whatever
    executor runs in the background) can connect to the 'E' part from here as well!
    That would mean, we could install a callback or a notification or something in
    the future... go full cycle and give feedback to the TPS-parameters!
      All good and well. The 'Measurement' is only a convenience wrapper after all.
    Let's implement the tough part - the 'Instrument' - first and see...

    When the measurement has been prepared, let the measurement run. This will
    block the execution of the script at this point! Internally, the control is
    given to the 'Instrument':

    >>> m.run(m)  # run the Measurement once...
    >>> m.run_forever(m)  # ...or repeat the schedule forever...
    ...
    >>> m  # the Instrument is not Busy, the Measurement is!!
    Running
    >>> m.run_for(seconds=120)  # blocks for two minutes
    >>> m.run_for(cycles=120)  # blocks for 120 cycles
    >>> m.run_for(reps=5)  # blocks for five repetitions
    ...

    # ..  or the measurement was stopped for some reason


    >>> ptr.get_schedule()  # same in green, but read out the instrument buffer

    >>> m.blocks(marker='AddData/PTR_Instrument/DPS_Udrift')  # every set of instrument parameters forms a 'block', until any parameter changes
    <generator>

    >>> m.blocks(marker=pytrms.markers.Periodic(20))
    <generator>

    """

    def is_local(self):
        return os.path.exists(self.filename)

    def __init__(self, filename):
        self.h5 = H5Reader(filename)

    @property
    def filename(self):
        return self.h5.path
    
    @property
    def timezero(self):
        return self.h5.timezero

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
        return self.h5.get_all(kind, index, force_original)

    def __iter__(self):
        return iter(self.h5)

