"""Tests for shared iter_specdata subscription handling."""

from types import SimpleNamespace
from unittest.mock import patch

from pytrms.clients.mqtt import _FullCycleDataHub, _SpecdataSubscription


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


def test_fullcycle_hub_refcount():
    fake = _FakePahoClient()
    mqtt_client = SimpleNamespace(client=fake)
    hub = _FullCycleDataHub(mqtt_client)

    sub_a = hub.attach(10)
    sub_b = hub.attach(10)
    assert len(fake.subscriptions) == 1
    assert fake.unsubscriptions == []

    hub.detach(sub_a)
    assert fake.unsubscriptions == []
    assert sub_b in hub._subs

    hub.detach(sub_b)
    assert len(fake.unsubscriptions) == 1
    assert fake.callbacks == {}


def test_fullcycle_hub_overrun_is_per_subscriber():
    fake = _FakePahoClient()
    mqtt_client = SimpleNamespace(client=fake)
    hub = _FullCycleDataHub(mqtt_client)
    sub = _SpecdataSubscription(1)
    hub._subs.add(sub)
    hub._subscribed = True

    fc = SimpleNamespace(timecycle=SimpleNamespace(abs_cycle=1))
    msg = SimpleNamespace(payload=b"x")

    with patch("pytrms.clients.mqtt._parse_fullcycle", return_value=fc):
        hub._on_message(fake, None, msg)
    assert not sub.overrun

    with patch("pytrms.clients.mqtt._parse_fullcycle", return_value=fc):
        hub._on_message(fake, None, msg)
    assert sub.overrun
