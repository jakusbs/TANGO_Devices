"""The MFLI lock-in servers (one source, two TANGO classes) against a fake
ziDAQServer, served in-process.

`zhinst.ziPython` is replaced by a stub module before the package is
imported; the fake data server answers getDouble/setDouble/setInt/subscribe/
poll for ANY device id, is steered through a small JSON control file and
records every write in a trace file (the server runs in a child process, so
a plain attribute on the fake would not be reachable).

Pinned down here:
- the Start contract the SAMBA scan engine relies on (Samba CLAUDE.md §67 /
  §86): RUNNING → ON with the scaled averages, NaN (not 0) when a poll
  returns no samples, FAULT after a failed acquisition and a Start that then
  RAISES instead of returning quietly, Reconnect recovering;
- that `ZI` and `ZI2` are the same server: identical attribute and command
  sets, differing only in the `DeviceId` / `ZI_Host` defaults, and that each
  configures ITS instrument (node paths under its own device id).
"""
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
PKG_DIR = os.path.join(ROOT, "tango_servers_new", "ZurichInstruments_lockin")
_TMP = tempfile.mkdtemp()
CTL = os.environ.setdefault("ZI_FAKE_CTL", os.path.join(_TMP, "ctl.json"))
TRACE = os.environ.setdefault("ZI_FAKE_TRACE", os.path.join(_TMP, "trace.json"))


class FakeDaq:
    """Just enough of ziDAQServer for zi_lockin, for any device id."""

    _DEFAULTS = {
        "demods/0/timeconstant": 0.01,
        "demods/0/order": 4,
        "demods/0/rate": 1674.0,
        "oscs/0/freq": 100.0,
        "sigouts/0/amplitudes/0": 0.5,
    }

    def __init__(self, host, port, api_level, allow_version_mismatch=False):
        self.nodes = {}
        self._trace("connect", f"{host}:{port}/{api_level}")

    @staticmethod
    def _suffix(p):
        return p.split("/", 2)[2]          # "/dev4855/demods/0/rate" -> "demods/0/rate"

    def _trace(self, kind, path, value=None):
        try:
            with open(os.environ["ZI_FAKE_TRACE"]) as f:
                rows = json.load(f)
        except Exception:
            rows = []
        rows.append([kind, path, value])
        with open(os.environ["ZI_FAKE_TRACE"], "w") as f:
            json.dump(rows, f)

    def getDouble(self, p):
        return float(self.nodes.get(p, self._DEFAULTS.get(self._suffix(p), 0.0)))

    def setDouble(self, p, v):
        self.nodes[p] = float(v); self._trace("setDouble", p, float(v))

    def setInt(self, p, v):
        self.nodes[p] = int(v);   self._trace("setInt", p, int(v))

    def subscribe(self, p):      self._trace("subscribe", p)
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
        # Answer for whichever device ids have been subscribed.
        devs = {p.split("/")[1] for p in self.nodes if "/demods/" in p} or {"dev30933"}
        return {f"/{d}/demods/{i}/sample":
                {"x": np.full(10, 1e-6 * (i + 1)), "y": np.full(10, -1e-6 * (i + 1))}
                for d in devs for i in range(4)}


def _ctl(**kw):
    with open(CTL, "w") as f:
        json.dump(kw, f)


def _trace_rows():
    try:
        with open(TRACE) as f:
            return json.load(f)
    except Exception:
        return []


# Stub zhinst, then import the package from its directory.
_zh = types.ModuleType("zhinst"); _zp = types.ModuleType("zhinst.ziPython")
_zp.ziDAQServer = FakeDaq; _zh.ziPython = _zp
sys.modules["zhinst"] = _zh; sys.modules["zhinst.ziPython"] = _zp
sys.path.insert(0, PKG_DIR)
import zi_lockin                                                # noqa: E402
from zi_lockin import ZI, ZI2, ZILockin, AcquisitionThread      # noqa: E402


def _serve(cls, **props):
    try:
        ctx = DeviceTestContext(cls, process=True, timeout=30, properties=props)
        p = ctx.__enter__()
    except Exception as e:                                      # pragma: no cover
        pytest.skip(f"cannot start an in-process device server here: {e}")
    return ctx, p


@pytest.fixture(scope="module")
def zi():
    """The IR class, as the historic test_zi2.py served it."""
    _ctl()
    ctx, p = _serve(ZI2, DeviceId="dev30933")
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


# ---- the Start contract (unchanged from test_zi2.py) ------------------------

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
    assert "ZI2::Start" in ei.value.args[0].origin
    zi.Reconnect()
    assert zi.state() == DevState.ON
    zi.Start()
    assert _wait_state(zi, DevState.ON)
    assert zi.x1 == pytest.approx(math.sqrt(2))


def test_integration_time_round_trips(zi):
    zi.integrationtime = 0.123
    assert zi.integrationtime == pytest.approx(0.123)
    zi.integrationtime = 0.05


# ---- one source, two classes ------------------------------------------------

def test_zi_and_zi2_differ_only_in_property_defaults():
    assert issubclass(ZI, ZILockin) and issubclass(ZI2, ZILockin)
    assert (ZI.DeviceId.default_value, ZI.ZI_Host.default_value) == ("dev4855", "192.168.1.62")
    assert (ZI2.DeviceId.default_value, ZI2.ZI_Host.default_value) == ("dev30933", "192.168.1.144")
    assert list(ZILockin.Harmonics.default_value) == [1, 2, 3, 1]
    # Everything else is inherited: pytango's metaclass copies the inherited
    # TANGO objects into each subclass namespace, so check the SOURCE — the
    # two subclass bodies declare exactly the two properties and nothing else.
    import ast
    tree = ast.parse(open(os.path.join(PKG_DIR, "zi_lockin", "device.py")).read())
    for cls in ("ZI", "ZI2"):
        node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
        assert [b.id for b in node.bases] == ["ZILockin"]
        declared = sorted(t.id for n in node.body if isinstance(n, ast.Assign)
                          for t in n.targets if isinstance(t, ast.Name))
        assert declared == ["DeviceId", "ZI_Host"], declared
        assert not any(isinstance(n, ast.FunctionDef) for n in node.body)
    assert zi_lockin.main_zi is not zi_lockin.main_zi2


def test_green_class_serves_its_own_instrument_with_the_same_interface(zi):
    """ZI (dev4855) must expose exactly ZI2's attributes/commands and talk to
    node paths under ITS device id — the whole point of one source."""
    open(TRACE, "w").write("[]")
    ctx, g = _serve(ZI)                         # property defaults only
    try:
        assert g.info().dev_class == "ZI"
        assert g.state() == DevState.ON
        rows = _trace_rows()
        harmonics = {r[1]: r[2] for r in rows if r[0] == "setDouble" and "/harmonic" in r[1]}
        assert harmonics == {f"/dev4855/demods/{i}/harmonic": h
                             for i, h in enumerate([1, 2, 3, 1])}
        assert any(r[0] == "connect" and r[1].startswith("192.168.1.62:8004") for r in rows)
        # Identical interface
        assert set(g.get_attribute_list()) == set(zi.get_attribute_list())
        assert set(g.get_command_list()) == set(zi.get_command_list())
        # ...and the acquisition path works for it too.
        g.integrationtime = 0.05
        g.Start()
        assert _wait_state(g, DevState.ON)
        assert g.x2 == pytest.approx(2e-6 * 1e6 * math.sqrt(2))
    finally:
        ctx.__exit__(None, None, None)


def test_thread_logs_under_the_parent_class_name():
    """The log prefix is the parent's class name, so the Green and IR servers
    keep logging as "ZI: …" and "ZI2: …" from one thread implementation."""
    for name in ("ZI", "ZI2"):
        parent = type(name, (), {"daq": None})()
        t = AcquisitionThread.__new__(AcquisitionThread); t.p = parent
        assert t._tag == name
