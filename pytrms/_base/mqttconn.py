import os
import time
import logging
import json
from collections import deque
from itertools import cycle
from threading import Condition, RLock
from datetime import datetime as dt
from abc import ABC, abstractmethod

import paho.mqtt.client as mqtt


log = logging.getLogger()

__all__ = ['MqttConn']


def _on_connect(client, self, flags, rc):
    # Note: ensure subscription after re-connecting,
    #  wildcards are '+' (one level), '#' (all levels):
    default_QoS = 2
    topics = set()
    for subscriber in self._subscriber_functions:
        topics.update(set(getattr(subscriber, "topics", [])))
    subs = sorted(zip(topics, cycle([default_QoS])))
    log.debug(f"[{self}] " + "\n   --> ".join(["subscribing to"] + list(map(str, subs))))
    rv = client.subscribe(subs)
    log.info(f"[{self}] successfully connected with {rv = }")

def _on_subscribe(client, self, mid, granted_qos):
    log.info(f"[{self}] successfully subscribed with {mid = } | {granted_qos = }")

def _on_publish(client, self, mid):
    log.debug(f"[{self}] published {mid = }")

def _on_disconnect(client, self):
    log.debug(f"[{self}] has disconnected")


class MqttConn(ABC):

    @property
    @abstractmethod
    def is_connected(self):
        '''Returns `True` if connection to IoniTOF could be established.'''
        return (True
            and self.client.is_connected())

    def __init__(self, host, subscriber_functions,
            on_connect, on_subscribe, on_publish, on_disconnect):
        # Note: circumvent (potentially sluggish) Windows DNS lookup:
        self.host = '127.0.0.1' if host == 'localhost' else str(host)
        # configure connection...
        self.client = mqtt.Client()
        self.client.on_connect   = on_connect    if on_connect    else _on_connect
        self.client.on_subscribe = on_subscribe  if on_subscribe  else _on_subscribe
        self.client.on_publish   = on_publish    if on_publish    else _on_publish
        self._on_disconnect      = on_disconnect if on_disconnect else _on_disconnect
        # ...subscribe to topics...
        self._subscriber_functions = list(subscriber_functions)
        for subscriber in self._subscriber_functions:
            for topic in getattr(subscriber, "topics", []):
                self.client.message_callback_add(topic, subscriber)
        # ...pass this instance to each callback...
        self.client.user_data_set(self)
        # ...and connect to the server:
        self.connect()

    def connect(self, timeout_s=10):
        log.info(f"[{self}] connecting to mqtt broker at {self.host}")
        self.client.connect(self.host, 1883, 60)
        self.client.loop_start()  # runs in a background thread
        started_at = time.monotonic()
        while time.monotonic() < started_at + timeout_s:
            if self.is_connected:
                break

            time.sleep(10e-3)
        else:
            self.disconnect()
            raise TimeoutError(f"[{self}] no connection to IoniTOF");

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
        # may be used to reset internal queues to their defaults:
        self._on_disconnect(self.client, self)

    def __repr__(self):
        return f"<{self.__class__.__name__} @ {self.host}>"

