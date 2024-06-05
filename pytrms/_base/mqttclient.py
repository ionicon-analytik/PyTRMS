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

from .ioniclient import IoniClientBase

log = logging.getLogger()

__all__ = ['MqttClientBase']


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


class MqttClientBase(IoniClientBase):

    @property
    @abstractmethod
    def is_connected(self):
        '''Returns `True` if connection to IoniTOF could be established.'''
        return (True
            and self.client.is_connected())

    def __init__(self, host, subscriber_functions,
            on_connect, on_subscribe, on_publish):
        super().__init__(host, port=1883)
        # configure connection...
        self.client = mqtt.Client(clean_session=True)
        # clean_session is a boolean that determines the client type. If True,
        # the broker will remove all information about this client when it
        # disconnects. If False, the client is a persistent client and
        # subscription information and queued messages will be retained when the
        # client disconnects.
        # The clean_session argument only applies to MQTT versions v3.1.1 and v3.1.
        # It is not accepted if the MQTT version is v5.0 - use the clean_start
        # argument on connect() instead.
        self.client.on_connect   = on_connect    if on_connect   is not None else _on_connect
        self.client.on_subscribe = on_subscribe  if on_subscribe is not None else _on_subscribe
        self.client.on_publish   = on_publish    if on_publish   is not None else _on_publish
        # ...subscribe to topics...
        self._subscriber_functions = list(subscriber_functions)
        for subscriber in self._subscriber_functions:
            for topic in getattr(subscriber, "topics", []):
                self.client.message_callback_add(topic, subscriber)
        # ...pass this instance to each callback...
        self.client.user_data_set(self)
        # ...and connect to the server:
        try:
            self.connect()
        except TimeoutError as exc:
            log.warn(f"{exc} (retry connecting when the Instrument is set up)")

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
            self.disconnect()
            raise TimeoutError(f"[{self}] no connection to IoniTOF");

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

