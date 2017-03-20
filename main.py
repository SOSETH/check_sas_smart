#!/usr/bin/env python3

import argparse
from subprocess import Popen
from subprocess import PIPE
import re
from enum import Enum

class ReturnCode(Enum):
    OK = 0
    WARNING = 1
    CRITICAL = 2
    UNKNOWN = 3

    def updateRc(self, obj, new):
        if new.value < obj.rc.value:
            obj.rc = new

class Main:
    NORMAL_VARS = {
        "Current Drive Temperature": {'name': "Temperature", 'wval': 42, 'cval': 45},
        "Accumulated start-stop cycles": {'name': "Start_Stop"},
        "Accumulated load-unload cycles": {'name': "Load_Unload"},
        "Non-medium error count": {'name': "Non-media_errors"},
        "Accumulated power on time": {'name': "Power-On-Hours", "cparse": (lambda x: re.match('\D*(?P<val>\d+):\d+.*]', x).group('val'))},
        "Invalid DWORD count": {'name': "InvalidDWORD"},
        "Loss of DWORD synchronization": {'name': "DWORDSyncLoss"},
        "Phy reset problem": {'name': "PhyResetProblems"},
    }

    def __init__(self):
        parser = argparse.ArgumentParser(description='Icinga check for SMART values of SAS disks')
        parser.add_argument('Disk')
        parser.add_argument('-c', dest='check', action="store_true", help='Only check if the disk is a SAS disk')
        parser.add_argument('-d', dest='infile', help='Use this file as input instead of executing smartctl')
        parser.add_argument('-v', dest='vebose', action="store_true",  help='Be verbose')
        parser.set_defaults(check=False)
        parser.set_defaults(verbose=False)
        parser.set_defaults(infile='')
        self.avg = None
        self.args = parser.parse_args()
        self.val = None
        self.pdata = ''
        self.dstr = ''
        self.ctr = {}
        self.rc = ReturnCode.UNKNOWN

    def load(self):
        if self.args.infile != '':
            f = open('output.txt', 'r')
            self.val = f.read()
            f.close()
        else:
            smartproc = Popen(['smartctl', '-l', self.args.Disk], stdout=PIPE, bufsize=8192)
            smartproc.wait()
            (indata, _) = smartproc.communicate()
            self.val += indata
            if self.args.verbose:
                print(indata)
        self.val = self.val.split('\n')

    def isSAS(self):
        for line in self.val:
            if line.startswith('Transport protocol:'):
                print(line)
                if 'SAS' in line:
                    exit(0)
                else:
                    exit(1)

    ELC_NAME_MAP = {
        1: "CorECCFast=",
        2: "CorECCSlow=",
        3: "CorRedo=",
        4: "CorTotal=",
        7: "UncorrTotal="
    }

    def parseECLRow(self, name, pos):
        str = self.val[pos]
        arr = list(filter(lambda x: x != '', str.split(' ')))
        for i in [1,2,3,4,7]:
            if int(arr[i]) > 20:
                self.rc.updateRc(self, ReturnCode.CRITICAL)
                self.dstr += 'CRITICAL: '
            elif int(arr[i]) > 1:
                self.rc.updateRc(self, ReturnCode.WARNING)
                self.dstr += 'WARNING: '
            else:
                self.dstr += 'OK: '
            self.dstr += (name + self.ELC_NAME_MAP[i])+arr[i] + '\n'
            self.pdata += (name + self.ELC_NAME_MAP[i]) + arr[i] + ', '


    def printPerformanceData(self):
        # Normal values
        for line in self.val:
            for key in self.NORMAL_VARS:
                if key in line:
                    if not (key in self.ctr.keys()):
                        val = ''
                        if 'cparse' in self.NORMAL_VARS[key].keys():
                            val = self.NORMAL_VARS[key]['cparse'](line)
                        else:
                            arr = line.split(':')
                            if len(arr) == 1:
                                arr = line.split('=')
                            val = arr[1]
                            val = val.replace(' C', '').replace(' ', '')
                        if 'wval' in self.NORMAL_VARS[key].keys():
                            if int(val) > self.NORMAL_VARS[key]['wval']:
                                self.dstr += 'WARNING: '
                                self.rc.updateRc(self,ReturnCode.WARNING)
                        if 'cval' in self.NORMAL_VARS[key].keys():
                            if int(val) > self.NORMAL_VARS[key]['cval']:
                                self.dstr += 'CRITICAL: '
                                self.rc.updateRc(self,ReturnCode.CRITICAL)
                        #else:
                        #    self.dstr += 'OK: '
                        self.dstr += self.NORMAL_VARS[key]['name']+' = '+val+'\n'
                        self.pdata += self.NORMAL_VARS[key]['name']+'='+val+', '
                        self.ctr[key] = 1

        # Special values
        for idx, line in enumerate(self.val):
            if line.startswith('Error counter log'):
                # line + 1-3: Headings
                # line 4: read
                self.parseECLRow('Read', idx+4)
                # line 5: write
                self.parseECLRow('Write', idx+5)
                # line 6: verify
                self.parseECLRow('Verify', idx+6)
        # Drop ',' after last value
        self.pdata = self.pdata[0:len(self.pdata)-2]
        print (self.dstr)


obj = Main()
obj.load()
obj.printPerformanceData()