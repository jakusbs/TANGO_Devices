# File:             HysteresisThread.py
# description:      MOKE Hysteresis measurement routine
# author:           C. Stamm
# copyright:        ETH Zurich, Switzerland, D-MATL INTERMAG


import time
import threading
import PyTango
import numpy as np
             
class HysteresisThread(threading.Thread):
    lock = threading.Lock()
    def __init__(self,parent):
        # Define some variables if necessary
        self.p = parent
        threading.Thread.__init__(self)
        
    def run(self):
        print ("Starting Hysteresis measurement ({:d} cycles)".format(self.p.attr_Cycles_read))
        self.p.set_state(PyTango.DevState.RUNNING)
        pollingTime = self.p.BeckhoffPollingTime
        # variables init
        field = self.p.attr_MagneticField_read/self.p.AmperePerVolt # should not change during run!
        arraylength = self.p.attr_NumberOfPoints_read # should not change during run!
        result1pos = np.zeros(arraylength)
        result1neg = np.zeros(arraylength)
        result2pos = np.zeros(arraylength)
        result2neg = np.zeros(arraylength)
        result3pos = np.zeros(arraylength)
        result3neg = np.zeros(arraylength)
        result4pos = np.zeros(arraylength)
        result4neg = np.zeros(arraylength)
        result5pos = np.zeros(arraylength)
        result5neg = np.zeros(arraylength)
        result6pos = np.zeros(arraylength)
        result6neg = np.zeros(arraylength)
              
        counter = 0
        self.p.attr_CycleReadback_read = counter
        
        # set initial magetic field
        # check BeckhoffHystChannelValue
        if self.p.BeckhoffHystChannelValue == 1:
            # use DAC1
            self.p.ads.WriteReal("MAIN.AnalogOut1={:6f}".format(-field))
        else:
            # use DAC2
            self.p.ads.WriteReal("MAIN.AnalogOut2={:6f}".format(-field))
        time.sleep(0.5)
        
        # repeat for each cycle, while running (not aborted)
        while (counter < self.p.attr_Cycles_read) and (self.p.get_state() == PyTango.DevState.RUNNING):
            counter += 1
            # set positive magnetic field
            self.p.ads.WriteReal(self.p.BeckhoffHystField+"={:6f}".format(field))
            # start Beckhoff Hysteresis (1st half loop)
            #print "Starting positive loop number "+str(counter)
            self.p.set_status("Starting positive loop number {:d}".format(counter))
            self.p.ads.WriteBool(self.p.BeckhoffHystStart+"=true")
            # wait until finished
            time.sleep(pollingTime)
            while self.p.ads.ReadBool(self.p.BeckhoffHystRunning):
                time.sleep(pollingTime)
            # read results
            result1pos += self.p.ads.ReadRealArray(self.p.BeckhoffResult1Name+",{:d}".format(arraylength))
            result2pos += self.p.ads.ReadRealArray(self.p.BeckhoffResult2Name+",{:d}".format(arraylength))
            result3pos += self.p.ads.ReadRealArray(self.p.BeckhoffResult3Name+",{:d}".format(arraylength))
            result4pos += self.p.ads.ReadRealArray(self.p.BeckhoffResult4Name+",{:d}".format(arraylength))
            result5pos += self.p.ads.ReadRealArray(self.p.BeckhoffResult5Name+",{:d}".format(arraylength))
            result6pos += self.p.ads.ReadRealArray(self.p.BeckhoffResult6Name+",{:d}".format(arraylength))
            
            # set negative magnetic field
            self.p.ads.WriteReal(self.p.BeckhoffHystField+"={:6f}".format(-field))
            # start Beckhoff Hysteresis (2nd half loop)
            #print "Starting negative loop "+str(counter)
            self.p.set_status("Starting negative loop number {:d}".format(counter))
            self.p.ads.WriteBool(self.p.BeckhoffHystStart+"=true")
            # wait until finished
            time.sleep(pollingTime)
            while self.p.ads.ReadBool(self.p.BeckhoffHystRunning):
                time.sleep(pollingTime)
            # read results
            result1neg += self.p.ads.ReadRealArray(self.p.BeckhoffResult1Name+",{:d}".format(arraylength))
            result2neg += self.p.ads.ReadRealArray(self.p.BeckhoffResult2Name+",{:d}".format(arraylength))
            result3neg += self.p.ads.ReadRealArray(self.p.BeckhoffResult3Name+",{:d}".format(arraylength))
            result4neg += self.p.ads.ReadRealArray(self.p.BeckhoffResult4Name+",{:d}".format(arraylength))
            result5neg += self.p.ads.ReadRealArray(self.p.BeckhoffResult5Name+",{:d}".format(arraylength))
            result6neg += self.p.ads.ReadRealArray(self.p.BeckhoffResult6Name+",{:d}".format(arraylength))
                        
            # construct full loop and average:
            self.p.attr_result1_read = np.concatenate([result1pos,result1neg])/counter
            self.p.attr_result2_read = np.concatenate([result2pos,result2neg])/counter
            self.p.attr_result3_read = np.concatenate([result3pos,result3neg])/counter
            self.p.attr_result4_read = np.concatenate([result4pos,result4neg])/counter
            self.p.attr_result5_read = np.concatenate([result5pos,result5neg])/counter
            self.p.attr_result6_read = np.concatenate([result6pos,result6neg])/counter
            self.p.attr_CycleReadback_read = counter
            
            # field channel: result5 (or could be separate for longitudinal and polar)
            if self.p.BeckhoffHystChannelValue == 1:
                # longitudinal geometry
                field_up = result5pos/counter
                field_dn = result5neg/counter
            else:
                # polar geometry
                field_up = result5pos/counter
                field_dn = result5neg/counter
            # field scaling to mT
            field_up *= 1000/self.p.HallSensitivity * self.p.attr_fieldCorrectionFactor_read # for mTesla scale
            field_dn *= 1000/self.p.HallSensitivity * self.p.attr_fieldCorrectionFactor_read
            self.p.attr_field_read = np.concatenate([field_up,field_dn])
            
            # calculations: take MOKE signal in result1, field 
            result_up = self.p.attr_result1_read[:arraylength] #result1pos/counter # first half
            result_dn = self.p.attr_result1_read[arraylength:] #result1neg/counter # second half

            # evaluate Hc, Hshift
            meanresult = np.mean(np.concatenate([result_up,result_dn])) # average signal of hysteresis
            """
            index = np.argmin(abs(result_up-meanresult)) # find index of transition through zero
            Hc_up = field_up[np.argmin(abs(result_up-meanresult))]
            index = np.argmin(abs(result_dn-meanresult))
            Hc_dn = field_dn[np.argmin(abs(result_dn-meanresult))]
            """
            # find Hc starting from center of loop
            # first inspect up branch
            index = arraylength//2
            offset = 1
            while index + offset < arraylength:
                if (result_up[index+offset] - meanresult)*(result_up[index] - meanresult) < 0:
                    # going up: change in sign means we found Hc
                    index=index+offset
                    break
                if (result_up[index-offset] - meanresult)*(result_up[index] - meanresult) < 0:
                    # going up: change in sign means we found Hc
                    index=index-offset
                    break
                offset += 1
            Hc_up = field_up[index]
            # now same for down branch            
            index = arraylength//2
            offset = 1
            while index + offset < arraylength:
                if (result_dn[index+offset] - meanresult)*(result_dn[index] - meanresult) < 0:
                    # going up: change in sign means we found Hc
                    index=index+offset
                    break
                if (result_dn[index-offset] - meanresult)*(result_dn[index] - meanresult) < 0:
                    # going up: change in sign means we found Hc
                    index=index-offset
                    break
                offset += 1
            Hc_dn = field_dn[index]
            
            self.p.attr_Hc_read = (Hc_up - Hc_dn)/2.0 # half of the opening
            self.p.attr_Hshift_read = (Hc_up + Hc_dn)/2.0 # average value of switching fields
                        
            # evaluate remanence Mr and saturation magnetization Ms
            self.p.attr_Mr_read = (result_up[arraylength//2] - result_dn[arraylength//2])/2;
            self.p.attr_Ms_read = (result_up[0] + result_dn[-1] - result_up[-1] - result_dn[0])/2
        
        # all cycles are done, set the tango state back to ON
        self.p.set_state(PyTango.DevState.ON)
        self.p.set_status("Device ready (ON state)")
        #print "All cycles done, thread finished"
        
    def stop(self):
        
        # send abort command to Beckhoff system
        self.p.ads.WriteBool(self.p.BeckhoffHystAbort+"=true")
        print("Aborted hysteresis measurement".format(self.p.attr_Cycles_read))
        self.p.set_state(PyTango.DevState.ON)
        
