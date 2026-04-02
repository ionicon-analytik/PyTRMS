"""@file componist.py

"""
import time
import threading
import contextlib
import logging

from ..clients import db_api, mqtt

log = logging.getLogger(__name__)

__all__ = ['Componist']


@contextlib.contextmanager
def double_lock(api, mq):
    ## implement a "double-lock" for capturing either api- or mqtt-stop-mechanism
    import threading

    href = api.get_location("/api/measurements/current")  # may raise!

    def wait_for_mqtt():
        while mq.is_running:   # waits for other thread..
            time.sleep(50e-3)
        log.debug(f"[{threading.current_thread().name}] { mq.is_running = }, stopping api...")
        sc, loc = api.patch(href, { "isRunning": False })

    def wait_for_api():
        e = next(api.iter_events())  # waits for other thread..
        if not e.event.startswith("stop"):
            log.error(f"[{threading.current_thread().name}] unexpected event: '{e.event}'")
        log.debug(f"[{threading.current_thread().name}] got:{ e.event = }, stopping mqtt...")
        mq.stop_measurement()  # (no-op if already stopped)

    # use:
    t_api = threading.Thread(target=wait_for_api)
    t_mq = threading.Thread(target=wait_for_mqtt)
    try:
        t_api.start()
        t_mq.start()
        yield
    finally:
        t_api.join()
        t_mq.join()


class Componist:
    """
    The Great Componist: Conductor of Composition files for AME.

    This synchronizes the startup sequence between the HTTP-API
    and the PTR-Instrument (over MQTT). 
    """

    def __init__(self, host, port, *, mqtt_host=None, mqtt_port=None):
        mqtt_host = mqtt_host or host
        mqtt_port = mqtt_port or port

        self.api = db_api.IoniConnect(host, port)
        log.debug(f"{ self.api = }")
        assert self.api.is_connected, "no connection to database"

        self.mq = mqtt.MqttClient(mqtt_host, mqtt_port)
        log.debug(f"{ self.mq = }")
        assert self.mq.is_connected, "no connection to instrument"

    def run_once(self):
        api = self.api
        mq = self.mq

        # 1. subscribe, so we catch all further changes:
        events = api.iter_events(r'(new|start|stop) measurement')

        # 2. then initialize the current state of affairs:
        current_meas = api.get("/api/measurements/current")
        mq_is_running = mq.is_running  # avoid race-condition
        # two bools make 4 cases..
        if current_meas is None:
            if not mq_is_running:
                # OK.
                pass
            if mq_is_running:
                # OK: IoniTOF may run w/o AME.
                pass
        if current_meas is not None:
            if mq_is_running:
                # not OK! weren't *WE* the one supposed to be scheduling this!?
                raise RuntimeError("duplicate or crashed Componist left measurement running")
            if not mq_is_running:
                # not OK! let the api know about the actual state:
                log.warning(f"clearing current measurement slot from previous run")
                href = current_meas["_links"]["self"]["href"]
                sc, loc = api.patch(href, { "isRunning": False })
                assert sc == 204, f"unexpected status-code [{sc}] for {loc}"
                # Bug! THIS DOESN'T WORK, because the '.iter_events()'
                #  is (still) not being primed for some reason (this
                #  does not matter in the next call below, where we
                #  don't wait for ourselves). We can do without..
                #e = next(events)
                #assert e.event.startswith("stop"), f"unexpected event: '{e.event}'"
                assert api.get("/api/measurements/current") is None, "unexpected: meas/current not empty"

        # 3. good, all we gotta do now is wait:
        log.info("waiting for new measurement event...")
        # Note: meanwhile, IoniTOF may have been started and stopped
        #  multiple times manually! We're only interested in AME events..
        e = next(events)
        assert e.event.startswith("new"), f"unexpected event: {e.event}"
        #  ..however, we have no choice but to force-stop IoniTOF in
        #  this case to keep everything consistent:
        if mq.is_running:
            log.warning(f"force-stopping IoniTOF in response to {e.event}")
            mq.stop_measurement()

        # 4. the state is now 'new measurement' and we manage the start-up:
        current_meas = api.get(e.data)
        href = current_meas["_links"]["self"]["href"]
        master_recipe_dir = current_meas["recipeDirectory"]

        ##>>>>>> TODO
        log.info(master_recipe_dir)
        log.info("init. scheduling..."); time.sleep(1)
        # this is dumb: just ask the API!
        #composition_file = next_best_file(master_recipe_dir, 'Componist', ['', '.json'])
        #ctx.obj["componist"].start(None, composition_file, dry_run=dry_run)



        log.info("preparing recipe dir..."); time.sleep(1)
        #meas.new_folder()
        # OooooooooR ........ we COUUUUUULD wait for action0 : >  new sourcefile!
        #   ginge im Prinzip, ABER wer startet die action?
        #   wir habe vll. keinen launcher ?!
        # das *koennte* man vll. optional machen.. fuer's REPLAY ist's eh ein bischen unpraktisch


  #     mq.start_measurement(master_recipe_dir2recipe_h5_file)
#         A__ this may raise  if itof is already running!!
        mq.start_measurement()  # blocks..
        ##<<<<<<

        # confirm the state on the api:
        sc, loc = api.patch(href, { "isRunning": True })
        assert sc == 204, f"unexpected status-code [{sc}] for {loc}"
        e = next(events)
        assert e.event.startswith("start"), f"unexpected event: {e.event}"


        # main loop:
        #   keep scheduling..
        #   when 'stop measurement' event
        #    OR mq.is_running == False
        #   ~> clean up the state again and start over (in the daemon case)

        with double_lock(api, mq):
            while mq.is_running:
                log.info("keep scheduling..."); time.sleep(5)
                # siehe componist

        log.info("STOPPED")

