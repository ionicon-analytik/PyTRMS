import os
import time
import logging
import json
from itertools import cycle, zip_longest
from collections import deque
from queue import Queue
from threading import Condition, RLock
from datetime import datetime as dt

import paho.mqtt.client as mqtt

from .._base.mqttconn import MqttConn


log = logging.getLogger()

__all__ = ['MqttClient']


def _build_header():
    ts = dt.now()
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
        # Note: True is also instance of int!
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

class ParsingError(Exception):
    pass

def _parse_data_element(elm):
    '''
    raises: ParsingError, KeyError
    '''
    # make a Python object of a DataElement
    if elm["Datatype"] == "BOOL":
        return bool(elm["Value"])
    elif elm["Datatype"] == "STRING":
        return str(elm["Value"])
    elif elm["Datatype"] == "I32":
        return int(elm["Value"])
    elif elm["Datatype"] == "DBL":
        return float(elm["Value"])
    raise ParsingError("unknown datatype: " + str(elm["Datatype"]))

def _parse_fullcycle(byte_string, add_data=None, need_masscal=False):
    '''Parses 'timecycle', 'intensity', 'mass_cal' and 'add_data' from bytes.

    @params
    - add_data a dictionary that will be filled or `None` if not needed
    - need_masscal if `False`, the 'mass_cal' returned will be None

    Parsing the AddData-cluster is much slower than parsing the intensity-array.
    Therefore, this may be skipped to improve performance, but is necessary if
    the 'mass_cal' is needed:

    performance (on a Intel Core i5, 8th Gen Ubuntu Linux):
      < 2 ms  when `add_data=None, need_masscal=False` (default)
      6-7 ms  when needing to parse the AddData-cluster (else)
    
    @returns a tuple ('timecycle', 'intensity', 'mass_cal')
    '''
    import numpy as np
    from collections import namedtuple

    tc_tup = namedtuple('timecycle',
            ['rel_cycle','abs_cycle','abs_time','rel_time', 'run', 'cpx'])
    ad_tup = namedtuple('add_data',
            ['value', 'name', 'unit', 'view'])
    mc_tup = namedtuple('masscal',
            ['mode', 'masses', 'timebins', 'cal_pars', 'cal_segs'])
    rv_tup = namedtuple('fullcycle',
            ['timecycle', 'intensity', 'mass_cal'])

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
    
    tc_cluster      = rd_arr1d(dtype=_f64, count=6)
    # SpecData #
    intensity       = rd_arr1d(dtype=_f32)
    sum_inty        = rd_arr1d(dtype=_f32)  # (discarded)
    mon_peaks       = rd_arr2d(dtype=_f32)  # (discarded)
    
    if add_data is None and not need_masscal:
        # skip costly parsing of Trace- and Add-Data cluster:
        return rv_tup(tc_tup(*tc_cluster), intensity, None)

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
        if add_data is None:
            # Note: the AddData is discarded, but if the caller
            #  needs the mass-cal then we have to do the parsing,
            #  because of the unknown length of arrays and strings..
            pass
        else:
            add_data[grp_name] = [ad_tup(*tup) for tup in zip_longest(data, descr, units, view)]

    # MassCal #
    mc_masses       = rd_arr1d(dtype=_f64)
    mc_tbins        = rd_arr1d(dtype=_f64)
    cal_paras       = rd_arr1d(dtype=_f64)
    segmnt_cal_pars = rd_arr2d(dtype=_f64)
    mcal_mode       = rd_single(dtype=_i16)
    mass_cal = mc_tup(mcal_mode, mc_masses, mc_tbins, cal_paras, segmnt_cal_pars)

    return rv_tup(tc_tup(*tc_cluster), intensity, mass_cal)

def follow_schedule(client, self, msg):
    log.debug(f"received: {msg.topic} | QoS: {msg.qos} | retain? {msg.retain}")
    with follow_schedule._lock:
        if msg.topic.startswith("DataCollection"):
            if not msg.payload:
                log.warn("empty ACQ_SRV_Schedule payload has cleared retained topic")
                self.sched_cmds.clear()
                return

            if msg.retain:
                # Note: we either have received a message that has been
                #  retained because of a new connection..
                payload = json.loads(msg.payload.decode())
                self.sched_cmds.clear()
                self.sched_cmds.extend(payload["CMDs"])
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
            self.sched_cmds.extend(payload["CMDs"])

follow_schedule.topics = ["DataCollection/Act/ACQ_SRV_Schedule", "IC_Command/Write/Scheduled"]
follow_schedule._lock = RLock()

def follow_state(client, self, msg):
    if not msg.payload:
        # empty payload will clear a retained topic
        return

    payload = json.loads(msg.payload.decode())
    state = payload["DataElement"]["Value"]
    log.debug(f"[{self}] new server-state: " + str(state))
    # replace the current state with the new element:
    self.server_state.append(state)

follow_state.topics = ["DataCollection/Act/ACQ_SRV_CurrentState"]

def follow_sourcefile(client, self, msg):
    payload = json.loads(msg.payload.decode())
    path = payload["DataElement"]["Value"]
    log.debug(f"[{self}] new source-file: " + str(path))
    # replace the current path with the new element:
    self.sf_filename.append(path)

follow_sourcefile.topics = ["DataCollection/Act/ACQ_SRV_SetFullStorageFile"]

def follow_set(client, self, msg):
    if not msg.payload:
        # empty payload will clear a retained topic
        return

    try:
        payload = json.loads(msg.payload.decode())
        *_, parID = msg.topic.split('/')
        if parID == "PTR_CalcConzInfo":
            return
        self.act_values[parID] = _parse_data_element(payload["DataElement"])
    except json.decoder.JSONDecodeError as exc:
        log.error(str(exc) + " :: " + str(msg.payload.decode()))
        raise
    except KeyError as exc:
        log.error(str(exc))
        pass
    except ParsingError as exc:
        log.error(f"while parsing [{parID}] :: {str(exc)}")
        pass

follow_set.topics = ["DataCollection/Set/#", "Automation/Act/#", "PTR/Act/#", "TPS/Act/#"]

def follow_cycle(client, self, msg):
    if not msg.payload:
        # empty payload will clear a retained topic
        return

    payload = json.loads(msg.payload.decode())
    current = int(payload["DataElement"]["Value"])
    # replace the current timecycle with the new element:
    self.overallcycle.append(current)

follow_cycle.topics = ["DataCollection/Act/ACQ_SRV_OverallCycle"]

# collect all follow-functions together:
_subscriber_functions = [fun for name, fun in list(vars().items())
    if callable(fun) and name.startswith('follow_')]


def on_disconnect(client, self):
    # reset internal queues to their defaults:
    self.sched_cmds     = MqttClient.sched_cmds
    self.server_state   = MqttClient.server_state
    self.sf_filename    = MqttClient.sf_filename
    self.overallcycle   = MqttClient.overallcycle
    self.act_values     = MqttClient.act_values


_NOT_INIT = object()


class MqttClient(MqttConn):

    sched_cmds   = deque([_NOT_INIT], maxlen=None)
    server_state = deque([_NOT_INIT], maxlen=1)
    sf_filename  = deque([""],        maxlen=1)
    overallcycle = deque([0],         maxlen=1)
    act_values   = dict()
    
    @property
    def is_connected(self):
        '''Returns `True` if connection to IoniTOF could be established.'''
        return (True
            and self.client.is_connected()
            and self.server_state[0] is not _NOT_INIT
            and (len(self.sched_cmds) == 0 or self.sched_cmds[0] is not _NOT_INIT))

    @property
    def is_running(self):
        '''Returns `True` if IoniTOF is currently acquiring data.'''
        return self.current_server_state == 'ACQ_Aquire'  # yes, there's still a typo :)

    @property
    def current_schedule(self):
        '''Returns a list with the upcoming write commands in ascending order.'''
        if not self.is_connected:
            return []

        current_cycle = self.overallcycle[0]
        filter_fun = lambda cmd: float(cmd["Schedule"]) > current_cycle
        sorted_fun = lambda cmd: float(cmd["Schedule"])

        return sorted(filter(filter_fun, self.sched_cmds), key=sorted_fun)

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
            return self.server_state[0]
        return "<unknown>"

    @property
    def current_sourcefile(self):
        '''Returns the path to the hdf5-file that is currently (or soon to be) written.
        
        May be an empty string if no sourcefile has yet been set.
        '''
        return self.sf_filename[0]

    @property
    def current_cycle(self):
        '''Returns the current 'AbsCycle' (/'OverallCycle').'''
        if self.is_connected:
            return self.overallcycle[0]
        return 0

    def __init__(self, host='127.0.0.1'):
        # this sets up the mqtt connection with default callbacks:
        super().__init__(host, _subscriber_functions, None, None, None, on_disconnect)

    def get(self, parID):
        '''Return the last value for the given 'parID' or None if not known.'''
        return self.act_values.get(parID)

    def set(self, parID, new_value, unit='-'):
        '''Set a 'new_value' to 'parID' in the DataCollection.'''
        if not self.is_connected:
            raise Exception(f"[{self}] no connection to instrument");

        topic, qos, retain = "DataCollection/Set/" + str(parID), 2, True
        log.info(f"setting '{parID}' ~> [{new_value}]")
        payload = {
            "Header":      _build_header(),
            "DataElement": _build_data_element(new_value, unit),
        }
        return self.client.publish(topic, json.dumps(payload), qos=qos, retain=retain)

    def filter_schedule(self, parID):
        '''Returns a list with the upcoming write commands for 'parID' in ascending order.'''
        return (cmd for cmd in self.current_schedule if cmd["ParaID"] == str(parID))

    def write(self, parID, new_value):
        '''Write a 'new_value' to 'parID' directly.'''
        if not self.is_connected:
            raise Exception(f"[{self}] no connection to instrument");

        topic, qos, retain = "IC_Command/Write/Direct", 2, False
        log.info(f"writing '{parID}' ~> [{new_value}]")
        cmd = _build_write_command(parID, new_value)
        payload = {
            "Header": _build_header(),
            "CMDs": [ cmd, ]
        }
        return self.client.publish(topic, json.dumps(payload), qos=qos, retain=retain)

    def schedule(self, parID, new_value, future_cycle):
        '''Schedule a 'new_value' to 'parID' for the given 'future_cycle'.

        If 'future_cycle' is actually in the past, the behaviour is defined by IoniTOF
        (most likely the command is ignored). The current cycle should be checked before
        and after running the schedule command to be actually in the future.
        '''
        if not self.is_connected:
            raise Exception(f"[{self}] no connection to instrument");

        topic, qos, retain = "IC_Command/Write/Scheduled", 2, False
        log.info(f"scheduling '{parID}' ~> [{new_value}] for cycle ({future_cycle})")
        cmd = _build_write_command(parID, new_value, future_cycle)
        payload = {
            "Header": _build_header(),
            "CMDs": [ cmd, ]
        }
        return self.client.publish(topic, json.dumps(payload), qos=qos, retain=retain)

    def schedule_filename(self, path, future_cycle):
        '''Start writing to a new .h5 file with the beginning of 'future_cycle'.'''
        # try to make sure that IoniTOF accepts the path:
        if self.host == '127.0.0.1':
            os.makedirs(os.path.dirname(path), exist_ok=True)
            try:
                with open(path, 'x'):
                    log.info("touched new file:", path)
            except FileExistsError as exc:
                log.error(f"new filename '{path}' already exists and will not be scheduled!")
                return

        # immediately check if we're not too late:
        if not future_cycle > self.overallcycle[0]:
            raise TimeoutError(f"while scheduling: the 'future_cycle' is already in the past")

        return self.schedule('ACQ_SRV_SetFullStorageFile', path.replace('/', '\\'), future_cycle)

    def start_measurement(self, path=None):
        '''Start a new measurement and block until the change is confirmed.

        If 'path' is not None, write to the given .h5 file.
        '''
        if path is None:
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
        if future_cycle is None or not future_cycle > self.overallcycle[0]:
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
            if self.overallcycle[0] >= int(cycle):
                break
            time.sleep(10e-3)
        else:
            return 0

        return self.overallcycle[0]

    def iter_specdata(self, add_data=None, need_masscal=False):
        '''Returns an iterator over the fullcycle-data as long as it is available.

        Elements will be buffered up to a maximum of 300 cycles. A `queue.Full`
        exception will be raised when the caller fails to consume the iterator!

        '''
        q = Queue(300)
        timeout_s = 60
        topic = "DataCollection/Act/ACQ_SRV_FullCycleData"
        qos = 2

        def callback(client, self, msg):
            q.put(_parse_fullcycle(msg.payload, add_data, need_masscal), timeout_s)

        # Note: when using a simple generator function like this, the following lines
        #  will not be excecuted until the first call to `next` on the iterator!
        #  this means, the callback will not yet be executed, the queue not filled 
        #  and we might miss the first cycles...
        self.client.message_callback_add(topic, callback)
        self.client.subscribe(topic, qos)
        yield q.get()  # waiting indefinitely to run..
        while self.is_running or not q.empty():
            yield q.get(timeout_s)

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

