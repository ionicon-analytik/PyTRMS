import time
import json
import queue
from itertools import chain
from enum import Enum
from threading import Thread, Condition

import pandas as pd

from .helpers import convert_labview_to_posix, PTRConnectionError


def parse(response, trace='raw'):
    jsonized = json.loads(response)
    info = jsonized['TimeCycle']
    ts = convert_labview_to_posix(info['AbsTime'])

    data = [list(info.values())] + [a['Data'] for a in jsonized['AddData']] + [jsonized[trace]]
    desc = [list(info.keys())] + [a['Desc'] for a in jsonized['AddData']] + [jsonized['masses']]
    chained_data = chain(*data)
    chained_desc = chain(*desc)

    return pd.Series(data=chained_data, index=chained_desc, name=ts)


class TraceBuffer(Thread):

    poll = 0.2  # seconds

    class State(Enum):
        CONNECTING = -1
        IDLE = 0
        ACTIVE = 1

    def __init__(self, client):
        """'client' must provide a `.get_traces()` method that returns raw json data.
        """
        Thread.__init__(self)
        self.daemon = True
        self.client = client
        self.queue = queue.Queue()
        self.state = TraceBuffer.State.CONNECTING
        self._cond = Condition()

    def is_connected(self):
        return self.state != TraceBuffer.State.CONNECTING

    def is_idle(self):
        return self.state == TraceBuffer.State.IDLE

    def wait_for_connection(self, timeout=5):
        '''
        will raise a PTRConnectionError if not connected after `timeout` 
        '''
        waited = 0
        dt = 0.01
        while not self.is_connected():
            waited += dt
            if waited > timeout:
                raise PTRConnectionError('no connection to instrument')
            time.sleep(dt)

    def run(self):
        last = -753  # the year Rome was founded is never a valid cycle
        while True:
            #TODO :: das kann ja gar nicht funktionieren!?!?
            #if not self.is_connected():
            #    time.sleep(self.poll)
            #    continue

            time.sleep(self.poll)

            with self._cond:  # .acquire()`s the underlying lock
                raw = self.client.get_traces()
                #try:
                #except PTRConnectionError as exc:
                #    print(exc)
                #    break
                if not len(raw):
                    continue

                jsonized = json.loads(raw)
                ts = jsonized['TimeCycle']['AbsTime']
                oc = jsonized['TimeCycle']['OverallCycle']
                # the client returns the "current", i.e. last known trace data, even if
                # the machine is currently stopped. we want to definitely reflect this
                # idle state of the (actual) machine in our Python objects!
                # TODO :: *ideally*, the state is returned by a webAPI-call.. but as long
                # as this doesn't work perfectly, let's just do the next best thing and
                # watch the current cycle:
                if last < 0: last = oc

                if oc > last:
                    pd_series = parse(raw)
                    self.queue.put(pd_series)
                    self.state = TraceBuffer.State.ACTIVE
                else:
                    self.state = TraceBuffer.State.IDLE
                last = oc

                # This method releases the underlying lock, and then blocks until it is
                # awakened by a notify() or notify_all() call for the same condition variable
                # in another thread, or until the optional timeout occurs. Once awakened or
                # timed out, it re-acquires the lock and returns.  The return value is True
                # unless a given timeout expired, in which case it is False.
                if self._cond.wait(self.poll):
                    break

