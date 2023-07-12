"""Module modbus.py

"""
import os
import struct
import time
import logging
from collections import namedtuple
from functools import lru_cache

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
_parameter = namedtuple('Parameter', ('Set', 'Act', 'Id', 'State'))


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


        assert _unpack([17446, 32768], 'float') == 666.
        assert _unpack([16875, 61191, 54426, 37896], 'double') == 3749199524.83057
        assert _unpack([16875, 61191, 54426, 37896], 'long') == 4750153048903029768

    def test_unpack_fails_with_nonsensical_arguments(self):
        with pytest.raises(struct.error):
            _unpack([16875, 61191, 54426, 37896], 'float')

        with pytest.raises(struct.error):
            _unpack([17446, 32768], 'long')
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
    n, c_format, reg_format = _get_fmt(format)

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
        # ('n_corr', (7000, '>i')),  # not implemented?
        ('n_masses', (8000, '>f')),
        ('user_number', (13900, '>i')),
        ('step_number', (13902, '>i')),
        ('run_number', (13904, '>i')),
        ('use_mean', (13906, '>i')),
        ('action_number', (13912, '>i')),
        ('ame_state', (13914, '>i')),     # Running 0=Off; 1=On
        ('n_components', (14000, '>f')),
    ])

    _ame_parameter = namedtuple('ame_parameter',
        ['user_number', 'step_number', 'run_number', 'use_mean', 'action_number', 'ame_state']
    )

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

    def read_parameters(self):
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
            print(superblock)
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
    def read_masses(self):
        self.open()
        start_reg, _ = self.address['n_masses']
        start_reg += 2  # number of components as float..
        value_start_reg = 6014  # conc data (skipping timing info)

        rv = []
        for index in range(self.n_masses):
            mass = self._read_reg(start_reg + index * 2, '>f')
            mass_key = "{0:.4}".format(mass)
            self.address[mass_key] = value_start_reg + index * 2
            rv.append(mass)

        return rv

    def read_traces(self, kind='conc'):
        self.open()
        start_reg, _ = self.address['n_' + kind]
        info_regs = 14  # timecycle_width

        # Note: the look-up-table .address is not so useful here,
        #  because of the different kinds (conc, raw [,corr]):
        return dict(zip(
            ("{0:.4}".format(mass) for mass in self.read_masses()),
            (self._read_reg(start_reg + info_regs + offset, '>f')
                for offset in range(0, self.n_masses * 2, 2))
        ))

    @lru_cache
    def read_component_names(self):
        # 14002 ff: Component Names (maximum length per name:
        # 32 chars (=16 registers), e.g. 14018 to 14033: "Isoprene")
        self.open()
        start_reg, _ = self.address['n_components']
        start_reg += 2  # number of components as float..
        value_start_reg = 10014  # AME data (skipping timing info)

        rv = []
        for index in range(self.n_components):
            n_bytes, c_format, reg_format = _get_fmt('>16H')
            input_reg = self.mc.read_input_registers(start_reg + index * 16, n_bytes)
            chars = struct.pack(reg_format, *input_reg)
            decoded = chars.decode('latin-1').strip('\x00')
            self.address[decoded] = (value_start_reg + index * 2, '>f')
            rv.append(decoded)

        return rv

    def read_components(self):
        self.open()
        return dict((name, self._read_reg(*self.address[name])) for name in self.read_component_names())

    def read_parameter(self, par_name):
        """Read any previously loaded parameter by name.

        For example, after calling `.read_components()`, one can call
        `.read_parameter('DPS_Udrift')` to get only this value with no overhead.
        """
        self.open()
        try:
            return self._read_reg(*self.address[par_name])
        except KeyError as exc:
            raise KeyError("did you call one of .read_parameters(), .read_traces(), et.c. first?")

    def read_timecycle(self):
        ## TODO odbus register 10000-11999: AME Data
        # Register 10000-10001: Number of AME compounds plus 6 SGL Values for Timing Info
        # Register 10002-10013: AME timing info (10002-10003: Cycle   AS FLOAT ! '>f'
        # , 10004-10005: Overall cycle, 10006 to
        # 10009: Absolute time as double (8 bytes), seconds since 01.01.1904, 01:00 am, 10010 to 10013:
        # Relative time as double (8 bytes) in seconds since measurement start )
        # Register 10014-11999: AME data (the Simulation Server only fills only 2 FLOAT values , so the first 4
        # U16 registers). Reg. 10014-10015: Value Acetone, Reg. 10016-10017: Value Isoprene
        pass

    def read_ame_parameters(self):
        self.open()
        return IoniconModbus._ame_parameter(
            int(self._read_reg(*self.address['user_number'])),
            int(self._read_reg(*self.address['step_number'])),
            int(self._read_reg(*self.address['run_number'])),
            int(self._read_reg(*self.address['use_mean'])),
            int(self._read_reg(*self.address['action_number'])),
            int(self._read_reg(*self.address['ame_state']))
        )

    def _read_reg(self, addr, c_format):
        n_bytes, c_format, reg_format = _get_fmt(c_format)
        input_reg = self.mc.read_input_registers(addr, n_bytes)
        if input_reg is None and self.is_open:
            raise IOError(f"unable to read ({n_bytes}) registers at [{addr}] from connection")
        elif input_reg is None and not self.is_open:
            raise IOError("trying to read from closed Modbus-connection")

        return _unpack(input_reg, c_format)
