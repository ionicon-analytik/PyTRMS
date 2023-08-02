import re
import logging
from collections import defaultdict

__all__ = ['eventinit', 'eventhook']


log = logging.getLogger(__name__)

_eventinits = dict()
_eventhooks = defaultdict(list)


def eventinit(fun):
    """
    Mark this function to be executed once before listening to events.

    The function is expected to have a single argument and will be
     called with a http-connection object of `class IoniConnect`.

    Any object returned from this function will be passed into all
     of the corresponding `eventhook`s defined in the same module. 
     An `eventinit` may only be defined once per module.
    """
    if fun.__code__.co_argcount != 1:
        raise Exception(f"eventinit must be callable like '{fun.__name__}(api)'")

    if fun.__module__ in _eventinits:
        raise Exception('_An `eventinit` may only be defined once per module')

    _eventinits[fun.__module__] = fun
    log.debug(f"added event-initializer '{fun.__module__}.{fun.__name__}()'")

    return fun


def eventhook(topic=None):
    """
    Mark this function to be executed on an API-event.

    The function is expected to have three arguments (e.g. `api, rep, state=None`)
     and will be called with an API-connection object, the json-representation of
     the event's subject and any initial state returned from the `eventinit`
     defined in the same module, respectively. A module may contain multiple
     `eventhook`s.

    If `topic` is given (e.g. 'timecycle', 'average updated', ...), listen for the
     specified event only. This may be a regular expression.
    """

    def decorator(fun):
        if fun.__code__.co_argcount != 3:
            raise Exception(f"eventhook must be callable like '{fun.__name__}(api, json_obj, state)'")

        fun._topic = topic
        fun._topic_re = re.compile('.*' + topic + '.*')  # be very loose with matching..

        _eventhooks[fun.__module__].append(fun)
        log.debug(f"added event-hook '{fun.__module__}.{fun.__name__}()'")

        return fun

    return decorator

