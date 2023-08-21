


def connect_(*args):

    from ..instrument import Instrument
    from .mockclient import MockClient
    from ..tracebuffer import TraceBuffer
    
    mock = MockClient()
    buffer = TraceBuffer(mock)

    return Instrument(mock, buffer)

