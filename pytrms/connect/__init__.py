from .._version import __version__

import sys
import os
import platform
import re
import logging
from os.path import abspath, dirname, join

import h5py

arch = 'x64' if '64' in platform.python_compiler() else 'x86'
sys.path.append(join(abspath(dirname(__file__)), 'bin', arch))

log = logging.getLogger(__name__)

from ._base import epoch_diff_s
#from .high5 import High5
from .ionitof import IoniTOF
from .utils import Validator

from .modbus import IoniconModbus
try:
    from .twincat import TwinCat_ADS
    _has_TwinCat = True
except ImportError:
    _has_TwinCat = False

__all__ = ['__version__', 'High5', 'IoniTOF', 'connect']


#from .mode import Mode, ModeTable
#from .feature import Feature

__all__ += ['Mode', 'ModeTable', 'Feature']


_root = os.path.abspath(os.path.dirname(__file__))
_IoniTofPrefs_default = os.path.join(_root, 'data', 'IoniTofPrefs.ini')


def connect(address, root_dir='.', mode_table=None):
    """Connect to either ip or file and return a fully initialized Connector."""
    if address == 'localhost':
        address = '127.0.0.1'
    if os.path.exists(address):
        return _make_file_connector(address, mode_table)
    elif re.match(r'[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+', address):
        return _make_online_connector(address, root_dir, mode_table)
    else:
        raise ValueError("Invalid adress: %s! Expected either path to a file/directory "
                         "or an ip-adress." % address)


def _make_online_connector(ip, root_dir='.', mode_table=None):
    try:
        from ._adapter import IcAPIAdapter
    except ImportError:
        raise SystemError("Can't find IcAPI.dll neccessary to instanciate connection!")

    source = IcAPIAdapter(ip)
    if _has_TwinCat:
        twincat_ads = TwinCat_ADS.connect('192.168.127.198')
    else:
        twincat_ads = None

    try:
        modbus_ctrl = IoniconModbus(ip, port=502)
    except IOError as exc:
        log.warning("Got %s: %s This means the current step information is not available."
                    % (type(exc).__name__, str(exc)))
        modbus_ctrl = None

    ionitof_prefs_file = r'C:\ProgramData\IoniconTOF\IoniTofPrefs.ini'
    if not os.path.exists(ionitof_prefs_file):
        log.warning("IoniTofPrefs.ini not found. Using default config file.")
        ionitof_prefs_file = _IoniTofPrefs_default

    # if mode_table is not None:
        # pass
    # elif any('.xml' in fname for fname in os.listdir(root_dir)):
        # cfg = next(fname for fname in os.listdir(root_dir) if '.xml' in fname)
        # mode_table = ModeTable.from_file(cfg)

    # elif any('.ics1' in fname for fname in os.listdir(root_dir)):
        # cfg = next(fname for fname in os.listdir(root_dir) if '.ics1' in fname)
        # mode_table = ModeTable.from_file(cfg)
    # else:
        # log.warning("Did not find valid config file in %s! Using default Mode Table."
                    # % root_dir)
        # mode_table = ModeTable.default()

    return IoniTOF(icapi_controller=source, tps_controller=twincat_ads,
                   modbus_controller=modbus_ctrl, ionitof_prefs_file=ionitof_prefs_file,
                   #mode_table=mode_table)
                   mode_table=None)


def _make_file_connector(filename, mode_table=None):
    root_dir = os.path.dirname(filename)
    filetype = High5.determine_filetype(filename)
    if filetype == 'ionicon':
        h5file = h5py.File(filename, 'r')
        valid = Validator()
        log.info("Validating sections...")
        High5.validate_sections(h5file, notifier=valid)
        if not valid:
            for error in valid:
                log.warning(error)

        if mode_table is not None:
            pass
        elif not valid.has_occurred(High5.CheckResult.NoAMEData): # | Check.AMEDataCorrupt):
            log.info("Inferring Mode Table from AME data...")
            mode_table = High5.infer_mode_table(h5file)
        elif any('.xml' in fname for fname in os.listdir(root_dir)):
            cfg = next(fname for fname in os.listdir(root_dir) if '.xml' in fname)
            log.info("Inferring Mode Table from %s..." % cfg)
            mode_table = ModeTable.from_file(cfg)
        elif any('.ics1' in fname for fname in os.listdir(root_dir)):
            cfg = next(fname for fname in os.listdir(root_dir) if '.ics1' in fname)
            log.info("Inferring Mode Table from %s..." % cfg)
            mode_table = ModeTable.from_file(cfg)
        else:
            log.warning("Did not find valid AME/Data in %s! Using default Mode Table."
                        % filename)
            mode_table = ModeTable.default()

        log.info("Done creating file connection.")
        return High5(h5file, mode_table)

    elif filetype == 'ame_trace':
        raise NotImplementedError("no reader for ame_trace - like filetype...")

    else:
        raise Exception("Cannot read from filetype <%s>!" % filetype)

