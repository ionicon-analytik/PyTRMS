from collections import namedtuple

class itype:

    table_setting_t = namedtuple('mass_mapping', ['name', 'mass2value'])
    timecycle_t     = namedtuple('timecycle',  ['rel_cycle','abs_cycle','abs_time','rel_time'])
    masscal_t       = namedtuple('masscal',    ['mode', 'masses', 'timebins', 'cal_pars', 'cal_segs'])
    add_data_item_t = namedtuple('add_data',   ['value', 'name', 'unit', 'view'])
    fullcycle_t     = namedtuple('fullcycle',  ['timecycle', 'intensity', 'mass_cal', 'add_data'])

