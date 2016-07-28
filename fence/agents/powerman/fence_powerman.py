#!/usr/bin/env python
import os
import time
from datetime import datetime
import sys
import subprocess
import re
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import run_delay
import logging


#BEGIN_VERSION_GENERATION
RELEASE_VERSION="Powerman Fencing Agent"
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION


#### important!!! #######
# the command I need to implement somehow in this script is:
# $ pm -h elssd1:10101 <option> <node>
#       where option is something like --off, --on, --cycle
#       and where node is lssd8, lssd9, or whatever names are given in
#       powerman.conf (that is the key, because otherwise they won't work
class PowerMan:
    program_name = "powerman"

    def __init__(self, server_name, port="10101"):
        self.server_name = server_name
        self.port = port
        self.server_and_port = server_name + ":" + str(port)
        # this is a list of the command and its options. For example:
        # ['powerman', '--server-host', 'elssd1:10101']
        self.base_cmd = [
            self.program_name, 
            "--server-host", 
            self.server_and_port
        ]
        logging.debug("PowerMan: __init__: self.base_cmd = %s\n", self.base_cmd)

    def _test_run(self, cmd):
        run_this = self.base_cmd + cmd # add the 2 command lists together to get whole command to run
        out = subprocess.check_call(run_this)
        return out

    def _run(self, cmd):
        # Args:
        #   cmd: (list) commands and arguments to pass to the program_name
        run_this = self.base_cmd + cmd # add the 2 command lists together to get whole command to run
        try:
            popen = subprocess.Popen(run_this, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            out = popen.communicate()
        except OSError as e:
	    logging.debug("_run command error: %s\n", e)
            sys.exit(1)
            
        result = out[0].decode().strip()
        return (result, popen.returncode)

    def is_running(self):
        cmd = ["-q"] # just check if we get a response from the server
        result, ret_code = self._run(cmd)
        logging.debug("PowerMan is_running? result = %s, ret_code = %s\n", result, ret_code)
        if ret_code != 0:
            return False
        return True

    def on(self, host):
        logging.debug("PowerMan on: %s\n", host)
        cmd = ["--on", host]
        try:
            result, ret_code = self._run(cmd)
        except OSError as e:
            logging.debug("PowerMan Error: The command '--on' failed: %s\n", e)
        except ValueError as e:
            logging.debug("PowerMan Error: Popen: invalid arguments: %s\n", e)
        logging.debug("result: %s ret_code: %s\n", result, ret_code)
        return ret_code

    def off(self, host):
        cmd = ["--off", host]
        try:
            out = self._run(cmd)
        except OSError as e:
            logging.debug("PowerMan Error: The command '%s' failed: %s\n", cmd, e)
        except ValueError as e:
            logging.debug("PowerMan Error: Popen: invalid arguments: %s\n", e)
        result = out[0]
        ret_code = out[1]
        logging.debug("%s\n", result)
        return ret_code

    def query(self, host):
        cmd = ["--query", host]
        try:
            out = self._run(cmd)
        except OSError as e:
            logging.debug("PowerMan Error: The command '%s' failed: %s\n", cmd, e)
        except ValueError as e:
            logging.debug("PowerMan Error: Popen: invalid arguments: %s\n", e)
        result = out[0]
        ret_code = out[1]
        if ret_code < 0:
            # there was an error with the command
            return ret_code
        else:
            res = result.split('\n')
            res = [r.split() for r in res]
            # find the host in command's returned output
            for lst in res:
                if lst[0] == 'No' and lst[1] == 'such' and lst[2] == 'nodes:':
                    return -1
                if host in lst:
                    return lst[0][:-1] # lst[0] would be 'off:'-- this removes the colon
            # host isn't in the output
            return -1


def get_power_status(conn, options):
    logging.debug("get_power_status function:\noptions: %s\n", str(options))
    pm = PowerMan(options['--ip'], options['--ipport'])
    # if Pacemaker is checking the status of the Powerman server...
    if options['--action'] == 'monitor':
        if pm.is_running():
            logging.debug("Powerman is running\n")
            return "on"
        logging.debug("Powerman is NOT running\n")
        return "off"
    else:
        status = pm.query(options['--plug'])
        if isinstance(int, type(status)):
            # query only returns ints on error
            logging.debug("get_power_status: query returned %s\n", str(status))
            fail(EC_STATUS)
        return status


def set_power_status(conn, options):
    logging.debug("set_power_status function:\noptions: %s", str(options))
    pm = PowerMan(options['--ip'], options['--ipport'])

    action = options["--action"]
    if action == "on":
        pm.on(options['--plug'])
    elif action == "off":
        pm.off(options['--plug'])

    return


def reboot(conn, options):
    logging.debug("reboot function:\noptions: %s", str(options))
    pm = PowerMan(options['--ip'], options['--ipport'])
    res = pm.off(options['--plug'])
    if res < 0:
        logging.debug("reboot: power off failed!\n")
        return False
    time.sleep(2)
    res = pm.on(options['--plug'])
    if res < 0:
        logging.debug("reboot: power on failed!\n")
        return False
    return True

def get_list(conn, options):
    logging.debug("get_list function:\noptions: %s", str(options))
    outlets = {'elssd8': 'on', 'elssd9': 'on'}
    return outlets


def define_new_opts():
    # AS of right now, we don't even need this function--it's unused
    all_opt["hosts"] = {
        "getopt" : ":",
        "longopt" : "hosts",
        "help" : "--hosts=hostname1,hostname2,...	List of hosts this device should fence (must be reachable by Powerman)",
        "required" : "0",
        "shortdesc" : "Fence-able hosts in the cluster",
        "order" : 1,
    }
def main():
    device_opt = [
        'ipaddr',
        'hosts',
        'no_password',
        'no_login',
    ]

    atexit.register(atexit_handler)

    define_new_opts()
    
    # redefine default values for the options given by fencing.py
    all_opt['ipport']['default'] = '10101'
    all_opt['delay']['default'] = '3'
    all_opt['power_wait']['default'] = '3'

    options = check_input(device_opt, process_input(device_opt))
    logging.debug("Entered main() and received options: %s", str(options))
    docs = {}
    docs["shortdesc"] = "Fence Agent for Powerman"
    docs["longdesc"] = "This is a Pacemaker Fence Agent for the \
Powerman management utility that was designed for LLNL systems."
    docs["vendorurl"] = "https://github.com/chaos/powerman"
    show_docs(options, docs)

    ## Do the delay of the fence device before logging in
    ## Delay is important for two-node clusters fencing but we do not need to delay 'status' operations
    run_delay(options)

    if options["--action"] in ["off", "reboot"]:
        time.sleep(int(options["--delay"]))
    result = fence_action(
                 None,
                 options,
                 set_power_status,
                 get_power_status,
                 None,
                 reboot
             )
    
    sys.exit(result)


if __name__ == "__main__":
    main()
