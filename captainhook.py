
## TODO :: captain hook !
#
#    hier kommt ein "executor" hin!
#
#     lade hook-funktionen aus Python module
#     ..markiert mit gewuenschtem event
#     ..und die werden dann ausgefuerht
#     ..ganz genau wie die AME plugins (nur in Python)
#    => das ist dann die Blaupause fuer die AME-execution!
#
#   und man kann alle moeglichen hook-skripte in einen Ordner schmeissen und draus laden..
#   ..oder dann eben gesammelt auf eine ganze reihe von averages ausfuehren!
#
#  so stell ich mir das vor.

# ein generator fuer ... averages?
# die werden alle abgearbeitet
# kommen von events oder von einer selection /api/averages?since=2023-01-19
##
import os
import sys
from glob import iglob
import importlib.util
import logging
from itertools import chain

# NOTE: must be called *before* any loggers in upcoming imports are defined:
logging.basicConfig(level=logging.WARN)

from pytrms.clients.db_api import IoniConnect
from pytrms.clients.ssevent import SSEventListener

from pytrms.clients import ionitof_url
from pytrms.clients import database_url


from decorators import _eventinits as eventinits
from decorators import _eventhooks as eventhooks


log = logging.getLogger(__name__)

log.info('ready to rumble')

print('scanning directory', os.getcwd(), 'example_hooks')

# TODO :
# - [ ] argparser
# - [ ] define search-directory other than example_hooks
# - [ ] replace print with log.
# - [ ] cleanup
# - [ ] add alternative generator for applying hooks to all existing (or selection of) averages



for mod_file in iglob('example_hooks/*.py'):

    # this follows the recipe from the Python docs:
    #  https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly

    mod_name, ext = os.path.splitext(os.path.basename(mod_file))
    spec = importlib.util.spec_from_file_location(mod_name, mod_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    log.info(f'import {mod_name} (from {mod_file})')
    spec.loader.exec_module(module)


print(eventhooks, eventinits)



print(database_url)  # set DATABASE_HOST=

db_api = IoniConnect() #url)

def generate_averages():

    j = db_api.get('/api/averages')

    hrefs = (item["href"] for item in j["_links"]["item"])  # wtf ???

    topic = "average"  # behave as if SSE ...
    for href in hrefs:
        yield topic, href

def make_sse_listener(subscribe_to_topics):

    sse = SSEventListener(url + '/api/events')

    for topic in subscribe_to_topics:
        sse.subscribe(topic)

    return sse.items()


def main():

    print('initializing...')

    initial_values = dict()
    for mod, e_init in eventinits.items():
        print(mod, e_init.__name__)
        initial_values[mod] = e_init(db_api)

    print("listening to average events...")

    if False:
        topics = {e._topic for e in chain.from_iterable(eventhooks.values())}
        gen = make_sse_listener(topics)
    else:
        gen = generate_averages()


    for topic, endpoint in gen:
        # load whatever is behind the endpoint...
        try:
            api_object = db_api.get(endpoint)
        except Exception as e:
            print(e)
            continue  # can't GET /api/averages/xx/parameter_traces ???!??!?!

        # ...and execute all matching hooks:

        for mod, e_hooks in eventhooks.items():
            for e_hook in e_hooks:
                log.debug(f"executing {e_hook.__name__}() [if '{e_hook._topic}' matches '{topic}']")
                if e_hook._topic_re.match(topic):
                    e_hook(db_api, api_object, initial_values.get(mod))



if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        url = str(sys.argv[1])
    else:
        url = database_url

    if len(sys.argv) > 1 and sys.argv[1] == '--verbose':
        logging.getLogger().setLevel(logging.DEBUG)

    main() #sys.argv)

