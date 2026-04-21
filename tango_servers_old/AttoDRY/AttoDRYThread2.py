# File:             AttoDRYThread2.py
# author:           C. Murer
# copyright:        ETH Zurich, Switzerland, D-MATL INTERMAG


import time
import threading
import PyTango
import numpy as np
import re
import socket             
             
class AttoDRYThread(threading.Thread):
    lock = threading.Lock()
    def __init__(self,parent):
        # Define some variables if necessary
        self.p = parent
        threading.Thread.__init__(self)
        
    def run(self):
        self.p.s.sendto('Read'.encode('utf-8'), self.p.server)
        self.p.datastring, addr = self.p.s.recvfrom(256)
        self.p.datastring = self.p.datastring.decode('utf-8')

        while not self.p.datastring.startswith('ReadA'):
            self.p.datastring, addr = self.p.s.recvfrom(256)
            self.p.datastring = self.p.datastring.decode('utf-8')
            print('skipped invalid packet: ' + self.p.datastring)
        
        # now unpack using self.p.datastring
        pkt = self.p.datastring
        self.p.is_controlling_field       = re.search(r'A(.*)B', pkt).group(1)
        self.p.is_controlling_temperature = re.search(r'B(.*)C', pkt).group(1)
        self.p.is_persistent_mode_set     = re.search(r'C(.*)D', pkt).group(1)
        self.p.current_magnetic_field     = re.search(r'D(.*)E', pkt).group(1)
        self.p.sample_temperature         = re.search(r'E(.*)F', pkt).group(1)
        self.p.vti_temperature            = re.search(r'F(.*)G', pkt).group(1)
        self.p.magnet_temperature         = re.search(r'G(.*)H', pkt).group(1)
        self.p.reservoir_temperature      = re.search(r'H(.*)I', pkt).group(1)
        self.p.cryostat_out_pressure      = re.search(r'I(.*)J', pkt).group(1)
        self.p.cryostat_in_pressure       = re.search(r'J(.*)K', pkt).group(1)
        self.p.reservoir_heater_power     = re.search(r'K(.*)L', pkt).group(1)
        self.p.vti_heater_power           = re.search(r'L(.*)M', pkt).group(1)
        self.p.sample_heater_power        = re.search(r'M(.*)N', pkt).group(1)       
            

    def stop(self):
        # set everything back to the beginning

        # set the tango state back to ON:
        self.p.set_state(PyTango.DevState.ON)
