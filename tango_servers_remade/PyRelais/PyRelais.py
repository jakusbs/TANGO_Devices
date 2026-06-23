# -*- coding: utf-8 -*-
"""
PyRelais
Controls a relay via a Beckhoff digital output channel through AdsBridge2.
Uses a ground-short safety sequence to prevent voltage spikes when switching.
"""

import time

import tango
from tango import DevState, AttrWriteType
from tango.server import Device, command, attribute, device_property, run

__all__ = ["PyRelais", "main"]


class PyRelais(Device):
    """
    Relay controller using a Beckhoff digital output.
    The ON/OFF sequence grounds the contact before switching to prevent damage.

    **Properties:**
    - AdsBridge: TANGO path to AdsBridge2 device
    - BeckhoffVariable: Beckhoff variable that switches the relay (True=ON)
    - BeckhoffGround: Beckhoff variable that grounds the relay contact
    """

    AdsBridge = device_property(
        dtype='str',
        default_value='hpp-N42/beckhoff/adsBridge2',
        doc="TANGO path to AdsBridge2 device"
    )
    BeckhoffVariable = device_property(
        dtype='str',
        default_value='MAIN.DigitalOut2',
        doc="Beckhoff variable for relay coil"
    )
    BeckhoffGround = device_property(
        dtype='str',
        default_value='MAIN.DigitalOut7',
        doc="Beckhoff variable to ground the relay contact before switching"
    )

    def init_device(self):
        Device.init_device(self)
        self._switchvar = 0
        self.ads = tango.DeviceProxy(self.AdsBridge)
        self.info_stream("PyRelais: opened AdsBridge proxy at " + self.AdsBridge)
        self.set_state(DevState.ON)

    def always_executed_hook(self):
        pass

    # ---- Attributes -----------------------------------------------------

    @attribute(dtype=tango.DevShort, access=AttrWriteType.READ_WRITE,
               doc="Write odd value → ON, even value → OFF")
    def switchvar(self):
        return self._switchvar

    @switchvar.write
    def switchvar(self, value):
        # Cache updated only after the hardware sequence succeeded, so a
        # failed switch does not leave the cache disagreeing with hardware.
        if value % 2 == 0:
            self.OFF()
        else:
            self.ON()
        self._switchvar = value

    # ---- Commands -------------------------------------------------------

    def _switch(self, turn_on):
        """Ground → switch → unground.  The unground always runs; if it
        fails too (e.g. AdsBridge down for the whole sequence), the relay
        contact may still be grounded — set FAULT with a descriptive status
        and raise an error carrying BOTH failures instead of letting the
        unground exception mask the original one."""
        switch_err = None
        try:
            self.ads.WriteBool(self.BeckhoffGround + '=true')
            time.sleep(0.05)
            self.ads.WriteBool(self.BeckhoffVariable +
                               ('=true' if turn_on else '=false'))
            time.sleep(0.05)
        except Exception as e:
            switch_err = e
        try:
            self.ads.WriteBool(self.BeckhoffGround + '=false')
        except Exception as unground_err:
            self.set_state(DevState.FAULT)
            self.set_status("Unground write failed — relay contact may still "
                            "be grounded: {}".format(unground_err))
            tango.Except.throw_exception(
                "Relay may still be grounded",
                "unground failed: {}{}".format(
                    unground_err,
                    "; original switch error: {}".format(switch_err)
                    if switch_err else ""),
                "PyRelais::_switch")
        if switch_err is not None:
            raise switch_err
        self.set_state(DevState.ON if turn_on else DevState.STANDBY)

    @command()
    def ON(self):
        """Set relay to ON (ground → set → unground). unground always runs."""
        self._switch(True)

    @command()
    def OFF(self):
        """Set relay to OFF (ground → clear → unground). unground always runs."""
        self._switch(False)


def main(args=None, **kwargs):
    return run((PyRelais,), args=args, **kwargs)


if __name__ == '__main__':
    main()
