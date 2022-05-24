import json
import queue
from threading import Thread, Condition

from requests import ReadTimeout


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
        dt = 0
        while not self._stopped:
            self._cond.acquire()
            try:
                raw = self._client.get_traces()
            except ReadTimeout:
                self._cond.release()
                break

            dat = json.loads(raw)
            ts = dat['TimeCycle']['AbsTime']

            self.queue.put(dat)

            dt = 1.5 - ts % 1  # try to settle in between two full seconds
            print('wait for', dt)

            # This method releases the underlying lock, and then blocks until it is
            # awakened by a notify() or notify_all() call for the same condition variable
            # in another thread, or until the optional timeout occurs. Once awakened or
            # timed out, it re-acquires the lock and returns.  The return value is True
            # unless a given timeout expired, in which case it is False.
            if self._cond.wait(dt):
                break

