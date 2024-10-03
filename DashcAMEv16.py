"""
Monitoring AME.

REFACTOR:

    Das script macht im Grunde:

    1) Zu ubidots connecten
    2) die AME components per modbus auslesen
    3) die variablen bei ubidots anlegen, falls es sie noch nicht gibt
    4) die AME step/run/action/alive per modbus auslesen
    5) wenn der step wechselt: AME component-vals per modbus auslesen..
    6) ..und auf ubidots hochladen

    also exakt das, was die IoniConnect.API auch inzwischen kann!

    TODO

    - [x] die 'f[A-Z][a-z]+' -Funktionen (modbus) durch pytrms ersetzen
    - [x] pytrms: ein Instrument-alive-counter bauen (because why not?)
    - [x] pytrms.db_api: ein DB-API-connector (get_component(), create_component(),
           save_component(), ...)
    - [ ] with pytrms.pretty_print('check foo'): ~> 'check foo..........[OK]' :)
    - [ ] das Skript von ~400 auf ~40 (o. ~200) Zeilen eindampfen (wichtig ist nur
           die letzte Schleife...)


"""
import os
import sys
import time
import logging
from socket import gethostname

from ctypes import *  # win-api console magick..

import pandas as pd

import pytrms
from pytrms.clients.modbus import IoniconModbus
from pytrms.clients.db_api import IoniConnect

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)  # / .INFO

#ch = logging.StreamHandler()
#ch.setLevel(logging.DEBUG)
#log.addHandler(ch)

############# USER CONFIG ######################

MODBUS_HOST = "127.0.0.1"
API_HOST = "127.0.0.1"
API_PORT = 5066
API_URL = f"http://{API_HOST}:{API_PORT}" 

ds_name = 'FAT-3' #  This is the slot in the LAB / or EXTernal, this will not change. System Name can change 
ds_sysname = gethostname() #'Silberkiste Monitor'# gethostname()# + " Monitor"

#dfComponentsModes = pd.read_csv(r'ComponentsModes.tsv',
#                                delimiter='\t',
#                                header=None,
#                                names=['Component', 'Action'], 
#                                skipinitialspace=True,
#                                )
#dfComponentsModes['Action'].fillna(0, inplace=True)

################################################


## TODO :: solche hacks evtl auch in PyTRMS unterbringen??

def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear') # Clear console


class COORD(Structure):
    pass
 
COORD._fields_ = [("X", c_short), ("Y", c_short)]
 
STD_OUTPUT_HANDLE = -11

def print_at(r, c, s):
    if sys.platform == 'linux':
        return

    h = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
    windll.kernel32.SetConsoleCursorPosition(h, COORD(c, r))
 
    c = s.encode("windows-1252")
    windll.kernel32.WriteConsoleA(h, c_char_p(c), len(c), None, None)

def prompt_for_continue():
    inputvar = input("press <enter> to continue ('no' to quit): ")
    if inputvar == 'no':
        sys.exit('Discontinued.')
    else:
        clear_console()
        print_at(0, 0, "") # Return to top of console

def wait_for_next_step_and_yield_last_step_once_we_reach_use_mean_gleich_True():

    # 13.07.: SCHNELL, SCHNELL (es ist 17 Uhr 57 und ich will die Modbus-instrument
    #  daten noch hochladen):
    # we make 2 stops! new step, but ame.use_mean = False, and again at ame.use_mean = True

    last_ame = this_ame = mb.read_ame_numbers()

    while True:
        this_ame = mb.read_ame_numbers()

        if (this_ame.use_mean and this_ame.step_number != last_ame.step_number):
            yield last_ame # ~> and upload..
            last_ame = this_ame

        # Return to top of console:
        print_at(0, 0, "")
        print("Cycle:\t", mb.read_timecycle().abs_cycle,
              "\tRun:", this_ame.run_number,
              "\tStep:", this_ame.step_number,
              "\tUseMean:", this_ame.use_mean
        )
        time.sleep(1)    


    
################################################################
#       Initialize                                             #
#                                                              #
# connect to cloud, AME, make sure Device and Variables exist  #
#                                                              #
################################################################

log.debug('\nConnecting to AME .....\tIP: ' + MODBUS_HOST)    

mb = IoniconModbus(host=MODBUS_HOST)
api = IoniConnect(API_URL)

prompt_for_continue()


if not mb.n_components > 0:
    sys.exit('No AME Components found')
else:
    log.debug('\nFound number of Components:\t' + str(mb.n_components))    


log.debug('\nGetting all Components Names .....')    

comp_names = mb.read_component_names()

#dfComponents = pd.DataFrame(columns = ['Component', 'Value'])
#dfComponents.loc[:, 'Component'] = mb.read_component_names()

log.debug('\nChecking if Components exist in Cloud .....')  

for comp_name in comp_names:
    try:
        log.debug('Checking:\t' + comp_name)
        var_component = api.get_component(comp_name)
        log.debug(comp_name + '\texists.')
    except KeyError:
        api.create_component(comp_name)
        log.debug(comp_name + '\tcreated.')

#for idx in dfComponentsModes.index:
#    if dfComponentsModes.loc[idx, 'Action'] > 0:
#        # if there is a mode entered, not 0 or '', use Component@mode as a name
#        comp_name = '{}@{:0.0f}'.format(
#                dfComponentsModes.loc[idx, 'Component'],
#                dfComponentsModes.loc[idx, 'Action'])
#    else:
#        comp_name = dfComponentsModes.loc[idx, 'Component']
#
#    try:
#        log.debug('Checking:\t' + comp_name)
#        var_component = api.get_component(comp_name)
#        log.debug(comp_name + '\texists.')
#    except KeyError:
#        api.create_component(comp_name)
#        log.debug(comp_name + '\tcreated.')
        

prompt_for_continue()


################## REPEAT ###########################
#                                                   #
#             Update all AME values in a loop       #
#                                                   #
#####################################################

for ame in wait_for_next_step_and_yield_last_step_once_we_reach_use_mean_gleich_True():

    print_at(3, 0, "") # Return to top of console +1
    log.debug('Updating Concentrations fom AME.......')

    tc = mb.read_ame_timecycle()  # this is the last upload by AME-app "a couple seconds ago"!

    auto = {
        "AME_RunNumber": ame.run_number,
        "AME_StepNumber": ame.step_number,
        "AME_ActionNumber": ame.action_number,
        "AUTO_UseMean": True  # ame.use_mean  (but beware of start-stop-delays..)
    }

    uri = api.create_timecycle(*tc, sourcefile_path="/foo.h5", automation=auto)
    log.debug(f"created timecycle @ '{uri}'")

    uri = api.create_average(ame.run_number, ame.step_number, ame.action_number)
    log.debug(f"created average @ '{uri}'")

    api.save_component_values(mb.read_components())
    log.debug("successfully uploaded components")
    
    api.save_instrument_values(mb.read_instrument_data())
    log.debug("successfully uploaded components")
    
    #if len(dfComponents) != mb.n_components:
    #    sys.exit('Exit. Number of AME values has changed.')

    #dfComponents.loc[:, 'Value'] = mb.read_components()
    #print(dfComponents)
    #print('{}\t{:.3f}'.format(dfComponents.loc[idx, 'Component'], dfComponents.loc[idx, 'Value']))
        
    #print('\nUpdating Concentrations to Cloud....... - Action: none/0 or {:0.0f}'.format(ame.action_number))
   
    # Go through all Components in the update list
    #for idx in dfComponentsModes.index:
    #    currentComponentName = dfComponentsModes.loc[idx, 'Component']
    #    # find the corresponding value in the AME Components
    #    currentValue = (dfComponents.loc[dfComponents['Component']
    #            == currentComponentName]['Value'].values[0])
    #    if currentValue == None: # well something went wrong, no value found
    #        log.debug('No value found for:\t'+ currentComponentName)
    #        break
    #    
    #    # Update if without Action
    #    if dfComponentsModes.loc[idx, 'Action'] == 0: # all components 
    #        currentComponentNameAction = dfComponentsModes.loc[idx, 'Component']
    #        print('{}\t{:.3f}'.format(currentComponentNameAction, currentValue))
    #        try:
    #            currentVariable = get_component(currentComponentNameAction, ds)
    #            currentVariable.save_value({'value': currentValue})
    #        except:
    #            print('Update failed')

    #    if ame.action_number > 0:
    #        # Bei Action=0 werden sonst auch 
    #        # ----------------baseline@0 upgedated, was es nicht gibt            
    #        # Update if with corrrect action
    #        if dfComponentsModes.loc[idx, 'Action'] == ame.action_number: # The correct action 
    #            currentComponentNameAction = '{}@{:0.0f}'.format(dfComponentsModes.loc[idx, 'Component'],dfComponentsModes.loc[idx, 'Action'])
    #            print('{}\t{:.3f}'.format(currentComponentNameAction, currentValue))
    #            try:
    #                currentVariable = get_component(currentComponentNameAction, ds)
    #                currentVariable.save_value({'value': currentValue})
    #            except:
    #                print('Update failed')

