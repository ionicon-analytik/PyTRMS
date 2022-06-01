import json
import queue
from itertools import chain
from threading import Thread, Condition

from requests import ReadTimeout
import pandas as pd


def parse(response, trace='raw'):
    jsonized = json.loads(response)
    info = jsonized['TimeCycle']
    labview_ts = info['AbsTime']
    posix_ts = labview_ts - 2082844800
    ts = pd.Timestamp(posix_ts, unit='s')

    data = [list(info.values())] + [a['Data'] for a in jsonized['AddData']] + [jsonized[trace]]
    desc = [list(info.keys())] + [a['Desc'] for a in jsonized['AddData']] + [jsonized['masses']]
    chained_data = chain(*data)
    chained_desc = chain(*desc)

    return pd.Series(data=chained_data, index=chained_desc, name=ts)


class TraceBuffer(Thread):

    def __init__(self, client):
        Thread.__init__(self)
        self._client = client
        self._cond = Condition()
        self.queue = queue.Queue()
        self._stopped = False

    def stop_producing(self):
        try:
            self._cond.notify()
        except RuntimeError:
            self._stopped = True

    def run(self):
        poll = 0.2  # seconds
        last = 0xffffffffffffffff  # largest reasonable integer
        while not self._stopped:
            with self._cond:  #.acquire()
                raw = self._client.get_traces()

                jsonized = json.loads(raw)
                ts = jsonized['TimeCycle']['AbsTime']
                oc = jsonized['TimeCycle']['OverallCycle']
                if oc > last:
                    self.queue.put(parse(raw))
                last = oc

                # This method releases the underlying lock, and then blocks until it is
                # awakened by a notify() or notify_all() call for the same condition variable
                # in another thread, or until the optional timeout occurs. Once awakened or
                # timed out, it re-acquires the lock and returns.  The return value is True
                # unless a given timeout expired, in which case it is False.
                print('wait for', poll)
                if self._cond.wait(poll):
                    break

