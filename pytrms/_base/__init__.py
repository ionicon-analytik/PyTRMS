from collections import namedtuple

from .mqttclient import MqttClientBase as _MqttClientBase
from .ioniclient import IoniClientBase as _IoniClientBase

class itype:

    table_setting_t = namedtuple('mass_mapping', ['name', 'mass2value'])
    timecycle_t     = namedtuple('timecycle',  ['rel_cycle','abs_cycle','abs_time','rel_time'])
    masscal_t       = namedtuple('masscal',    ['mode', 'masses', 'timebins', 'cal_pars', 'cal_segs'])
    add_data_item_t = namedtuple('add_data',   ['value', 'name', 'unit', 'view'])
    fullcycle_t     = namedtuple('fullcycle',  ['timecycle', 'intensity', 'mass_cal', 'add_data'])

    AME_RUN    = 8
    AME_STEP   = 7
    AME_ACTION = 5
    USE_MEAN   = 2  # (only in AUTO_UseMean)

    REACT_Udrift = 0
    REACT_pDrift = 1
    REACT_Tdrift = 2
    REACT_PI_Idx = 4  # skipping E/N = 3
    REACT_TM_Idx = 5

