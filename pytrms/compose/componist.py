"""@file componist.py

"""
import os
import time
import threading
import contextlib
import logging
from collections import deque
from functools import partial
from itertools import islice

from .composition import Composition
from ..clients import db_api, mqtt

log = logging.getLogger(__name__)

__all__ = ['Componist']


@contextlib.contextmanager
def double_lock(api, mq):
    ## implement a "double-lock" for capturing either api- or mqtt-stop-mechanism
    ## by running two inter-dependent threads that each wait on the respective case
    import threading
    from collections import deque

    href = api.get_location("/api/measurements/current")  # may raise!
    _go = deque([1], maxlen=1)

    def wait_for_mqtt():
        while mq.is_running:   # waits for other thread..
            time.sleep(50e-3)
        log.debug(f"[{threading.current_thread().name}] { mq.is_running = }, stopping api...")
        _go.clear()
        try:
            api.patch(href, { "isRunning": False })  # (emits 'stop measurement')
        except db_api.ConnectionError:
            # API is down, so will be the other thread..
            pass

    def wait_for_api():
        stop_event = api.iter_events("stop measurement")
        try:
            e = next(stop_event)  # waits for other thread..
            log.debug(f"[{threading.current_thread().name}] got:{ e.event = }, stopping mqtt...")
            _go.clear()
        except StopIteration:
            log.warning(f"API seems down, clearing double_lock by force-stopping instrument")
        mq.stop_measurement()  # (no-op if already stopped)

    # use:
    t_api = threading.Thread(target=wait_for_api)
    t_mq = threading.Thread(target=wait_for_mqtt)
    try:
        t_api.start()
        t_mq.start()
        yield _go
    finally:
        t_api.join()
        t_mq.join()


def _make_buffered_schedule_fun(mqtt_client):
    '''
    returns: a callable 'schedule_fun(parID, value, schedule_cycle)'
    usage:
      fun = make_fun()
      fun(par_id, value, future_cycle)
      fun(par_id, value, future_cycle)
       ...
      fun()  ~> sentinel, joins thread
    '''
    q = deque()
    b = threading.BoundedSemaphore()

    def consumer():
        nonlocal q

        while len(q) or b.acquire():  # blocks...

            adjusted_batch_size = max(10, int(0.1 * len(q)))

            # by splitting the batch, we could also recover from
            #  being too late to schedule it!
            batch = islice(q, adjusted_batch_size)
            try:
                mqtt_client.schedule_many(batch, on_missed_cycle_raise=True)
            except ValueError:
                # some funny guy queued a sentinel :)
                break
            except TimeoutError:
                raise # or recover..

            # collect the remainder (even items appended in the meantime):
            q = deque(islice(q, adjusted_batch_size, None))
            # sleep to reach throughput..
            # TODO :: muss man rumprobieren! ist jetzt 10 alle 2 sekunden erst mal..
            # throughput_per_sec=5
            buffer_time_sec = 2 # adjusted_batch_size / throughput_per_sec
            time.sleep(buffer_time_sec)

    t = threading.Thread(target=consumer)
    t.daemon = False
    t.start()
    log.debug(f"started consumer {t}")

    def s_fun(*arg_tuple):
        assert t.is_alive(), f"consumer thread is dead, instrument running? ({t.ident=})"
        q.append(arg_tuple)
        try:
            b.release()
        except ValueError:
            # already released, batch still processing..
            pass
        if not arg_tuple:
            # sentinel..
            t.join()

    return s_fun


class Componist:
    """
    The Great Componist: Conductor of Composition files for AME.

    This synchronizes the startup sequence between the HTTP-API
    and the PTR-Instrument (over MQTT). 
    """

    def __init__(self, api_client, mqtt_client):
        self.api = api_client
        self.mq = mqtt_client

    def run_forever(self):
        """Run the Componist as a daemon.

        This checks for the clients to be connected and re-connects as neccessary.

        A CTRL-C signal (SIGINT) will stop the daemon.
        """
        retries = 0
        while True:
            try:
                if not self.mq.is_connected: self.mq.connect()
                if not self.api.is_connected: self.api.connect()

                log.info(f"connected to both {self.api} and {self.mq}")
                self.run_once()
            except (TimeoutError, AssertionError) as exc:
                log.error(str(exc))
                retries += 1
                log.warning(f"reconnection attempt ({retries})")
                continue
            except (db_api.ConnectionError, StopIteration) as exc:
                # Note: StopIteration from next(events)..
                log.error(str(exc))
                if self.mq.is_connected:
                    log.warning("force-stopping instrument to preserve database consistency")
                    self.mq.stop_measurement()
                continue
            except KeyboardInterrupt:
                log.warning(f"terminated by user (KeyboardInterrupt)")
                return

    def run_once(self):
        """Initialize the start-sequence and wait for a 'new measurement' event.

        Keeps scheduling until either a 'stop measurement' event is received or
        the instrument is forcibly stopped. The instrument is put under control
        of the Componist while this method is blocking.
        """
        foresight_runs = 10

        # 1. then initialize the current state of affairs:
        current_meas = self.api.get("/api/measurements/current")
        mq_is_running = self.mq.is_running  # avoid race-condition
        # two bools make 4 cases..
        if current_meas is None:
            if not mq_is_running:
                # OK.
                pass
            if mq_is_running:
                # OK: IoniTOF may run w/o AME.
                pass
        if current_meas is not None:
            current_href = current_meas["_links"]["self"]["href"]
            if mq_is_running:
                # not OK! weren't *WE* the one supposed to be scheduling this!?
                hint = (' hint: to clean up, stop IoniTOF and use '
                    + '`POST ' + current_href + ' { "isRunning": "false" }`)')
                raise RuntimeError("duplicate or crashed Componist left measurement running!" + hint)
            if not mq_is_running:
                # not OK! let the api know about the actual state:
                log.warning(f"clearing current measurement slot from previous run")
                sc, loc = self.api.patch(current_href, { "isRunning": False })
                assert sc == 204, f"unexpected status-code [{sc}] for {loc}"
                assert self.api.get("/api/measurements/current") is None, "unexpected: meas/current not empty"

        # 2. subscribe, so we catch all further changes:
        events = self.api.iter_events(r'(new|start|stop) (measurement|result)')

        # 3. good, all we gotta do now is wait:
        log.info("waiting for new measurement event...")
        e = next(events)
        # Note: meanwhile, IoniTOF may have been started and stopped
        #  multiple times manually! We're only interested in AME events..
        assert e.event == "new measurement", f"unexpected event: {e.event}"
        j = self.api.get(e.data)
        meas_ref = j["_links"]["self"]["href"]
        recipe_ref = j["_links"]["describedby"]["href"]
        #  ..however, we have no choice but to force-stop IoniTOF in
        #  this case to keep everything consistent:
        if self.mq.is_running:
            log.warning(f"force-stopping IoniTOF in response to {e.event}")
            self.mq.stop_measurement()

        # 4. the state is now 'new measurement' and we manage the start-up:
        log.info("waiting for new result event...")
        e = next(events)
        assert e.event == "new result", f"unexpected event: {e.event}"
        j = self.api.get(e.data)
        result_path = j["path"]

        j = self.api.get(recipe_ref + "/files")
        names = (f["name"] for f in j["_embedded"]["files"])
        # this may raise! the recipe must have exactly one Composition file:
        comp_name = next(name for name in names if name.startswith("Composition"))
        with self.api.open(recipe_ref + "/files", name=comp_name) as f:
            composition = Composition.load(f)

        log.info("initialize the schedule...")
        sched_fun = _make_buffered_schedule_fun(self.mq)
        sched_coro = composition.schedule_routine(sched_fun, foresight_runs=foresight_runs)
        sched_coro.send(0)  # i.e. the self.mq.current_cycle!

        sf_path = result_path + os.path.basename(result_path) + ".h5"
        self.mq.start_measurement(sf_path)  # blocks..

        # confirm the state on the api:
        sc, loc = self.api.patch(meas_ref, { "isRunning": True })
        assert sc == 204, f"unexpected status-code [{sc}] for {loc}"
        e = next(events)
        assert e.event == "start measurement", f"unexpected event: {e.event}"
        # and keep scheduling!
        with double_lock(self.api, self.mq) as go:
            while go:
                wake_cycle = sched_coro.send(self.mq.current_cycle)
                log.info("next schedule refill at {wake_cycle=}...")
                self.mq.block_until(wake_cycle)

        log.info("STOPPED")
        sched_fun()

