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
timecycle    = deque([], maxlen=1)  # never empty!
_tc_queue    = deque([], maxlen=1)  # maybe empty!
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

def _build_command(parID, value, future_cycle=None):
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
        cmd.update({"Datatype": "STR"})
    elif isinstance(value, int):
        cmd.update({"Datatype": "I32"})
    elif isinstance(value, float):
        cmd.update({"Datatype": "DBL"})
    else:
        raise NotImplemented("unknown datatype")

    return cmd


def on_connect(client, userdata, flags, rc):
    log.info("connected: " + str(rc))
    # Note: ensure subscription after re-connecting,
    #  wildcards are '+' (one level), '#' (all levels):
    client.subscribe("IC_Command/Write/Scheduled")
    client.subscribe("DataCollection/Act/ACQ_SRV_CurrentState")
    client.subscribe("DataCollection/Act/ACQ_SRV_CurrentTraceData")

def on_publish(client, userdata, mid):
    log.debug("published: " + str(mid))

def follow_schedule(client, userdata, msg):
    log.debug(f"received: {msg.topic} | QoS: {msg.qos}")
    payload = json.loads(msg.payload.decode())
    commands.extend(payload["CMDs"])
    
def follow_state(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    state = payload["DataElement"]["Value"]
    log.info("new server-state: " + str(state))
    # replace the current state with the new element:
    server_state.append(state)
    if state == "ACQ_JustStarted":
        _tc_queue.clear()
    if state == "ACQ_JustStopped":
        commands.clear()

def follow_tc(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    tc = payload["DataElement"]["Value"]["TimeCycle"]
    log.debug("new timecycle " + str(tc))
    # replace the current timecycle with the new element:
    timecycle.append(tc)
    # Note: this is the thread-safe variant for ONE thread
    #  waiting for the _tc_queue to be filled (may be empty):
    with _tc_lock:
        _tc_queue.append(tc)
        _tc_lock.notify()
    # manually delete the outdated requests..
    outdated = []
    for cmd in commands:
        current =    tc[cmd["SchedMode"]]
        future  = float(cmd["Schedule"])
        if current >= future:
            outdated.append(cmd)
    for cmd in outdated:
        commands.remove(cmd)


class MqttClient:

    QoS_level = 1  # "at least once"

    @property
    def current_schedule(self):
        return sorted(commands, key=lambda x: float(x["Schedule"]))

    @property
    def current_server_state(self):
        return server_state[0]

    @property
    def current_timecycle(self):
        return timecycle[0]

    @property
    def is_running(self):
        return current_server_state == 'ACQ_Aquire'  # yes, there's still a typo :)

    def __init__(self, host=ionitof_host):
        commands.clear()
        timecycle.append({ "Cycle": 0, "OverallCycle": 0, "RelTime": 0, "AbsTime": 0 })
        self.host = host
        self.client = mqtt.Client()
        #self.client.user_data_set(commands)  # this ain't working..
        self.client.on_connect = on_connect
        self.client.on_publish = on_publish
        self.client.message_callback_add("IC_Command/Write/Scheduled", follow_schedule)
        self.client.message_callback_add("DataCollection/Act/ACQ_SRV_CurrentState", follow_state)
        self.client.message_callback_add("DataCollection/Act/ACQ_SRV_CurrentTraceData", follow_tc)
        # ..and connect to the server:
        self.connect()

    def connect(self):
        self.client.connect(self.host, 1883, 60)
        self.client.loop_start()  # runs in a background thread

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def __del__(self):
        self.disconnect()

    def write(self, parID, new_value):
        '''Write a 'new_value' to 'parID' directly.'''
        cmd = _build_command(parID, new_value)
        payload = {
            "Header": _build_header(),
            "CMDs": [ cmd, ]
        }
        return self.client.publish("IC_Command/Write/Direct", json.dumps(payload),
                qos=self.QoS_level)

    def schedule(self, parID, new_value, future_cycle):
        '''Schedule a 'new_value' to 'parID' for the given 'future_cycle'.'''
        if future_cycle is None:
            return self.write(parID, new_value)

        cmd = _build_command(parID, new_value, future_cycle)
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
            if timecycle[0]["OverallCycle"] >= int(future_cycle):
                return True
            time.sleep(.1)
        return False

    def iter_timecycles(self):
        '''Returns an iterator over the current TimeCycle/Automation.

        Calling next on the iterator will block until the next timecycle is available.
        '''
        while self.is_running:
            with _tc_lock:
                while not len(_tc_queue):
                    _tc_lock.wait()
                yield _tc_queue.pop()

