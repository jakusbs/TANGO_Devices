# -*- coding: utf-8 -*-
"""
TTbeckhoff
Triggers a time-trace measurement on the Beckhoff PLC and reads the result
array via AdsBridge2. Polls BeckhoffTTrun in always_executed_hook until the
PLC signals completion, then reads the array and computes statistics.
"""

import tango
from tango import DevState, AttrWriteType
from tango.server import Device, command, attribute, device_property, run

__all__ = ["TTbeckhoff", "main"]

TT_LENGTH = 350  # number of points to read from PLC array (max 400)


class TTbeckhoff(Device):
    """
    Beckhoff time-trace server. Triggers a PLC time trace, polls until done,
    reads the result array and exposes timetrace/average/min/max attributes.

    **Properties:**
    - AdsBridge: TANGO path to AdsBridge2 device
    - BeckhoffVariable: PLC array variable holding the time trace (e.g. MAIN.TT1)
    - BeckhoffTTrun: PLC bool used to start/stop the time trace (e.g. MAIN.TTrunning)
    """

    AdsBridge = device_property(
        dtype='str', default_value='hpp-n42/beckhoff/adsBridge2',
        doc="TANGO path to AdsBridge2 device"
    )
    BeckhoffVariable = device_property(
        dtype='str', default_value='MAIN.TT1',
        doc="PLC array variable holding the time trace"
    )
    BeckhoffTTrun = device_property(
        dtype='str', default_value='MAIN.TTrunning',
        doc="PLC bool flag — write True to start, goes False when done"
    )

    def init_device(self):
        Device.init_device(self)
        self.ads = tango.DeviceProxy(self.AdsBridge)
        self._continuous = False
        self._timetrace = [0.0] * TT_LENGTH
        self._average = 0.0
        self._min = 0.0
        self._max = 0.0
        self.set_state(DevState.ON)
        self.set_status("Ready")

    def always_executed_hook(self):
        if self.get_state() != DevState.RUNNING:
            return
        try:
            still_running = self.ads.ReadBool(self.BeckhoffTTrun)
        except Exception as e:
            self.error_stream("TTbeckhoff: ReadBool failed: {}".format(e))
            return
        if still_running:
            return

        # PLC finished — read the array
        try:
            result = self.ads.ReadRealArray(
                '{},{}'.format(self.BeckhoffVariable, TT_LENGTH))
            self._timetrace = list(result)
            self._min     = min(self._timetrace)
            self._max     = max(self._timetrace)
            self._average = sum(self._timetrace) / len(self._timetrace)
        except Exception as e:
            self.error_stream("TTbeckhoff: ReadRealArray failed: {}".format(e))

        self.set_state(DevState.ON)
        self.set_status("Ready")

        if self._continuous:
            self.Start()

    # ---- Attributes ---------------------------------------------------------

    @attribute(dtype=bool, access=AttrWriteType.READ_WRITE,
               doc="If True, automatically restarts after each measurement")
    def ContinuousRun(self):
        return self._continuous

    @ContinuousRun.write
    def ContinuousRun(self, value):
        self._continuous = value

    @attribute(dtype=float, doc="Average of last time trace")
    def average(self):
        return self._average

    @attribute(dtype=float, doc="Minimum of last time trace")
    def min(self):
        return self._min

    @attribute(dtype=float, doc="Maximum of last time trace")
    def max(self):
        return self._max

    @attribute(dtype=(float,), max_dim_x=400, doc="Time trace array (350 points)")
    def timetrace(self):
        return self._timetrace

    # ---- Commands -----------------------------------------------------------

    @command()
    def Start(self):
        """Start a single time-trace measurement."""
        self.ads.WriteBool(self.BeckhoffTTrun + '=true')
        self.set_state(DevState.RUNNING)
        self.set_status("Measuring time trace")

    @command()
    def Abort(self):
        """Abort the current measurement and clear ContinuousRun."""
        self._continuous = False
        try:
            self.ads.WriteBool(self.BeckhoffTTrun + '=false')
        except Exception as e:
            self.error_stream("TTbeckhoff: Abort WriteBool failed: {}".format(e))
        self.set_state(DevState.ON)
        self.set_status("Ready after abort")

    @command()
    def StartContinuous(self):
        """Set ContinuousRun and start the first measurement."""
        self._continuous = True
        self.Start()


def main(args=None, **kwargs):
    return run((TTbeckhoff,), args=args, **kwargs)


if __name__ == '__main__':
    main()
