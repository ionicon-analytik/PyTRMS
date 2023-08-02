
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
logging.basicConfig(level=logging.DEBUG)

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


def main(args):

    if len(args) > 1:
        url = str(args[1])
    else:
        url = database_url

    print(url)

    db_api = IoniConnect(url)

    print('initializing...')

    initial_values = dict()
    for mod, e_init in eventinits.items():
        print(mod, e_init.__name__)
        initial_values[mod] = e_init(db_api)

    print("listening to average events...")

    sse = SSEventListener(url + '/api/events')
    
    print('subscribing to topics...')

    all_hooks = chain.from_iterable(eventhooks.values())
    for topic in [e._topic for e in all_hooks]:
        sse.subscribe(topic) ##'new average')  # TODO :: allow reg-ex and None in Listener!!

    for topic, endpoint in sse.items():

        print('got:', topic)

        current_avg_endpoint = endpoint


        print('got:', current_avg_endpoint)

        # load whatever is behind the endpoint...

        try:
            api_object = db_api.get(endpoint)
        except Exception as e:
            print(e)
            continue  # can't GET /api/averages/xx/parameter_traces ???!??!?!

        # ...and execute all matching hooks:
        print(' ...and execute all matching hooks:')

        for mod, e_hooks in eventhooks.items():
            print('scanning module', mod)
            for e_hook in e_hooks:
                print('checking', e_hook, 'with', e_hook._topic)
                if e_hook._topic_re.match(topic):
                    e_hook(db_api, api_object, initial_values.get(mod))



if __name__ == '__main__':
    import sys
    main(sys.argv)

