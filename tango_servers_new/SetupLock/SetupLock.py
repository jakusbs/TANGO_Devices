# -*- coding: utf-8 -*-
#
# This file is part of the Setup_lock project
#
#
#
# Distributed under the terms of the none license.
# See LICENSE.txt for more info.

"""
Samba

TANGO device server acting as a mutex/lock for three setups controled by Samba
"""

# PROTECTED REGION ID(Setup_lock.system_imports) ENABLED START #
# PROTECTED REGION END #    //  Setup_lock.system_imports

# PyTango imports
import tango
from tango import DebugIt
from tango.server import run
from tango.server import Device
from tango.server import attribute, command
from tango import AttrQuality, DispLevel, DevState
from tango import AttrWriteType
# Additional import
# PROTECTED REGION ID(Setup_lock.additionnal_import) ENABLED START #
import json
from lease_store import LeaseStore
# PROTECTED REGION END #    //  Setup_lock.additionnal_import

__all__ = ["Setup_lock", "main"]


class Setup_lock(Device):
    """
    TANGO device server acting as a mutex/lock for three setups controled by Samba
    """
    # PROTECTED REGION ID(Setup_lock.class_variable) ENABLED START #
    # PROTECTED REGION END #    //  Setup_lock.class_variable

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initializes the attributes and properties of the Setup_lock."""
        Device.init_device(self)
        # PROTECTED REGION ID(Setup_lock.init_device) ENABLED START #
        self._leases = LeaseStore()
        self.set_state(DevState.ON)
        self.set_status('Setup_lock ready - all setups free')
        # PROTECTED REGION END #    //  Setup_lock.init_device

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""
        # PROTECTED REGION ID(Setup_lock.always_executed_hook) ENABLED START #
        any_busy = any(self._leases.status(name)["busy"] for name in ("green", "ir", "cryo"))
        self.set_state(DevState.RUNNING if any_busy else DevState.ON)
        # PROTECTED REGION END #    //  Setup_lock.always_executed_hook

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """
        # PROTECTED REGION ID(Setup_lock.delete_device) ENABLED START #
        # PROTECTED REGION END #    //  Setup_lock.delete_device

    # ----------
    # Attributes
    # ----------

    @attribute(
        label='GreenBusy',
        dtype='DevBoolean',
        access=AttrWriteType.READ_WRITE,
        doc="True when Green setup is measuring",
    )
    def greenbusy(self):
        # PROTECTED REGION ID(Setup_lock.GreenBusy_read) ENABLED START #
        """Return the GreenBusy attribute."""
        return self._leases.status("green")["busy"]
        # PROTECTED REGION END #    //  Setup_lock.GreenBusy_read

    @greenbusy.write
    def greenbusy(self, value):
        # PROTECTED REGION ID(Setup_lock.GreenBusy_write) ENABLED START #
        """Set the GreenBusy attribute."""
        self._leases.legacy_write("green", "busy", value)
        # PROTECTED REGION END #    //  Setup_lock.GreenBusy_write

    @attribute(
        label='IrBusy',
        dtype='DevBoolean',
        access=AttrWriteType.READ_WRITE,
        doc="True when Ir setup is measuring",
    )
    def irbusy(self):
        # PROTECTED REGION ID(Setup_lock.IrBusy_read) ENABLED START #
        """Return the IrBusy attribute."""
        return self._leases.status("ir")["busy"]
        # PROTECTED REGION END #    //  Setup_lock.IrBusy_read

    @irbusy.write
    def irbusy(self, value):
        # PROTECTED REGION ID(Setup_lock.IrBusy_write) ENABLED START #
        """Set the IrBusy attribute."""
        self._leases.legacy_write("ir", "busy", value)
        # PROTECTED REGION END #    //  Setup_lock.IrBusy_write

    @attribute(
        label='CryoBusy',
        dtype='DevBoolean',
        access=AttrWriteType.READ_WRITE,
        doc="True when Cryo setup is measuring",
    )
    def cryobusy(self):
        # PROTECTED REGION ID(Setup_lock.CryoBusy_read) ENABLED START #
        """Return the CryoBusy attribute."""
        return self._leases.status("cryo")["busy"]
        # PROTECTED REGION END #    //  Setup_lock.CryoBusy_read

    @cryobusy.write
    def cryobusy(self, value):
        # PROTECTED REGION ID(Setup_lock.CryoBusy_write) ENABLED START #
        """Set the CryoBusy attribute."""
        self._leases.legacy_write("cryo", "busy", value)
        # PROTECTED REGION END #    //  Setup_lock.CryoBusy_write

    @attribute(
        label='GreenInfo',
        dtype='DevString',
        access=AttrWriteType.READ_WRITE,
    )
    def greeninfo(self):
        # PROTECTED REGION ID(Setup_lock.GreenInfo_read) ENABLED START #
        """Return the GreenInfo attribute."""
        return self._leases.status("green")["owner"]
        # PROTECTED REGION END #    //  Setup_lock.GreenInfo_read

    @greeninfo.write
    def greeninfo(self, value):
        # PROTECTED REGION ID(Setup_lock.GreenInfo_write) ENABLED START #
        """Set the GreenInfo attribute."""
        self._leases.legacy_write("green", "info", value)
        # PROTECTED REGION END #    //  Setup_lock.GreenInfo_write

    @attribute(
        label='IrInfo',
        dtype='DevString',
        access=AttrWriteType.READ_WRITE,
    )
    def irinfo(self):
        # PROTECTED REGION ID(Setup_lock.IrInfo_read) ENABLED START #
        """Return the IrInfo attribute."""
        return self._leases.status("ir")["owner"]
        # PROTECTED REGION END #    //  Setup_lock.IrInfo_read

    @irinfo.write
    def irinfo(self, value):
        # PROTECTED REGION ID(Setup_lock.IrInfo_write) ENABLED START #
        """Set the IrInfo attribute."""
        self._leases.legacy_write("ir", "info", value)
        # PROTECTED REGION END #    //  Setup_lock.IrInfo_write

    @attribute(
        label='CryoInfo',
        dtype='DevString',
        access=AttrWriteType.READ_WRITE,
    )
    def cryoinfo(self):
        # PROTECTED REGION ID(Setup_lock.CryoInfo_read) ENABLED START #
        """Return the CryoInfo attribute."""
        return self._leases.status("cryo")["owner"]
        # PROTECTED REGION END #    //  Setup_lock.CryoInfo_read

    @cryoinfo.write
    def cryoinfo(self, value):
        # PROTECTED REGION ID(Setup_lock.CryoInfo_write) ENABLED START #
        """Set the CryoInfo attribute."""
        self._leases.legacy_write("cryo", "info", value)
        # PROTECTED REGION END #    //  Setup_lock.CryoInfo_write

    # --------
    # Commands
    # --------


    @command(dtype_in=str, dtype_out=str)
    def AcquireLease(self, argin):
        """JSON {setup, owner, ttl} -> JSON {acquired, owner}."""
        # PROTECTED REGION ID(Setup_lock.AcquireLease) ENABLED START #
        args = json.loads(argin)
        return json.dumps(self._leases.acquire(args["setup"], args["owner"], args.get("ttl", 180)))
        # PROTECTED REGION END #    //  Setup_lock.AcquireLease

    @command(dtype_in=str, dtype_out=bool)
    def RenewLease(self, argin):
        """Renew only the current, unexpired owner."""
        # PROTECTED REGION ID(Setup_lock.RenewLease) ENABLED START #
        args = json.loads(argin)
        return self._leases.renew(args["setup"], args["owner"], args.get("ttl", 180))
        # PROTECTED REGION END #    //  Setup_lock.RenewLease

    @command(dtype_in=str, dtype_out=bool)
    def ReleaseLease(self, argin):
        """Release only the current owner; another client cannot clear it."""
        # PROTECTED REGION ID(Setup_lock.ReleaseLease) ENABLED START #
        args = json.loads(argin)
        return self._leases.release(args["setup"], args["owner"])
        # PROTECTED REGION END #    //  Setup_lock.ReleaseLease


# ----------
# Run server
# ----------

# PROTECTED REGION ID(Setup_lock.custom_code) ENABLED START #
# PROTECTED REGION END #    //  Setup_lock.custom_code


def main(args=None, **kwargs):
    """Main function of the Setup_lock module."""
    # PROTECTED REGION ID(Setup_lock.main) ENABLED START #
    return run((Setup_lock,), args=args, **kwargs)
    # PROTECTED REGION END #    //  Setup_lock.main

# PROTECTED REGION ID(Setup_lock.custom_functions) ENABLED START #
# PROTECTED REGION END #    //  Setup_lock.custom_functions


if __name__ == '__main__':
    main()
