import os
import time
import logging
import json
from collections import deque
from threading import Condition
from datetime import datetime as dt

import paho.mqtt.client as mqtt

from . import ionitof_host

log = logging.getLogger()

__all__ = ['MqttClient']

commands     = deque([], maxlen=1000)
server_state = deque(["<unknown>"], maxlen=1)
sf_filename  = deque(["<unknown>"], maxlen=1)
overallcycle = deque([], maxlen=1)  # never empty!
_tc_queue    = deque([])  #, maxlen=1)  # maybe empty!
_tc_lock     = Condition()

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


def on_connect(client, userdata, flags, rc):
    log.info("connected: " + str(rc))
    default_qos = 1
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

def on_subscribe(client, userdata, mid, granted_qos):
    print("subscribed ({}) with QoS: {}".format(mid, granted_qos))

def on_publish(client, userdata, mid):
    log.debug("published: " + str(mid))

def follow_schedule(client, userdata, msg):
    log.info(f"received: {msg.topic} | QoS: {msg.qos} | retain? {msg.retain}")
    if msg.topic.split('/')[-1] == "Scheduled":
        payload = json.loads(msg.payload.decode())
        commands.extend(payload["CMDs"])
    
def follow_state(client, userdata, msg):
    print("retained?", msg.retain)
    payload = json.loads(msg.payload.decode())
    state = payload["DataElement"]["Value"]
    log.info("new server-state: " + str(state))
    # replace the current state with the new element:
    server_state.append(state)
    if state == "ACQ_JustStarted":
        _tc_queue.clear()
    if state == "ACQ_JustStopped":
        commands.clear()

def follow_sourcefile(client, userdata, msg):
    print("retained?", msg.retain)
    payload = json.loads(msg.payload.decode())
    path = payload["DataElement"]["Value"]
    log.info("new source-file: " + str(path))
    # replace the current path with the new element:
    sf_filename.append(path)

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

_datacollection_dict = dict()

def follow_set(client, userdata, msg):
    print("retained?", msg.retain, msg.topic)
    try:
        payload = json.loads(msg.payload.decode())
        *more, parID = msg.topic.split('/')
        _datacollection_dict[parID] = _parse_data_element(payload["DataElement"])
    except json.decoder.JSONDecodeError:
        print(msg.payload.decode())
    except KeyError:
        pass  # probably cleared...

def follow_tc(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    current = int(payload["DataElement"]["Value"])
    log.debug("new timecycle " + str(current))
    # replace the current timecycle with the new element:
    overallcycle.append(current)
    # Note: this is the thread-safe variant for ONE thread
    #  waiting for the _tc_queue to be filled (may be empty):
    with _tc_lock:
        _tc_queue.append(current)
        _tc_lock.notify()
    # manually delete the outdated requests..
    outdated = []
    for cmd in commands:
        future  = float(cmd["Schedule"])
        if current >= future:
            outdated.append(cmd)
    for cmd in outdated:
        commands.remove(cmd)


class MqttClient:

    QoS_level = 1  # "at least once"

    @property
    def is_connected(self):
        return self.client.is_connected()

    @property
    def current_schedule(self):
        return sorted(commands, key=lambda x: float(x["Schedule"]))

    @property
    def current_server_state(self):
        return server_state[0]

    @property
    def current_sourcefile(self):
        return sf_filename[0]

    @property
    def current_cycle(self):
        return overallcycle[0]

    @property
    def is_running(self):
        return self.current_server_state == 'ACQ_Aquire'  # yes, there's still a typo :)

    def __init__(self, host=ionitof_host):
        commands.clear()
        overallcycle.append(0)
        self.host = host
        self.client = mqtt.Client()
        #self.client.user_data_set(commands)  # this ain't working..
        self.client.on_connect = on_connect
        self.client.on_subscribe = on_subscribe
        self.client.on_publish = on_publish
        self.client.message_callback_add("IC_Command/Write/+", follow_schedule)
        self.client.message_callback_add("DataCollection/Act/ACQ_SRV_CurrentState", follow_state)
        self.client.message_callback_add("DataCollection/Act/ACQ_SRV_SetFullStorageFile", follow_sourcefile)
        self.client.message_callback_add("DataCollection/Set/#", follow_set)
        self.client.message_callback_add("DataCollection/Act/ACQ_SRV_OverallCycle", follow_tc)
        # ..and connect to the server:
        self.connect()

    def connect(self):
        self.client.connect(self.host, 1883, 60)
        self.client.loop_start()  # runs in a background thread

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def get(self, parID):
        return _datacollection_dict.get(parID)

    def set(self, parID, new_value, unit='-'):
        '''Set a 'new_value' to 'parID' in the DataCollection.'''
        payload = {
            "Header":      _build_header(),
            "DataElement": _build_data_element(new_value, unit),
        }
        topic = "DataCollection/Set/" + str(parID)
        self.client.publish(topic, json.dumps(payload), qos=2, retain=True)

    def write(self, parID, new_value):
        '''Write a 'new_value' to 'parID' directly.'''
        cmd = _build_write_command(parID, new_value)
        payload = {
            "Header": _build_header(),
            "CMDs": [ cmd, ]
        }
        return self.client.publish("IC_Command/Write/Direct", json.dumps(payload),
                qos=self.QoS_level, retain=False)

    def schedule(self, parID, new_value, future_cycle):
        '''Schedule a 'new_value' to 'parID' for the given 'future_cycle'.'''
        if future_cycle is None:
            return self.write(parID, new_value)

        cmd = _build_write_command(parID, new_value, future_cycle)
        payload = {
            "Header": _build_header(),
            "CMDs": [ cmd, ]
        }
        return self.client.publish("IC_Command/Write/Scheduled", json.dumps(payload),
                qos=self.QoS_level)

    def schedule_filename(self, path, future_cycle):
        '''Start writing to a new .h5 file with the beginning of 'future_cycle'.'''
        grace_time = 0  # how much time does IoniTOF need??
        return self.schedule('ACQ_SRV_SetFullStorageFile', path.replace('/', '\\'),
                future_cycle - grace_time)

    def start_measurement(self, path=None):
        '''Start a new measurement.

        If 'path' is not None, write to this .h5 file.'''
        if path is None:
            return self.write('ACQ_SRV_Start_Meas_Quick', True)
        else:
            return self.write('ACQ_SRV_Start_Meas_Record', path.replace('/', '\\'))

    def stop_measurement(self, future_cycle=None):
        '''Stop the current measurement.

        If 'future_cycle' is not None, schedule the stop command.'''
        return self.schedule('ACQ_SRV_Stop_Meas', True, future_cycle)

    def find_scheduled(self, parID):
        matches = [cmd for cmd in commands if cmd["ParaID"] == str(parID)]
        return sorted(matches, key=lambda x: float(x["Schedule"]))

    def block_until(self, future_cycle):
        '''Blocks the current thread until 'future_cycle' or the end of the measurement.'''
        while self.is_running:
            if overallcycle[0] >= int(future_cycle):
                return True
            time.sleep(.1)
        return False

    def iter_timecycles(self):
        '''Returns an iterator over the current TimeCycle/Automation.

        Calling next on the iterator will block until the next timecycle is available.
        '''
        while True:
            with _tc_lock:
                while not len(_tc_queue):
                    expired = _tc_lock.wait(timeout=0.100)
                    if not self.is_running:
                        return
                    if not expired:
                        yield _tc_queue.pop()
                # if not self.is_running:
                #     break
                # TODO :: ain't working this way...

