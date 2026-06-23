# File:             HysteresisThread.py
# description:      MOKE Hysteresis measurement routine
# author:           C. Stamm
# copyright:        ETH Zurich, Switzerland, D-MATL INTERMAG


import time
import threading
import PyTango
import numpy as np

# Safety multiplier on the expected half-loop duration. A half-loop should
# take ≈ IntegrationTime/2 seconds on the PLC (TANGO attr = full loop = 2x).
# Timeout = max(HALFLOOP_MIN_TIMEOUT_S, expected × HALFLOOP_TIMEOUT_FACTOR).
HALFLOOP_TIMEOUT_FACTOR = 5.0
HALFLOOP_MIN_TIMEOUT_S  = 60.0


class HysteresisThread(threading.Thread):
    lock = threading.Lock()
    def __init__(self,parent):
        # Define some variables if necessary
        self.p = parent
        threading.Thread.__init__(self)

    def _halfloop_timeout(self):
        """Timeout for one PLC half-loop, derived from the IntegrationTime attribute."""
        expected = (self.p.attr_IntegrationTime_read / 2.0) * HALFLOOP_TIMEOUT_FACTOR
        return max(HALFLOOP_MIN_TIMEOUT_S, expected)

    def _wait_for_plc_idle(self, label):
        """Poll HystRunning with a timeout sized to the measurement parameters, so
        a stuck PLC flag cannot hang the thread forever. Returns True on normal completion."""
        timeout_s = self._halfloop_timeout()
        deadline = time.time() + timeout_s
        pollingTime = self.p.BeckhoffPollingTime
        time.sleep(pollingTime)
        while self.p.ads.ReadBool(self.p.BeckhoffHystRunning):
            if time.time() > deadline:
                self.p.error_stream(
                    "HysteresisThread: {} timed out after {:.0f}s — aborting".format(
                        label, timeout_s))
                self.p.ads.WriteBool(self.p.BeckhoffHystAbort + "=true")
                return False
            if self.p.get_state() != PyTango.DevState.RUNNING:
                return False
            time.sleep(pollingTime)
        return True

    def run(self):
        print ("Starting Hysteresis measurement ({:d} cycles)".format(self.p.attr_Cycles_read))
        self.p.set_state(PyTango.DevState.RUNNING)
        pollingTime = self.p.BeckhoffPollingTime
        # variables init
        field = self.p.attr_MagneticField_read/self.p.AmperePerVolt # should not change during run!
        arraylength = self.p.attr_NumberOfPoints_read # should not change during run!
        # Retain each cycle's raw half-loops so a scan can be inspected
        # (GetCycle) and kicked out of the average (SetExcludedCycles +
        # RecomputeAverage) afterwards.  _cyc[ch] = list of (pos, neg) arrays.
        self.p._cyc = {ch: [] for ch in range(1, 7)}
        self.p._excluded_cycles = []
        result_names = [self.p.BeckhoffResult1Name, self.p.BeckhoffResult2Name,
                        self.p.BeckhoffResult3Name, self.p.BeckhoffResult4Name,
                        self.p.BeckhoffResult5Name, self.p.BeckhoffResult6Name]

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
            # wait until finished (with hard timeout)
            if not self._wait_for_plc_idle("positive half-loop"):
                return
            # read this cycle's positive half-loop
            cyc_pos = [np.asarray(self.p.ads.ReadRealArray(name + ",{:d}".format(arraylength)),
                                  dtype=float) for name in result_names]

            # set negative magnetic field
            self.p.ads.WriteReal(self.p.BeckhoffHystField+"={:6f}".format(-field))
            # start Beckhoff Hysteresis (2nd half loop)
            #print "Starting negative loop "+str(counter)
            self.p.set_status("Starting negative loop number {:d}".format(counter))
            self.p.ads.WriteBool(self.p.BeckhoffHystStart+"=true")
            # wait until finished (with hard timeout)
            if not self._wait_for_plc_idle("negative half-loop"):
                return
            # read this cycle's negative half-loop
            cyc_neg = [np.asarray(self.p.ads.ReadRealArray(name + ",{:d}".format(arraylength)),
                                  dtype=float) for name in result_names]

            # retain the individual cycle, then (re)average over all cycles so
            # far.  Averaging + Hc/Hshift/Mr/Ms derivation live in one shared
            # method on the device so the live loop and RecomputeAverage agree.
            for ch in range(1, 7):
                self.p._cyc[ch].append((cyc_pos[ch - 1], cyc_neg[ch - 1]))
            self.p._average_and_derive(range(1, counter + 1))
            self.p.attr_CycleReadback_read = counter
        
        # all cycles are done, set the tango state back to ON
        self.p.set_state(PyTango.DevState.ON)
        self.p.set_status("Device ready (ON state)")
        #print "All cycles done, thread finished"
        
    def stop(self):
        
        # send abort command to Beckhoff system
        self.p.ads.WriteBool(self.p.BeckhoffHystAbort+"=true")
        print("Aborted hysteresis measurement".format(self.p.attr_Cycles_read))
        self.p.set_state(PyTango.DevState.ON)
        
