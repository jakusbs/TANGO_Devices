# -*- coding: utf-8 -*-
#
# This file is part of the SmarActMCS2Stage project
#
#
#
# Distributed under the terms of the none license.
# See LICENSE.txt for more info.

"""
MCS2 All axis control

This class controls all 3 axis of the mcs2 motor system
"""
# PROTECTED REGION ID(SmarActMCS2Stage.system_imports) ENABLED START #
import time

# PROTECTED REGION END #    //  SmarActMCS2Stage.system_imports

# PyTango imports
import tango
from tango import DebugIt
from tango.server import run
from tango.server import Device
from tango.server import attribute, command
from tango.server import class_property, device_property
from tango import AttrQuality, DispLevel, DevState
from tango import AttrWriteType
# Additional import
# PROTECTED REGION ID(SmarActMCS2Stage.additionnal_import) ENABLED START #
# PROTECTED REGION END #    //  SmarActMCS2Stage.additionnal_import

__all__ = ["SmarActMCS2Stage", "main"]


class SmarActMCS2Stage(Device):
    """
    This class controls all 3 axis of the mcs2 motor system

    **Properties:**

    - Class Property
        MovementTimeout
            - how long to wait for a move
            - Type:'float'
    - Device Property
        ZMotorDevice
            - name of the motor device controling the axis z (smaract2/mcs2/z)
            - Type:'str'
        XMotorDevice
            - name of the motor device controling the axis X (smaract2/mcs2motor/x)
            - Type:'str'
        YMotorDevice
            - name of the motor device controling the axis y (smaract2/mcs2motor/y)
            - Type:'str'
    """
    # PROTECTED REGION ID(SmarActMCS2Stage.class_variable) ENABLED START #
    # PROTECTED REGION END #    //  SmarActMCS2Stage.class_variable

    # ----------------
    # Class Properties
    # ----------------

    MovementTimeout = class_property(
        dtype='float',
        default_value=30.0,
        doc="how long to wait for a move"
    )

    # -----------------
    # Device Properties
    # -----------------

    ZMotorDevice = device_property(
        dtype='str',
        doc="name of the motor device controling the axis z (smaract2/mcs2/z)",
        mandatory=True
    )

    XMotorDevice = device_property(
        dtype='str',
        doc="name of the motor device controling the axis X (smaract2/mcs2motor/x)",
        mandatory=True
    )

    YMotorDevice = device_property(
        dtype='str',
        doc="name of the motor device controling the axis y (smaract2/mcs2motor/y)",
        mandatory=True
    )

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initializes the attributes and properties of the SmarActMCS2Stage."""
        Device.init_device(self)
        self._z = 0.0
        self._x = 0.0
        self._y = 0.0
        # PROTECTED REGION ID(SmarActMCS2Stage.init_device) ENABLED START #
        self._x_proxy = None
        self._y_proxy = None
        self._z_proxy = None
        try:
            self._x_proxy = tango.DeviceProxy(self.XMotorDevice)
            self._y_proxy = tango.DeviceProxy(self.YMotorDevice)
            self._z_proxy = tango.DeviceProxy(self.ZMotorDevice)
            self.set_state(DevState.ON)
            self.set_status("Stage initialized and connected to all motor devices.")
        except Exception as e:
            self.set_state(DevState.FAULT)
            self.set_status(f"Failed to connect to motor devices: {e}")
        # PROTECTED REGION END #    //  SmarActMCS2Stage.init_device

    def _require_proxy(self, proxy, axis_name):
        if proxy is None:
            tango.Except.throw_exception(
                f"{axis_name} axis not connected",
                "Motor proxy unavailable — check XMotorDevice/YMotorDevice/ZMotorDevice properties and restart the server",
                f"SmarActMCS2Stage::{axis_name}")

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""
        # PROTECTED REGION ID(SmarActMCS2Stage.always_executed_hook) ENABLED START #
        # PROTECTED REGION END #    //  SmarActMCS2Stage.always_executed_hook

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """
        # PROTECTED REGION ID(SmarActMCS2Stage.delete_device) ENABLED START #
        self._x_proxy = None
        self._y_proxy = None
        self._z_proxy = None
        # PROTECTED REGION END #    //  SmarActMCS2Stage.delete_device
        
    # ----------
    # Attributes
    # ----------

    @attribute(
        label='Z',
        dtype='DevDouble',
        access=AttrWriteType.READ_WRITE,
    )
    def z(self):
        # PROTECTED REGION ID(SmarActMCS2Stage.Z_read) ENABLED START #
        """Return the Z attribute."""
        self._require_proxy(self._z_proxy, "Z")
        self._z = self._z_proxy.Position
        return self._z
        # PROTECTED REGION END #    //  SmarActMCS2Stage.Z_read

    @z.write
    def z(self, value):
        # PROTECTED REGION ID(SmarActMCS2Stage.Z_write) ENABLED START #
        """Set the Z attribute."""
        self._require_proxy(self._z_proxy, "Z")
        self._z_proxy.Position = value
        self._wait_for_motor(self._z_proxy, "Z")
        # PROTECTED REGION END #    //  SmarActMCS2Stage.Z_write

    @attribute(
        label='X',
        dtype='DevDouble',
        access=AttrWriteType.READ_WRITE,
    )
    def x(self):
        # PROTECTED REGION ID(SmarActMCS2Stage.X_read) ENABLED START #
        """Return the X attribute."""
        self._require_proxy(self._x_proxy, "X")
        self._x = self._x_proxy.Position
        return self._x
        # PROTECTED REGION END #    //  SmarActMCS2Stage.X_read

    @x.write
    def x(self, value):
        # PROTECTED REGION ID(SmarActMCS2Stage.X_write) ENABLED START #
        """Set the X attribute."""
        self._require_proxy(self._x_proxy, "X")
        self._x_proxy.Position = value
        self._wait_for_motor(self._x_proxy, "X")
        # PROTECTED REGION END #    //  SmarActMCS2Stage.X_write

    @attribute(
        label='Y',
        dtype='DevDouble',
        access=AttrWriteType.READ_WRITE,
    )
    def y(self):
        # PROTECTED REGION ID(SmarActMCS2Stage.Y_read) ENABLED START #
        """Return the Y attribute."""
        self._require_proxy(self._y_proxy, "Y")
        self._y = self._y_proxy.Position
        return self._y
        # PROTECTED REGION END #    //  SmarActMCS2Stage.Y_read

    @y.write
    def y(self, value):
        # PROTECTED REGION ID(SmarActMCS2Stage.Y_write) ENABLED START #
        """Set the Y attribute."""
        self._require_proxy(self._y_proxy, "Y")
        self._y_proxy.Position = value
        self._wait_for_motor(self._y_proxy, "Y")
        # PROTECTED REGION END #    //  SmarActMCS2Stage.Y_write

    # --------
    # Commands
    # --------


    @command(
    )
    @DebugIt()
    def Stop(self):
        # PROTECTED REGION ID(SmarActMCS2Stage.Stop) ENABLED START #
        """
        :rtype: PyTango.DevVoid
        """
        for proxy, name in [(self._x_proxy, "X"), (self._y_proxy, "Y"), (self._z_proxy, "Z")]:
            if proxy is None:
                self.warn_stream(f"{name} axis not connected, skipping Stop")
                continue
            try:
                proxy.command_inout("Stop")
            except Exception as e:
                self.warn_stream(f"Failed to stop {name} axis: {e}")
        self.set_state(DevState.ON)
        self.set_status("All axes stopped.")
        # PROTECTED REGION END #    //  SmarActMCS2Stage.Stop

    @command(
    )
    @DebugIt()
    def Initialise(self):
        # PROTECTED REGION ID(SmarActMCS2Stage.Initialise) ENABLED START #
        """
        Re-initialise all three motor axes — the fix for a wedged SmarAct axis
        after manual use with the hand controller.  Sends the standard TANGO
        ``Init`` command to each underlying motor device (X, Y, Z), which
        re-runs its ``init_device`` and re-establishes the MCS2 connection
        (this is the "Initialise" one otherwise clicks per-axis in Jive —
        distinct from Home / CalibrateAxis).  The stage's own cached proxies
        are then refreshed.  All axes are attempted even if one fails; any
        errors are collected and raised together.

        :rtype: PyTango.DevVoid
        """
        errors = []
        for name, dev in [("X", self.XMotorDevice),
                          ("Y", self.YMotorDevice),
                          ("Z", self.ZMotorDevice)]:
            try:
                tango.DeviceProxy(dev).command_inout("Init")
            except Exception as e:
                errors.append(f"{name} ({dev}): {e}")
                self.warn_stream(f"Failed to initialise {name} axis: {e}")
        # Refresh our own proxies so the next read/write hits the fresh motors.
        try:
            self._x_proxy = tango.DeviceProxy(self.XMotorDevice)
            self._y_proxy = tango.DeviceProxy(self.YMotorDevice)
            self._z_proxy = tango.DeviceProxy(self.ZMotorDevice)
        except Exception as e:
            errors.append(f"stage proxies: {e}")
        if errors:
            self.set_state(DevState.FAULT)
            self.set_status("Initialise errors: " + "; ".join(errors))
            tango.Except.throw_exception(
                "Initialise failed",
                "; ".join(errors),
                "SmarActMCS2Stage::Initialise")
        self.set_state(DevState.ON)
        self.set_status("All axes re-initialised.")
        # PROTECTED REGION END #    //  SmarActMCS2Stage.Initialise

# ----------
# Run server
# ----------

# PROTECTED REGION ID(SmarActMCS2Stage.custom_code) ENABLED START #
    def _wait_for_motor(self, proxy, axis_name):
            """Wait for a motor to reach ON state after a move, respecting MovementTimeout."""
            deadline = time.time() + self.MovementTimeout
            self.set_state(DevState.MOVING)
            self.set_status(f"Moving {axis_name} axis...")
            while time.time() < deadline:
                try:
                    state = proxy.state()
                    if state == DevState.ON:
                        self.set_state(DevState.ON)
                        self.set_status("Move completed.")
                        return
                    elif state == DevState.FAULT:
                        self.set_state(DevState.FAULT)
                        self.set_status(f"{axis_name} axis is in FAULT state.")
                        return
                except Exception as e:
                    self.set_state(DevState.FAULT)
                    self.set_status(f"Error reading {axis_name} axis state: {e}")
                    return
                time.sleep(0.05)
            self.set_state(DevState.FAULT)
            self.set_status(f"{axis_name} axis move timed out after {self.MovementTimeout}s.")
# PROTECTED REGION END #    //  SmarActMCS2Stage.custom_code


def main(args=None, **kwargs):
    """Main function of the SmarActMCS2Stage module."""
    # PROTECTED REGION ID(SmarActMCS2Stage.main) ENABLED START #
    return run((SmarActMCS2Stage,), args=args, **kwargs)
    # PROTECTED REGION END #    //  SmarActMCS2Stage.main

# PROTECTED REGION ID(SmarActMCS2Stage.custom_functions) ENABLED START #
# PROTECTED REGION END #    //  SmarActMCS2Stage.custom_functions


if __name__ == '__main__':
    main()
