print('TEST ENV TEST ENV TEST ENV TEST ENV TEST ENV')



def connect_():

    from ..instrument import Instrument
    from ..clients.mockclient import MockClient
    from ..tracebuffer import TraceBuffer
    
    mock = MockClient()
    buffer = TraceBuffer(mock)

    return Instrument(mock, buffer)

