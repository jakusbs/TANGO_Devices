# File:             AttoDRYCheck.py
# author:           C. Murer
# copyright:        ETH Zurich, Switzerland, D-MATL INTERMAG


import time
import threading
import PyTango
import numpy as np
import re
import socket             
             
class AttoDRYCheck(threading.Thread):
    lock = threading.Lock()
    def __init__(self,parent):
        # Define some variables if necessary
        self.p = parent
        threading.Thread.__init__(self)
        
    def run(self):
        # checks if the difference in applied and real field is still there...
        while abs(self.p.attr_MagneticField_read-self.p.setField)>0.001 or abs(self.p.attr_Temperature_read-self.p.setTemp)> 0.2:
            self.p.set_state(PyTango.DevState.MOVING)
            print('Difference in field to set field is: '+str(self.p.attr_MagneticField_read-self.p.setField))
            print('Difference in temperature to set temperature is: '+str(self.p.attr_Temperature_read-self.p.setTemp))
            if abs(self.p.attr_MagneticField_read-self.p.setField)<=0.001 and abs(self.p.attr_Temperature_read-self.p.setTemp)<= 0.2:
                self.p.set_state(PyTango.DevState.ON)
                break
                
                
    def stop(self):
        self.p.set_state(PyTango.DevState.ON)
