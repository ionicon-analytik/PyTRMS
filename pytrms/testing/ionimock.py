"""@file ionimock.py

"""
import os
import json
import time

import pickle
import shutil
import sched
import zipfile

import threading

import logging
from itertools import starmap

import paho.mqtt.publish as publish

from .._base.mqttclient import MqttClientBase
from ..clients.mqtt import _build_header, _build_data_element

from . import msg_info

assert msg_info._fields == ('timestamp', 'topic', 'payload', 'qos', 'retain')

log = logging.getLogger(__name__)


# prepare some common MQTT payloads...
the_truth = json.dumps({
    "Header": _build_header(),
    "DataElement": _build_data_element(True)
})
cycle0 = json.dumps({
    "Header": _build_header(),
    "DataElement": _build_data_element(0)
})
no_CMDs = json.dumps({
    "Header": _build_header(),
    "CMDs": []
})
no_source = json.dumps({
    "Header": _build_header(),
    "DataElement": _build_data_element('')
})
ACQ_Idle = json.dumps({
    "Header": _build_header(),
    "DataElement": _build_data_element("ACQ_Idle")
})
ACQ_Aquire = json.dumps({
    "Header": _build_header(),
    "DataElement": _build_data_element("ACQ_Aquire")
})
ACQ_SRV_SpecTime_ms = json.dumps({
    "Header": _build_header(),
    "DataElement": _build_data_element(1000.0)
})
CLEAR = ""


# prepare MQTT callbacks...
def follow_cmd_direct(client, self, msg):
    if not msg.payload:
        return

    j = json.loads(msg.payload.decode())
    parID = j["CMDs"][0]["ParaID"]
    value = j["CMDs"][0]["Value"]
    log.info(f"IC_Command: {parID} ~> {value}")

    if parID == "ACQ_SRV_Stop_Meas":
        self.emulate_stop()
    if parID == "ACQ_SRV_Start_Meas_Quick":
        self.emulate_start(path=None)
    if parID == "ACQ_SRV_Start_Meas_Record":
        self.emulate_start(path=value)


follow_cmd_direct.topics = ['IC_Command/Write/Direct']


class IoniMock(MqttClientBase):

#   @property
#   def is_running(self):
#       '''Returns `True` if IoniTOF is currently acquiring data.'''
#       return self.current_server_state == 'ACQ_Aquire'  # yes, there's a typo, plz keep it :)
    is_running = False

    def __init__(self, host='localhost', port=1883):
        super().__init__(host, port, [follow_cmd_direct])

        self.emulate_stop()  # initial reset
        self.publish_with_ack("DataCollection/Set/ACQ_SRV_SpecTime_ms",  ACQ_SRV_SpecTime_ms, qos=1, retain=True)
        log.info(f"[{self}] ready")

    def play(self, record_file, speed=1.0, dry_run=False):
        """ b) replay

        - fill the scheduler
        - wait for start per IC_Command ...
        - run the scheduler
        - wait for stop per IC_Command ...
        - cancel the whole thing
        - [repeat]
        """
        assert self.is_connected, "not connected"
        assert speed > 0, "speed must be positive"

        def publish_from_content(m, *, z=None):
            # reload bytes on-demand from content:
            payload = z.read(m.payload)
            # Note: overrides m.retain!
            self.publish_with_ack(m.topic, payload, qos=m.qos, retain=False)

        def print_value(m):
            value = json.loads(m.payload.decode())["DataElement"]["Value"]
            print(f'{m.timestamp:.6f} [{m.topic}] ~ {value = }')

        def print_partial(m):
            print(f'{m.timestamp:.6f} [{m.topic}] ~ {m.payload[:50]}')

        log.info(f'unzipping {record_file}...')
        z = zipfile.ZipFile(record_file, 'r')
        messages = pickle.loads(z.read('messages'))

        log.info(f'init scheduler...')
        now = time.monotonic()
        s = sched.scheduler()
        t0 = msg_info(*next(iter(messages))).timestamp
        for msg in starmap(msg_info, messages):

    # TODO :: hier noch die start/stop related Sachen + v.a. die source-file (D:/AMEData!) rausfischen!

            t = msg.timestamp
            rel_time = (t - t0) / speed

            if dry_run:
                s.enter(rel_time, 1, print_partial, argument=(msg,))
            elif isinstance(msg.payload, str):
                s.enter(rel_time, 1, publish_from_content, argument=(msg,), kwargs={'z': z})
            else:
                args = (msg.topic, msg.payload)
                kwargs = {
                    'qos': msg.qos,
                    'retain': True, # Note: overrides msg.retain!
                }
                s.enter(rel_time, 1, self.publish_with_ack, argument=args, kwargs=kwargs)

            if msg.topic.endswith('OverallCycle'):
                # just for feedback about what's happening...
                s.enter(rel_time, 1, print_value, argument=(msg,))

        if dry_run:
            print(f'\n*******************************\n')
            print(f'{ len(s.queue) = }')
            print(f'{time.monotonic() = }')
            print(f'{time.time() = }')
            print(f'{t0 = }')
            print(f'{time.monotonic() - t0 = }')

        if not self.is_running:
            self.emulate_start()
            self.wait_for_ack()
        while self.is_running and not s.empty():
            # send all pending MQTT messages for this timeslot...
            sleep_for = s.run(blocking=False)
            self.wait_for_ack()
            if sleep_for is None:
                self.emulate_stop()
                self.wait_for_ack()
                break

            # ...and take a short break:
            time.sleep(sleep_for)

    def emulate_start(self, path=None):
        # do what the IoniTOF would do when starting...
        self.publish_with_ack("DataCollection/Act/ACQ_SRV_CurrentState", ACQ_Aquire, qos=1, retain=True)

        if path is not None:
            path = path or "D:\\wie\\Dieter.h5"
            data = json.dumps({
                "Header": _build_header(),
                "DataElement": _build_data_element(path)
            })
            self.publish_with_ack("DataCollection/Act/ACQ_SRV_SetFullStorageFile", data, qos=1, retain=True)

        self.is_running = True
        if path is None:
            self.emulate_overallcycle()
        log.info(f"[{self}] started")

    def emulate_overallcycle(self):

        def x(mock, single_spec_duration_ms=1000.0):
            cycle = 0
            while mock.is_running:
                payload = json.dumps({
                    "Header": _build_header(),
                    "DataElement": _build_data_element(cycle)
                })
                self.publish_with_ack('DataCollection/Act/ACQ_SRV_OverallCycle', payload, qos=2, retain=True)
                cycle += 1
                time.sleep(single_spec_duration_ms * 1.0e-3)

        if self.t is None:
            self.t = threading.Thread(target=x, args=(self,), kwargs=None)
            self.t.start()
        log.debug(f"[{self}] started overallcycle {t.name}")

    t = None  # bg thread

    def emulate_stop(self):
        # do what the IoniTOF would do when stopping ~> set state to IDLE and clear schedule:
        self.publish_with_ack('DataCollection/Act/ACQ_SRV_CurrentState',        ACQ_Idle,  qos=1, retain=True)
        self.publish_with_ack('DataCollection/Act/ACQ_SRV_Schedule',            no_CMDs,   qos=1, retain=True)
        self.publish_with_ack('DataCollection/Act/ACQ_SRV_ScheduleClear',       the_truth, qos=1, retain=True)
        self.publish_with_ack('DataCollection/Act/ACQ_SRV_OverallCycle',        cycle0,    qos=1, retain=True)
        self.publish_with_ack('DataCollection/Act/ACQ_SRV_SetFullStorageFile',  no_source, qos=1, retain=True)
        self.is_running = False
        if self.t is not None:
            self.t.join()
            self.t = None
        log.info(f"[{self}] stopped")

    def __repr__(self):
        return f"{self.__class__.__name__} ({'running' if self.is_running else 'idle'})" # @ {self.host}:{self.port}

