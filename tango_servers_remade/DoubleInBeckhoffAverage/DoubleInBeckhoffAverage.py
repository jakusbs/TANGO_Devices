# -*- coding: utf-8 -*-
"""
DoubleInBeckhoffAverage
Reads a Beckhoff-averaged double value via AdsBridge2.
The Beckhoff PLC performs on-board averaging; this device starts/aborts
the averaging and reads the result. IntegrationTime maps to the number
of PLC cycles (cyclesPerSecond = 1000).
"""

import tango
from tango import DevState, AttrWriteType
from tango.server import Device, command, attribute, device_property, run

__all__ = ["DoubleInBeckhoffAverage", "main"]

CYCLES_PER_SECOND = 1000.0


class DoubleInBeckhoffAverage(Device):
    """
    Reads a Beckhoff averaged double.
    State RUNNING while PLC averaging is in progress; ON when ready.

    **Properties:**
    - AdsBridge: TANGO path to AdsBridge2 device
    - BeckhoffVariable: PLC variable holding the averaged result (LREAL)
    - BeckhoffAveraging: PLC bool flag — True while averaging is running
    - BeckhoffAverageNum: PLC INT variable for number of cycles to average
    - BeckhoffAverageAbort: PLC bool flag — write True to abort averaging
    """

    AdsBridge = device_property(
        dtype='str', default_value='adsBridge2',
        doc="TANGO path to AdsBridge2 device"
    )
    BeckhoffVariable = device_property(
        dtype='str', mandatory=True,
        doc="PLC LREAL variable with the averaged result"
    )
    BeckhoffAveraging = device_property(
        dtype='str', mandatory=True,
        doc="PLC BOOL flag that is True while averaging is running"
    )
    BeckhoffAverageNum = device_property(
        dtype='str', mandatory=True,
        doc="PLC INT variable: number of cycles to average"
    )
    BeckhoffAverageAbort = device_property(
        dtype='str', mandatory=True,
        doc="PLC BOOL flag — write True to abort averaging"
    )

    def init_device(self):
        Device.init_device(self)
        self._value = -10.0
        self._integration_time = 0.0
        self.ads = tango.DeviceProxy(self.AdsBridge)
        self.info_stream("DoubleInBeckhoffAverage: using {} via {}".format(
            self.BeckhoffVariable, self.AdsBridge))
        self.set_state(DevState.ON)
        self.set_status("Ready to read average of " + self.BeckhoffVariable)

    def always_executed_hook(self):
        """Poll the PLC averaging flag to keep the TANGO state in sync."""
        try:
            averaging = self.ads.ReadBool(self.BeckhoffAveraging)
            if averaging:
                self.set_state(DevState.RUNNING)
            else:
                self.set_state(DevState.ON)
                self.set_status("Ready to read average of " + self.BeckhoffVariable)
        except Exception:
            pass

    # ---- Attributes -----------------------------------------------------

    @attribute(dtype=float, doc="Averaged value read from the PLC")
    def Value(self):
        try:
            self._value = self.ads.ReadReal(self.BeckhoffVariable)
        except Exception:
            self._value = -10.0
        return self._value

    @attribute(dtype=float, access=AttrWriteType.READ_WRITE,
               unit='s', doc="Integration time in seconds (converted to PLC cycle count)")
    def IntegrationTime(self):
        try:
            num = self.ads.ReadShort(self.BeckhoffAverageNum)
            self._integration_time = float(num) / CYCLES_PER_SECOND
        except Exception:
            pass
        return self._integration_time

    @IntegrationTime.write
    def IntegrationTime(self, value):
        num_cycles = int(value * CYCLES_PER_SECOND)
        self.ads.WriteShort("{}={}".format(self.BeckhoffAverageNum, num_cycles))
        self._integration_time = value

    # ---- Commands -------------------------------------------------------

    @command()
    def Start(self):
        """Start averaging on the PLC."""
        self.set_state(DevState.RUNNING)
        self.set_status("Averaging")
        self.ads.WriteBool(self.BeckhoffAveraging + '=true')

    @command()
    def Abort(self):
        """Abort the current averaging process."""
        self.ads.WriteBool(self.BeckhoffAverageAbort + '=true')
        self.set_state(DevState.ON)
        self.set_status("Aborted last averaging process")


def main(args=None, **kwargs):
    return run((DoubleInBeckhoffAverage,), args=args, **kwargs)


if __name__ == '__main__':
    main()
