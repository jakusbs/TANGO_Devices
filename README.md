How to install cpp tango devices.

1) Copy the folder(s) into tango-devices on machine where you want to host them.
2) Install make-essential if missing
3) run "make clean", install missing packages
4) If successful, the newly made file will be dumped into DeviceServers.
5) sudo cp that file into usr/local/tango_servers (or mkdir if not existing).

Python based tango-devices you can just copy that to usr/local/tango_servers (or mkdir if not existing) directly. 
to run them now:

for python files:
  first tell it to use the python3: sed 'ls;^;#!/usr/bin/env python3\n' FILENAME.py > FILENAME
  python3 /usr/local/tango_servers/FILENAME DEVICE, you get this information from jive-> Server. Find the same server as your file name and the first dropdown is the device
