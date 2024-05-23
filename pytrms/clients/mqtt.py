import os
import time
import logging
import json
from collections import deque
from threading import Condition
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

def on_connect(client, self, flags, rc):
    log.info("connected: " + str(rc))
    # Note: ensure subscription after re-connecting,
    #  wildcards are '+' (one level), '#' (all levels):
    rc, mid = client.subscribe([
        ("DataCollection/Act/ACQ_SRV_OverallCycle",             2),
        ("IC_Command/Write/Scheduled",                          2),
        ("IC_Command/Write/Direct",                             2),
        ("DataCollection/Act/ACQ_SRV_CurrentState",             2),
        ("DataCollection/Act/ACQ_SRV_CurrentTraceData",         2),
        ("DataCollection/Act/ACQ_SRV_SetFullStorageFile",       2),
        ("DataCollection/Set/#",        2),
    ])
    print("subscribed (rc) @mid [{}]".format(rc, mid))

def on_subscribe(client, self, mid, granted_qos):
    print("subscribed ({}) with QoS: {}".format(mid, granted_qos))

def on_publish(client, self, mid):
    log.debug("published: " + str(mid))

def follow_schedule(client, self, msg):
    print(f"received: {msg.topic} | QoS: {msg.qos} | retain? {msg.retain}")
    if not msg.payload:
        # empty payload will clear a retained topic
        return

    if msg.topic.split('/')[-1] == "Scheduled":
        payload = json.loads(msg.payload.decode())
        self.commands.extend(payload["CMDs"])
    
def follow_state(client, self, msg):
    print("retained?", msg.retain)
    print("QoS-level?", msg.qos)
    if not msg.payload:
        # empty payload will clear a retained topic
        return

    payload = json.loads(msg.payload.decode())
    state = payload["DataElement"]["Value"]
    log.info("new server-state: " + str(state))
    # replace the current state with the new element:
    self.server_state.append(state)
    if state == "ACQ_JustStarted":
        self._tc_queue.clear()
    if state == "ACQ_JustStopped":
        self.commands.clear()

def follow_sourcefile(client, self, msg):
    print("retained?", msg.retain)
    payload = json.loads(msg.payload.decode())
    path = payload["DataElement"]["Value"]
    log.info("new source-file: " + str(path))
    # replace the current path with the new element:
    self.sf_filename.append(path)

def _parse_data_element(elm):
    # make a Python object of a DataElement
    if elm["Datatype"] == "BOOL":
        return bool(elm["Value"])
    elif elm["Datatype"] == "STRING":
        return str(elm["Value"])
    elif elm["Datatype"] == "I32":
        return int(elm["Value"])
    else:  # if elm["Datatype"] == "DBL":
        return float(elm["Value"])


def follow_set(client, self, msg):
    print("retained?", msg.retain, msg.topic)
    if not msg.payload:
        # empty payload will clear a retained topic
        return

    try:
        payload = json.loads(msg.payload.decode())
        *more, parID = msg.topic.split('/')
        self._datacollection_dict[parID] = _parse_data_element(payload["DataElement"])
    except json.decoder.JSONDecodeError:
        print(msg.payload.decode())
    except KeyError:
        pass  # probably cleared...

def follow_tc(client, self, msg):
    if not msg.payload:
        # empty payload will clear a retained topic
        return

    payload = json.loads(msg.payload.decode())
    current = int(payload["DataElement"]["Value"])
    log.debug("new timecycle " + str(current))
    # replace the current timecycle with the new element:
    self.overallcycle.append(current)
    # Note: this is the thread-safe variant for ONE thread
    #  waiting for the _tc_queue to be filled (may be empty):
    with self._tc_lock:
        self._tc_queue.append(current)
        self._tc_lock.notify()
    # manually delete the outdated requests..
    outdated = []
    for cmd in self.commands:
        future  = float(cmd["Schedule"])
        if current >= future:
            outdated.append(cmd)
    for cmd in outdated:
        self.commands.remove(cmd)


class MqttClient:
    commands     = deque([], maxlen=1000)
    server_state = deque([], maxlen=1)
    sf_filename  = deque([""], maxlen=1)
    overallcycle = deque([0], maxlen=1)  # never empty!
    _tc_queue    = deque([])  #, maxlen=1)  # maybe empty!
    _tc_lock     = Condition()
    _datacollection_dict = dict()
    
    @property
    def is_connected(self):
        '''Returns `True` if connection to IoniTOF could be established.'''
        return self.client.is_connected() and len(self.server_state)

    @property
    def is_running(self):
        '''Returns `True` if IoniTOF is currently acquiring data.'''
        return self.current_server_state == 'ACQ_Aquire'  # yes, there's still a typo :)

    @property
    def current_schedule(self):
        '''Returns a list with the upcoming write commands in ascending order.'''
        if self.is_connected:
            return sorted(self.commands, key=lambda x: float(x["Schedule"]))

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
        '''Returns the path to the hdf5-file that is currently (or soon to be) written.'''
        if self.is_connected:
            return self.sf_filename[0]
        return "<unknown>"

    @property
    def current_cycle(self):
        '''Returns the current 'AbsCycle' (/'OverallCycle').'''
        if self.is_connected:
            return self.overallcycle[0]
        return 0

    def filter_scheduled(self, parID):
        '''Returns a list with the upcoming write commands for 'parID' in ascending order.'''
        return (cmd for cmd in self.current_schedule if cmd["ParaID"] == str(parID))

    def __init__(self, host='127.0.0.1'):
        self.commands.clear()
        self.host = str(host)
        # configure connection...
        self.client = mqtt.Client()
        self.client.on_connect = on_connect
        self.client.on_subscribe = on_subscribe
        self.client.on_publish = on_publish
        # ...subscribe to topics...
        self.client.message_callback_add("IC_Command/Write/+",
                follow_schedule)
        self.client.message_callback_add("DataCollection/Act/ACQ_SRV_CurrentState",
                follow_state)
        self.client.message_callback_add("DataCollection/Act/ACQ_SRV_SetFullStorageFile",
                follow_sourcefile)
        self.client.message_callback_add("DataCollection/Set/#",
                follow_set)
        self.client.message_callback_add("DataCollection/Act/ACQ_SRV_OverallCycle",
                follow_tc)
        # ...pass this instance to each callback...
        self.client.user_data_set(self)
        # ...and connect to the server:
        self.connect()

    def connect(self, timeout_s=10):
        self.client.connect(self.host, 1883, 60)
        self.client.loop_start()  # runs in a background thread
        delta_s = 10e-3
        while not len(self.server_state):
            # wait for server_state to be populated by IoniTOF (retained topic):
            time.sleep(delta_s)
            timeout_s -= delta_s
            if timeout_s < 0:
                raise TimeoutError("no connection to IoniTOF");

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
        # reset internal queues to their defaults:
        self.commands          = MqttClient.commands
        self.server_state   = MqttClient.server_state
        self.sf_filename    = MqttClient.sf_filename
        self.overallcycle   = MqttClient.overallcycle
        self._tc_queue      = MqttClient._tc_queue
        self._datacollection_dict = MqttClient._datacollection_dict

    def get(self, parID):
        return self._datacollection_dict.get(parID)

    def set(self, parID, new_value, unit='-'):
        '''Set a 'new_value' to 'parID' in the DataCollection.'''
        if not self.is_connected:
            raise Exception("no connection to instrument");

        topic, qos, retain = "DataCollection/Set/" + str(parID), 2, True
        payload = {
            "Header":      _build_header(),
            "DataElement": _build_data_element(new_value, unit),
        }
        return self.client.publish(topic, json.dumps(payload), qos=qos, retain=retain)

    def write(self, parID, new_value):
        '''Write a 'new_value' to 'parID' directly.'''
        if not self.is_connected:
            raise Exception("no connection to instrument");

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
            raise Exception("no connection to instrument");

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
        delta_s = 0.1
        while timeout_s > 0:  # TODO :: this is much nicer using Recipe 12.13 ...
            if self.is_running:
                return
            
            timeout_s -= delta_s
            time.sleep(delta_s)
            
        raise TimeoutError("error starting measurement")

    def stop_measurement(self, future_cycle=None):
        '''Stop the current measurement and block until the change is confirmed.

        If 'future_cycle' is not None and in the future, schedule the stop command.'''
        if future_cycle is None or not future_cycle > self.overallcycle[0]:
            self.write('ACQ_SRV_Stop_Meas', True)
        else:
            self.schedule('ACQ_SRV_Stop_Meas', True, future_cycle)
        # confirm change of state...
        if future_cycle is not None:
            self.block_until(future_cycle)
        timeout_s = 10
        delta_s = 0.01
        while timeout_s > 0:  # TODO :: this is much nicer using Recipe 12.13 ...
            if not self.is_running:
                return
            
            timeout_s -= delta_s
            time.sleep(delta_s)
            
        raise TimeoutError("error stopping measurement")

    def block_until(self, cycle):
        '''Blocks the current thread until at least 'cycle' has passed or acquisition stopped.

        Returns the actual current cycle.
        '''
        while self.is_running:
            if self.overallcycle[0] >= int(cycle):
                return self.overallcycle[0]
            time.sleep(10e-3)
        
        return 0

    def iter_timecycles(self):
        '''Returns an iterator over the current TimeCycle/Automation.

        Calling next on the iterator will block until the next timecycle is available.
        '''
        while True:
            with self._tc_lock:
                while not len(self._tc_queue):
                    expired = self._tc_lock.wait(timeout=0.100)
                    if not self.is_running:
                        return
                    if not expired:
                        yield self._tc_queue.pop()
                # if not self.is_running:
                #     break
                # TODO :: ain't working this way...

