# File:             ThreadSR7265.py
# author:           P. Noel and C. Murer
# copyright:        ETH Zurich, Switzerland, D-MATL INTERMAG

import time
import threading
import PyTango
import zhinst
import zhinst.ziPython as ziPython
import math
import numpy as np

class ThreadZI(threading.Thread):
    lock = threading.Lock()
    def __init__(self,parent):
        # Define some variables if necessary
        self.p = parent
        threading.Thread.__init__(self)
        
    def run(self):
        #print "Entering Thread"
        self.p.set_state(PyTango.DevState.RUNNING)
        ### Program part ###
		# integration time is only written here and not before...
        data = self.p.daq.poll(self.p.attr_integrationtime_read, 500, 0, self.p.flat_dictionary_key)
        x1 = data['dev4855']['demods']['0']['sample']['x']
        y1 = data['dev4855']['demods']['0']['sample']['y']
        x2 = data['dev4855']['demods']['1']['sample']['x']
        y2 = data['dev4855']['demods']['1']['sample']['y']
        x3 = data['dev4855']['demods']['2']['sample']['x']
        y3 = data['dev4855']['demods']['2']['sample']['y']
        x4 = data['dev4855']['demods']['3']['sample']['x']
        y4 = data['dev4855']['demods']['3']['sample']['y']
        print('Getting all the data...')
        # write all the variables and give them in uV peak-peak (This would be amplitude and not peak to peak? CM 03.02.2021)
        self.p.attr_x1_read = np.mean(x1)*1e6*np.sqrt(2)
        self.p.attr_y1_read = np.mean(y1)*1e6*np.sqrt(2) 
        self.p.attr_x2_read = np.mean(x2)*1e6*np.sqrt(2)
        self.p.attr_y2_read = np.mean(y2)*1e6*np.sqrt(2)
        self.p.attr_x3_read = np.mean(x3)*1e6*np.sqrt(2)
        self.p.attr_y3_read = np.mean(y3)*1e6*np.sqrt(2)
        self.p.attr_x4_read = np.mean(x4)*1e6*np.sqrt(2)
        self.p.attr_y4_read = np.mean(y4)*1e6*np.sqrt(2)
        print('taking mean of all the data..')
        #print(i)
        self.p.set_state(PyTango.DevState.ON)

    def stop(self):
        # set everything back to the beginning

        # set the tango state back to ON:
        self.p.set_state(PyTango.DevState.ON)
