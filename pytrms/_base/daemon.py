"""@file daemon.py

"""
import os
import time
import logging
import abc

from ..clients import db_api, mqtt

log = logging.getLogger(__name__)


class Daemon(abc.ABC):

    def __init__(self, api_client, mqtt_client):
        self.api = api_client
        self.mq = mqtt_client

    @abc.abstractmethod
    def run_once(**kwargs):
        pass

    def run_forever(self, *, stop_on_error=True, **kwargs):
        """Run as a daemon.

        This checks for the clients to be connected and re-connects as neccessary.

        A CTRL-C signal (SIGINT) will stop the daemon.
        """
        retries = 0
        while True:
            try:
                if not self.mq.is_connected: self.mq.connect()
                if not self.api.is_connected: self.api.connect()

                log.info(f"connected to both {self.api} and {self.mq}")
                self.run_once(**kwargs)
            except (TimeoutError, AssertionError) as exc:
                log.error(str(exc))
                retries += 1
                log.warning(f"reconnection attempt ({retries})")
                time.sleep(1)
                continue
            except (db_api.ConnectionError, StopIteration) as exc:
                # Note: StopIteration from next(events)..
                log.error(str(exc))
                if stop_on_error and self.mq.is_connected:
                    log.warning("force-stopping instrument to preserve database consistency")
                    self.mq.stop_measurement()
                continue
            except KeyboardInterrupt:
                log.warning(f"terminated by user (KeyboardInterrupt)")
                return

