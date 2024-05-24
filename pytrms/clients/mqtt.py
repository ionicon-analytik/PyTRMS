import os
import time
import logging
import json
from collections import deque
from itertools import cycle
from threading import Condition, RLock
from datetime import datetime as dt

import paho.mqtt.client as mqtt


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

def _parse_fullcycle(byte_string):
    import numpy as np
    from collections import namedtuple

    rv = namedtuple('fullcycle', ['timecycle', 'n_timebins', 'intensity'])
    _f32 = np.dtype(np.float32).newbyteorder('>')
    _f64 = np.dtype(np.float64).newbyteorder('>')
    _i32 = np.dtype(np.int32).newbyteorder('>')

    offset = 0
    tc = np.frombuffer(byte_string, dtype=_f64, count=6, offset=offset)
    offset += tc.nbytes
    _arr = np.frombuffer(s, dtype=_i32, count=1, offset=offset)
    offset += _arr.nbytes
    n_tb, = _arr
    inty = np.frombuffer(s, dtype=_f32, count=n_tb, offset=offset)
    offset += inty.nbytes
    # TODO :: t.b.c. ...

    return rv(tc, n_tb, inty)


def follow_schedule(client, self, msg):
    log.debug(f"received: {msg.topic} | QoS: {msg.qos} | retain? {msg.retain}")
    with follow_schedule._lock:
        if msg.topic.startswith("DataCollection"):
            # this is the schedule maintained by IoniTOF
            if not msg.payload:
                log.debug("empty ACQ_SRV_Schedule payload has cleared retained topic")
                self.sched_cmds.clear()
            elif msg.retain:
                # we have recently connected and received a message that has been retained
                payload = json.loads(msg.payload.decode())
                self.sched_cmds.clear()
                self.sched_cmds.extend(payload["CMDs"])
        if msg.topic.startswith("IC_Command"):
            # these are the fresh scheduling requests
            #payload = json.loads(msg.payload.decode())
            #self.sched_cmds.extend(payload["CMDs"])
            pass

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

follow_set.topics = ["DataCollection/Set/#", "PTR/Act/#", "TPS/Act/#"]

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

def on_connect(client, self, flags, rc):
    # Note: ensure subscription after re-connecting,
    #  wildcards are '+' (one level), '#' (all levels):
    default_QoS = 2
    topics = set()
    for subscriber in _subscriber_functions:
        topics.update(set(getattr(subscriber, "topics", [])))
    subs = sorted(zip(topics, cycle([default_QoS])))
    log.debug(f"[{self}] " + "\n   --> ".join(["subscribing to"] + list(map(str, subs))))
    rv = client.subscribe(subs)
    log.info(f"[{self}] successfully connected with {rv = }")

def on_subscribe(client, self, mid, granted_qos):
    log.info(f"[{self}] successfully subscribed with {mid = } | {granted_qos = }")

def on_publish(client, self, mid):
    log.debug(f"[{self}] published {mid = }")


_NOT_INIT = object()


class MqttClient:

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

    def filter_schedule(self, parID):
        '''Returns a list with the upcoming write commands for 'parID' in ascending order.'''
        return (cmd for cmd in self.current_schedule if cmd["ParaID"] == str(parID))

    def __init__(self, host='127.0.0.1'):
        # Note: circumvent (potentially sluggish) Windows DNS lookup:
        self.host = '127.0.0.1' if host == 'localhost' else str(host)
        # configure connection...
        self.client = mqtt.Client()
        self.client.on_connect   = on_connect
        self.client.on_subscribe = on_subscribe
        self.client.on_publish   = on_publish
        # ...subscribe to topics...
        for subscriber in _subscriber_functions:
            for topic in getattr(subscriber, "topics", []):
                self.client.message_callback_add(topic, subscriber)
        # ...pass this instance to each callback...
        self.client.user_data_set(self)
        # ...and connect to the server:
        self.connect()

    def connect(self, timeout_s=10):
        log.info(f"[{self}] connecting to mqtt broker at {self.host}")
        self.client.connect(self.host, 1883, 60)
        self.client.loop_start()  # runs in a background thread
        started_at = time.monotonic()
        while time.monotonic() < started_at + timeout_s:
            if self.is_connected:
                break

            time.sleep(10e-3)
        else:
            self.disconnect()
            raise TimeoutError(f"[{self}] no connection to IoniTOF");

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
        # reset internal queues to their defaults:
        self.sched_cmds     = MqttClient.sched_cmds
        self.server_state   = MqttClient.server_state
        self.sf_filename    = MqttClient.sf_filename
        self.overallcycle   = MqttClient.overallcycle
        self.act_values     = MqttClient.act_values

    def get(self, parID):
        '''Return the last value for the given 'parID' or None if not known.'''
        return self.act_values.get(parID)

    def set(self, parID, new_value, unit='-'):
        '''Set a 'new_value' to 'parID' in the DataCollection.'''
        if not self.is_connected:
            raise Exception(f"[{self}] no connection to instrument");

        topic, qos, retain = "DataCollection/Set/" + str(parID), 2, True
        payload = {
            "Header":      _build_header(),
            "DataElement": _build_data_element(new_value, unit),
        }
        return self.client.publish(topic, json.dumps(payload), qos=qos, retain=retain)

    def write(self, parID, new_value):
        '''Write a 'new_value' to 'parID' directly.'''
        if not self.is_connected:
            raise Exception(f"[{self}] no connection to instrument");

        topic, qos, retain = "IC_Command/Write/Direct", 2, False
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
        cmd = _build_write_command(parID, new_value, future_cycle)
        payload = {
            "Header": _build_header(),
            "CMDs": [ cmd, ]
        }
        return self.client.publish(topic, json.dumps(payload), qos=qos, retain=retain)

    def schedule_filename(self, path, future_cycle):
        '''Start writing to a new .h5 file with the beginning of 'future_cycle'.'''
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

    def __repr__(self):
        return f"<{self.__class__.__name__}[{self.host}]>"

