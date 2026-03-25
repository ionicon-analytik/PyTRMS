import os
import time
import logging
import json
from collections import deque, namedtuple
from itertools import cycle
from threading import Condition, RLock
from datetime import datetime as dt

import paho.mqtt.client

log = logging.getLogger(__name__)

__all__ = ['MqttClientBase']


def _on_connect(client, self, flags, rc):
    # ensure subscription on each re-connect

    topics = set()
    for subscriber in self._subscriber_functions:
        topics.update(set(getattr(subscriber, "topics", [])))

    # Note: quality-of-service level 2 increases overhead!
    #  However, the actual level depends on what the publishing
    #  side is willing to do and may be lower:
    default_QoS = 2
    subs = sorted(zip(topics, cycle([default_QoS])))
    log.debug(f"[{self}] " + "\n   --> ".join(["subscribing to"] + list(map(str, subs))))
    client.subscribe(subs)
    log.info(f"[{self}] successfully connected")


def _on_subscribe(client, self, mid, granted_qos):
    log.info(f"[{self}] subscribed | {granted_qos = }")


def _on_publish(client, self, mid):
    log.debug(f"[{self}] published {mid = } | #pending messages: ({len(self._mid_ticklist)})")
    try:
        self._mid_ticklist.remove(mid)
    except KeyError:
        log.warning(f"mid ({mid}) missing in ticklist: did you not use .publish_with_ack?")


def _exception_safe(callback_fun):
    # rest assured, that we never throw inside callbacks!

    cb_name = callback_fun.__code__.co_name
    cb_argc = callback_fun.__code__.co_argcount
    short_payload = lambda s: s[:50] + ('...' if len(s) > 50 else '')

    assert cb_argc == 3, "subscriber callback must have arguments (client, obj, msg)"

    def exception_safe_callback_wrapper(client, data, msg):
        try:
            callback_fun(client, data, msg)
        except Exception as exc:
            log.warning(f"unhandled {exc.__class__.__name__}: {exc} "
                      + f"in callback {cb_name}({msg.topic}, <obj>, {short_payload(msg.payload)})")
            pass
        except:
            log.warning(f"exception unhandled "
                      + f"in callback {cb_name}({msg.topic}, <obj>, {short_payload(msg.payload)})")
            pass

    return exception_safe_callback_wrapper


class MqttClientBase:
    """Mix-in class that supplies basic MQTT-callback functions.

    Implements part of the `IoniClientBase` interface.
    """

    @property
    def is_connected(self):
        '''Returns `True` if connected to the server.

        Note: This property will be polled on initialization.
         Subclasses should return `True` if a connection could be established!
        '''
        return self.client.is_connected()

    def __init__(self, host, port, subscriber_functions, *legacy_Nones):
        if len(legacy_Nones):
            log.warning("custom callbacks are deprecated")

        # Note: circumvent (potentially sluggish) Windows DNS lookup:
        self.host = '127.0.0.1' if host == 'localhost' else str(host)
        self.port = int(port)

        assert len(subscriber_functions) > 0, "no subscribers: for some unknown reason this causes disconnects"

        # Note: Version 2.0 of paho-mqtt introduced versioning of the user-callback to fix
        #  some inconsistency in callback arguments and to provide better support for MQTTv5.
        #  VERSION1 of the callback is deprecated, but is still supported in version 2.x.
        #  If you want to upgrade to the newer version of the API callback, you will need
        #  to update your callbacks:
        paho_version = int(paho.mqtt.__version__.split('.')[0])
        if paho_version == 1:
            self.client = paho.mqtt.client.Client(clean_session=True)
        elif paho_version == 2:
            self.client = paho.mqtt.client.Client(paho.mqtt.client.CallbackAPIVersion.VERSION1,
                    clean_session=True)
        else:
            # see https://eclipse.dev/paho/files/paho.mqtt.python/html/migrations.html
            raise NotImplementedError("API VERSION2 for MQTTv5 (use paho-mqtt 2.x or implement user callbacks)")

        # clean_session is a boolean that determines the client type. If True,
        # the broker will remove all information about this client when it
        # disconnects. If False, the client is a persistent client and
        # subscription information and queued messages will be retained when the
        # client disconnects.
        # The clean_session argument only applies to MQTT versions v3.1.1 and v3.1.
        # It is not accepted if the MQTT version is v5.0 - use the clean_start
        # argument on connect() instead.
        self.client.on_connect   = _on_connect
        self.client.on_subscribe = _on_subscribe
        self.client.on_publish   = _on_publish
        # ...subscribe to topics...
        self._subscriber_functions = list(subscriber_functions)
        for subscriber in self._subscriber_functions:
            for topic in getattr(subscriber, "topics", []):
                self.client.message_callback_add(topic, _exception_safe(subscriber))
        # ...pass this instance to each callback...
        self.client.user_data_set(self)
        # ...and connect to the server:
        try:
            self.connect()
        except TimeoutError as exc:
            log.warning(f"{exc} (retry connecting when the instrument is set up)")

    def connect(self, timeout_s=10):
        log.info(f"[{self}] connecting to MQTT broker...")
        self.client.connect(self.host, self.port, timeout_s)
        self.client.loop_start()  # runs in a background thread
        started_at = time.monotonic()
        while time.monotonic() < started_at + timeout_s:
            if self.is_connected:
                break

            time.sleep(10e-3)
        else:
            self._mid_ticklist.clear()  # no reason to wait in disconnect..
            self.disconnect()
            raise TimeoutError(f"[{self}] no connection to broker")

    def publish_with_ack(self, topic, data, **kwargs):
        """Subclasses should use this method wrapper for publishing through the client.

        This handles the problem of lost messages on early exit and the
        clearing of retained topics when used together with the
        `.disconnect()` method before exiting the application.
        """
        # CAVEAT: "[..] waiting for publish is really waiting for
        #  **transport-level state advancement**, not end-to-end
        #  success! Why wait at all? Because if no PUBACK arrives,
        #  Eclipse Paho keeps the packet inflight and retransmits
        #  after reconnect or retry interval. [..] But even that
        #  only works if: the client persists session state correctly,
        #  packet ids survive restart, reconnect happens, and
        #  retry policy is implemented.
        #  *A crashed publisher without persistence loses unsent
        #   guarantees immediately!*" (out of the chatgippitty)
        msg = self.client.publish(topic, data, **kwargs)
        #msg.wait_for_publish(timeout=timeout_s)  # No!
        # if we happen to be in a callback, the mqtt protocol loop
        # hangs forever, until PUBACK is handled!
        # the correct place for this is actually in `on_publish`:
        self._mid_ticklist.add(msg.mid)

        if len(data) and kwargs.get("retain", False):
            self._retained_set.add(topic)

        return msg  # caller may check msg.is_published() ...

    _mid_ticklist = set()
    _retained_set = set()

    def disconnect(self, clear_retained=True, timeout_s=10):
        if clear_retained:
            log.info(f"clearing ({len(self._retained_set)}) retained topics...")
            for topic in self._retained_set:
                self.publish_with_ack(topic, b"", qos=1, retain=True)

        self._retained_set.clear()

        log.info(f"wait for pending messages...")
        started_at = time.monotonic()
        while time.monotonic() < started_at + timeout_s:
            if len(self._mid_ticklist) == 0:
                break

            time.sleep(10e-3)
        else:
            log.error(f"timeout: there were ({len(self._mid_ticklist)}) messages left unpublished")

        self._mid_ticklist.clear()

        self.client.loop_stop()
        self.client.disconnect()
        log.info(f"[{self}] successfully disconnected!")

    def __repr__(self):
        return f"<{self.__class__.__name__} @ {self.host}[:{self.port}]>"

