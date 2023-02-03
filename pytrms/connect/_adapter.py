"""Module icapiadapter.py.

"""
import struct
import re
import time
import logging
from collections import namedtuple

import numpy as np

# noinspection PyUnresolvedReferences
import icapi

from ._base import epoch_diff_s

log = logging.getLogger(__name__)

__all__ = ['IcAPIAdapter']


class IcAPIError(Exception):
    pass


def call(cmd, *args):
    """wrap any call to icapi with separate logging and Exception handling."""
    log.debug('calling icapi.%s()...' % cmd)
    f = getattr(icapi, cmd)
    try:
        return f(*args)
    except Exception as exc:
        raise IcAPIError(exc)


class IcAPIAdapter:
    """Adapts the Python wrapper of the IcAPI to be even more intuitive to use.

    Serves as a provider for the 'IoniTOF' class.
    """
    _measure_state_to_enum = dict(icapi.measure_state)
    _server_state_to_enum = dict(icapi.server_state)
    _server_action_to_enum = dict(icapi.server_actions)
    _enum_to_measure_state = dict((enum, name) for name, enum in icapi.measure_state)
    _enum_to_server_state = dict((enum, name) for name, enum in icapi.server_state)
    _enum_to_server_action = dict((enum, name) for name, enum in icapi.server_actions)

    _ptr_params_template = namedtuple('PTR_Data', ('key', 'index', 'label', 'setv', 'actv',
                                                   'nil', 'unit', 'ts'))

    def __init__(self, ip='127.0.0.1', timeout_s=5):
        if not re.match(r'[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+', ip):
            raise ValueError("Invalid IP adress: %s" % ip)

        self.ip = ip
        success = self.reconnect(timeout_s)
        if not success:
            raise IOError("Could not connect to ip %s!" % self.ip)

    def reconnect(self, timeout_s=5):
        log.debug('checking connection...')
        if call('CheckConnection'):
            return True

        log.info("Connecting to %s..." % self.ip)
        call('connect', self.ip)
        tries = 0
        dt = 1
        while tries * dt < timeout_s:
            if call('CheckConnection'):
                return True

            tries += 1
            time.sleep(dt)
            log.info("Checking connection after (%d) tries..." % tries)

        raise Exception("Unable to connect to %s! Timed out after (%d) seconds." % (self.ip, timeout_s))

    @staticmethod
    def get_status():
        """Return the MeasureState, ServerState, ServerAction as a tuple of strings."""
        ms = IcAPIAdapter._enum_to_measure_state[call('GetMeasureState')]
        ss = IcAPIAdapter._enum_to_server_state[call('GetServerState')]
        sa = IcAPIAdapter._enum_to_server_action[call('GetServerAction')]

        return ms, ss, sa

    @staticmethod
    def get_timebins():
        """Read out number of timebins."""
        timebins, *more = call('GetArrayLength')

        return timebins

    @staticmethod
    def get_current_spectrum():
        """Read current spectrum, unpack and convert timestamp to POSIX."""
        acycle, fcycle, ts, data = call('GetCurrentSpectrum')
        # unpack the time information stored as 4 float values:
        at, rt = struct.unpack('>dd', struct.pack('>ffff', *tuple(ts)))
        # convert to POSIX timestamp:
        at -= epoch_diff_s

        return acycle, fcycle, at, rt, data

    @staticmethod
    def get_trace_data():
        """Read current traces, unpack and convert timestamp to POSIX."""
        acycle, fcycle, ts, data = call('GetTraceData')
        # unpack the time information stored as 4 float values:
        at, rt = struct.unpack('>dd', struct.pack('>ffff', *tuple(ts)))
        # convert to POSIX timestamp:
        at -= epoch_diff_s

        return acycle, fcycle, at, rt, data

    @staticmethod
    def get_masses():
        """Return the correct masses as np.array rounded to 4 decimal places."""
        # Note, that there are two flavours, the other being
        # 'GetCurrentMasses()'. I don't know the difference...
        return np.around(call('GetTraceMasses'), decimals=4)

    @staticmethod
    def parse_ptr_params():
        """Return a list of namedtuples with the complete PTR Data."""
        return [IcAPIAdapter._ptr_params_template._make(param) for param in
                call('read_PTR_data')]

    @staticmethod
    def parse_reaction_params():
        """Return a list of namedtuples with the essential Reaction Data."""
        # first 7 entries contain (among others) DPS_Udrift and PrimionIdx:
        return [IcAPIAdapter._ptr_params_template._make(param) for param in
                call('read_PTR_data')[:7]]

    @staticmethod
    def start(timeout_s=5):
        """Attempt to start a measurement and return only if MeasureState was set or timed out."""
        active = IcAPIAdapter._measure_state_to_enum['MeasurementActive']
        tried = 0
        dt = 0.1
        call('start')
        while tried > timeout_s:
            if call('GetMeasureState') == active:
                return IcAPIAdapter._enum_to_measure_state[active]
            tried += dt
            time.sleep(dt)
            log.debug("Starting IcAPI (tries=%d)..." % int(tried / dt))

        raise Exception("Start measurement request timed out after (%d) seconds!" % timeout_s)

    @staticmethod
    def stop(timeout_s=5):
        """Attempt to stop a measurement and return only if MeasureState was set or timed out."""
        active = IcAPIAdapter._measure_state_to_enum['MeasurementActive']
        tried = 0
        dt = 0.1
        call('stop')
        while tried > timeout_s:
            if not call('GetMeasureState') == active:
                return IcAPIAdapter._enum_to_measure_state[call('GetMeasureState')]
            tried += dt
            time.sleep(dt)
            log.debug("Stopping IcAPI (tries=%d)..." % int(tried / dt))

        raise Exception("Stop measurement request timed out after (%d) seconds!" % timeout_s)
