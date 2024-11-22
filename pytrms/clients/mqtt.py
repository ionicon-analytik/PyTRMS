import os
import time
import json
import queue
from collections import deque, namedtuple
from datetime import datetime
from functools import wraps
from itertools import cycle, chain, zip_longest
from threading import Condition, RLock

from . import _logging
from . import _par_id_file
from .._base import itype, MqttClientBase


log = _logging.getLogger(__name__)

__all__ = ['MqttClient', 'MqttClientBase']


with open(_par_id_file) as f:
    from pandas import read_csv, isna

    _par_id_info = read_csv(f, sep='\t').drop(0).set_index('Name')
    if isna(_par_id_info.at['MPV_1', 'Access']):
        log.warning(f'filling in read-properties still missing in {os.path.basename(_par_id_file)}')
        _par_id_info.at['MPV_1', 'Access'] = 'RW'
        _par_id_info.at['MPV_2', 'Access'] = 'RW'
        _par_id_info.at['MPV_3', 'Access'] = 'RW'



## >>>>>>>>    adaptor functions    <<<<<<<< ##

def _build_header():
    ts = datetime.now()
    header = {
        "TimeStamp": {
            "Str": ts.isoformat(),
            "sec": ts.timestamp() + 2082844800,  # convert to LabVIEW time
        },
    }
    return header

def _build_data_element(value, unit="-"):
    elm = {
        "Datatype": "",
        "Index": -1,
        "Value": str(value),
        "Unit": str(unit),
    }
    if isinstance(value, bool):
        # Note: True is also instance of int! Therefore, we must check it first:
        elm.update({"Datatype": "BOOL", "Value": str(value).lower()})
    elif isinstance(value, str):
        elm.update({"Datatype": "STRING"})
    elif isinstance(value, int):
        elm.update({"Datatype": "I32"})
    elif isinstance(value, float):
        elm.update({"Datatype": "DBL"})
    else:
        raise NotImplemented("unknown datatype")

    return elm

def _build_write_command(parID, value, future_cycle=None):
    cmd = {
        "ParaID": str(parID),
        "Value": str(value),
        "Datatype": "",
        "CMDMode": "Set",
        "Index": -1,
    }
    if future_cycle is not None:
        cmd.update({
            "SchedMode": "OverallCycle",
            "Schedule": str(future_cycle),
        })
    if isinstance(value, bool):
        # Note: True is also instance of int!
        cmd.update({"Datatype": "BOOL", "Value": str(value).lower()})
    elif isinstance(value, str):
        cmd.update({"Datatype": "STRING"})
    elif isinstance(value, int):
        cmd.update({"Datatype": "I32"})
    elif isinstance(value, float):
        cmd.update({"Datatype": "DBL"})
    else:
        raise NotImplemented("unknown datatype")

    return cmd


## >>>>>>>>    parsing functions    <<<<<<<< ##

class ParsingError(Exception):
    pass


def _parse_data_element(elm):
    '''
    raises: ParsingError, KeyError
    '''
    # make a Python object of a DataElement
    if elm["Datatype"] == "BOOL":
        return bool(elm["Value"])
    elif elm["Datatype"] == "DBL":
        return float(elm["Value"])
    elif elm["Datatype"] == "SGL":
        return float(elm["Value"])
    elif elm["Datatype"] == "I32":
        return int(elm["Value"])
    elif elm["Datatype"] == "I16":
        return int(elm["Value"])
    elif elm["Datatype"] == "STRING":
        return str(elm["Value"])
    raise ParsingError("unknown datatype: " + str(elm["Datatype"]))

def _parse_fullcycle(byte_string, need_add_data=False):
    '''Parses 'timecycle', 'intensity', 'mass_cal' and 'add_data' from bytes.

    Important: the byteorder of the parsed arrays will be big-endian! This
     may be aligned if needed with the `.byteswap()`-method on the array,
     but is not automatically performed to avoid any extra copy.

    @params
    - need_add_data if `False`, the 'mass_cal' and 'add_data' returned will be None

    Parsing the AddData-cluster is much slower than parsing the intensity-array!
     This may be skipped to improve performance, but is necessary for loading
     the 'mass_cal' anyway. For orientation:

    performance (on a Intel Core i5, 8th Gen Ubuntu Linux):
      < 2 ms  when `need_add_data=False` (default)
      6-7 ms  when needing to parse the AddData-cluster (else)
    
    @returns a namedtuple ('timecycle', 'intensity', 'mass_cal', 'add_data')
    '''
    import numpy as np

    _f32 = np.dtype(np.float32).newbyteorder('>')
    _f64 = np.dtype(np.float64).newbyteorder('>')
    _i16 = np.dtype(np.int16).newbyteorder('>')
    _i32 = np.dtype(np.int32).newbyteorder('>')
    _i64 = np.dtype(np.int64).newbyteorder('>')
    _chr = np.dtype(np.int8).newbyteorder('>')

    offset = 0

    def rd_single(dtype=_i32):
        nonlocal offset
        _arr = np.frombuffer(byte_string, dtype=dtype, count=1, offset=offset)
        offset += _arr.nbytes
        return _arr[0]
    
    def rd_arr1d(dtype=_f32, count=None):
        nonlocal offset
        if count is None:
            count = rd_single()
        arr = np.frombuffer(byte_string, dtype=dtype, count=count, offset=offset)
        offset += arr.nbytes
        return arr
    
    def rd_arr2d(dtype=_f32):
        nonlocal offset
        n = rd_single()
        m = rd_single()
        arr = np.frombuffer(byte_string, dtype=dtype, count=n*m, offset=offset)
        offset += arr.nbytes
        return arr.reshape((n, m))

    def rd_string():
        nonlocal offset
        return rd_arr1d(dtype=_chr).tobytes().decode('latin-1').lstrip('\x00')
    
    tc_cluster      = rd_arr1d(dtype=_f64, count=4)
    run__, cpx__    = rd_arr1d(dtype=_f64, count=2)  # (discarded)
    # SpecData #
    intensity       = rd_arr1d(dtype=_f32)
    sum_inty        = rd_arr1d(dtype=_f32)  # (discarded)
    mon_peaks       = rd_arr2d(dtype=_f32)  # (discarded)
    
    if not need_add_data:
        # skip costly parsing of Trace- and Add-Data cluster:
        return itype.fullcycle_t(itype.timecycle_t(*tc_cluster), intensity, None, None)

    # TraceData #  (as yet discarded)
    tc_cluster2     = rd_arr1d(dtype=_f64, count=6)
    twoD_raw        = rd_arr2d(dtype=_f32)
    sum_raw         = rd_arr1d(dtype=_f32)
    sum_corr        = rd_arr1d(dtype=_f32)
    sum_conz        = rd_arr1d(dtype=_f32)
    calc_traces     = rd_arr1d(dtype=_f32)
    n_calc_trcs     = rd_single()
    for i in range(n_calc_trcs):
        calc_names  = rd_arr1d(dtype=_chr)
    peak_centrs     = rd_arr1d(dtype=_f32)
    # AddData #
    add_data = dict()
    n_add_data      = rd_single()
    for i in range(n_add_data):
        grp_name    = rd_string()
        descr = []
        for i in range(rd_single()):
            descr.append(rd_string())
        units = []
        for i in range(rd_single()):
            units.append(rd_string())
        data        = rd_arr1d(dtype=_f32)
        view        = rd_arr1d(dtype=_chr)
        n_lv_times  = rd_single()
        offset += 16 * n_lv_times  # skipping LabVIEW timestamp
        add_data[grp_name] = [itype.add_data_item_t(*tup) for tup in zip_longest(data, descr, units, view)]

    # MassCal #
    mc_masses       = rd_arr1d(dtype=_f64)
    mc_tbins        = rd_arr1d(dtype=_f64)
    cal_paras       = rd_arr1d(dtype=_f64)
    segmnt_cal_pars = rd_arr2d(dtype=_f64)
    mcal_mode       = rd_single(dtype=_i16)
    mass_cal = itype.masscal_t(mcal_mode, mc_masses, mc_tbins, cal_paras, segmnt_cal_pars)

    return itype.fullcycle_t(itype.timecycle_t(*tc_cluster), intensity, mass_cal, add_data)


class CalcConzInfo:

    def __init__(self):
        self.tables = {
            "primary_ions": list(),
            "transmission": list(),
        }

    @staticmethod
    def load_json(json_string):
        cc = CalcConzInfo()
        j = json.loads(json_string)
        delm = j["DataElement"]
        for li in delm["Value"]["PISets"]["PiSets"]:
            if not li["PriIonSetName"]:
                log.info(f'loaded ({len(cc.tables["primary_ions"])}) primary-ion settings')
                break

            masses = map(float, filter(lambda x: x > 0, li["PriIonSetMasses"]))
            values = map(float, li["PriIonSetMultiplier"])
            cc.tables["primary_ions"].append(itype.table_setting_t(str(li["PriIonSetName"]), list(zip(masses, values))))

        for li in j["DataElement"]["Value"]["TransSets"]["Transsets"]:
            if not li["Name"]:
                log.info(f'loaded ({len(cc.tables["transmission"])}) transmission settings')
                break

            masses = map(float, filter(lambda x: x > 0, li["Mass"]))
            values = map(float, li["Value"])
            # float(li["Voltage"])  # (not used)
            cc.tables["transmission"].append(itype.table_setting_t(str(li["Name"]), list(zip(masses, values))))

        return cc


## >>>>>>>>    callback functions    <<<<<<<< ##

def follow_calc_conz_info(client, self, msg):
    if not msg.payload:
        # empty payload will clear a retained topic
        self._calcconzinfo = MqttClient._calcconzinfo
        return

    if not self._calcconzinfo[0] is _NOT_INIT:
        # nothing to do..
        return

    log.debug(f"updating tm-/pi-table from {msg.topic}...")
    self._calcconzinfo.append(CalcConzInfo.load_json(msg.payload.decode('latin-1')))

follow_calc_conz_info.topics = ["PTR/Act/PTR_CalcConzInfo"]

def follow_schedule(client, self, msg):
    with follow_schedule._lock:
        if msg.topic.endswith("SRV_ScheduleClear"):
            self._sched_cmds.clear()
            return

        if msg.topic.endswith("SRV_Schedule"):
            if not msg.payload:
                log.warn("empty ACQ_SRV_Schedule payload has cleared retained topic")
                self._sched_cmds.clear()
                return

            if msg.retain:
                # Note: we either have received a message that has been
                #  retained because of a new connection..
                payload = json.loads(msg.payload.decode())
                self._sched_cmds.clear()
                self._sched_cmds.extend(payload["CMDs"])
            else:
                #  ..or the schedule as maintained by IoniTOF has changed,
                #  which we handle ourselves below:
                pass

        if msg.topic.startswith("IC_Command"):
            if not msg.payload:
                log.error("empty IC_Command! has topic been cleared?")
                return

            # these are the freshly added scheduling requests:
            payload = json.loads(msg.payload.decode())
            self._sched_cmds.extend(payload["CMDs"])

follow_schedule.topics = [
    "DataCollection/Act/ACQ_SRV_Schedule",
    "DataCollection/Set/ACQ_SRV_ScheduleClear",
    "IC_Command/Write/Scheduled"
]
follow_schedule._lock = RLock()

def follow_state(client, self, msg):
    if not msg.payload:
        # empty payload will clear a retained topic
        self._server_state = MqttClient._server_state
        return

    payload = json.loads(msg.payload.decode())
    state = payload["DataElement"]["Value"]
    log.debug(f"[{self}] new server-state: " + str(state))
    # replace the current state with the new element:
    self._server_state.append(state)
    meas_running = (state == "ACQ_Aquire")  # yes, there's a typo, plz keep it :)
    just_started = (meas_running and not msg.retain)
    if meas_running:
        # signal the relevant thread(s) that we need an update:
        self._calcconzinfo.append(_NOT_INIT)
    if just_started:
        # invalidate the source-file until we get a new one:
        self._sf_filename.append(_NOT_INIT)

follow_state.topics = ["DataCollection/Act/ACQ_SRV_CurrentState"]

def follow_sourcefile(client, self, msg):
    if not msg.payload:
        # empty payload will clear a retained topic
        self._sf_filename = MqttClient._sf_filename
        return

    payload = json.loads(msg.payload.decode())
    path = payload["DataElement"]["Value"]
    log.debug(f"[{self}] new source-file: " + str(path))
    # replace the current path with the new element:
    self._sf_filename.append(path)

follow_sourcefile.topics = ["DataCollection/Act/ACQ_SRV_SetFullStorageFile"]

def follow_act_set_values(client, self, msg):
    if not msg.payload:
        # empty payload will clear a retained topic
        return

    try:
        server, kind, parID = msg.topic.split('/')
        if server == "DataCollection":
            # Note: this topic doesn't strictly follow the convention and is handled separately
            return

        if server == "Sequencer":
            # Note: this is a separate program and will be ignored (has its own AUTO_-numbers et.c.)
            return

        if parID == "PTR_CalcConzInfo":
            # another "special" topic handled in 'follow_calc_conz_info' ...
            return

        if parID not in _par_id_info.index:
            log.warning(f"unknown par-ID in [{msg.topic}]")
            return

        payload = json.loads(msg.payload.decode())
        if kind == "Act":
            self.act_values[parID] = _parse_data_element(payload["DataElement"])
        if kind == "Set":
            self.set_values[parID] = _parse_data_element(payload["DataElement"])
    except json.decoder.JSONDecodeError as exc:
        log.error(f"{exc.__class__.__name__}: {exc} :: while processing [{msg.topic}] ({msg.payload})")
        raise
    except KeyError as exc:
        log.error(f"{exc.__class__.__name__}: {exc} :: while processing [{msg.topic}] ({msg.payload})")
        pass
    except ParsingError as exc:
        log.error(f"while parsing [{parID}] :: {str(exc)}")
        pass

follow_act_set_values.topics = ["+/Act/+", "+/Set/+"]

def follow_cycle(client, self, msg):
    if not msg.payload:
        # empty payload will clear a retained topic
        return

    payload = json.loads(msg.payload.decode())
    current = int(payload["DataElement"]["Value"])
    # replace the current timecycle with the new element:
    self._overallcycle.append(current)

follow_cycle.topics = ["DataCollection/Act/ACQ_SRV_OverallCycle"]

# collect all follow-functions together:
_subscriber_functions = [fun for name, fun in list(vars().items())
    if callable(fun) and name.startswith('follow_')]


_NOT_INIT = object()


class MqttClient(MqttClientBase):
    """a simplified client for the Ionicon MQTT API.

    > mq = MqttClient()
    > mq.write('TCP_MCP_B', 3400)
    ValueError()

    """

    _sched_cmds   = deque([_NOT_INIT], maxlen=None)
    _server_state = deque([_NOT_INIT], maxlen=1)
    _calcconzinfo = deque([_NOT_INIT], maxlen=1)
    _sf_filename  = deque([""],        maxlen=1)
    _overallcycle = deque([0],         maxlen=1)
    act_values    = dict()
    set_values    = dict()

    set_value_limit = {
        "TCP_MCP_B": 3200.0,
    }
    
    @property
    def is_connected(self):
        '''Returns `True` if connection to IoniTOF could be established.'''
        return (super().is_connected
            and self._server_state[0] is not _NOT_INIT
            and (len(self._sched_cmds) == 0 or self._sched_cmds[0] is not _NOT_INIT))

    @property
    def is_running(self):
        '''Returns `True` if IoniTOF is currently acquiring data.'''
        return self.current_server_state == 'ACQ_Aquire'  # yes, there's a typo, plz keep it :)

    @property
    def current_schedule(self):
        '''Returns a list with the upcoming write commands in ascending order.'''
        if not self.is_connected:
            return []

        current_cycle = self._overallcycle[0]
        filter_fun = lambda cmd: float(cmd["Schedule"]) > current_cycle
        sorted_fun = lambda cmd: float(cmd["Schedule"])

        return sorted(filter(filter_fun, self._sched_cmds), key=sorted_fun)

    @property
    def current_server_state(self):
        '''Returns the state of the acquisition-server. One of:

        - "ACQ_Idle"
        - "ACQ_JustStarted"
        - "ACQ_Aquire"
        - "ACQ_Stopping"

        or "<unknown>" if there's no connection to IoniTOF.
        '''
        if self.is_connected:
            return self._server_state[0]
        return "<unknown>"

    @property
    def current_sourcefile(self):
        '''Returns the path to the hdf5-file that is currently being written.
        
        Returns an empty string if no measurement is running.
        '''
        if not self.is_running:
            return ""

        if self._sf_filename[0] is not _NOT_INIT:
            return self._sf_filename[0]

        # Note: '_NOT_INIT' is set by us on start of acquisition, so we'd expect
        #  to receive the source-file-topic after a (generous) timeout:
        timeout_s = 15
        started_at = time.monotonic()
        while time.monotonic() < started_at + timeout_s:
            if self._sf_filename[0] is not _NOT_INIT:
                return self._sf_filename[0]
    
            time.sleep(10e-3)
        else:
            raise TimeoutError(f"[{self}] unable to retrieve source-file after ({timeout_s = })");

    @property
    def current_cycle(self):
        '''Returns the current 'AbsCycle' (/'OverallCycle').'''
        if self.is_running:
            return self._overallcycle[0]
        return 0

    def __init__(self, host='127.0.0.1', port=1883):
        # this sets up the mqtt connection with default callbacks:
        super().__init__(host, port, _subscriber_functions, None, None, None)
        log.debug(f"connection check ({self.is_connected}) :: {self._server_state = } / {self._sched_cmds = }");

    def disconnect(self):
        super().disconnect()
        log.debug(f"[{self}] has disconnected")
        # reset internal queues to their defaults:
        self._sched_cmds   = MqttClient._sched_cmds
        self._server_state = MqttClient._server_state
        self._calcconzinfo = MqttClient._calcconzinfo
        self._sf_filename  = MqttClient._sf_filename
        self._overallcycle = MqttClient._overallcycle
        self.act_values    = MqttClient.act_values
        self.set_values    = MqttClient.set_values

    def get(self, parID, kind="set"):
        '''Return the last known value for the given `parID`.

        - kind: one of 'set'/'act' (default: 'set')

        A `KeyError` will be raised if the given `parID` is unknown!
        '''
        if not self.is_connected:
            raise Exception(f"[{self}] no connection to instrument");

        _lut = self.act_values if kind.lower() == "act" else self.set_values
        is_read_only = ('W' not in _par_id_info.loc[parID].Access)  # may raise KeyError!
        if _lut is self.set_values and is_read_only:
            raise ValueError(f"'{parID}' is read-only, did you mean `kind='act'`?")

        if not parID in _lut:
            # Note: The values should need NO! time to be populated from the MQTT topics,
            #  because all topics are published as *retained* by the PTR-server.
            #  However, a short timeout is respected before raising a `KeyError`:
            time.sleep(200e-3)
            rv = _lut.get(parID)
            if rv is not None:
                return rv

            # still not found? give some useful hints for the user not to go crazy:
            error_hint = (
                "act" if parID in self.act_values else
                "set" if parID in self.set_values else
                "")
            raise KeyError(str(parID) + (' (did you mean `kind="%s"`?)' % error_hint) if error_hint else "")
        return _lut[parID]

    def get_table(self, table_name):
        timeout_s = 10
        started_at = time.monotonic()
        try:
            while time.monotonic() < started_at + timeout_s:
                # confirm change of state:
                if not self._calcconzinfo[0] is _NOT_INIT:
                    return self._calcconzinfo[0].tables[table_name]
    
                time.sleep(10e-3)
            else:
                raise TimeoutError(f"[{self}] unable to retrieve calc-conz-info from PTR server");
        except KeyError as exc:
            raise KeyError(str(exc) + f", possible values: {list(CalcConzInfo.tables.keys())}")

    def set(self, parID, new_value, unit='-'):
        '''Set a 'new_value' to 'parID' in the DataCollection.'''
        if not self.is_connected:
            raise Exception(f"[{self}] no connection to instrument");

        raise NotImplementedError("DataCollection/Set, did you mean .write(parID)?")

        topic, qos, retain = "DataCollection/Set/" + str(parID), 1, True
        log.info(f"setting '{parID}' ~> [{new_value}]")
        payload = {
            "Header":      _build_header(),
            "DataElement": _build_data_element(new_value, unit),
        }
        return self.publish_with_ack(topic, json.dumps(payload), qos=qos, retain=retain)

    def filter_schedule(self, parID):
        '''Returns a list with the upcoming write commands for 'parID' in ascending order.'''
        return (cmd for cmd in self.current_schedule if cmd["ParaID"] == str(parID))

    def write(self, parID, new_value):
        '''Write a 'new_value' to 'parID' directly.'''
        if not self.is_connected:
            raise Exception(f"[{self}] no connection to instrument");

        if not 'W' in _par_id_info.loc[parID].Access:  # may raise KeyError!
            raise ValueError(f"'{parID}' is read-only")

        if parID in __class__.set_value_limit and new_value > __class__.set_value_limit[parID]:
            raise ValueError("set value limit of {__class__.set_value_limit[parID]} on '{parID}'")

        topic, qos, retain = "IC_Command/Write/Direct", 1, False
        log.info(f"writing '{parID}' ~> [{new_value}]")
        cmd = _build_write_command(parID, new_value)
        payload = {
            "Header": _build_header(),
            "CMDs": [ cmd, ]
        }
        return self.publish_with_ack(topic, json.dumps(payload), qos=qos, retain=retain)

    def schedule(self, parID, new_value, future_cycle):
        '''Schedule a 'new_value' to 'parID' for the given 'future_cycle'.

        If 'future_cycle' is in fact in the past, the behaviour is defined by IoniTOF
        (most likely the command is ignored). To be sure, the '.current_cycle' should
        be checked before and after running the '.schedule' command programmatically!
        '''
        if not self.is_connected:
            raise Exception(f"[{self}] no connection to instrument");

        if not 'W' in _par_id_info.loc[parID].Access:  # may raise KeyError!
            raise ValueError(f"'{parID}' is read-only")

        if parID in __class__.set_value_limit and new_value > __class__.set_value_limit[parID]:
            raise ValueError("set value limit of {__class__.set_value_limit[parID]} on '{parID}'")

        if (future_cycle == 0 and not self.is_running):
            # Note: ioniTOF40 doesn't handle scheduling for the 0th cycle!
            if parID == "AME_ActionNumber":
                # a) the action-number will trigger a script for the 0th cycle, so
                #    we *must* be scheduling it!
                self.write("AME_ActionNumber", new_value)
            elif parID.startswith("AME_"):
                # b) the AME-numbers cannot (currently) be set (i.e. written), but since
                #    they are inserted just *before* the cycle, this will work just fine:
                future_cycle = 1
            else:
                # c) in all other cases, let's assume the measurement will start soon
                #    and dare to write immediately, skipping the schedule altogether:
                log.debug(f"immediately writing {parID = } @ cycle '0' (measurement stopped)")
                return self.write(parID, new_value)

        if not future_cycle > self.current_cycle:
            log.warn(f"attempting to schedule past cycle, hope you know what you're doing");
            pass  # and at least let's debug it in MQTT browser (see also doc-string above)!

        topic, qos, retain = "IC_Command/Write/Scheduled", 1, False
        log.info(f"scheduling '{parID}' ~> [{new_value}] for cycle ({future_cycle})")
        cmd = _build_write_command(parID, new_value, future_cycle)
        payload = {
            "Header": _build_header(),
            "CMDs": [ cmd, ]
        }
        return self.publish_with_ack(topic, json.dumps(payload), qos=qos, retain=retain)

    def schedule_filename(self, path, future_cycle):
        '''Start writing to a new .h5 file with the beginning of 'future_cycle'.'''
        assert str(path), "filename cannot be empty!"
        # try to make sure that IoniTOF accepts the path:
        if self.host == '127.0.0.1':
            os.makedirs(os.path.dirname(path), exist_ok=True)
            try:
                with open(path, 'x'):
                    log.info("touched new file:", path)
            except FileExistsError as exc:
                log.error(f"new filename '{path}' already exists and will not be scheduled!")
                return

        return self.schedule('ACQ_SRV_SetFullStorageFile', path.replace('/', '\\'), future_cycle)

    def start_measurement(self, path=None):
        '''Start a new measurement and block until the change is confirmed.

        If 'path' is not None, write to the given .h5 file.
        '''
        if not path:
            self.write('ACQ_SRV_Start_Meas_Quick', True)
        else:
            self.write('ACQ_SRV_Start_Meas_Record', path.replace('/', '\\'))
        timeout_s = 30
        started_at = time.monotonic()
        while time.monotonic() < started_at + timeout_s:
            if self.is_running:
                break

            time.sleep(10e-3)
        else:
            self.disconnect()
            raise TimeoutError(f"[{self}] error starting measurement");

    def stop_measurement(self, future_cycle=None):
        '''Stop the current measurement and block until the change is confirmed.

        If 'future_cycle' is not None and in the future, schedule the stop command.'''
        if future_cycle is None or not future_cycle > self._overallcycle[0]:
            self.write('ACQ_SRV_Stop_Meas', True)
        else:
            self.schedule('ACQ_SRV_Stop_Meas', True, future_cycle)
        # may need to wait until the scheduled event..
        if future_cycle is not None:
            self.block_until(future_cycle)
        # ..for this timeout to be applicable:
        timeout_s = 30
        started_at = time.monotonic()
        while time.monotonic() < started_at + timeout_s:
            # confirm change of state:
            if not self.is_running:
                break

            time.sleep(10e-3)
        else:
            self.disconnect()
            raise TimeoutError(f"[{self}] error stopping measurement");

    def block_until(self, cycle):
        '''Blocks the current thread until at least 'cycle' has passed or acquisition stopped.

        Returns the actual current cycle.
        '''
        while self.is_running:
            if self._overallcycle[0] >= int(cycle):
                break
            time.sleep(10e-3)
        else:
            return 0

        return self._overallcycle[0]

    def iter_specdata(self, timeout_s=None, buffer_size=300):
        '''Returns an iterator over the fullcycle-data as long as it is available.

        * This will wait up to `timeout_s` (or indefinitely if `None`) for a
          measurement to start or raise a TimeoutError (default: None).
        * Elements will be buffered up to a maximum of `buffer_size` cycles (default: 300).
        * Cycles recorded prior to calling `next()` on the iterator may be missed,
          so ideally this should be set up before any measurement is running.
        * [Important]: When the buffer runs full, a `queue.Full` exception will be raised!
          Therefore, the caller should consume the iterator as soon as possible while the
          measurement is running.
        '''
        q = queue.Queue(buffer_size)
        topic = "DataCollection/Act/ACQ_SRV_FullCycleData"
        qos = 2

        def callback(client, self, msg):
            try:
                q.put_nowait(_parse_fullcycle(msg.payload, need_add_data=True))
                log.debug(f"received fullcycle, buffer at ({q.qsize()}/{q.maxsize})")
            except queue.Full:
                # DO NOT FAIL INSIDE THE CALLBACK!
                log.error(f"iter_specdata({q.maxsize}): fullcycle buffer overrun!")
                client.unsubscribe(topic)

        if not self.is_connected:
            raise Exception("no connection to MQTT broker")

        # Note: when using a simple generator function like this, the following lines
        #  will not be excecuted until the first call to `next` on the iterator!
        #  this means, the callback will not yet be executed, the queue not filled 
        #  and we might miss the first cycles...
        self.client.message_callback_add(topic, callback)
        self.client.subscribe(topic, qos)
        try:
            # Note: Prior to 3.0 on POSIX systems, and for *all versions on Windows*,
            #  if block is true and timeout is None, [the q.get()] operation goes into an
            #  uninterruptible wait on an underlying lock. This means that no exceptions
            #  can occur, and in particular a SIGINT will not trigger a KeyboardInterrupt!
            yield q.get(block=True, timeout=timeout_s)  # waiting for measurement to run...

            while self.is_running or not q.empty():
                if q.full():
                    # re-raise what we swallowed in the callback..
                    raise queue.Full

                if not self.is_connected:
                    # no more data will come, so better prevent a deadlock:
                    break

                try:
                    yield q.get(block=True, timeout=1.0)  # seconds
                except queue.Empty:
                    continue

        except queue.Empty:
            assert timeout_s is not None, "this should never happen"
            raise TimeoutError("no measurement running after {timeout_s} seconds")

        finally:
            #  ...also, when using more than one iterator, the first to finish will
            #  unsubscribe and cause all others to stop maybe before the time!
            #  all of this might not actually be an issue right now, but
            # TODO :: fix this weird behaviour (can only be done by implementing the
            #  iterator-protocol properly using a helper class)!
            self.client.unsubscribe(topic)
            self.client.message_callback_remove(topic)

    iter_specdata.__doc__ += _parse_fullcycle.__doc__

    def __repr__(self):
        return f"<{self.__class__.__name__}[{self.host}]>"

