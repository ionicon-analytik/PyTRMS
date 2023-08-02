from decorators import *


@eventinit
def example_init(db_api):
    print('initializing example...')

    return db_api.get('/api/parameters/32')


@eventhook('average')
def example_hook(db_api, json_object, initial_state):
    print('executing example...')

    print(db_api.get('/api/times/last'))
    print(json_object)
    print(initial_state)

