How to install cpp tango devices.

1) Copy the folder(s) into tango-devices on machine where you want to host them.
2) Install make-essential if missing
3) run "make clean", install missing packages
4) If successful, the newly made MYCPPSERVER will be dumped into DeviceServers.
5) Install it to the appropriate folder: sudo install -m 755 /home/intermag/DeviceServers/MYCPPSERVER /usr/local/tango_servers/MYCPPSERVER
6) Then run it: /usr/local/tango_servers/MYCPPSERVER INSTANCE

Python based tango-devices you can just copy that to usr/local/tango_servers (or mkdir if not existing) directly. 
to run them now:

for python files:
  first tell it to use the python3: sed 'ls;^;#!/usr/bin/env python3\n' MYPYSERVER.py > MYPYSERVER
  python3 /usr/local/tango_servers/MYPYSERVER INSTANCE, you get this information from jive-> Server. Find the same server as your file name and the first dropdown is the device
