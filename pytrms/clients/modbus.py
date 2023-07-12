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


class IoniconModbus:

    address = dict([
        ('server_state', (0, '>f')),      # 0: Not ready, 1: Ready, 2: Startup
        ('measure_state', (2, '>f')),     # 0: Not running | 1: running | 2: Just Started | 3: Just Stopped
        ('instrument_state', (4, '>f')),  # 0: Not Ok, 1: Ok, 2: Error, 3: Warning
        ('alive_counter', (6, '>H')),     # (updated every 500 ms)
        ('n_parameters', (2000, '>H')),
        ('n_raw', (4000, '>f')),
        ('n_conc', (6000, '>f')),
        ('n_masses', (8000, '>f')),
        # ('n_corr', (7000, '>i')),       # not implemented?
        ('ame_data', (10014, '>f')),
        ('user_number', (13900, '>i')),
        ('step_number', (13902, '>i')),
        ('run_number', (13904, '>i')),
        ('use_mean', (13906, '>i')),
        ('action_number', (13912, '>i')),
        ('ame_state', (13914, '>i')),     # Running 0=Off; 1=On (not implemented!)
        ('n_components', (14000, '>f')),
        ('component_names', (14002, '>f')),
    ])

    @property
    def is_alive(self):
        """Wait for the IoniTOF alive-counter to change (1 second max)."""
        initial_count = self._read_reg(*self.address['alive_counter'])
        for i in range(10):
            if initial_count != self._read_reg(*self.address['alive_counter']):
                return True

            time.sleep(.1)

        return False

    @property
    def is_open(self):
        return self.mc.is_open

    def __init__(self, host='localhost', port=502):
        self.mc = client.ModbusClient(host=host, port=port)
        if not self.mc.open():
            raise IOError("Cannot connect to modbus socket @ %s:%d!" % (str(host), port))

        self._addresses = {}

    def open(self):
        if not self.mc.is_open:
            self.mc.open()

    def close(self):
        if self.mc.open():
            self.mc.close()

    def __del__(self):
        self.close()

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
        self.open()
        try:
            return self._read_reg(*self.address[par_name])
        except KeyError as exc:
            raise KeyError("did you call one of .read_instrument_data(), .read_traces(), et.c. first?")

    def read_instrument_data(self):
        self.open()

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
            input_regs = self.mc.read_input_registers(
                start_register + superblock, superblocksize)
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

    @lru_cache
    def read_masses(self, update_address_at=None, with_format='>f'):
        self.open()
        start_reg, _ = self.address['n_masses']
        start_reg += 2  # number of components as float..

        masses = self._read_reg_multi(start_reg, '>f', self.n_masses)

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
        self.open()
        start_reg, _ = self.address['n_' + kind]
        start_reg += 14  # skipping timecycles..

        # update the address-space with the current kind
        #  for later calls to `.read_parameter()`:
        masses = self.read_masses(update_address_at=start_reg)
        values = self._read_reg_multi(start_reg, '>f', self.n_masses)

        return dict(zip(
            ("{0:.4}".format(mass) for mass in masses), values
        ))

    def read_timecycle(self, kind='conc'):
        """Returns the current timecycle, where `kind` is one of 'conc', 'raw', 'components'.

        Absolute time as double (8 bytes), seconds since 01.01.1904, 01:00 am.
        Relative time as double (8 bytes) in seconds since measurement start.
        """
        self.open()
        start_reg, _ = self.address['n_' + kind]

        return _timecycle(
            int(self._read_reg(start_reg + 2, '>f')),
            int(self._read_reg(start_reg + 4, '>f')),
            float(self._read_reg(start_reg + 6, '>d')),
            float(self._read_reg(start_reg + 10, '>d')),
        )

    @lru_cache
    def read_component_names(self):
        self.open()
        # 14002 ff: Component Names (maximum length per name:
        # 32 chars (=16 registers), e.g. 14018 to 14033: "Isoprene")
        start_reg, _ = self.address['component_names']
        value_start_reg, c_fmt = self.address['ame_data']

        rv = []
        for index in range(self.n_components):
            n_bytes, c_format, reg_format = _get_fmt('>16H')
            input_reg = self.mc.read_input_registers(start_reg + index * 16, n_bytes)
            chars = struct.pack(reg_format, *input_reg)
            decoded = chars.decode('latin-1').strip('\x00')
            self.address[decoded] = (value_start_reg + index * 2, c_fmt)
            rv.append(decoded)

        return rv

    def read_components(self):
        self.open()
        start_reg = 10014  # AME Data (skipping timecycles)
        values = self._read_reg_multi(start_reg, '>f', self.n_components)

        return dict(zip(self.read_component_names(), values))

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
        self.open()
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

    def read_ame_mean(self, step_number=None):
        self.open()
        data_ok = int(self._read_reg(26000, '>f'))
        if not data_ok:
            return IoniconModbus._ame_mean(data_ok, 0, 0, 0, [], [])

        n_masses = int(self._read_reg(26006, '>f'))
        n_steps = int(self._read_reg(26008, '>f'))

        if step_number is None:
            step_number = int(self._read_reg(*self.address['step_number']))
        elif not (0 < step_number <= n_steps):
            raise IndexError(f"step_number [{step_number}] out of bounds: 0 < step <= [{n_steps}]")

        datablock_size = 1 + 1 + n_masses + n_masses
        start_addr = (26010
                + n_masses * 2  # skip the masses, same as everywhere
                + (step_number-1) * datablock_size * 2)  # select datablock

        return IoniconModbus._ame_mean(
            data_ok,
            self._read_reg(26002, '>d'),
            self._read_reg(start_addr + 0, '>f'),
            self._read_reg(start_addr + 2, '>f'),
            self._read_reg_multi(start_addr + 4, '>f', n_masses),
            self._read_reg_multi(start_addr + 4 + n_masses * 2, '>f', n_masses),
        )

    def _read_reg(self, addr, c_format):
        n_bytes, c_format, reg_format = _get_fmt(c_format)
        input_reg = self.mc.read_input_registers(addr, n_bytes)
        if input_reg is None and self.is_open:
            raise IOError(f"unable to read ({n_bytes}) registers at [{addr}] from connection")
        elif input_reg is None and not self.is_open:
            raise IOError("trying to read from closed Modbus-connection")

        return _unpack(input_reg, c_format)

    def _read_reg_multi(self, addr, c_format, n_values):
        rv = []
        if not n_values > 0:
            return rv

        n_bytes, c_format, reg_format = _get_fmt(c_format)
        n_regs = n_bytes * n_values

        # Note: there seems to be a limitation of modbus that
        #  the limits the number of registers to 125, so we
        #  read input-registers in blocks of 120:
        blocks = ((addr + block, min(120, n_regs - block))
                    for block in range(0, n_regs, 120))

        for block in blocks:
            input_reg = self.mc.read_input_registers(*block)
            if input_reg is None and self.is_open:
                raise IOError(f"unable to read ({block[1]}) registers at [{block[0]}] from connection")
            elif input_reg is None and not self.is_open:
                raise IOError("trying to read from closed Modbus-connection")

            # group the register-values by n_bytes, e.g. [1,2,3,4,..] ~> [(1,2),(3,4),..]
            # this is a trick from the itertools-recipes, see
            # https://docs.python.org/3.8/library/itertools.html?highlight=itertools#itertools-recipes
            # note, that the iterator is cloned n-times and therefore 
            # all clones advance in parallel and can be zipped below:
            batches = [iter(input_reg)] * n_bytes

            rv += [_unpack(reg, c_format) for reg in zip(*batches)]

        return rv

