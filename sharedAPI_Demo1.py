#################################################
#                                               #
# Ionicon SharedAPI - usage example 1           #
#                                               #
#################################################

import os
import sys
from ctypes import *
from struct import *
import time


lib = cdll.LoadLibrary(r'C:\Users\Moritz.Koenemann\home\venv\pyconnect\Lib\site-packages\pyconnect\bin\x64\IcAPI_c_x64.dll')
# ver = c_double();
# lib.IcAPI_GetVersion(byref(ver));
# print("Version: ");
# print(ver.value);
#IP = b'172.21.1.94';
IP = b'192.168.128.11';
timeout_ms = c_long();
timeout_ms.value = 500
iNumPeaks = c_ulong();
iNumTimebins = c_long();

class IcTimingInfo(Structure):
    _pack_ = 1
    _fields_ = [
        ("Cycle", c_long),
        ("CycleOverall", c_long),
        ("absTime", c_double),
        ("relTime", c_double)
    ]

timingItem = IcTimingInfo()


def get_file():
    b_fname = b''
    state = c_char_p(b_fname);
    ret =lib.IcAPI_GetCurrentDataFileName(IP, byref(state));
    if ret ==1:
        print("IcAPI_GetServerState: return ERROR!!");
    else:
        print("IcAPI_GetServerState: ");
        print(state.value);


def get_state():
    state = c_uint();
    ret =lib.IcAPI_GetServerState(IP, byref(state));
    if ret ==1:
        print("IcAPI_GetServerState: return ERROR!!");
    else:
        print("IcAPI_GetServerState: ");
        print(state.value);


def get_spec():

    numCycles = 10;
    cycle = 0;
    cycleSpec = 0;

    #print(n);
    time.sleep(0.05) # Sleep

 

    #read spec data
    ret =lib.IcAPI_GetNumberOfTimebins(IP, byref(iNumTimebins));
    if ret ==1:
        print("IcAPI_GetNumberOfTimebins: return ERROR!!");
        print("let's use... 160")
        n_timebins = 160
    else:
        n_timebins = iNumTimebins.value
        
    #get spec data
    start = time.time()
    pyarrSpec = [0]*n_timebins
    dataArrSpec = (c_float * len(pyarrSpec))(*pyarrSpec)
    pyarrMassCal = [0]*2
    dataArrMassCal = (c_float * len(pyarrMassCal))(*pyarrMassCal)
    ret =lib.IcAPI_GetCurrentSpec(IP,byref(dataArrSpec),byref(timingItem),byref(dataArrMassCal),n_timebins,2);
    end = time.time()
    
    
    
    if ret ==1:
        print("IcAPI_GetCurrentSpec: return ERROR!!");
    else:
        if cycleSpec != timingItem.CycleOverall:
            print("SPEC: CYCLE=",timingItem.CycleOverall,"RelTime[sec]=",timingItem.relTime," ,#Timebins=",iNumTimebins.value,", Duration[ms]=",(end - start)*1000);
            print("data", dataArrSpec[500:550])
        cycleSpec = timingItem.CycleOverall;


get_state()





























