"""@file recorder.py

"""
import os
import sys
import pickle
import json
import time
import threading
import queue
import zipfile
from collections import namedtuple

from . import msg_info
from .._base.mqttclient import MqttClientBase
from ..clients.mqtt import _parse_data_element

# Note: 'self.messages' must be compatible with 'msg_info' (which can't be pickled)!
assert msg_info._fields == ('timestamp', 'topic', 'payload', 'qos', 'retain')


_fc_q = queue.Queue()
_sf_q = queue.Queue()
_sf_q_sentinel = object()

def record_msg(client, self, msg):
    if not self.is_running:
        return

    if msg.topic.endswith('FullCycleData') and msg.payload:
        # record in dedicated function:
        _fc_q.put(msg)
        return

    # Note: the 'msg.retain' flag can o.c. only be read on connect, so that's
    #  not indicative of the publisher's *intention* to publish retained (or not)!
    #  The retained topics have a retain flag, only if they were received retained.
    self.messages.append((msg.timestamp, msg.topic, msg.payload, msg.qos, msg.retain))

record_msg.topics = ["+/Act/#", "+/Set/#", "IC_Command/#"]

def record_sourcefile(client, self, msg):
    # AAAAAAAAACHTUNG: das hier ist keine Garantie, dass dieses sourcefile
    #  aktuell ist, weil das IoniTOF zu lahm beim starten ist:
    if not self.is_running:
        return

    # ...was dann zum Problem wird, wenn das 'prev' sourcefile einen Ordner
    # markiert, der Daten ueber 4 Tage enthaelt, wodurch 6 Gb gezippt werden!
    # Auch sonst nicht schoen, aber ich glaube, ich lasse es so, mir faellt
    # grad nichts besseres ein...

    if not msg.payload:
        return

    payload = json.loads(msg.payload.decode())
    fullpath = _parse_data_element(payload["DataElement"])
    _sf_q.put(fullpath)

record_sourcefile.topics = ["DataCollection/Act/ACQ_SRV_SetFullStorageFile"]

def fc_q_worker(self):
    _id = threading.get_ident()
    print(f'starting fc_q_worker thread[{_id}]...')
    while True:
        msg = _fc_q.get()
        # store the fullcycle-data separately in the zip-file:
        fc_count = self.fc_counter[0]
        self.fc_counter[0] += 1
        filename = f'data/fullcycle_{fc_count:05d}.dat'
        with self._z_lck:
            self.z.writestr(filename, msg.payload)
        retain = False
        # Note: must be compatible with 'msg_info' (which can't be pickled)!
        self.messages.append((msg.timestamp, msg.topic, filename, msg.qos, retain))
        _fc_q.task_done()

def sf_q_worker(self):
    _id = threading.get_ident()
    print(f'starting sf_q_worker thread[{_id}]...')
    # fetch the next..
    prev = _sf_q.get()
    while True:
        # ..and the overnext message:
        curr = _sf_q.get()

        # we got the curr[ent] and can pack the prev[ious]..
        directory = os.path.dirname(prev).replace('\\', '/')
        drive, fullpath = directory.split(':')
        arcname = '/'.join(['sources', drive.lower(), fullpath, ''])

        with self._z_lck:
            _pack_dir(self.z, directory, prefix=arcname)

        _sf_q.task_done()  # curr done!
        if curr is _sf_q_sentinel:
            _sf_q.task_done()  # prev done!
            prev = _sf_q.get()
        else:
            prev = curr


_subscriber_functions = [
    record_msg,
    record_sourcefile,
]


def _pack_dir(z, directory, prefix='master_recipe/'):
    # pack the directory recursively under prefix 'master_recipe'
    for dirname, dirs, files in os.walk(directory):
        for file in files:
            path = os.path.join(dirname, file)
            relpath = os.path.relpath(path, start=directory)
            z.write(path, arcname=prefix + relpath)


class Recorder(MqttClientBase):

    __README__ = """This is a replay of an AME measurement.

    Essentially, this captures the MQTT messages only and lets us replay
    them in the same order and with the same timing as originally published
    by the IoniTOF. The idea is to have *as close as a substitute* as
    possible to the original measurement to
    a) perform debugging and testing w/o a running instrument
    b) reproduce (byte-)exact results for Quality Assurance.

    To make things simple, this is a common zip-file with the file-extension
    '.REPLAY' and filename of the original recipe-directory. It can be simply
    dropped into any master-recipe-directory, where it should be picked up
    and automatically played by the AME_launcher.

    The only MQTT-topics that are specially handled are
    - ACQ_SRV_Stop_Meas ~> will stop the replay
    - FullCycleData ~> compressed and stored separately in ./data
    - ACQ_SRV_SetFullStorageFile ~> the source-file is required for analysis

    On replay, the ./sources shall be extracted into the *same location*
    as on the original machine, together with the folder-content, such that
    the AME-toolchain will find itself in a believable simulation.

    The needed content is that of the master-recipe-directory, copied from
    the sourcefile-folder. The results however - such as 'RAW_SEM.tsv' -,
    will also be "pre-emptively" copied to the sourcefile-folder. There is
    currently to convenient way to distinguish between what's a config-file
    and what belongs to the results. When the AME-toolchain is running, the
    result-files will simply be overwritten! To compare the original results,
    extract them to a different location from ./sources archive.
    """

    _z_lck = threading.RLock()

    @property
    def is_running(self):
        return self._is_running

    @is_running.setter
    def is_running(self, val):
        self._is_running = bool(val)
    
    _is_running = False

    def __init__(self, host='localhost', port=1883):
        super().__init__(host, port, _subscriber_functions, None, None, None)

        self.messages = list()
        self.fc_counter = [0]
        self.z = None
        self.is_running = True  # important to catch initially retained messages!

        t1 = threading.Thread(target=fc_q_worker, args=(self,), daemon=True)
        t1.start()

        t2 = threading.Thread(target=sf_q_worker, args=(self,), daemon=True)
        t2.start()

    def record(self, out_file, master_recipe):
        """Record a running measurement and pack into a replayable `out_file`.

        out_file - path to the archive to write
        master_recipe - path to a recipe-directory to include in the archive
        """
        # Note (to myself): to get a clean record, we'd like the initially
        #  retained messages to be caught! because this is a bit tricky the
        #  way this class is set up now, just prohibit another run:
        assert self.is_running, "called 'record' twice, but this is a one-shot instance"

        with zipfile.ZipFile(out_file, 'w', zipfile.ZIP_DEFLATED, compresslevel=2) as self.z:
            try:
                while True:
                    print(f'still alive: {_fc_q.qsize() = } | {_sf_q.qsize() = } | {len(self.messages) = }')
                    time.sleep(3)
            except KeyboardInterrupt:
                print('\ncancelled by user!')
                self.is_running = False

                print('waiting for zipfile being released..')
                _fc_q.join()

                print('waiting for the sourcefiles being compressed..')
                _sf_q.put(_sf_q_sentinel)
                _sf_q.join()

                print('writing messages to zip-file...')
                self.z.writestr('messages', pickle.dumps(self.messages))
                self.z.writestr('README', Recorder.__README__)
                print('packing recipe-directory to zip-file...')
                _pack_dir(self.z, master_recipe, prefix='master_recipe/')
            finally:
                self.z.close()

        self.z = None

