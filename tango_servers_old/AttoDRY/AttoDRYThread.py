# File:             AttoDRYThread.py
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
        self.p.datastring, addr = self.p.s.recvfrom(128)
        #print(addr)
        self.p.datastring = self.p.datastring.decode('utf-8')
        # make sure that what you read is actually a string containing information...
        while self.p.datastring[:5] != 'ReadA':
            self.p.datastring, addr = self.p.s.recvfrom(128)
            self.p.datastring = self.p.datastring.decode('utf-8')
            print('datastrings that where not read: '+self.p.datastring)
        
        if self.p.datastring[:5] == 'ReadA':
            #print('In thread: ')
            self.p.res1 = re.search('A(.*)B',self.p.datastring).group(1)
            self.p.res2 = re.search('B(.*)C',self.p.datastring).group(1)
            self.p.res3 = re.search('C(.*)D',self.p.datastring).group(1)
            self.p.res4 = re.search('D(.*)E',self.p.datastring).group(1)
            self.p.res5 = re.search('E(.*)F',self.p.datastring).group(1)
            #print('In thread: '+str(self.p.res5))
            

    def stop(self):
        # set everything back to the beginning

        # set the tango state back to ON:
        self.p.set_state(PyTango.DevState.ON)
