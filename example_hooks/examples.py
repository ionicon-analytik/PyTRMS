from decorators import *


@eventinit
def example_init(db_api):
    print('initializing example...')

    return dict(foo='bars')  # db_api.get('/api/parameters/32')


@eventhook('average')
def example_hook(db_api, json_object, initial_state):
    print('executing example...')
    
    avg = json_object

    for k, v in initial_state.items():
        print(f'initially: a {k} that {v}')

    href = avg["_links"]["self"]["href"]
    print('got:', href)

    j = db_api.get(href + '/sources')

    print(j["count"])

    for source in j["_embedded"]["sources"]:
        source["path"]

