"""Module modbus.py

"""
import os
import struct
import time
import logging
from collections import namedtuple
from functools import lru_cache, partial
from itertools import tee

import pyModbusTCP.client

from . import _par_id_file
from .._base import _IoniClientBase

log = logging.getLogger(__name__)

__all__ = ['IoniconModbus']


def _patch_is_open():
    # Note: the .is_open and .timeout attributes were changed
    #  from a function to a property!
    # 
    # 0.2.0 2022-06-05
    # 
    #  - ModbusClient: parameters are now properties instead of methods (more intuitive).
    # 
    # from the [changelog](https://github.com/sourceperl/pyModbusTCP/blob/master/CHANGES):
    major, minor, patch = pyModbusTCP.__version__.split('.')
    if int(minor) < 2:
        return lambda mc: mc.is_open()
    else:
        return lambda mc: bool(mc.is_open)

_is_open = _patch_is_open()

with open(_par_id_file) as f:
    it = iter(f)
    assert next(it).startswith('ID\tName'), ("Modbus parameter file is corrupt: "
            + f.name
            + "\n\ntry re-installing the PyTRMS python package to fix it!")
    _id_to_descr = {int(id_): name for id_, name, *_ in (line.strip().split('\t') for line in it)}

# look-up-table for c_structs (see docstring of struct-module for more info).
# Note: almost *all* parameters used by IoniTOF (esp. AME) are 'float', with
#  some exceptions that are 'short' (alive_counter, n_parameters) or explicitly
#  marked to be 'int' (AME_RunNumber, et.c.):
_fmts = dict([
    ('float',   '>f'),
    ('double',  '>d'),
    ('short',   '>h'),
    ('int',     '>i'),
    ('long',    '>q'),
])

_register = namedtuple('register_info', ['n_registers', 'c_format', 'reg_format'])
_timecycle = namedtuple('timecycle_info', ('rel_cycle', 'abs_cycle', 'abs_time', 'rel_time'))
_parameter = namedtuple('parameter_info', ('set', 'act', 'par_id', 'state'))


def _get_fmt(c_format):
    if c_format in _fmts:
        c_format = _fmts[c_format]

    n_registers = max(struct.calcsize(c_format) // 2, 1)
    reg_format = '>' + 'H' * n_registers

    return _register(n_registers, c_format, reg_format)


def _unpack(registers, format='>f'):
    """Convert a list of register values to a numeric Python value.

    Depending on 'c_type', the value is packed into two or four
    8-bit registers, for 2-byte (single) and 4-byte (double)
    representation, respectively.

    >>> _unpack([17448, 0], 'float')
    672.0

    >>> _unpack([17446, 32768], 'float')
    666.0
    
    >>> _unpack([16875, 61191, 54426, 37896], 'double')
    3749199524.83057
    
    >>> _unpack([16875, 61191, 54426, 37896], 'long')
    4750153048903029768
    
    """
    n, c_format, reg_format = _get_fmt(format)
    assert n == len(registers), f"c_format '{c_format}' needs [{n}] registers (got [{len(registers)}])"

    return struct.unpack(c_format, struct.pack(reg_format, *registers))[0]

def _pack(value, format='>f'):
    """Convert floating point 'value' to registers.

    Depending on 'c_type', the value is packed into two or four
    8-bit registers, for 2-byte (single) and 4-byte (double)
    representation, respectively.
    """
    _, c_format, reg_format = _get_fmt(format)

    return struct.unpack(reg_format, struct.pack(c_format, value))

_fast  = 0      # MPV direction enum
_DO_ON = 0x3F80 # digital output magick number


class IoniconModbus(_IoniClientBase):

    address = dict([
        ('server_state',     (    0, '>f', False)),  # 0: Not ready, 1: Ready, 2: Startup
        ('measure_state',    (    2, '>f', False)),  # 0: Not running | 1: running | 2: Just Started | 3: Just Stopped
        ('instrument_state', (    4, '>f', False)),  # 0: Not Ok, 1: Ok, 2: Error, 3: Warning
        ('alive_counter',    (    6, '>H', False)),  # (updated every 500 ms)
        ('n_parameters',     ( 2000, '>H', False)),
        ('tc_raw',           ( 4000, '>f', False)),
        ('tc_conc',          ( 6000, '>f', False)),
        ('n_masses',         ( 8000, '>f', False)),
        # ('n_corr',         ( 7000, '>i', False)),  # not implemented?
        ('tc_components',    (10000, '>f', False)),
        ('ame_alarms',       (12000, '>f', False)),
        ('user_number',      (13900, '>i', False)),
        ('step_number',      (13902, '>i', False)),
        ('run_number',       (13904, '>i', False)),
        ('use_mean',         (13906, '>i', False)),
        ('action_number',    (13912, '>i', False)),
        ('version_major',    (13918, '>h', False)),
        ('version_minor',    (13919, '>h', False)),
        ('version_patch',    (13920, '>h', False)),
        ('ame_state',        (13914, '>i', False)),  # Running 0=Off; 1=On (not implemented!)
        ('n_components',     (14000, '>f', False)),
        ('component_names',  (14002, '>f', False)),
        ('ame_mean_data',    (26000, '>f', False)),
        ('n_ame_mean',       (26002, '>d', False)),
    ])

    _lookup_offset = dict([
        # parID  offset     name in Modbus manual   special procedure
        ( 42,   (3 *  0,    'FC H2O',           partial(_pack, format='>f')         )),
        (  1,   (3 *  1,    'PC',               partial(_pack, format='>f')         )),
        (  2,   (3 *  2,    'FC inlet',         partial(_pack, format='>f')         )),
        (  3,   (3 *  3,    'FC O2',            partial(_pack, format='>f')         )),
        (  4,   (3 *  4,    'FC NO',            partial(_pack, format='>f')         )),
        (  5,   (3 *  5,    'FC Dilution',      partial(_pack, format='>f')         )),
        (  6,   (3 *  6,    'FC Krypton',       partial(_pack, format='>f')         )),
        (  7,   (3 *  7,    'FC Xenon',         partial(_pack, format='>f')         )),
        (  8,   (3 *  8,    'FC Purge',         partial(_pack, format='>f')         )),
        (  9,   (3 *  9,    'FC FastGC',        partial(_pack, format='>f')         )),
        ( 10,   (3 * 10,    'FC Custom 1',      partial(_pack, format='>f')         )),
        ( 11,   (3 * 11,    'FC Custom 2',      partial(_pack, format='>f')         )),
        ( 12,   (3 * 12,    'FC Custom 3',      partial(_pack, format='>f')         )),
        ( 13,   (3 * 13,    'FC Custom 4',      partial(_pack, format='>f')         )),
        ( 14,   (3 * 14,    'FC Custom 5',      partial(_pack, format='>f')         )),
        ( 15,   (3 * 15,    'FC Custom 6',      partial(_pack, format='>f')         )),
        ( 16,   (3 * 16,    'FC Custom 7',      partial(_pack, format='>f')         )),
        ( 17,   (3 * 17,    'FC Custom 8',      partial(_pack, format='>f')         )),
        ( 18,   (3 * 18,    'FC Custom 9',      partial(_pack, format='>f')         )),
        (556,   (3 * 19,    'Measure Start',    partial(_pack, format='>f')         )),
        (559,   (3 * 20,    'Measure Stop',     partial(_pack, format='>f')         )),
        ( 70,   (3 * 21,    'Set MPV1',         lambda v: [_fast, *_pack(v, '>h')]  )),
        ( 71,   (3 * 22,    'Set MPV2',         lambda v: [_fast, *_pack(v, '>h')]  )),
        ( 72,   (3 * 23,    'Set MPV3',         lambda v: [_fast, *_pack(v, '>h')]  )),
        (138,   (3 * 24,    'DO 1',             lambda v: [_DO_ON if v else 0x0, 0] )),
        (139,   (3 * 25,    'DO 2',             lambda v: [_DO_ON if v else 0x0, 0] )),
    ])

    @classmethod
    def use_holding_registers(klaas, use_holding=True):
        """Use Modbus HOLDING- instead of INPUT-registers (default: INPUT, compatible with AME1 and AME2)."""
        modded = dict()
        for key, vals in klaas.address.items():
            modded[key] = vals[0], vals[1], use_holding
        klaas.address.update(modded)

    @property
    def _alive_counter(self):
        return self._read_reg(*self.address['alive_counter'])

    @property
    def is_connected(self):
        if not _is_open(self.mc):
            return False

        try:
            # wait for the IoniTOF alive-counter to change (1 second max)...
            initial_count = self._alive_counter
            timeout_s = 3  # counter should increase every 500 ms, approximately
            started_at = time.monotonic()
            while time.monotonic() < started_at + timeout_s:
                if initial_count != self._alive_counter:
                    return True

                time.sleep(10e-3)
            return False
        except IOError:
            # bug-fix: failing to read _alive_counter closed the connection,
            #  even after checking .is_open! Don't let this property throw:
            return False

    @property
    def is_running(self):
        return 1.0 == self._read_reg(*self.address['measure_state'])

    @property
    def error_state(self):
        value = self._read_reg(*self.address['instrument_state'])
        return IoniconModbus._instrument_states.get(value, value)

    _instrument_states = {
            0.0: "Not Okay",
            1.0: "Okay",
            2.0: "Error",
            3.0: "Warning",
    }

    @property
    def server_state(self):
        value = self._read_reg(*self.address['server_state'])
        return IoniconModbus._server_states.get(value, value)

    _server_states = {
            0.0: "Not Ready",
            1.0: "Ready",
            2.0: "Startup",
    }

    def __init__(self, host='localhost', port=502):
        super().__init__(host, port)
        # Note: we patch the behaviour such, that it behaves like pre-0.2
        #  (from the time of development of this module), BUT we skip the
        #  auto_close-feature for the sake of speed:
        # 
        # 0.2.0 2022-06-05
        # 
        #  - ModbusClient: now TCP auto open mode is active by default (auto_open=True, auto_close=False).
        #
        # from the [changelog](https://github.com/sourceperl/pyModbusTCP/blob/master/CHANGES)
        self.mc = pyModbusTCP.client.ModbusClient(host=self.host, port=self.port,
                auto_open = False, auto_close = False
        )
        # try connect immediately:
        try:
            self.connect()
        except TimeoutError as exc:
            log.warning(f"{exc} (retry connecting when the Instrument is set up)")
        self._addresses = {}

    def connect(self, timeout_s=10):
        log.info(f"[{self}] connecting to Modbus server...")
        # Note: .timeout-attribute changed to a property with 0.2.0 (see comments above)
        if callable(self.mc.timeout):
            self.mc.timeout(timeout_s)
        else:
            self.mc.timeout = timeout_s
        if not (_is_open(self.mc) or self.mc.open()):
            raise TimeoutError(f"[{self}] no connection to modbus socket")

        started_at = time.monotonic()
        while time.monotonic() < started_at + timeout_s:
            if self.is_connected:
                break

            time.sleep(10e-3)
        else:
            self.disconnect()
            raise TimeoutError(f"[{self}] no connection to IoniTOF");

    def disconnect(self):
        if _is_open(self.mc):
            self.mc.close()

    def start_measurement(self, path=None):
        '''Start a new measurement and block until the change is confirmed.

        'path' is ignored!
        '''
        if path is not None:
            log.warning(f'ignoring .h5-filepath in Modbus command and starting quick measurement')

        # Note: let's assume one of them will be right and calling it twice don't hurt:
        self.write_instrument_data('ACQ_SRV_Start_Meas_Quick', 1, oldschool=False, timeout_s=10)
        self.write_instrument_data('ACQ_SRV_Start_Meas_Quick', 1, oldschool=True)

        timeout_s = 10
        started_at = time.monotonic()
        while time.monotonic() < started_at + timeout_s:
            if self.is_running:
                break

            time.sleep(10e-3)
        else:
            raise TimeoutError(f"[{self}] unable to start measurement after { timeout_s = }");

    def stop_measurement(self, future_cycle=None):
        '''Stop the current measurement and block until the change is confirmed.

        'future_cycle' is ignored!
        '''
        if future_cycle is not None:
            log.info(f'block until {future_cycle = } (current_cycle = {self.read_timecycle().abs_cycle})')
            while self.read_timecycle().abs_cycle < int(future_cycle):
                time.sleep(200e-3)

        # Note: let's assume one of them will be right and calling it twice don't hurt:
        self.write_instrument_data('ACQ_SRV_Stop_Meas', 1, oldschool=False, timeout_s=10)
        self.write_instrument_data('ACQ_SRV_Stop_Meas', 1, oldschool=True)

        timeout_s = 10
        started_at = time.monotonic()
        while time.monotonic() < started_at + timeout_s:
            if not self.is_running:
                break

            time.sleep(10e-3)
        else:
            raise TimeoutError(f"[{self}] unable to stop measurement after { timeout_s = }");

    @property
    @lru_cache
    def n_parameters(self):
        return int(self._read_reg(*self.address['n_parameters']))

    @property
    @lru_cache
    def n_masses(self):
        return int(self._read_reg(*self.address['n_masses']))

    @property
    @lru_cache
    def n_components(self):
        return int(self._read_reg(*self.address['n_components']))

    def read_parameter(self, par_name):
        """Read any previously loaded parameter by name.

        For example, after calling `.read_components()`, one can call
        `.read_parameter('DPS_Udrift')` to get only this value with no overhead.
        """
        try:
            return self._read_reg(*self.address[par_name])
        except KeyError as exc:
            raise KeyError("did you call one of .read_instrument_data(), .read_traces(), et.c. first?")

    def read_instrument_data(self):

        # Each block consists of 6 registers:
        # Register 1: Parameter ID
        # Register 2-3: Parameter Set Value as float(real)
        # Register 4-5: Parameter Act Value as float(real)
        # Register 6: Parameter state
        start_register = 2001
        blocksize = 6
        superblocksize = 20*blocksize

        rv = dict()
        # read 20 parameters at once to save transmission..
        for superblock in range(0, blocksize*self.n_parameters, superblocksize):
            offset = start_register + superblock
            # always using input_register
            input_regs = self.mc.read_input_registers(offset, superblocksize)
            # ..and handle one block per parameter:
            for block in range(0, superblocksize, blocksize):
                par_id, set1, set2, act1, act2, state = input_regs[block:block+6]
                par_id = _unpack([par_id], '>H')
                if len(rv) >= self.n_parameters or par_id == 0:
                    break

                try:
                    descr = _id_to_descr[par_id]
                except KeyError as exc:
                    log.error("par Id %d not in par_ID_list!" % (par_id))
                    continue

                # save the *act-value* in the address-space for faster lookup:
                self.address[descr] = (start_register + superblock + block + 1 + 2, '>f')
                vset = _unpack([set1, set2], '>f')
                vact = _unpack([act1, act2], '>f')
                rv[descr] = _parameter(vset, vact, par_id, state)

        return rv

    def write_instrument_data(self, par_id, new_value, oldschool=False, timeout_s=10):
        '''Send a write command via the Modbus protocol.

        See the Modbus manual for implementation details.

        'par_id' - (int or string) the parameter-ID or -descriptor from the parID-list
        'new_value' - the value to write (will be converted to float32)
        'oldschool' - use the legacy Modbus write procedure (Register 40000)
        'timeout_s' - timeout in seconds
        '''
        if isinstance(par_id, str):
            try:
                par_id = next(k for k, v in _id_to_descr.items() if v == par_id)
            except StopIteration as exc:
                raise KeyError(str(par_id))
        par_id = int(par_id)
        if par_id not in _id_to_descr:
            raise IndexError(str(par_id))

        # Each command-block consists of 3 registers:
        #  Register 1: Parameter ID (newschool) / execute bit (oldschool)
        #  Register 2-3: Parameter Set Value as float(real)
        # Note: The newschool command-structure is written as an array:
        #   Register 0: number of command-blocks to write
        #  This coincides with the oldschool protocol, where
        #   Register 0: ready to write (execute bit) ~> 1
        #  We use only the first command-block for writing...
        n_blocks = 1
        assert (n_blocks == 1 or not oldschool), "oldschool instrument protocol doesn't allow multiple writes"
        reg_values = []
        if oldschool:
            offset, name, packer = IoniconModbus._lookup_offset[par_id]
            start_register = 40_000 + offset
            reg_values += list(_pack(1, '>h'))  # execute!
            reg_values += list(packer(new_value))
            log.debug(f'WRITE REG {start_register} ({name}) w/ oldschool protocol')
        else:
            start_register = 41_000
            # ...although we could add more command-blocks here (newschool):
            reg_values += list(_pack(n_blocks, '>h'))
            # the parameter to write is written to the command block (newschool):
            reg_values += list(_pack(par_id, '>h'))
            reg_values += list(_pack(new_value, '>f'))
            log.debug(f'WRITE REG {start_register} ({par_id = }) w/ newschool protocol')

        assert len(reg_values) == (4 - bool(oldschool)), "invalid program: unexpected number of registers to write"

        # wait for instrument to receive...
        retry_time = 0
        while retry_time < timeout_s:
            # a value of 0 indicates ready-to-write:
            if self.mc.read_holding_registers(start_register) == [0]:
                break
            retry_time += 0.2
            time.sleep(0.2)
        else:
            raise TimeoutError(f'instrument not ready for writing after ({timeout_s}) seconds')

        self.mc.write_multiple_registers(start_register, reg_values)

    @lru_cache
    def read_masses(self, update_address_at=None, with_format='>f'):
        start_reg, c_fmt, _ = self.address['n_masses']
        start_reg += 2  # number of components as float..
        masses = self._read_reg_multi(start_reg, c_fmt, self.n_masses)  # input_register
        if update_address_at:
            n_bytes, c_fmt, _ = _get_fmt(with_format)
            self.address.update({
                "{0:.4}".format(mass): (update_address_at + i * n_bytes, c_fmt)
                for i, mass in enumerate(masses)
            })

        return masses

    def read_traces(self, kind='conc'):
        """Returns the current traces, where `kind` is one of 'conc', 'raw', 'components'.
        """
        start_reg, c_fmt, _is_holding = self.address['tc_' + kind]
        start_reg += 14  # skipping timecycles..

        # update the address-space with the current kind
        #  for later calls to `.read_parameter()`:
        masses = self.read_masses(update_address_at=start_reg)
        values = self._read_reg_multi(start_reg, c_fmt, self.n_masses, _is_holding)

        return dict(zip(
            ("{0:.4}".format(mass) for mass in masses), values
        ))

    def read_timecycle(self, kind='conc'):
        """Returns the current timecycle, where `kind` is one of conc|raw|components.

        Absolute time as double (8 bytes), seconds since 01.01.1904, 01:00 am.
        Relative time as double (8 bytes) in seconds since measurement start.
        """
        start_reg, _, _is_holding = self.address['tc_' + kind]

        return _timecycle(
            int(  self._read_reg(start_reg +  2, '>f', _is_holding)),
            int(  self._read_reg(start_reg +  4, '>f', _is_holding)),
            float(self._read_reg(start_reg +  6, '>d', _is_holding)),
            float(self._read_reg(start_reg + 10, '>d', _is_holding)),
        )

    @lru_cache
    def read_component_names(self):
        # 14002 ff: Component Names (maximum length per name:
        # 32 chars (=16 registers), e.g. 14018 to 14033: "Isoprene")
        name_start_reg, _, _is_holding = self.address['component_names']
        data_start_reg, c_fmt, _       = self.address['tc_components']
        data_start_reg += 14  # skip timecycle info..

        _read = self.mc.read_holding_registers if _is_holding else self.mc.read_input_registers
        rv = []
        for index in range(self.n_components):
            n_bytes, c_format, reg_format = _get_fmt('>16H')
            register = _read(name_start_reg + index * 16, n_bytes)
            chars = struct.pack(reg_format, *register)
            decoded = chars.decode('latin-1').strip('\x00')
            self.address[decoded] = (data_start_reg + index * 2, c_fmt, _is_holding)
            rv.append(decoded)

        return rv

    def read_components(self):
        start_reg, c_fmt, _is_holding = self.address['tc_components']
        start_reg += 14  # skipping timecycles...
        values = self._read_reg_multi(start_reg, c_fmt, self.n_components, _is_holding)

        return dict(zip(self.read_component_names(), values))

    def read_ame_version(self):
        start_reg, c_fmt, _is_holding = self.address['version_major']
        major, minor, patch = self._read_reg_multi(start_reg, c_fmt, 3, _is_holding)

        return f"{major}.{minor}.{patch}"

    def read_ame_alarms(self):
        start_reg, c_fmt, _is_holding = self.address['ame_alarms']
        n_alarms = int(self._read_reg(start_reg, c_fmt, _is_holding))
        alarm_levels = self._read_reg_multi(start_reg + 2, c_fmt, n_alarms, _is_holding)

        return dict(zip(self.read_component_names(), alarm_levels))

    def read_ame_timecycle(self):
        return self.read_timecycle(kind='components')

    _ame_parameter = namedtuple('ame_parameter', [
        'step_number',
        'run_number',
        'use_mean',
        'action_number',
        'user_number'
    ])

    def read_ame_numbers(self):
        return IoniconModbus._ame_parameter(
            int(self._read_reg(*self.address['step_number'])),
            int(self._read_reg(*self.address['run_number'])),
            int(self._read_reg(*self.address['use_mean'])),
            int(self._read_reg(*self.address['action_number'])),
            int(self._read_reg(*self.address['user_number'])),
        )

    _ame_mean = namedtuple('ame_mean_info', [
        'data_ok',
        'mod_time',
        'start_cycle',
        'stop_cycle',
        'mean_values',
        'std_error',
    ])

    def write_ame_action(self, action_number):
        self.write_instrument_data(596, action_number, oldschool=False, timeout_s=10)

    def read_ame_mean(self, step_number=None):
        start_reg, c_fmt, _is_holding = self.address['ame_mean_data']
        data_ok = int(self._read_reg(start_reg, c_fmt, _is_holding))
        if not data_ok:
            return IoniconModbus._ame_mean(data_ok, 0, 0, 0, [], [])

        n_masses = int(self._read_reg(start_reg + 6, c_fmt, _is_holding))
        n_steps  = int(self._read_reg(start_reg + 8, c_fmt, _is_holding))

        if step_number is None:
            step_number = int(self._read_reg(*self.address['step_number']))
        elif not (0 < step_number <= n_steps):
            raise IndexError(f"step_number [{step_number}] out of bounds: 0 < step <= [{n_steps}]")

        datablock_size = 1 + 1 + n_masses + n_masses
        start_addr = (start_reg
                + 10
                + n_masses * 2  # skip the masses, same as everywhere
                + (step_number-1) * datablock_size * 2)  # select datablock

        return IoniconModbus._ame_mean(
            data_ok,
            self._read_reg(*self.address['n_ame_mean']),
            self._read_reg(start_addr + 0, c_fmt, _is_holding),
            self._read_reg(start_addr + 2, c_fmt, _is_holding),
            self._read_reg_multi(start_addr + 4,                c_fmt, n_masses, _is_holding),
            self._read_reg_multi(start_addr + 4 + n_masses * 2, c_fmt, n_masses, _is_holding),
        )

    def _read_reg(self, addr, c_format, is_holding_register=False):
        if not _is_open(self.mc):
            raise IOError("trying to read from closed Modbus-connection")

        _read = self.mc.read_holding_registers if is_holding_register else self.mc.read_input_registers

        n_bytes, c_format, reg_format = _get_fmt(c_format)

        register = _read(addr, n_bytes)
        if register is None:
            raise IOError(f"unable to read ({n_bytes}) registers at [{addr}] from connection")

        return _unpack(register, c_format)

    def _read_reg_multi(self, addr, c_format, n_values, is_holding_register=False):
        rv = []
        if not n_values > 0:
            return rv

        if not _is_open(self.mc):
            raise IOError("trying to read from closed Modbus-connection")

        _read = self.mc.read_holding_registers if is_holding_register else self.mc.read_input_registers

        n_bytes, c_format, reg_format = _get_fmt(c_format)
        n_regs = n_bytes * n_values

        # Note: there seems to be a limitation of modbus that
        #  the limits the number of registers to 125, so we
        #  read input-registers in blocks of 120:
        blocks = ((addr + block, min(120, n_regs - block))
                    for block in range(0, n_regs, 120))

        for block in blocks:
            register = _read(*block)
            if register is None:
                raise IOError(f"unable to read ({block[1]}) registers at [{block[0]}] from connection")

            # group the register-values by n_bytes, e.g. [1,2,3,4,..] ~> [(1,2),(3,4),..]
            # this is a trick from the itertools-recipes, see
            # https://docs.python.org/3.8/library/itertools.html?highlight=itertools#itertools-recipes
            # note, that the iterator is cloned n-times and therefore 
            # all clones advance in parallel and can be zipped below:
            batches = [iter(register)] * n_bytes

            rv += [_unpack(reg, c_format) for reg in zip(*batches)]

        return rv

