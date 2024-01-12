import os
import time
import logging
import json
from collections import deque
from datetime import datetime as dt

import paho.mqtt.client as mqtt

from . import ionitof_url

log = logging.getLogger()

set_vals = deque([], maxlen=1000)
tc = dict()
ss = deque(["<unknown>"], maxlen=1)

def on_connect(client, userdata, flags, rc):
    print("connected:", str(rc))
    # Note: ensure subscription after re-connecting,
    #  wildcards are '+' (one level), '#' (all levels):
    client.subscribe("IC_Command/Write/Scheduled")
    client.subscribe("DataCollection/Act/ACQ_SRV_CurrentState")
    client.subscribe("DataCollection/Act/ACQ_SRV_CurrentTraceData")

def on_publish(client, userdata, mid):
    print("published:", mid)

def on_message(client, userdata, msg):
    print("received:", msg.topic, "QoS:", str(msg.qos))
    payload = json.loads(msg.payload.decode())
    set_vals.extend(payload["CMDs"])
    
def follow_state(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    state = payload["DataElement"]["Value"]
    ss.append(state)
    print("new server-state:", state)
    if state == "ACQ_JustStarted":
        tc.clear()
    if state == "ACQ_JustStopped":
        set_vals.clear()

def follow_tc(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    tc.update(payload["DataElement"]["Value"]["TimeCycle"])
    print(tc)
    # manually delete the outdated requests..
    outdated = []
    for elm in set_vals:
        current = tc[elm["SchedMode"]]
        future = float(elm["Schedule"])
        if current >= future:
            outdated.append(elm)
    for elm in outdated:
        set_vals.remove(elm)


class MQTTScheduler:

    @property
    def current_schedule(self):
        return sorted(set_vals, key=lambda x: float(x["Schedule"]))

    @property
    def current_server_state(self):
        return ss[0]

    @property
    def current_timecycle(self):
        return tc

    def __init__(self, host="localhost"):
        set_vals.clear()
        tc.clear()
        self.host = host
        self.client = mqtt.Client()
        self.client.user_data_set(set_vals)
        self.client.on_connect = on_connect
        self.client.on_publish = on_publish
        self.client.message_callback_add("IC_Command/Write/Scheduled", on_message)
        self.client.message_callback_add("DataCollection/Act/ACQ_SRV_CurrentState", follow_state)
        self.client.message_callback_add("DataCollection/Act/ACQ_SRV_CurrentTraceData", follow_tc)

    def connect(self):
        self.client.connect(self.host, 1883, 60)
        self.client.loop_start()  # runs in a background thread

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def __del__(self):
        self.disconnect()

    def _make_header(self):
        ts = dt.now()
        header = {
            "TimeStamp": {
                "Str": ts.isoformat(),
                "sec": ts.timestamp() + 2082844800,
            },
        }
        return header

    def push(self, parID, new_value, future_cycle):
        cmd = {
            "ParaID": str(parID),
            "Value": str(new_value),
            "Datatype": "DBL",
            "CMDMode": "Set",
            "SchedMode": "OverallCycle",
            "Schedule": str(future_cycle),
            "Index": -1,
        }
        if isinstance(new_value, bool):
            # Note: True is also instance of int!
            cmd.update({"Datatype": "BOOL", "Value": str(new_value).lower()})
        elif isinstance(new_value, str):
            cmd.update({"Datatype": "STR"})
        elif isinstance(new_value, int):
            cmd.update({"Datatype": "I32"})
        elif isinstance(new_value, float):
            cmd.update({"Datatype": "DBL"})
        payload = {
            "Header": self._make_header(),
            "CMDs": [ cmd, ]
        }
        self.client.publish("IC_Command/Write/Scheduled", json.dumps(payload))

    def push_filename(self, path, future_cycle):
        grace_time = 0  # how much time does IoniTOF need??
        return self.push('ACQ_SRV_SetFullStorageFile',
                path.replace('/', '\\'),
                future_cycle - grace_time)

    def find_scheduled(self, parID):
        matches = [cmd for cmd in set_vals if cmd["ParaID"] == str(parID)]
        return sorted(matches, key=lambda x: float(x["Schedule"]))

    def block_until(self, future_cycle):
        while len(tc) and tc["OverallCycle"] < int(future_cycle):
            time.sleep(.1)

