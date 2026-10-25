"""The ZI2 lock-in server against a fake ziDAQServer, served in-process.

`zhinst.ziPython` is replaced by a stub module before ZI2.py is imported;
the fake data server answers getDouble/setDouble/setInt/subscribe/poll and
is steered through a small JSON control file (the server runs in a child
process, so a plain attribute on the fake would not be reachable).

What is pinned down here is the Start contract the SAMBA scan engine relies
on (Samba CLAUDE.md §67 / §86): RUNNING → ON with the scaled averages, NaN
(not 0) when a poll returns no samples, FAULT after a failed acquisition and
a Start that then RAISES instead of returning quietly, Reconnect recovering.
"""
import importlib.util
import json
import math
import os
import sys
import tempfile
import time
import types

import numpy as np
import pytest

tango = pytest.importorskip("tango")
from tango import DevState                                      # noqa: E402
from tango.test_context import DeviceTestContext                # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ZI_DIR = os.path.join(ROOT, "tango_servers_new", "ZurichInstruments_lockin2_correct_read")
CTL = os.environ.setdefault("ZI_FAKE_CTL", os.path.join(tempfile.mkdtemp(), "ctl.json"))


class FakeDaq:
    """Just enough of ziDAQServer for ZI2.py + ThreadZI2."""

    def __init__(self, host, port, api_level, allow_version_mismatch=False):
        self.nodes = {
            "/dev30933/demods/0/timeconstant": 0.01,
            "/dev30933/demods/0/order": 4,
            "/dev30933/demods/0/rate": 1674.0,
            "/dev30933/oscs/0/freq": 100.0,
            "/dev30933/sigouts/0/amplitudes/0": 0.5,
        }

    def getDouble(self, p):      return float(self.nodes.get(p, 0.0))
    def setDouble(self, p, v):   self.nodes[p] = float(v)
    def setInt(self, p, v):      self.nodes[p] = int(v)
    def subscribe(self, p):      pass
    def disconnect(self):        pass

    def _ctl(self):
        try:
            with open(os.environ["ZI_FAKE_CTL"]) as f:
                return json.load(f)
        except Exception:
            return {}

    def poll(self, duration, timeout_ms, flags, flat):
        time.sleep(duration)
        ctl = self._ctl()
        if ctl.get("fail"):
            raise RuntimeError("ZI data server gone")
        if ctl.get("empty"):
            return {}
        return {f"/dev30933/demods/{i}/sample":
                {"x": np.full(10, 1e-6 * (i + 1)), "y": np.full(10, -1e-6 * (i + 1))}
                for i in range(4)}


def _ctl(**kw):
    with open(CTL, "w") as f:
        json.dump(kw, f)


# Stub zhinst, then import the server from its directory.  ZI2.py does
# `from ThreadZI2 import ThreadZI2`; in the repo the file is
# ThreadZI2_DAQ.py (the install script renames it), so load it under the
# name the server expects first.
_zh = types.ModuleType("zhinst"); _zp = types.ModuleType("zhinst.ziPython")
_zp.ziDAQServer = FakeDaq; _zh.ziPython = _zp
sys.modules["zhinst"] = _zh; sys.modules["zhinst.ziPython"] = _zp


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ZI_DIR, filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_load("ThreadZI2", "ThreadZI2_DAQ.py")
ZI2 = _load("ZI2", "ZI2.py").ZI2


@pytest.fixture(scope="module")
def zi():
    _ctl()
    try:
        ctx = DeviceTestContext(ZI2, process=True, timeout=30,
                                properties={"DeviceId": "dev30933"})
        p = ctx.__enter__()
    except Exception as e:                                      # pragma: no cover
        pytest.skip(f"cannot start an in-process device server here: {e}")
    try:
        yield p
    finally:
        ctx.__exit__(None, None, None)


def _wait_state(p, state, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if p.state() == state:
            return True
        time.sleep(0.01)
    return False


def test_start_runs_and_scales_the_average(zi):
    _ctl()
    zi.integrationtime = 0.05
    assert zi.state() == DevState.ON
    zi.Start()
    assert _wait_state(zi, DevState.ON)
    assert zi.x1 == pytest.approx(1e-6 * 1e6 * math.sqrt(2))     # µV RMS
    assert zi.y1 == pytest.approx(-1e-6 * 1e6 * math.sqrt(2))
    assert zi.x4 == pytest.approx(4e-6 * 1e6 * math.sqrt(2))


def test_settling_time_follows_the_filter(zi):
    # order 4 → 10.0 × TC (99 % settling of the Butterworth cascade)
    assert zi.settlingtime == pytest.approx(10.0 * 0.01)
    assert zi.filterorder == 4
    assert zi.timeconstant == pytest.approx(0.01)


def test_empty_poll_yields_nan_not_zero(zi):
    _ctl(empty=True)
    try:
        zi.Start()
        assert _wait_state(zi, DevState.ON)
        assert math.isnan(zi.x1) and math.isnan(zi.y1)
    finally:
        _ctl()


def test_failed_acquisition_faults_and_start_raises_until_reconnect(zi):
    _ctl(fail=True)
    try:
        zi.Start()
        assert _wait_state(zi, DevState.FAULT), "a failed acquisition must end in FAULT"
    finally:
        _ctl()
    # The contract the scan engine depends on: no quiet return.
    with pytest.raises(tango.DevFailed) as ei:
        zi.Start()
    assert ei.value.args[0].reason == "Not_ready"
    zi.Reconnect()
    assert zi.state() == DevState.ON
    zi.Start()
    assert _wait_state(zi, DevState.ON)
    assert zi.x1 == pytest.approx(math.sqrt(2))


def test_integration_time_round_trips(zi):
    zi.integrationtime = 0.123
    assert zi.integrationtime == pytest.approx(0.123)
    zi.integrationtime = 0.05
