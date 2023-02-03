"""
_interface
===================================================================

Collection of abstract interfaces with documentation but no implementation.

All datetimes used by the Connector sub-classes shall be simple
UTC-datetimes. Making a case for timezone-unaware (naive) datetime-objects:

1) conversion is really slow:

In [5]: %timeit now = datetime.datetime.now(tz=dateutil.tz.gettz())
96 µs ± 458 ns per loop (mean ± std. dev. of 7 runs, 10000 loops each)
  versus..
In [6]: %timeit datetime.datetime.now()
690 ns ± 12.5 ns per loop (mean ± std. dev. of 7 runs, 1000000 loops each)

2) all timing information in the IoniTOF manager and the .h5-files
   is saved and broadcasted as UTC-timestamp with epoch 1904 (changed
   to POSIX epoch 1970 by the IcAPIAdapter, see `epoch_diff_s` below).

3) changing to another timezone later is actually really easy:
>>> from datetime import datetime
>>> import dateutil
>>> tz = dateutil.tz.gettz('Pacific/Kiritimati')
>>> utc = datetime.utcfromtimestamp(1234567890)
>>> utc
datetime.datetime(2009, 2, 13, 23, 31, 30)
>>> utc.astimezone(tz)
datetime.datetime(2009, 2, 14, 12, 31, 30, tzinfo=tzfile('Pacific/Kiritimati'))

"""
from abc import ABC, abstractmethod
from math import nan
from collections import namedtuple

# difference in days between 1904 and 1970 (<http://www.ni.com/tutorial/7900/en/>):
# 24107 = 365 * 66 + 66 // 4 + 1  (there were 66 // 4 = 16 leapdays + 1904 was a leap-year)
# difference in seconds between 1904 and 1970:
# 24107 * 24 * 60 * 60 = 2082844800
epoch_diff_s = 2082844800

_specdata_template = namedtuple('Spectrum',
                                ('AbsoluteCycle', 'FileCycle', 'DateTime', 'RelTime', 'Data'))
_trace_template = namedtuple('Trace', ('AbsoluteCycle', 'FileCycle', 'Run', 'Step',
                                       'TimeStamp', 'RelTime', 'Data'))
_ptr_status_template = namedtuple('PTRdata', ('key', 'index', 'type',
                                              'set', 'act', 'bool', 'unit', 'time'))

_PTR_reaction_params = {
    'DPS_Us': 'V',
    'DPS_Uso': 'V',
    'DPS_Udrift': 'V',
    'DPS_Udx_Uql': 'V',
    'DPS_Ihc': 'A',
    'DPS_IhcOnOff': 'A',
    'PrimionIdx': '-',
}
_PTR_labels_to_keys = {
    'Us': 'DPS_Us',
    'Us_Act': 'DPS_Us',
    'Uso': 'DPS_Uso',
    'Uso_Act': 'DPS_Uso',
    'Udrift': 'DPS_Udrift',
    'Udrift_Act': 'DPS_Udrift',
    'Udx': 'DPS_Udx_Uql',
    'Udx_Act': 'DPS_Udx_Uql',
    'Ihc': 'DPS_Ihc',
    'Ihc_Act': 'DPS_Ihc',
    'Source On/Off': 'DPS_IhcOnOff',
    'Source On/Off_Act': 'DPS_IhcOnOff',
    'PrimIon': 'PrimionIdx',
    'PrimIon_Act': 'PrimionIdx',
}

__all__ = ['BaseConnector', 'TPSAdapter', 'epoch_diff_s',
           '_PTR_reaction_params', '_PTR_labels_to_keys', '_specdata_template']


class BaseConnector(ABC):
    """The `Connector` is the main entry point to the IConnect module.

    It provides a unfied source for all data, regardless whether it came from
    an online measurement session or from an archived directory on the hard disk.

    It also provides a certain amount of control over the playback of the data,
    which depends on the data source: The playback speed of a hdf5-file can be
    controlled, while setting a new parameter value is only possible in an online
    session.

    """
    _specdata_template = _specdata_template
    _trace_template = _trace_template
    _ptr_status_template = _ptr_status_template

    @abstractmethod
    def play(self, playback_speed=1):
        """Start a measurement or playback.

        If the IoniTOF Manager was not in ActiveMeasurement mode, attempt to start it first.
        """

    @abstractmethod
    def pause(self):
        """Pause the current measurement.

         (Does not effect the IoniTOF Manager.)
         """

    @abstractmethod
    def stop(self):
        """Stop the current measurement and possibly the IoniTOF Manager."""

    @property
    @abstractmethod
    def tof_settings(self):
        """Returns the current TOF settings as dict of (value, unit)-pairs.

        Among these are (guaranteed):

        - timebin_width
        - single_spec_duration
        - max_flight_time
        - start_delay
        - autocal_period
        - poisson_dead_time

        """

    @property
    @abstractmethod
    def ptr_params(self) -> dict:
        """Returns the current PTR parameter settings as dict of (value, unit)-pairs.

        Among these are typically:

        - DPS_Udrift
        - DPS_Ihc
        - PrimionIdx
        - ...

        """

    @property
    @abstractmethod
    def reaction_params(self) -> dict:
        """Returns the current reaction parameters as dict of (value, unit)-pairs.

        This is usually a subset of the `ptr_params`. It is guaranteed to include

        - DPS_Udrift
        - PrimionIdx

        and all other parameters listed in `_interface._PTR_reaction_params`.
        """

    @property
    @abstractmethod
    def tps_voltages(self) -> dict:
        """Returns the current TPS voltages as dict of (value, unit)-pairs.

        Among these are typically:

        - Lens 1
        - Refl. Back
        - MCP F
        - ...

        """

    @property
    @abstractmethod
    def prim_ions(self) -> tuple:
        """Returns a tuple with the primary ion descriptors in their correct indexing order."""

    @property
    @abstractmethod
    def n_timebins(self):
        """Returns the number of timebins in a spectrum."""

    @property
    @abstractmethod
    def specdata(self):
        """Returns the raw mass spectrum of the last measurement or cursor position."""

    @abstractmethod
    def iter_specdata(self, on_mode_mismatch='skip'):
        """Returns an iterator over the specdata, step.

        If the `.pause()` method has been called in the meantime, this iterator
        waits in an infinite loop doing nothing.

        If the `.stop()` method has been called in the meantime, this iterator
        quits (raises StopIteration).

        Keyword arguments:

        - `on_mode_mismatch`:  What to do if the *reaction data* doesn't fit any *Mode*.
          Choices are 'skip' (default) and 'ignore'. The latter uses the last valid *Step*.

        """

    @property
    @abstractmethod
    def state(self):
        """The current state of the iterator is one of 'wait', 'take' or 'idle'."""

    @abstractmethod
    def resume(self):
        """Force the iterator to resume the 'take' state and release the `.wait_lock`."""

    @property
    @abstractmethod
    def traces(self):
        """Returns the traces of the last measurement or cursor position as a 2D np.array.

        The first axis contains raw-, corrected- and concentration traces, respectively
        """

    @property
    @abstractmethod
    def masses(self):
        """Returns the exact masses list that match the current traces."""


class TPSAdapter(ABC):
    """Defines the functionality to read/write TPS parameters (Lens voltages, MCP voltages...).

    """
    rv_dict = {'Lens 1': (nan, 'V'),
               'Lens 2': (nan, 'V'),
               'Lens 3': (nan, 'V'),
               'Lens 4': (nan, 'V'),
               'Lens 5': (nan, 'V'),
               'Lens 6': (nan, 'V'),
               'Lens 7': (nan, 'V'),
               'Push H': (nan, 'V'),
               'Push L': (nan, 'V'),
               'Pull H': (nan, 'V'),
               'Pull L': (nan, 'V'),
               'Grid': (nan, 'V'),
               'Cage': (nan, 'V'),
               'Refl. Grid': (nan, 'V'),
               'Refl. Back': (nan, 'V'),
               'MCP F': (nan, 'V'),
               'MCP B': (nan, 'V'),
               'CurrPush H': (nan, 'V'),
               'CurrPush L': (nan, 'V'),
               'CurrPull H': (nan, 'V'),
               'CurrPull L': (nan, 'V'),
               'CurrGrid': (nan, 'V'),
               'CurrCage': (nan, 'V'),
               'CurrRefl. Grid': (nan, 'V'),
               'CurrRefl. Back': (nan, 'V'),
               'CurrMCP F': (nan, 'V'),
               'CurrMCP B': (nan, 'V'),
               }

    @abstractmethod
    def act_value(self, key):
        """Returns the current value of TPS parameter `key` as a value, unit pair."""
        return

    @abstractmethod
    def act_values(self):
        """Returns a dictionary with TPS parameters as value, unit pairs."""
        return

    @abstractmethod
    def set_value(self, key, value, unit):
        """Set TPS parameter `key` to `value` with `unit`. Every key returned by
        `act_values()` may serve as an input parameter."""
        pass

    @abstractmethod
    def set_values(self, values):
        """Set multiple values at once (convenience wrapper for `set_value()`).
        `values` must be a dictionary with value, unit pairs."""
        pass

