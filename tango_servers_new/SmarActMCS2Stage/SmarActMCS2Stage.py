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

    TravelLimitsPm = device_property(
        dtype=('float',),
        default_value=[],
        doc="Hardware travel limits, 6 values in PICOMETRES relative to the "
            "logical zero: [Xmin, Xmax, Ymin, Ymax, Zmin, Zmax]. "
            "Written to the controller's own range limit "
            "(SA_CTL_PKEY_RANGE_LIMIT_MIN/MAX via the motors' "
            "StepLimitMin/StepLimitMax attributes), which the MCS2 firmware "
            "enforces itself — independent of move mode, of the Tango "
            "servers, and of any client. This is the only guard that survives "
            "an Init, a wrong unit conversion or a stale move mode. "
            "An axis whose pair is 0,0 is left alone (range limit disabled). "
            "Leave the property empty to disable the feature entirely. "
            "Example for a stage that must not travel more than 40 um above "
            "its zero in Z: [-1e8, 1e8, -1e8, 1e8, -1e8, 4e7]. "
            "Re-applied automatically after Initialise and after SetZero — "
            "the limits live in logical coordinates, so re-zeroing would "
            "otherwise silently move them."
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

    # ── Settings that must survive a motor Init ───────────────────────────
    # SmarActMCS2Motor::init_device unconditionally resets these in the
    # server's own state:
    #
    #   Conversion    -> 1     (Position reverts to raw picometres, so every
    #                          number the client sends changes meaning by
    #                          orders of magnitude)
    #   UnitLimitMin  -> 0.0   (write_Position treats min == max == 0 as
    #   UnitLimitMax  -> 0.0    "no limits", so the travel guard disappears)
    #
    # They are declared memorized in the .xmi, but whether TANGO replays a
    # memorized value on the *Init command* — as opposed to at server
    # start-up — is version dependent, and on this deployment it demonstrably
    # does not (the same is true of MoveMode, which is why Initialise has to
    # push that explicitly).  So Initialise captures them before the Init and
    # writes them back afterwards.
    _PRESERVE_ATTRS = ("Conversion", "UnitLimitMin", "UnitLimitMax")

    def _memorized_value(self, dev, attr):
        """Memorized value of `attr` from the TANGO database, or None.

        This is what the operator configured, and — unlike a live readback —
        it is unaffected by an earlier Init having already clobbered the
        running value.  Used as the primary source so a stage that was
        re-initialised before this fix existed still recovers.
        """
        try:
            db = tango.Database()
            props = db.get_device_attribute_property(dev, [attr])
            val = props[attr]["__value"][0]
            return float(val)
        except Exception:
            return None

    def _capture_settings(self, dev, mp):
        """Snapshot the preserve-list for one motor: memorized value first,
        live readback as the fallback."""
        snap = {}
        for attr in self._PRESERVE_ATTRS:
            val = self._memorized_value(dev, attr)
            if val is None:
                try:
                    val = float(mp.read_attribute(attr).value)
                except Exception:
                    val = None
            if val is not None:
                snap[attr] = val
        # A Conversion of 1 is what init_device leaves behind, so it is far
        # more likely to be damage from an earlier Init than a real setting.
        # Restoring it would just re-apply the bug; drop it and say so.
        if snap.get("Conversion") == 1.0:
            snap.pop("Conversion")
        return snap

    def _travel_limits(self):
        """Configured hardware travel limits as {axis: (min_pm, max_pm)}.

        Returns {} when the property is unset or malformed — the feature is
        opt-in, so a stage without it behaves exactly as before.
        """
        vals = list(self.TravelLimitsPm or [])
        if not vals:
            return {}
        if len(vals) != 6:
            self.warn_stream(
                f"TravelLimitsPm has {len(vals)} values, expected 6 "
                "[Xmin,Xmax,Ymin,Ymax,Zmin,Zmax] — ignoring it")
            return {}
        out = {}
        for i, axis in enumerate(("X", "Y", "Z")):
            lo, hi = float(vals[2 * i]), float(vals[2 * i + 1])
            if lo == 0.0 and hi == 0.0:
                continue                      # this axis: limit disabled
            if hi <= lo:
                self.warn_stream(
                    f"TravelLimitsPm for {axis}: max ({hi}) <= min ({lo}) — "
                    "ignoring this axis")
                continue
            out[axis] = (int(lo), int(hi))
        return out

    def _apply_travel_limits(self):
        """Push the configured range limits into the controller.

        Returns (applied_description, problems).  Called after Initialise and
        after SetZero: the range limit is expressed in logical coordinates, so
        re-zeroing the frame moves it, and a limit that has quietly moved is
        worse than none at all.
        """
        limits = self._travel_limits()
        if not limits:
            return "", []
        applied, problems = [], []
        for name, dev in [("X", self.XMotorDevice),
                          ("Y", self.YMotorDevice),
                          ("Z", self.ZMotorDevice)]:
            if name not in limits:
                continue
            lo, hi = limits[name]
            try:
                mp = tango.DeviceProxy(dev)
                mp.write_attribute("StepLimitMin", lo)
                mp.write_attribute("StepLimitMax", hi)
                back_lo = int(mp.read_attribute("StepLimitMin").value)
                back_hi = int(mp.read_attribute("StepLimitMax").value)
                if (back_lo, back_hi) != (lo, hi):
                    problems.append(
                        f"{name}: range limit read back "
                        f"[{back_lo}, {back_hi}] pm, expected [{lo}, {hi}]")
                else:
                    applied.append(f"{name}=[{lo}, {hi}]pm")
            except Exception as e:
                problems.append(f"{name}: range limit not applied: {e}")
                self.warn_stream(f"{name}: range limit not applied: {e}")
        return ", ".join(applied), problems

    @command()
    @DebugIt()
    def ApplyTravelLimits(self):
        """
        Write the TravelLimitsPm property into the controller's own range
        limit for each configured axis, and verify it by reading back.

        The MCS2 firmware enforces this limit itself, so it holds even when
        the move mode, the unit conversion or the client are wrong — which is
        exactly the situation the software guards cannot cover.  Values are
        PICOMETRES in the current logical frame, so this is re-run
        automatically after Initialise and SetZero.

        :rtype: PyTango.DevVoid
        """
        limits = self._travel_limits()
        if not limits:
            self.set_state(DevState.ON)
            self.set_status(
                "No hardware travel limits configured — set the TravelLimitsPm "
                "device property ([Xmin,Xmax,Ymin,Ymax,Zmin,Zmax] in pm) to "
                "enable the controller-side guard.")
            return
        applied, problems = self._apply_travel_limits()
        if problems:
            self.set_state(DevState.FAULT)
            self.set_status("Travel limits: " + "; ".join(problems))
            tango.Except.throw_exception(
                "ApplyTravelLimits failed",
                "; ".join(problems),
                "SmarActMCS2Stage::ApplyTravelLimits")
        self.set_state(DevState.ON)
        self.set_status(f"Hardware travel limits applied: {applied}")

    def _restore_settings(self, name, mp, snap):
        """Write a captured snapshot back after Init.  Returns a list of
        human-readable problems (empty when everything was restored)."""
        problems = []
        for attr, val in snap.items():
            try:
                mp.write_attribute(attr, val)
                back = float(mp.read_attribute(attr).value)
                if abs(back - val) > 1e-9:
                    problems.append(
                        f"{name}.{attr} read back {back:g}, expected {val:g}")
            except Exception as e:
                problems.append(f"{name}.{attr} could not be restored: {e}")
        return problems

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

        The per-motor ``Init`` call is given a **long client timeout** (30 s):
        re-running the motor's ``init_device`` reconnects the Ctrl and
        re-subscribes its event channel, which on a wedged axis (exactly the
        case this command exists for) can take longer than the default 3 s
        TANGO client timeout.  Without this, the ``Init`` call raised a CORBA
        timeout and the stage went FAULT even though the motor recovered a
        moment later — which is why doing it per-axis in Jive worked but this
        command appeared to "not work".

        Each motor is also forced back to **closed-loop absolute** move mode
        (``MoveMode = 0``).  The motor's Position write branches on a *cached*
        move mode, and a motor's ``Init`` resets only that cache (to
        CL_ABSOLUTE) without pushing it to the controller — so a move mode the
        hand controller left on the **hardware** survives.  A µm Position write
        is then computed for CL_ABSOLUTE but executed by ``SA_CTL_Move`` in the
        stale hardware mode, which fails with "movement finished ...
        (invalid parameter)".  Writing MoveMode here sets both the hardware
        (``SetMoveMode``) and the cache, so they can no longer disagree.

        An axis whose ``Init`` completes but leaves the motor un-referenced
        (FAULT "run Home command") is reported in the status — that is a
        Home concern, not an Initialise failure, so it does not fault the
        stage.  Follow with the ``Home`` command to zero at the reference marks.

        :rtype: PyTango.DevVoid
        """
        errors = []
        states = []
        warnings = []
        self.set_state(DevState.INIT)
        for name, dev in [("X", self.XMotorDevice),
                          ("Y", self.YMotorDevice),
                          ("Z", self.ZMotorDevice)]:
            self.set_status(f"Re-initialising {name} axis...")
            try:
                mp = tango.DeviceProxy(dev)
                # Give Init room to reconnect the Ctrl + re-subscribe events.
                mp.set_timeout_millis(30000)
                snap = self._capture_settings(dev, mp)
                mp.command_inout("Init")
            except Exception as e:
                errors.append(f"{name} ({dev}): {e}")
                self.warn_stream(f"Failed to initialise {name} axis: {e}")
                continue
            # Force closed-loop absolute mode on the hardware so a stale move
            # mode from the hand controller can't be executed as an open-loop
            # step move.  NOT best-effort any more: leaving the controller in
            # STEP/SCAN mode while the motor's cache says CL_ABSOLUTE is the
            # exact condition that turns a small position write into an
            # uncontrolled open-loop run, so a failure here is an error.
            try:
                mp.write_attribute("MoveMode", 0)   # 0 = CL_ABSOLUTE
                if int(mp.read_attribute("MoveMode").value) != 0:
                    raise RuntimeError("MoveMode did not read back as 0")
            except Exception as e:
                errors.append(
                    f"{name}: could not force closed-loop absolute mode: {e}")
                self.warn_stream(f"{name}: could not force MoveMode: {e}")
            # Put back the unit conversion and travel limits the motor's
            # init_device just wiped.  Without this, every later position
            # write is interpreted in a different unit and the motor-side
            # limit check is disabled.
            problems = self._restore_settings(name, mp, snap)
            if problems:
                errors.extend(problems)
            missing = [a for a in self._PRESERVE_ATTRS if a not in snap]
            if missing:
                warnings.append(
                    f"{name}: no stored value for {'/'.join(missing)} — "
                    "check it in Jive")
                self.warn_stream(
                    f"{name}: nothing to restore for {'/'.join(missing)}")
            # Report the resulting motor state: an axis that comes back
            # FAULT/"not referenced" needs Home, not another Init.
            try:
                time.sleep(0.2)
                states.append(f"{name}:{mp.state()}")
            except Exception:
                states.append(f"{name}:?")
        # Refresh our own proxies so the next read/write hits the fresh motors.
        try:
            self._x_proxy = tango.DeviceProxy(self.XMotorDevice)
            self._y_proxy = tango.DeviceProxy(self.YMotorDevice)
            self._z_proxy = tango.DeviceProxy(self.ZMotorDevice)
        except Exception as e:
            errors.append(f"stage proxies: {e}")
        # Re-assert the controller-side range limits.  They live in the
        # controller and survive an Init on their own, but re-writing them
        # here means one command restores the whole safe state.
        limits_applied, limit_problems = self._apply_travel_limits()
        errors.extend(limit_problems)
        if errors:
            self.set_state(DevState.FAULT)
            self.set_status("Initialise errors: " + "; ".join(errors))
            tango.Except.throw_exception(
                "Initialise failed",
                "; ".join(errors),
                "SmarActMCS2Stage::Initialise")
        self.set_state(DevState.ON)
        msg = ("All axes re-initialised (" + ", ".join(states) + "), "
               "closed-loop absolute mode forced, unit conversion and unit "
               "limits restored. "
               "Any axis reading FAULT/not-referenced needs the Home command.")
        if limits_applied:
            msg += f"  Hardware travel limits: {limits_applied}."
        if warnings:
            msg += "  WARNING: " + "; ".join(warnings)
        self.set_status(msg)
        # PROTECTED REGION END #    //  SmarActMCS2Stage.Initialise

    @command(
    )
    @DebugIt()
    def Home(self):
        # PROTECTED REGION ID(SmarActMCS2Stage.Home) ENABLED START #
        """
        Reference (home) all three axes with auto-zero.

        For each axis (X, Y, Z — sequentially, so only one axis moves at a
        time):

        1. write ``AutoZero = True`` on the motor device — the position
           counter is set to 0 when the reference mark is found
           (``SA_CTL_PKEY_REFERENCING_OPTIONS`` /
           ``SA_CTL_REF_OPT_BIT_AUTO_ZERO``, applied by the Ctrl's
           ``SetAutoZero``);
        2. run the motor's ``Home`` command (``SA_CTL_Reference``);
        3. wait for the referencing to finish (bounded by
           ``MovementTimeout``) and verify ``PositionKnown``.

        The stage physically MOVES each axis to its reference mark; the
        position attributes read 0 there afterwards.  This is the clean
        recovery after manual hand-controller use: run ``Initialise`` first
        if the axes are wedged, then ``Home`` to restore a consistent,
        zeroed position frame.

        All axes are attempted even if one fails; errors are collected and
        raised together.  The wait loop deliberately tolerates transient
        FAULT states — a stale latched axis event (e.g. "movement finished
        ... invalid parameter" after hand-controller use) is only cleared
        by the fresh events the referencing itself generates.

        :rtype: PyTango.DevVoid
        """
        errors = []
        self.set_state(DevState.MOVING)
        for name, proxy in [("X", self._x_proxy), ("Y", self._y_proxy),
                            ("Z", self._z_proxy)]:
            if proxy is None:
                errors.append(f"{name}: motor proxy not connected")
                continue
            self.set_status(f"Homing {name} axis (auto-zero)...")
            try:
                try:
                    proxy.write_attribute("AutoZero", True)
                except Exception as e:
                    self.warn_stream(f"{name}: could not set AutoZero: {e}")
                proxy.command_inout("Home")
            except Exception as e:
                errors.append(f"{name}: Home failed: {e}")
                continue
            time.sleep(0.5)          # let the referencing engage
            deadline = time.time() + self.MovementTimeout
            ok = False
            while time.time() < deadline:
                try:
                    if proxy.state() == DevState.MOVING:
                        time.sleep(0.1)
                        continue
                    known = bool(proxy.read_attribute("PositionKnown").value)
                except Exception:
                    time.sleep(0.1)
                    continue
                if known:
                    ok = True
                    break
                time.sleep(0.1)
            if not ok:
                try:
                    st = proxy.status()
                except Exception:
                    st = "?"
                errors.append(
                    f"{name}: homing did not complete within "
                    f"{self.MovementTimeout}s ({st})")
        if errors:
            self.set_state(DevState.FAULT)
            self.set_status("Home errors: " + "; ".join(errors))
            tango.Except.throw_exception(
                "Home failed",
                "; ".join(errors),
                "SmarActMCS2Stage::Home")
        self.set_state(DevState.ON)
        self.set_status(
            "All axes homed (auto-zero) — positions read 0 at the reference marks.")
        # PROTECTED REGION END #    //  SmarActMCS2Stage.Home

    @command(
    )
    @DebugIt()
    def SetZero(self):
        # PROTECTED REGION ID(SmarActMCS2Stage.SetZero) ENABLED START #
        """
        Define the CURRENT position of all three axes as 0 — **no movement**.

        Unlike ``Home`` (which runs a referencing routine: the axis physically
        drives to its hardware reference mark and zeros there), this just
        re-labels the current position as the origin, in place.  It uses the
        controller's ``SetOffset`` command (``SA_CTL_PKEY_LOGICAL_SCALE_OFFSET``
        adjusted so the current reading becomes 0); the SmarAct routine
        preserves the move mode and does not travel.

        The motor devices do not expose ``SetOffset``, so this reaches the
        shared Ctrl directly, discovering its device name and each axis'
        channel number from the motor's own ``SmarActMCS2CtrlDevice`` /
        ``AxisNumber`` properties.  All axes are attempted; errors are
        collected and raised together.

        :rtype: PyTango.DevVoid
        """
        # Zeroing reads the current position to compute the offset, so an axis
        # that is still travelling would be pinned to a position it has
        # already left.  Refuse rather than silently mis-zero the frame.
        moving = []
        for name, proxy in [("X", self._x_proxy), ("Y", self._y_proxy),
                            ("Z", self._z_proxy)]:
            try:
                if proxy is not None and proxy.state() == DevState.MOVING:
                    moving.append(name)
            except Exception:
                pass
        if moving:
            self.set_state(DevState.FAULT)
            self.set_status(
                "SetZero refused: axis/axes still moving: " + ", ".join(moving))
            tango.Except.throw_exception(
                "SetZero refused",
                "Axes still moving: " + ", ".join(moving) +
                ". Wait for the move to finish (or send Stop) and retry.",
                "SmarActMCS2Stage::SetZero")

        errors = []
        for name, dev in [("X", self.XMotorDevice),
                          ("Y", self.YMotorDevice),
                          ("Z", self.ZMotorDevice)]:
            try:
                mp = tango.DeviceProxy(dev)
                props = mp.get_property(["SmarActMCS2CtrlDevice", "AxisNumber"])
                ctrl_name = props["SmarActMCS2CtrlDevice"][0]
                axis = int(props["AxisNumber"][0])
                ctrl = tango.DeviceProxy(ctrl_name)
                # SetOffset(channel, target): make the current reading = target.
                ctrl.command_inout("SetOffset", [axis, 0])
            except Exception as e:
                errors.append(f"{name} ({dev}): {e}")
                self.warn_stream(f"Failed to zero {name} axis: {e}")
                continue
            # The Ctrl's SetOffset re-arms closed-loop holding by briefly
            # switching to CL_RELATIVE and then restoring whatever move mode
            # it found — including STEP or SCAN, which a hand controller can
            # leave behind.  That would put the hardware back into open-loop
            # mode while the motor's cache still says CL_ABSOLUTE, so the next
            # position write becomes an open-loop step move.  Re-assert
            # closed-loop absolute on both sides afterwards.  (Defence in
            # depth: this works even against a Ctrl server that has not been
            # rebuilt with the matching fix.)
            try:
                mp.write_attribute("MoveMode", 0)   # 0 = CL_ABSOLUTE
                if int(mp.read_attribute("MoveMode").value) != 0:
                    raise RuntimeError("MoveMode did not read back as 0")
            except Exception as e:
                errors.append(
                    f"{name}: closed-loop absolute mode not restored after "
                    f"zeroing: {e}")
                self.warn_stream(f"{name}: MoveMode not restored: {e}")
        # The controller's range limits are expressed in the LOGICAL frame we
        # have just moved, so a limit configured before the re-zero now sits
        # somewhere else entirely.  Re-apply it relative to the new zero — a
        # limit that has silently shifted is more dangerous than none.
        limits_applied, limit_problems = self._apply_travel_limits()
        errors.extend(limit_problems)
        # Refresh cached positions from the re-zeroed motors.
        try:
            self._x = self._x_proxy.Position if self._x_proxy else 0.0
            self._y = self._y_proxy.Position if self._y_proxy else 0.0
            self._z = self._z_proxy.Position if self._z_proxy else 0.0
        except Exception:
            pass
        if errors:
            self.set_state(DevState.FAULT)
            self.set_status("SetZero errors: " + "; ".join(errors))
            tango.Except.throw_exception(
                "SetZero failed",
                "; ".join(errors),
                "SmarActMCS2Stage::SetZero")
        self.set_state(DevState.ON)
        msg = "Current position defined as 0 on all axes (no movement)."
        if limits_applied:
            msg += f"  Hardware travel limits re-applied: {limits_applied}."
        self.set_status(msg)
        # PROTECTED REGION END #    //  SmarActMCS2Stage.SetZero

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
