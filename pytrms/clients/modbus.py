"""Module modbus.py

"""
import os
import struct
import time
import logging
from collections import namedtuple
from functools import lru_cache
from itertools import tee

from pyModbusTCP import client

from .._base.ioniclient import IoniClientBase

log = logging.getLogger(__name__)

__all__ = ['IoniconModbus']


_root = os.path.abspath(os.path.dirname(__file__))
_par_id_list = os.path.join(_root, '..', 'data', 'par_ID_list.txt')

with open(_par_id_list) as f:
    it = iter(f)
    assert next(it) == 'ID\tName\n', 'Modbus parameter file %s is corrupt!' % _par_id_list
    _id_to_descr = {int(id_): name for id_, name in (line.strip().split('\t') for line in it)}

# look-up-table for c_structs (see docstring of struct-module for more info).
# Note: almost *all* parameters used by IoniTOF (esp. AME) are 'float', with
#  some exceptions that are 'short' (alive_counter, n_parameters) or explicitly
#  marked to be 'int' (AME_RunNumber, et.c.):
_fmts = dict([
    ('float', '>f'),
    ('double', '>d'),
    ('short', '>h'),
    ('int', '>i'),
    ('long', '>q'),
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
    672.

    >>> _unpack([17446, 32768], 'float')
    666.
    
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


class IoniconModbus(IoniClientBase):

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
        ('tc_components',    (10000, '>f', True )),
        ('ame_alarms',       (12000, '>f', True )),
        ('user_number',      (13900, '>i', True )),
        ('step_number',      (13902, '>i', True )),
        ('run_number',       (13904, '>i', True )),
        ('use_mean',         (13906, '>i', True )),
        ('action_number',    (13912, '>i', True )),
        ('ame_state',        (13914, '>i', True )),  # Running 0=Off; 1=On (not implemented!)
        ('n_components',     (14000, '>f', True )),
        ('component_names',  (14002, '>f', True )),
        ('ame_mean_data',    (26000, '>f', True )),
        ('n_ame_mean',       (26002, '>d', True )),
    ])

    @property
    def _alive_counter(self):
        return self._read_reg(*self.address['alive_counter'])

    @property
    def is_connected(self):
        if not self.mc.is_open:
            return False

        # wait for the IoniTOF alive-counter to change (1 second max)...
        initial_count = self._alive_counter
        timeout_s = 3  # counter should increase every 500 ms, approximately
        started_at = time.monotonic()
        while time.monotonic() < started_at + timeout_s:
            if initial_count != self._alive_counter:
                return True

            time.sleep(10e-3)
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
        self.mc = client.ModbusClient(host=self.host, port=self.port)
        # try connect immediately:
        try:
            self.connect()
        except TimeoutError as exc:
            log.warn(f"{exc} (retry connecting when the Instrument is set up)")
        self._addresses = {}

    def use_all_input_registers(self):
        """Read from input- instead of holding-registers (legacy method to be compatible with AME1.0)."""
        modded = dict()
        for key, vals in self.address.items():
            modded[key] = vals[0], vals[1], False
        self.address.update(modded)

    def connect(self, timeout_s=10):
        log.info(f"[{self}] connecting to Modbus server...")
        self.mc.timeout = timeout_s
        self.mc.auto_open = True
        if not self.mc.open():
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
        if self.mc.is_open:
            self.mc.close()

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

    def write_instrument_data(self, par_id, new_value, timeout_s=10):

        # Each command-block consists of 3 registers:
        # Register 1: Parameter ID
        # Register 2-3: Parameter Set Value as float(real)
        start_register = 40000
        blocksize = 3

        if isinstance(par_id, str):
            try:
                par_id = next(k for k, v in _id_to_descr.items() if v == par_id)
            except StopIteration as exc:
                raise KeyError(str(par_id))
        par_id = int(par_id)
        if par_id not in _id_to_descr:
            raise IndexError(str(par_id))

        start_register += blocksize * par_id

        retry_time = 0
        while retry_time < timeout_s:
            # a value of 0 indicates ready-to-write:
            if self.mc.read_holding_registers(start_register) == [0]:
                break
            retry_time += 0.5
            time.sleep(0.5)
        else:
            raise TimeoutError(f'register {start_register} timed out after {timeout_s}s')

        reg_values = [start_register] + list(_pack(new_value))
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

    def read_ame_alarms(self):
        start_reg, c_fmt, _is_holding = self.address['ame_alarms']
        n_alarms = int(self._read_reg(start_reg, c_fmt, _is_holding))
        values = self._read_reg_multi(start_reg + 2, c_fmt, n_alarms, _is_holding)

        return dict(zip(self.read_component_names(), map(bool, values)))

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
        start_reg, c_fmt, _ = self.address['action_number']
        set_value = _pack(action_number, c_fmt)
        self.mc.write_multiple_registers(start_reg, set_value)

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
        n_bytes, c_format, reg_format = _get_fmt(c_format)
        _read = self.mc.read_holding_registers if is_holding_register else self.mc.read_input_registers
        
        register = _read(addr, n_bytes)
        if register is None and self.is_open:
            raise IOError(f"unable to read ({n_bytes}) registers at [{addr}] from connection")
        elif register is None and not self.is_open:
            raise IOError("trying to read from closed Modbus-connection")

        return _unpack(register, c_format)

    def _read_reg_multi(self, addr, c_format, n_values, is_holding_register=False):
        rv = []
        if not n_values > 0:
            return rv

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
            if register is None and self.is_connected:
                raise IOError(f"unable to read ({block[1]}) registers at [{block[0]}] from connection")
            elif register is None and not self.is_connected:
                raise IOError("trying to read from closed Modbus-connection")

            # group the register-values by n_bytes, e.g. [1,2,3,4,..] ~> [(1,2),(3,4),..]
            # this is a trick from the itertools-recipes, see
            # https://docs.python.org/3.8/library/itertools.html?highlight=itertools#itertools-recipes
            # note, that the iterator is cloned n-times and therefore 
            # all clones advance in parallel and can be zipped below:
            batches = [iter(register)] * n_bytes

            rv += [_unpack(reg, c_format) for reg in zip(*batches)]

        return rv

