#!/usr/bin/env python3

# Copyright (C) 2017  Maximilian Falkenstein <mfalkenstein@sos.ethz.ch>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import argparse
import re
from enum import Enum
from subprocess import PIPE
from subprocess import Popen


class ReturnCode(Enum):
    OK = 0
    WARNING = 1
    CRITICAL = 2
    UNKNOWN = 3

    @staticmethod
    def update_rc(obj, new):
        if (new.value > obj.rc.value) | (obj.rc == ReturnCode.UNKNOWN):
            obj.rc = new


class Main:
    NORMAL_VARS = {
        "Current Drive Temperature": {'name': "Temperature", 'wval': 44, 'cval': 46},
        "Accumulated start-stop cycles": {'name': "Start_Stop"},
        "Accumulated load-unload cycles": {'name': "Load_Unload"},
        "Non-medium error count": {'name': "Non_media_errors"},
        "Accumulated power on time": {'name': "Power_On_Hours",
                                      "cparse": (lambda x: re.match('\D*(?P<val>\d+):\d+.*]', x).group('val'))},
        "Invalid DWORD count": {'name': "InvalidDWORD"},
        "Loss of DWORD synchronization": {'name': "DWORDSyncLoss"},
        "Phy reset problem": {'name': "PhyResetProblems"},
    }

    # Special vars from space-formatted table...
    ELC_NAME_MAP = {
        1: "CorrectedECCFast",
        2: "CorrectedECCSlow",
        3: "CorrectedRedo",
        4: "CorrectedTotal",
        6: "ProcessedTotal",
        7: "UncorrectedTotal"
    }

    ELC_WARN_MAP = {
        7: 1
    }

    ELC_CRIT_MAP = {
        7: 3
    }

    def __init__(self):
        parser = argparse.ArgumentParser(description='Icinga check for SMART values of SAS disks')
        parser.add_argument('Disk')
        parser.add_argument('-c', dest='check', action="store_true", help='Only check if the disk is a SAS disk')
        parser.add_argument('-d', dest='infile', help='Use this file as input instead of executing smartctl')
        parser.add_argument('-v', dest='verbose', action="store_true", help='Be verbose')
        parser.add_argument('-raid', dest='raiddevice',
                            help='If the disk is behind a raid controller, specify the argument for \'-d\'')
        parser.set_defaults(check=False)
        parser.set_defaults(verbose=False)
        parser.set_defaults(infile='')
        parser.set_defaults(raiddevice='')
        self.avg = None
        self.args = parser.parse_args()
        self.val = None
        self.pdata = ''
        self.dstr = ''
        self.ctr = {}
        self.rc = ReturnCode.UNKNOWN

    def load(self):
        if self.args.infile != '':
            f = open(self.args.infile, 'r')
            self.val = f.read()
            f.close()
        else:
            args = ['sudo', '/usr/sbin/smartctl', '-x', self.args.Disk]
            if self.args.raiddevice != '':
                args.append('-d')
                args.append(self.args.raiddevice)
            smartproc = Popen(args, stdout=PIPE, bufsize=8192)
            smartproc.wait()
            (indata, _) = smartproc.communicate()
            self.val = str(indata)
        self.val = self.val.replace('\\n', '\n')
        self.val = self.val.split('\n')
        if self.args.verbose:
            print(self.val)

    def is_sas(self):
        for line in self.val:
            if line.startswith('Transport protocol:'):
                print(line)
                if 'SAS' in line:
                    exit(0)
                else:
                    exit(1)
        exit(1)

    def parse_elc_row(self, name, pos):
        string = self.val[pos]
        arr = list(filter(lambda x: x != '', string.split(' ')))
        for i in self.ELC_NAME_MAP.keys():
            val = float(arr[i])
            if i in self.ELC_WARN_MAP.keys():
                desc = ';' + str(self.ELC_WARN_MAP[i]) + ";" + str(self.ELC_CRIT_MAP[i])
                if val > self.ELC_CRIT_MAP[i]:
                    self.rc.update_rc(self, ReturnCode.CRITICAL)
                    self.dstr += 'CRITICAL: '
                elif val > self.ELC_WARN_MAP[i]:
                    self.rc.update_rc(self, ReturnCode.WARNING)
                    self.dstr += 'WARNING: '
                else:
                    self.dstr += 'OK: '
            else:
                desc = ''
                self.dstr += 'OK: '
            self.dstr += (name + self.ELC_NAME_MAP[i] + ' = ') + arr[i] + '\n'
            self.pdata += '\'' + (name + self.ELC_NAME_MAP[i] + '\'=') + arr[i] + 'c' + desc + ' '

    def build_performance_data(self):
        # Normal values
        for line in self.val:
            for key in self.NORMAL_VARS:
                if key in line:
                    if not (key in self.ctr.keys()):
                        if 'cparse' in self.NORMAL_VARS[key].keys():
                            val = self.NORMAL_VARS[key]['cparse'](line)
                        else:
                            arr = line.split(':')
                            if len(arr) == 1:
                                arr = line.split('=')
                            val = arr[1]
                            val = val.replace(' C', '').replace(' ', '')
                        prefix = 'OK: '
                        if 'wval' in self.NORMAL_VARS[key].keys():
                            if float(val) > self.NORMAL_VARS[key]['wval']:
                                prefix = 'WARNING: '
                                self.rc.update_rc(self, ReturnCode.WARNING)
                            if float(val) > self.NORMAL_VARS[key]['cval']:
                                prefix = 'CRITICAL: '
                                self.rc.update_rc(self, ReturnCode.CRITICAL)
                            astr = ";" + str(self.NORMAL_VARS[key]['wval']) + ";" + str(self.NORMAL_VARS[key]['cval'])
                        else:
                            astr = ''
                        self.dstr += prefix
                        self.dstr += self.NORMAL_VARS[key]['name'] + ' = ' + val + '\n'
                        self.pdata += '\'' + self.NORMAL_VARS[key]['name'] + '\'=' + val + 'c' + astr + ' '
                        self.ctr[key] = 1

        # Special values
        for idx, line in enumerate(self.val):
            if line.startswith('Error counter log'):
                # line + 1-3: Headings
                # line 4: read
                self.parse_elc_row('Read', idx + 4)
                # line 5: write
                self.parse_elc_row('Write', idx + 5)
                # line 6: verify, but only if the disk supports it
                if self.val[idx + 6].startswith('Verify'):
                    self.parse_elc_row('Verify', idx + 6)

        if len(self.pdata) > 10:
            self.rc.update_rc(self, ReturnCode.OK)
            # Drop ' ' after last value
            self.pdata = self.pdata[0:len(self.pdata) - 1]

    def run(self):
        try:
            self.load()
            if self.args.check:
                self.is_sas()  # Will exit
            if self.args.verbose:
                print("Output from smartctl:")
                print(self.val)
            self.build_performance_data()
            print(self.rc.name + " disk " + self.args.Disk + " | " + self.pdata)
            print(self.dstr)
            exit(self.rc.value)
        except Exception as e:
            print("UNKNOWN - Exception during execution:")
            print(e.__doc__)
            print(e.message)
            exit(ReturnCode.UNKNOWN)


def cli():
    obj = Main()
    obj.run()
