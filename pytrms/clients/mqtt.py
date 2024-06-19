import os
import time
import logging
import json
from functools import wraps
from itertools import cycle, chain, zip_longest
from collections import deque, namedtuple
import queue
from threading import Condition, RLock
from datetime import datetime as dt

from .._base.mqttclient import MqttClientBase


log = logging.getLogger(__name__)

__all__ = ['MqttClient', 'MqttClientBase', 'publisher', 'receiver']


def _publish_with_ack(client, *args, **kwargs):
    msg = client.publish(*args, **kwargs)
    msg.wait_for_publish(timeout=10)
    return msg


def publisher(to_publish=list(), qos=2, retain=False):
    """let a class automatically publish a subset of attributes directly to the mqtt broker.

    (class-decorator)

    wants the attributes ._client and ._topic from the sub-class.
    """
    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        if (self._publisher_init
          and name in self._published_attrs
          and self._client.is_connected):
            payload = getattr(self, name)
            _publish_with_ack(self._client, self._topic + "/" + name, payload,
                    self._publish_qos, self._publish_retain)


    def decorator(klass):
        @wraps(klass)
        def wrapper(*args, **kwargs):
            klass._publisher_init  = False
            klass._published_attrs = list(to_publish)
            klass._publish_qos     = int(qos)
            klass._publish_retain  = bool(retain)
            # replace the attribute-setter with our patch:
            klass.__setattr__ = __setattr__
            # wait until after __init__() to check for wanted attributes...
            inst = klass(*args, **kwargs)
            assert hasattr(inst, "_client"), f"decorator wants {__klass__}._client"
            assert hasattr(inst, "_topic"), f"decorator wants {__klass__}._topic"
            # ...and let everyone know, we're set:
            inst._publisher_init = True

            return inst
        return wrapper
    return decorator


def receiver(conversion_functions=dict()):
    """let a class converts a subset of its attributes before setting.

    (class decorator)
    
    `conversion_functions` dictionary with callables per attribute name
    """
    def __setattr__(self, name, value):
        if name in self._attr_converters:
            value = self._attr_converters[name](value)
        object.__setattr__(self, name, value)

    def decorator(klass):
        @wraps(klass)
        def wrapper(*args, **kwargs):
            klass._attr_converters = dict()
            klass.__setattr__ = __setattr__
            inst = klass(*args, **kwargs)

            return inst
        return wrapper
    return decorator


## >>>>>>>>    adaptor functions    <<<<<<<< ##

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

def _parse_fullcycle(byte_string, add_data=None, need_masscal=False):
    '''Parses 'timecycle', 'intensity', 'mass_cal' and 'add_data' from bytes.

    Important: the byteorder of the parsed arrays will be big-endian! This
     may be aligned if needed with the `.byteswap()`-method on the array,
     but is not automatically performed to avoid any extra copy.

    @params
    - add_data a dictionary that will be filled or `None` if not needed
    - need_masscal if `False`, the 'mass_cal' returned will be None

    Parsing the AddData-cluster is much slower than parsing the intensity-array!
     This may be skipped to improve performance, but is necessary for loading
     the 'mass_cal' anyway. For orientation:

    performance (on a Intel Core i5, 8th Gen Ubuntu Linux):
      < 2 ms  when `add_data=None, need_masscal=False` (default)
      6-7 ms  when needing to parse the AddData-cluster (else)
    
    @returns a tuple ('timecycle', 'intensity', 'mass_cal')
    '''
    import numpy as np

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


class FullCycle:

    add_data = dict()
    timecycle = None
    intensity = None
    mass_cal = None

    @staticmethod
    def load_bytes(byte_string):
        rv = FullCycle()
        rv.timecycle, rv.intensity, rv.mass_cal = _parse_fullcycle(byte_string,
            rv.add_data, need_masscal=True)
        return rv

    @property
    def ptr_reaction(self):
        rv = namedtuple('PTR_reaction', ['Udrift', 'pDrift', 'Tdrift', 'E_N', 'pi_index', 'tm_index'])
        value_list = [data.value for data in self.add_data["PTR-Reaction"]]  # may raise KeyError!

        return rv(*chain(map(float, value_list[:4]), map(int, value_list[4:])))


table_setting = namedtuple('mass_mapping', ['name', 'mass2value'])

class CalcConzInfo:

    tables = {
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
            cc.tables["primary_ions"].append(table_setting(str(li["PriIonSetName"]), list(zip(masses, values))))

        for li in j["DataElement"]["Value"]["TransSets"]["Transsets"]:
            if not li["Name"]:
                log.info(f'loaded ({len(cc.tables["transmission"])}) transmission settings')
                break

            masses = map(float, filter(lambda x: x > 0, li["Mass"]))
            values = map(float, li["Value"])
            # float(li["Voltage"])  # (not used)
            cc.tables["transmission"].append(table_setting(str(li["Name"]), list(zip(masses, values))))

        return cc


## >>>>>>>>    callback functions    <<<<<<<< ##

def follow_settings(client, self, msg):
    if not msg.payload:
        # empty payload will clear a retained topic
        return

    if not self.calcconzinfo[0] is _NOT_INIT:
        # nothing to do..
        return

    log.debug(f"updating tm-/pi-table from {msg.topic}...")
    self.calcconzinfo.append(CalcConzInfo.load_json(msg.payload.decode('latin-1')))

follow_settings.topics = ["PTR/Act/PTR_CalcConzInfo"]

def follow_schedule(client, self, msg):
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
    if state == "ACQ_Aquire":
        # signal to the relevant thread that we need an update:
        self.calcconzinfo.append(_NOT_INIT)

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
        log.error(f"{exc.__class__.__name__}: {exc} :: while processing [{msg.topic}] ({msg.payload})")
        raise
    except KeyError as exc:
        log.error(f"{exc.__class__.__name__}: {exc} :: while processing [{msg.topic}] ({msg.payload})")
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


_NOT_INIT = object()


class MqttClient(MqttClientBase):

    sched_cmds   = deque([_NOT_INIT], maxlen=None)
    server_state = deque([_NOT_INIT], maxlen=1)
    calcconzinfo = deque([_NOT_INIT], maxlen=1)
    sf_filename  = deque([""],        maxlen=1)
    overallcycle = deque([0],         maxlen=1)
    act_values   = dict()
    
    @property
    def is_connected(self):
        '''Returns `True` if connection to IoniTOF could be established.'''
        return (super().is_connected
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
        super().__init__(host, _subscriber_functions, None, None, None)
        log.debug(f"connection check ({self.is_connected}) :: {self.server_state = } / {self.sched_cmds = }");

    def disconnect(self):
        super().disconnect()
        log.debug(f"[{self}] has disconnected")
        # reset internal queues to their defaults:
        self.sched_cmds     = MqttClient.sched_cmds
        self.server_state   = MqttClient.server_state
        self.calcconzinfo   = MqttClient.calcconzinfo
        self.sf_filename    = MqttClient.sf_filename
        self.overallcycle   = MqttClient.overallcycle
        self.act_values     = MqttClient.act_values

    def get(self, parID):
        '''Return the last value for the given 'parID' or None if not known.'''
        return self.act_values.get(parID)

    def get_table(self, table_name):
        timeout_s = 10
        started_at = time.monotonic()
        try:
            while time.monotonic() < started_at + timeout_s:
                # confirm change of state:
                if not self.calcconzinfo[0] is _NOT_INIT:
                    return self.calcconzinfo[0].tables[table_name]
    
                time.sleep(10e-3)
            else:
                raise TimeoutError(f"[{self}] unable to retrieve calc-conz-info from PTR server");
        except KeyError as exc:
            raise KeyError(str(exc) + f", possible values: {list(CalcConzInfo.tables.keys())}")

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
        return _publish_with_ack(self.client, topic, json.dumps(payload), qos=qos, retain=retain)

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
        return _publish_with_ack(self.client, topic, json.dumps(payload), qos=qos, retain=retain)

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
        return _publish_with_ack(self.client, topic, json.dumps(payload), qos=qos, retain=retain)

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

    def iter_specdata(self, cycle_buffer=300):
        '''Returns an iterator over the fullcycle-data as long as it is available.

        Elements will be buffered up to a maximum of `cycle_buffer` cycles (default: 300).

        Important: when the buffer runs full, a `queue.Full` exception will be raised!
         Therefore, the caller should consume the iterator as soon as possible while the
         measurement is running.
        '''
        q = queue.Queue(cycle_buffer)
        topic = "DataCollection/Act/ACQ_SRV_FullCycleData"
        qos = 2

        def callback(client, self, msg):
            try:
                q.put_nowait(FullCycle.load_bytes(msg.payload))
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
        yield q.get()  # (waiting indefinitely for measurement to run)
        try:
            while self.is_running or not q.empty():
                # Note: Prior to 3.0 on POSIX systems, and for *all versions on Windows*,
                # if block is true and timeout is None, this operation goes into an
                # uninterruptible wait on an underlying lock. This means that no exceptions
                # can occur, and in particular a SIGINT will not trigger a KeyboardInterrupt!
                if q.full():
                    # re-raise what we swallowed in the callback..
                    raise queue.Full

                if not self.is_connected:
                    # no more data will come, so better prevent a deadlock:
                    break

                yield q.get()  # (blocks indefinitely, see above)

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

