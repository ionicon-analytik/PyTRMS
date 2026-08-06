"""Tests for shared iter_specdata subscription handling."""

import queue

from pytrms.clients.mqtt import MqttClient


class _FakePahoClient:
    def __init__(self):
        self.callbacks = {}
        self.subscriptions = []
        self.unsubscriptions = []

    def message_callback_add(self, topic, callback):
        self.callbacks[topic] = callback

    def message_callback_remove(self, topic):
        self.callbacks.pop(topic, None)

    def subscribe(self, topic, qos):
        self.subscriptions.append((topic, qos))

    def unsubscribe(self, topic):
        self.unsubscriptions.append(topic)


def test_iter_specdata_queue_refcount():
    """Mirrors subscribe / finally refcount on MqttClient._iter_specdata_queues."""
    fake = _FakePahoClient()
    topic = MqttClient._iter_specdata_topic
    queues = []
    q1, q2 = queue.Queue(10), queue.Queue(10)

    for q in (q1, q2):
        if not queues:
            fake.subscribe(topic, 2)
        queues.append(q)

    assert len(fake.subscriptions) == 1
    assert fake.unsubscriptions == []

    queues.remove(q1)
    assert fake.unsubscriptions == []

    queues.remove(q2)
    if not queues:
        fake.unsubscribe(topic)
        fake.message_callback_remove(topic)

    assert len(fake.unsubscriptions) == 1
    assert fake.callbacks == {}
