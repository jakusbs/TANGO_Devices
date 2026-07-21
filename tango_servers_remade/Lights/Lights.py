# -*- coding: utf-8 -*-
"""
Lights
Controls two LEDs via Beckhoff digital outputs through an AdsBridge2 proxy.
"""

import tango
from tango import DevState, AttrWriteType
from tango.server import Device, attribute, command, device_property, run

__all__ = ["Lights", "main"]


class Lights(Device):
    """
    Controls the two LEDs using Beckhoff digital output channels.
    State ON means both LEDs are on; STANDBY means at least one is off.

    **Properties:**
    - AdsBridge: TANGO path to the AdsBridge2 device
    - Light1: Beckhoff variable name for LED 1
    - Light2: Beckhoff variable name for LED 2
    """

    AdsBridge = device_property(
        dtype='str',
        default_value='adsBridge2',
        doc="TANGO path to AdsBridge2 device"
    )
    Light1 = device_property(
        dtype='str',
        default_value='MAIN.DigitalOut3',
        doc="Beckhoff variable for LED 1"
    )
    Light2 = device_property(
        dtype='str',
        default_value='MAIN.DigitalOut4',
        doc="Beckhoff variable for LED 2"
    )

    def init_device(self):
        Device.init_device(self)
        self.ads = tango.DeviceProxy(self.AdsBridge)
        self.info_stream("Lights: opened AdsBridge proxy at " + self.AdsBridge)
        self.set_state(DevState.ON)

    def always_executed_hook(self):
        pass

    # ---- Attributes ------------------------------------------------------
    # Read-back of the two LED states from the Beckhoff digital outputs, so
    # clients (SAMBA's Calibration tab) can show the actual on/off state
    # instead of only tracking the last command they sent.

    @attribute(dtype=bool)
    def led1(self):
        """LED 1 state (True = on), read live from the Beckhoff output."""
        return bool(self.ads.ReadBool(self.Light1))

    @attribute(dtype=bool)
    def led2(self):
        """LED 2 state (True = on), read live from the Beckhoff output."""
        return bool(self.ads.ReadBool(self.Light2))

    # ---- Commands -------------------------------------------------------

    @command()
    def LED1ON(self):
        """Turn LED 1 on."""
        self.ads.WriteBool(self.Light1 + '=true')
        if self.ads.ReadBool(self.Light2):
            self.set_state(DevState.ON)
        else:
            self.set_state(DevState.STANDBY)

    @command()
    def LED1OFF(self):
        """Turn LED 1 off."""
        self.ads.WriteBool(self.Light1 + '=false')
        if not self.ads.ReadBool(self.Light2):
            self.set_state(DevState.STANDBY)
        else:
            self.set_state(DevState.ON)

    @command()
    def LED2ON(self):
        """Turn LED 2 on."""
        self.ads.WriteBool(self.Light2 + '=true')
        if self.ads.ReadBool(self.Light1):
            self.set_state(DevState.ON)
        else:
            self.set_state(DevState.STANDBY)

    @command()
    def LED2OFF(self):
        """Turn LED 2 off."""
        self.ads.WriteBool(self.Light2 + '=false')
        if not self.ads.ReadBool(self.Light1):
            self.set_state(DevState.STANDBY)
        else:
            self.set_state(DevState.ON)

    @command()
    def AllON(self):
        """Turn both LEDs on."""
        self.ads.WriteBool(self.Light1 + '=true')
        self.ads.WriteBool(self.Light2 + '=true')
        self.set_state(DevState.ON)

    @command()
    def AllOFF(self):
        """Turn both LEDs off."""
        self.ads.WriteBool(self.Light1 + '=false')
        self.ads.WriteBool(self.Light2 + '=false')
        self.set_state(DevState.STANDBY)


def main(args=None, **kwargs):
    return run((Lights,), args=args, **kwargs)


if __name__ == '__main__':
    main()
