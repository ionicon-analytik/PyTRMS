import sys
import json
import logging
import argparse
from functools import wraps

import pytrms
from pytrms.clients.db_api import IoniConnect
from pytrms.clients.ssevent import SSEventListener
from pytrms.clients.ioniclient import IoniClient
from pytrms.clients.dirigent import Dirigent

from pytrms.compose.composition import Composition
from pytrms.compose.step import Step

from pytrms.clients import ionitof_url
from pytrms.clients import database_url

# logging.basicConfig()
# logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')
logging.basicConfig(format='[%(levelname)s]\t%(message)s')

log = logging.getLogger()

print(ionitof_url)
print(database_url)


def coroutine(func):
    @wraps(func)
    def primer(*args, **kwargs):
        coro = func(*args, **kwargs)
        next(coro)
        return coro
    return primer


parser = argparse.ArgumentParser(prog='componist',
                                 description=('reads a Composition file from the current directory'
                                              'and feeds the scheduler/"Dirigent" with steps and actions.'))
parser.add_argument('-f', '--file', type=str,
                    help=("alternative Composition file. if a directory, it will be"
                          "searched for a file named 'Composition' (no file extension)"),
                    required=False, default='./Composition')
parser.add_argument('--host-url', type=str,
                    help=('alternative HTTP-host url, default: http://127.0.0.1:8002'),
                    required=False, default=ionitof_url)
parser.add_argument('-c', '--create-file', action='store_true',
                    help=('create a template Composition file and exit'), )
parser.add_argument('--force', action='store_true',
                    help=('overwrite template file even if it already exists'), )
parser.add_argument('--foresight', type=int,
                    help=('the number of cycles to plan ahead in the schedule'), default=300)
parser.add_argument('--start-cycle', type=int,
                    help=('the offset in absolute cycles to start the first step'), default=0)
parser.add_argument('-g', '--generate-automation', action='store_true',
                    help=('whether to generate automation numbers like AME_RunNumber'), )
parser.add_argument('--start-when-ready', action='store_true',
                    help=('start the measurement as soon as initialization is complete'), )
parser.add_argument('-n', '--dry-run', action='store_true',
                    help=('do not actually schedule anything, just simulate what would happen'), )
parser.add_argument('--parse', type=str, help=('provide a sequence.xml file to parse'),
                    required=False)
parser.add_argument('-v', '--verbose', action='store_true', help=('increase verbosity'))


class Componist:
    '''
    '''

    def __init__(self, foresight=300):
        self.foresight = int(foresight)
        assert self.foresight > 0, "foresight cannot be negative"

        self.ptr = IoniClient('127.0.0.1', '8002')
        self.dirigent = Dirigent(ionitof_url)
        self.sse = SSEventListener(ionitof_url + '/api/timing/stream')
        self.db_api = IoniConnect(database_url, session=None)

        print("started clients/sessions...")

    @coroutine
    def schedule_routine(self, composition):  # TODO :: make part of Dirigent??
        # feed all future updates for a given current cycle to the Dirigent
        print("schedule_routine: initializing...")
        sequence = composition.sequence()
        future_cycle, set_values = next(sequence)

        while True:
            current_cycle = yield
            print(f"schedule_routine: got [{current_cycle}]")

            while future_cycle < current_cycle + self.foresight:
                print(f'scheduling cycle [{future_cycle}] ~> {set_values}')
                # schedule all...
                for parID, value in set_values.items():
                    self.dirigent.push(parID, value, future_cycle)
                # ...and fetch next (TODO :: make part of Composition/Dirigent?)
                future_cycle, set_values = next(sequence)

    def orchestrate(self, composition, start_when_ready):
        '''Start conducting the grand composition to the IoniTOF.

        This handles three APIs to...
         1) follow the stream of cycle-events
         2) upload cycles to the database
         3) schedule AME-steps via the Dirigent
         4) create averages after each finished step on the database
        '''
        last_run = last_step = None  # used to create averages.. TODO :: make part of the SSE-listener??

        print("listening to cycle events...")
        self.sse.subscribe('cycle')
        self.sse.subscribe('measurement')

        print("initializing measurement...")
        schedule_routine = self.schedule_routine(composition)
        schedule_routine.send(composition.start_cycle)

        # while future_cycle < abs_cycle + self.foresight:
        #     future_cycle, set_values = next(sequence)
        #     print(f'scheduling cycle [{future_cycle}] ~> {set_values}')
        #     for parID, value in set_values.items():
        #         self.dirigent.push(parID, value, future_cycle)

        print("start listening for events...")
        # TODO :: (siehe unten) ~> der "event-iterator" sollte HIER bis zum meas-stopped
        #         VORRUECKEN, weil das idR das erste ist, was man vom IoniTOF bekommt!
        was_running = False

        if start_when_ready:
            print("starting measurement...")
            self.ptr.start_measurement()

        for event in self.sse:
            j = json.loads(event)

            if self.sse.event == 'measurement' and j["state"] == 'stopped':
                if was_running:
                    print("measurement has stopped. shutting down...")
                    break  # TODO :: doesn't work smoothly ~ for some reasong the Py-SSEListener is one read-line late... ? that's why it gets the "meas-stopped" at the beginning!
                else:
                    continue
            was_running = True


            tc = j["TimeCycle"]
            auto = j["Automation"]
            abs_cycle = tc["OverallCycle"]

            loc = self.db_api.create_timecycle(
                rel_cycle=tc["Cycle"],
                abs_cycle=abs_cycle,
                abs_time=tc["AbsTime"],
                rel_time=tc["RelTime"],
                sourcefile_path=j["Datafile"],
                automation=auto
            )
            log.debug(f"created tc @ {loc}")

            schedule_routine.send(abs_cycle)

            run = auto["AME_RunNumber"]
            step = auto["AME_StepNumber"]
            action = auto["AME_ActionNumber"]

            if last_step is None:
                pass
            elif step != last_step:
                if last_step > 0 and last_run > 0:
                    print(f"creating average for last step [{last_step}]...")
                    self.db_api.create_average(last_run, last_step, use_mean=True)

            last_run = run
            last_step = step


def main(args):
    log = logging.getLogger()
    log.setLevel(logging.DEBUG if args.verbose else logging.INFO)

    log.debug('starting the componist')

    if args.create_file:
        log.debug('creating example Composition')
        mode = 'w' if args.force else 'x'
        with open(args.file, mode) as f:
            etude = Composition(steps=[Step("H60", {'DPS_Udrift': 600}, 10, 2),
                Step("H40", {'DPS_Udrift': 400}, 15, 5),
                Step("N30", {'DPS_Udrift': 300}, 25, 5)])
            etude.dump(f)
            return

    log.debug(f'loading componsition from {args.file}')
    with open(args.file, 'r') as f:
        die_moldau = Composition.load(f, start_cycle=args.start_cycle,
                                      generate_automation=args.generate_automation)

    if args.parse is not None:
        raise NotImplementedError()

    if args.dry_run:
        return

    karajan = Componist(foresight=args.foresight)
    karajan.orchestrate(die_moldau, args.start_when_ready)


if __name__ == '__main__':
    args = parser.parse_args()
    try:
        main(args)
    except KeyboardInterrupt:
        sys.exit(0)

