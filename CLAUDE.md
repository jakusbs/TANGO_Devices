# TANGO Devices — Project Context

## Repository Structure

```
tango_servers_old/                  # Original C++ (and some old Python) servers — do not modify
tango_servers_old/software_windows/ # Windows-side software: Beckhoff TwinCAT programs,
                                    # AttoDRY socket bridge scripts, hardware manuals (PDFs)
tango_servers_new/                  # AdsBridge2 and ZI servers (newer Python, kept separately)
tango_servers_remade/               # All servers ported to modern Python 3 tango.server API
```

Install target for all servers: `/usr/local/tango_servers`

Each server in `tango_servers_remade/` has:
- `<Server>.py` — the implementation
- `<Server>.xmi` — POGO PogoDSL 9.1 (PythonHL) descriptor for documentation
- `install.sh` — prepends shebang, makes executable, installs to `/usr/local/tango_servers`

---

## Servers in tango_servers_remade/

| Server | Hardware | Notes |
|---|---|---|
| `Socket` | TCP gateway | Used by ANC300, PyKeithley, PyKeithley2, PyKeithleyPulse |
| `Magnet` | Magnet power supply | |
| `ANC300` | Attocube ANC300 piezo controller | via Socket proxy |
| `ANM200` | ANM200 nano-positioner | |
| `AttoDRY` | AttoDRY2100 cryostat | UDP, has daemon thread |
| `DoubleInBeckhoffAverage` | Beckhoff ADS double input with averaging | |
| `Lights` | LED light controller | |
| `PyKeithley` | Keithley 6221 unit 1 | via Socket; trigger line 5 |
| `PyKeithley2` | Keithley 6221 unit 2 | via Socket; trigger line 3 |
| `PyKeithleyPulse` | Keithley 6221 square-wave mode | via Socket; same hardware as PyKeithley |
| `PyRelais` | Relay controller | |

---

## Socket Server — Critical Notes

The Python Socket server must match the behaviour of the original C++ Socket server.
Key differences found by comparing C++ and Python:

### `Write` appends `\r\n` (not just `\n`)
The C++ `Write` command always appended `\r\n`. The Python `Write` command must do the same.
`WriteLine` appends only `\n`. `WriteRead` and `WriteReadUntil` also append `\r\n` (matching C++).

### Error handling — only disconnect on connection errors
The C++ server only marked the connection as broken on: `ECONNRESET`, `EPIPE`, `ENOTCONN`, `EINTR`.
Timeouts (`EAGAIN`, `ETIMEDOUT`) raised an exception but kept the connection alive.

The Python server uses `_handle_error()` which only calls `_on_socket_error()` (disconnect + reconnect)
for `BrokenPipeError`, `ConnectionResetError`, `ConnectionAbortedError`, `ConnectionRefusedError`.
Timeouts re-raise directly without disconnecting.

### AutoReconnect property (default True)
- On connection error: closes socket, sets FAULT, immediately attempts reconnect
- `_require_connected()`: if `_sock is None` and AutoReconnect, tries to reconnect before raising
- `Reconnect` command: catches all exceptions gracefully — sets FAULT with status message, does not raise (so caller can retry after ~60 seconds)

### Non-blocking socket (C++) vs blocking with timeout (Python)
The C++ socket was non-blocking (`set_non_blocking(true)`). The Python socket is blocking with
`Readtimeout` ms timeout (default 1000 ms). Functionally equivalent for the use cases here.

---

## Keithley 6221 — Known Issues and Fixes

### Hardware
- **Unit 1 (PyKeithley)**: firmware D02 — has TCP drop bug, drops connection silently
- **Unit 2 (PyKeithley2)**: firmware D04 — stable, but affected by same Socket issues
- D04 firmware update available at: `https://www.tek.com/en/support/software/firmware/62206221-firmware-revision-d04`
- D04 has no USB port — firmware update must be done via RS-232 or GPIB
- **Do NOT install E-series firmware on D-series hardware** (bricks the unit)

### TCP connection behaviour (from Keithley 6221 manual 622x-901-01)
- Port: **1394** (raw TCP, not standard SCPI port 5025)
- Only **one TCP client at a time** — if previous session was not cleanly closed, new connection is blocked for ~30–60 seconds (TCP TIME_WAIT)
- When TCP drops, instrument **keeps running** (waveform continues, output stays on)
- Reconnecting to an instrument mid-wave: must send `SOUR:WAVE:ABOR` before any config commands

### SCPI commands — important rules
- All commands need `\n` terminator — use `WriteLine` not `Write`
- Waveform state machine: IDLE → `SOUR:WAVE:ARM` → ARMED → `SOUR:WAVE:INIT` → RUNNING
- Cannot write any `SOUR:WAVE:*` parameter while ARMED or RUNNING — causes settings-conflict error
- Always send `SOUR:WAVE:ABOR` before reconfiguring (safe to call in IDLE — no-op)
- Empirical: 100 ms delay required between last config command and `SOUR:WAVE:ARM`

### Fixes applied to PyKeithley, PyKeithley2, PyKeithleyPulse
1. All commands use `WriteLine` (adds `\n` terminator)
2. `SOUR:WAVE:ABOR` sent at start of `SINEWAVE`/`SQUAREWAVE`/`_rearm()` to ensure IDLE state
3. Recovery sequence in `init_device()`: `SOUR:WAVE:ABOR` + `OUTP OFF` (wrapped in try/except — instrument may not be ready immediately)
4. 100 ms `time.sleep(0.1)` before `SOUR:WAVE:ARM` in all waveform commands
5. PyKeithleyPulse: `_wave_running` flag — writing any parameter while wave is running auto-rearms the wave (no manual WAVEOFF/SQUAREWAVE cycle needed)
6. PyKeithleyPulse: `range` attribute added (same strings as PyKeithley/PyKeithley2)
7. PyKeithleyPulse: `pulseDuration` is a **computed** attribute (not stored independently) — reads as `1 / (2 × frequency)`, writes update `frequency` via `frequency = 1 / (2 × duration)`. Changing either `frequency` or `pulseDuration` updates the other automatically. Writing ≤ 0 raises `DevFailed`. Not memorized (derived value).

### PyKeithleyPulse range map
```python
'0.0002mA': '2e-7', '0.002mA': '2e-6', '0.02mA': '2e-5',
'0.2mA': '2e-4', '2mA': '0.002', '20mA': '0.02', '100mA': '0.1'
```
Note: PyKeithley/PyKeithley2 use different (older) range values inherited from old code —
do not change those without verifying on the actual hardware.

---

## AttoDRY — Notes

- Connects via UDP (not TCP) to a Windows PC running AttoDRY2100 software
- Properties: `AttoIP` (Windows PC IP), `AttoPort` (UDP port on PC), `LocalIP` (local NIC to bind to), `LocalPort` (local UDP port)
- `LocalIP` default is `0.0.0.0` (bind all interfaces) — works on any machine without updating the database. `LocalPort` default is `11005`.
- The `install.sh` copies three files: `AttoDRY` (executable), `AttoDRYThreadDaemon.py`, `AttoDRYCheck.py`

### Two-thread architecture
The remade AttoDRY uses two threads that must coexist cleanly:

1. **`AttoDRYThread`** (daemon, `AttoDRYThreadDaemon.py`) — runs continuously; sends `"Read"` every 0.2 s and parses the `ReadA...N` UDP packet to update all attribute caches. Started once by `Start()` and never restarted unless it dies.

2. **`AttoDRYCheck`** (`AttoDRYCheck.py`) — short-lived; started each time a `MagneticField` or `Temperature` setpoint is written. Polls the cached values (kept fresh by the daemon) and holds device state at `MOVING` until both field and temperature are within tolerance (0.001 T, 0.2 K), then sets state to `ON`. Without this thread there is no `MOVING` feedback — the device would appear done immediately after writing a setpoint.

### AttoDRYCheck — stop/restart on new setpoint
When a new setpoint arrives while `AttoDRYCheck` is still running (previous setpoint not yet reached):
- `stop()` sets `_stop_event` which immediately wakes the sleeping thread and exits its loop
- `join(timeout=1.0)` in `write_MagneticField`/`write_Temperature` waits for the old thread to finish before starting the new one — avoids two check threads running simultaneously against the same targets

`stop()` must set the event and nothing else. Do **not** call `set_state()` inside `stop()` — the new thread will own the state from the moment it starts.

### Attribute cache thread safety
`AttoDRY.init_device()` creates `self._cache_lock` (a `threading.Lock`).
`AttoDRYThread` holds this lock while writing all 26 attribute cache fields in one block.
`AttoDRYCheck` reads field/temperature caches under the same lock.
The main TANGO thread reads attributes directly from the cache (no lock needed for individual float reads on CPython, but the lock prevents partial-packet snapshots).

### Socket timeout
`Connect()` sets `s.settimeout(5.0)` before the handshake `recvfrom()`. If the Windows PC does not respond within 5 s the device goes to `OFF` cleanly instead of blocking forever. The daemon thread's `recvfrom()` also benefits — it catches `socket.timeout` and simply sleeps for the poll interval before retrying.

### Connect() port collision fix
`Connect()` stops the daemon listener and closes the existing socket **before** rebinding the port. Without this, calling `Connect()` a second time (e.g. manually from Jive) while the daemon was already running raised `OSError: Address already in use`. Sequence:
1. `listener.stop()` + `listener.join(timeout=2.0)` — daemon exits cleanly
2. `self.s.close()` — releases the port
3. New socket created, bound, timeout set, handshake performed

### AttoSocket2.py (Windows bridge, tango_servers_old/software_windows/)
Windows-side UDP bridge between the TANGO AttoDRY server and the PyAttoDRY DLL. Key design points:
- **Immediate ACK**: on `'start'` or `'ON'`, sends `b'ON'` reply *before* calling `connect_attodry()`. TANGO `Connect()` has a 5 s `recvfrom` timeout; the DLL init can take up to 10 s — without this the TANGO side always timed out and went to OFF.
- **Socket timeout**: `s.settimeout(10.0)` — no longer blocks forever if TANGO disappears.
- **Last-good-packet cache** (`last_packet`): if `build_packet()` fails or the DLL is not yet connected, the last successfully built `ReadA…N` packet is resent so the TANGO daemon does not stall on a missing reply.
- **Connection health check**: before each `Read`, calls `isDeviceConnected()` + `isDeviceInitialised()`; skips the DLL read and resends last packet if unhealthy.
- **All DLL calls wrapped in try/except** — a single failing DLL call does not crash the bridge.
- **No 10 ms inter-read sleeps** — DLL reads are from LabVIEW's cached state, so delays are unnecessary.
- Configuration constants at top of file: `HOST`, `PORT`, `COM_PORT`, `RECV_TIMEOUT_S`, `CONNECT_WAIT_S`.

### Known freeze points in the AttoDRY chain
Three identified freeze points:
1. **ACK timing** (fixed): AttoSocket2 must ACK before TANGO's 5 s timeout; DLL init is done in the background.
2. **Port collision** (fixed): TANGO `Connect()` now stops the daemon and closes the socket before rebinding.
3. **LabVIEW DLL deadlock** (unmitigatable in software): if `AttoDRYLib.dll` deadlocks internally, `build_packet()` or `connect_attodry()` will block forever. Only fix is restarting the Windows process. The bridge's socket timeout prevents the TANGO side from freezing in this case — TANGO sees repeated socket timeouts and stays in its last state.

---

## POGO / XMI Files

- All `.xmi` files use namespace `http://tango-controls.org/pogo/PogoDsl` (PythonHL, `pogoRevision="9.1"`)
- POGO can read these files and generate a skeleton, but the existing Python files are hand-written (no protected region markers) — POGO would overwrite them if code generation is run
- XMI files are kept for documentation and structural reference, not for active POGO code generation

### Memorized attribute mapping
- `memorized="true" memorizedAtInit="true"` → Python `memorized=True, hw_memorized=True`
- `memorized="true"` only → Python `memorized=True, hw_memorized=False`

---

## ANC300 — Notes

- Connects **directly via TCP** (Telnet, port **7230**) — no Socket proxy required
- Properties: `Hostname` (mandatory, IP of ANC300), `Port` (default 7230), `Readtimeout` (default 1000 ms), `password` (default `123456`), `addr_x/y/z` (axis addresses, defaults 4/5/6)
- On connect: discards Telnet IAC negotiation bytes (first recv), then sends password and checks for `'Authorization success'` in reply
- Commands use ASCII text with `\r\n` terminator — `_send()` appends this internally
- Command response timeout per manual: ~30 ms — the 100 ms sleeps in read helpers are safe
- `Reconnect` command: closes and reopens the socket; safe to call while other measurements are running (independent of Socket device)
- The old `Proxy` device property may still exist in the TANGO database — it is ignored by the new code

### Why direct TCP instead of Socket proxy
The Socket server is shared between Keithleys; restarting it while a measurement is running would
drop those connections. ANC300 has its own dedicated TCP connection, so it benefits from owning
the socket directly rather than going through an intermediary.

### Position writes (px/py/pz)
Position is tracked as a **relative step counter** — the hardware has no absolute encoder.
Write sequence: `setm <addr> stp` → sleep 0.1 s → `stepu`/`stepd`. Both commands must succeed before the cache is updated. If steps == 0 the step command is skipped (was previously issuing a `stepd 0`).

### Ground attributes (Gx/Gy/Gz)
- Write `True` → `setm <addr> gnd`
- Write `False` → `setm <addr> stp` (return to stepping mode)
- Previously, writing `False` was a silent no-op on hardware while updating the cache — fixed.

### Ground() command
Loops over all three axes with individual `try/except`; all axes are attempted even if one fails. Errors are collected and raised together at the end as a single `DevFailed`.

---

## ANM200 — Notes

- Controls three ANM200 DC piezo motors via three **DoubleOutBeckhoff** TANGO proxies
- Proxy chain: ANM200 → DoubleOutBeckhoff → AdsBridge2 → Beckhoff PLC
- Each proxy exposes a `Value` attribute (float, volts) that maps to one `AOC` output on the PLC
- Hardware limit: **±10 V** (Beckhoff AOC DAC range = ANM200 DC input range)

### Scaling
`scaling` converts between user units (µm) and DAC voltage: `voltage = position × scaling`.
- Default: `1.0` (1 V per unit). Must be set to the correct µm/V value before using position attributes.
- Writing `scaling = 0` raises `DevFailed` immediately.
- Writing a position that would require `abs(voltage) > 10 V` raises `DevFailed` before the hardware write.

### Startup state
`init_device()` reads the current `Value` from each DoubleOutBeckhoff proxy so the cached position reflects the actual hardware output. Without this, the cache starts at 0.0 V regardless of what the DAC was last set to.

---

## Beckhoff / DoubleInBeckhoffAverage — Notes

- `DoubleInBeckhoff` (in `tango_servers_new/PythonDoubleInBeckhoff/`) — simple live read of one PLC variable via AdsBridge2; no caching, no averaging.
- `DoubleInBeckhoffAverage` (in `tango_servers_remade/`) — adds on-board PLC averaging with `Start()`/`Abort()` commands and an `IntegrationTime` attribute.

### DoubleInBeckhoffAverage — key points
- `Start()` writes the averaging flag to the PLC **first**, then sets device state to `RUNNING`. (Previously state was set before the write — a failed write would leave the device stuck in RUNNING.)
- `Value` read raises on ADS failure (sets FAULT + logs) instead of silently returning −10.0.
- `IntegrationTime` is validated: must be > 0 and must not exceed **32.767 s** (32767 PLC cycles — the maximum for a 16-bit signed INT, which is what `AverageNum` is in the PLC).
- `always_executed_hook` surfaces ADS communication failures as FAULT state.

### Beckhoff TwinCAT program snapshots (software_windows/Beckhoff/)
Four versions of the PLC program are archived: Aug2020, Apr2023, Juni2024, Novi2025.
All run on a CX-16FC90, 1 ms task cycle, TwinCAT 2.11.

Key symbols accessible via ADS:
- `AnalogIn1_raw`–`AnalogIn6_raw` (DINT), `AnalogOut1_raw`–`AnalogOut4_raw` (INT)
- `AOC1`–`AOC8` (INT, 16-bit outputs → ANM200 channels), `ELM1`–`ELM6`
- `DigitalOut1`–`DigitalOut8` (BOOL)
- Averaging: `AverageNum`/`Averaging`/`AverageAbort` (three independent engines)
- Time-trace arrays `TT1`–`TT6`: fixed 400 points — cannot be resized without recompiling
- Hysteresis: `HystField`, `HystResult1`–`6`, `HystArrayLengthMax` (400 points)
- `HystFieldOffset` added in **Juni2024** — absent in Aug2020/Apr2023; reading it on older firmware raises an ADS symbol-not-found error
- Signal processing objects: `P_Lockin`, `P_PLL`, `P_Demod`, `P_FFTraw`, `P_SignalGenerator`

---

## AdsBridge2 — Notes

Lives in `tango_servers_new/adsbridge2/`. Replaces the old C++ AdsBridge. Uses `pyads` (pure Python ADS library).

- All read **and** write commands hold `self.lock` (a `threading.Lock`) — concurrent access is safe.
- `ReadBool` input: plain variable name (e.g. `MAIN.Averaging`)
- `WriteBool` input: `"VARIABLE=true"` or `"VARIABLE=false"` — note the asymmetry with ReadBool.
- `Reconnect` command: closes and reopens the ADS connection without restarting the server process. Still available for manual use, but no longer required for recovery (see below).
- **Auto-reconnect (July 2026)** — two layers, both controlled by the `AutoReconnect` device property (default `True`):
  - *On-demand*: every command runs through `_ads_call()`; on failure the connection is rebuilt and the operation retried **once** before the error propagates. A link that died since the last command costs one hiccup instead of `-----` panels until a manual `Reconnect`. ADS error 1808 (symbol not found — a caller mistake, e.g. `HystSource` on an old PLC program) is never retried.
  - *Keepalive watchdog*: a daemon thread issues a lightweight ADS `read_state()` every `KeepaliveInterval` seconds (property, default 10 s; 0 disables). This keeps the connection non-idle (defeats idle-session timeouts in network gear / the PLC router) and repairs a dead link between commands. It acquires the lock **non-blocking** — if a command holds it, traffic is flowing and the keepalive round is skipped, so the watchdog never delays real I/O. If `read_state()` keeps failing on fresh connections (3× in a row) the watchdog disables itself (quirky target) and only on-demand reconnect remains.
- The device **status string** carries a reconnect counter and timestamp (`ADS reconnect #N at HH:MM:SS — trigger: …`) — use it to diagnose periodic connection drops (e.g. an every-5-minutes pattern points at an idle/session timeout in the path to the PLC).
- A failed connection at `init_device` no longer throws: the device starts FAULT and self-heals via the watchdog / first command once the PLC is reachable.

---

## Other TANGO servers

### PyRelais
- ON/OFF commands use a ground → switch → unground sequence. The unground step is wrapped in `try/finally` so it still runs if the middle write fails, leaving the relay in a safe ungrounded state.
- Default Beckhoff variables use the `MAIN.` prefix (case-sensitive, matches the Beckhoff TwinCAT symbol table).

### Lights
- Default variables also use the `MAIN.` prefix.
- Read-modify-state sequence is non-atomic (write first, then read the other LED to set DevState). Concurrent calls can produce a state that disagrees with hardware — callers should serialise LED commands.

### PyHysteresis (in tango_servers_new/)
- `Abort()` guards with `hasattr` so it can be called safely before `Start()` without raising.
- `HysteresisThread` has a hard 600 s per half-loop timeout on the `HystRunning` PLC flag so a stuck flag cannot hang the thread forever — it auto-aborts on the PLC side and returns.
- `BeckhoffHystChannelValue` device property is **mandatory** in practice; comparing to `1` selects DAC1 (longitudinal), anything else falls to DAC2 (polar).
- **Source selection** (which signal is **read** into each result array): in the PLC, `HystResult1–6` historically record **AnalogIn1–6, hard-wired** — signals moved to the ELM terminals are invisible to DC hysteresis. The server now has memorized `source1`–`source6` attributes (1–6 = AnalogIn1–6, 11–16 = ELM1–6) writing `MAIN.HystSource1–6`; selections are re-pushed at every `Start()`. **Requires the matching PLC change** (see `tango_servers_new/PyHysteresis/PLC_source_selection.md` for the exact TwinCAT structured text); on older PLC programs the attribute write raises a clear error and the PLC keeps recording AnalogIn1–6.
- **Sweep selection** (which magnet/DAC is **driven**) is a *separate*, pre-existing mechanism: the `BeckhoffHystChannelValue` device property → `MAIN.HystChannel` (1 = `AnalogOut1` longitudinal, 2 = `AnalogOut2` polar). Set per device. Independent of the source/read selection above.
- **Single shared PLC engine**: there is exactly one hysteresis state machine on the PLC (one `HystStart`/`HystRunning`/`HystField`/`HystChannel`/`HystResult1–6`). Multiple PyHysteresis devices (polar + longitudinal) are **instances of the same class sharing that one engine** — they cannot measure simultaneously. `Start()` now reads `MAIN.HystRunning` first and raises "Hysteresis engine busy" rather than letting a second `Start` reset the running loop's arrays (which silently corrupted both readouts). Sequential use only.
- **Per-cycle retention & re-averaging**: `HysteresisThread` already reads each cycle's full half-loop off the PLC, then summed it away. It now keeps every cycle in `self.p._cyc[ch] = [(pos, neg), …]`. New commands: `GetNumberOfCycles`, `GetCycle(n)` (returns 7 blocks of `2×NumberOfPoints`: field + result1–6 for one cycle), `SetExcludedCycles(short[])`, `RecomputeAverage()` — drop a bad scan and re-derive result1–6/field/Hc/Hshift/Mr/Ms without re-measuring. The averaging + scalar derivation moved into one shared `_average_and_derive(included)` method used by **both** the live loop and `RecomputeAverage` (verified numerically identical to the original inline math). The live measurement is unchanged for the all-cycles case.

### Socket (remade)
- `Write` / `WriteRead` / `WriteReadUntil` / `WriteAndRead` all append `\r\n` (match original C++ Socket server).
- `WriteLine` appends only `\n` (for SCPI instruments like the Keithley).
- `Readln` strips a trailing `\r` before returning, so callers using `\r\n` protocols get a clean string.

### DG645 (in tango_servers_new/Digital_delay/)
- SRS DG645 Digital Delay Generator over TCP (default port 5025).
- Uses an `RLock` because `_reconnect` calls `_query` from inside a held lock.
- Rate-limited reconnect (`ReconnectInterval` class property, default 5 s) prevents reconnect storms.

### RTV40 (in tango_servers_new/RTV40_pulser/)
- Kentech RTV40 / RTV30 HV pulse generator over USB virtual COM port.
- Background poll thread owns all serial reads; attribute getters return cached values only, so TANGO polling cannot interleave with an active write.
- Wire-unit conversions: amplitude V → 0.1 V integer; pulse width ns → ps integer; clamping is applied before the wire write.

### SmarActMCS2Stage (in tango_servers_new/)
- Wraps three motor axis proxies. If any `DeviceProxy` fails in `init_device`, the corresponding `_x_proxy` / `_y_proxy` / `_z_proxy` stays `None`; attribute reads and `Stop()` now guard against this and raise a clear `DevFailed` instead of `AttributeError`.
- **`Initialise` command** (July 2026): re-initialises all three axes — the fix for a wedged IR SmarAct axis after manual hand-controller use. Propagates the standard TANGO `Init` command to each underlying motor device (X/Y/Z), which re-runs its `init_device` and re-establishes the MCS2 connection (distinct from Home / CalibrateAxis), then refreshes the stage's own cached proxies. All axes are attempted even if one fails; errors are collected and raised together as a single `DevFailed`. SAMBA's Calibration tab has a "⟲ Reinitialise" button that calls this (falling back to `Init` on servers predating the command).

### SetupLock (in tango_servers_new/)
- Three-way mutex device (green / IR / cryo setups). State flips to `RUNNING` when any `*Busy` flag is True, otherwise `ON`.

### DoubleInBeckhoff / DoubleOutBeckhoff (in tango_servers_new/)
- Minimal passthrough wrappers around AdsBridge2 `ReadReal` / `WriteReal`. No caching. No error handling — exceptions from AdsBridge propagate directly to the caller.

### ZI / ZI2 (in tango_servers_new/ZurichInstruments_lockin*_correct_read/)
- Both are Zurich Instruments MFLI lock-in servers. They differ only by default device ID (`dev4855` vs `dev30933`), default host IP and default `Harmonics`.
- **Ported to modern `tango.server.Device` API.** All ZI paths are now built from a `DeviceId` device property — no source edits needed to point at a different MFLI.
- New device properties: `DeviceId`, `ZI_Host`, `ZI_Port`, `ZI_ApiLevel`, `Harmonics` (4-element int array).
- `ZI2` defaults `Harmonics = [1,2,3,1]` — demod 3 uses harmonic 1 (not 4 as in `ZI`) per a 2024 change. Preserved as the property default; do not change without verifying the experimental setup.
- The companion `ThreadZI` / `ThreadZI2` no longer carry a hardcoded `DEVICE` constant — they pull `DeviceId` from the parent and write into `parent._x[i]` / `parent._y[i]`.
- Source files keep `from ThreadZI import ThreadZI` (resp. `ThreadZI2`); the `install_*_DAQ.sh` scripts rename `ThreadZI_DAQ.py` → `ThreadZI.py` and rewrite the import to a relative one inside the `ZI_DAQ` / `ZI2_DAQ` package. The launch entry point (`ZI_DAQ <instance>`) and Jive class names (`ZI`, `ZI2`) are unchanged.

### ZI / ZI2 — thread safety and crash fixes
`ziDAQServer` is a C extension that is **not thread-safe**. Three crash causes were identified and fixed:

1. **Concurrent `daq.*` access**: TANGO's attribute polling thread calls `daq.getDouble()` (for `timeconstant`, `filterorder`, `settlingtime`) while `ThreadZI.run()` calls `daq.poll()`. Fix: all `daq.*` calls in both the main thread and the background thread now hold `self._daq_lock` (`threading.Lock`). The thread holds the lock for the full poll duration so `getDouble` calls serialise against it. `timeconstant`, `filterorder`, and `settlingtime` use a **non-blocking** `acquire(blocking=False)` — if the lock is held by the poll they return the last cached value rather than stalling. `_refresh_cached_settings()` (called at init and `Reconnect`) seeds these caches so the first read always returns a real value. Writes (`Amplitude`, `frequency`, `samplingrate`, `phase`) and the internal `_settling_time()` helper keep blocking acquires — a hardware write must complete.

2. **Missing null guard**: if `ziDAQServer()` fails at startup, `self.daq` was never set, causing `AttributeError` on the next attribute read. Fix: `self.daq = None` is set at the start of `init_device`; `_require_daq()` raises a clean `DevFailed` if it is `None`; `always_executed_hook` also surfaces this as FAULT state.

3. **No recovery path**: opening the LabOne web interface can reset the data server's API session, staling `self.daq`. Fix: `Reconnect` command re-creates the `ziDAQServer`, re-subscribes demods, and restores cached settings — all under `_daq_lock`. Call it from Jive instead of restarting the process.

### ZI / ZI2 — firmware version mismatch
- ZI1 (dev4855, 192.168.1.62): LabOne **25.x** firmware.
- ZI2 (dev30933, 192.168.1.144): LabOne **24.10.6** firmware — one major version behind.
- Installed zhinst Python package: **25.4.1**. `ziDAQServer` does a strict version check on connect and throws if the API and firmware versions differ.
- Fix: `AllowVersionMismatch` device property (bool, default `False`). Set `True` in Jive for ZI2 to pass `allow_version_mismatch=True` to the constructor. Long-term fix is updating ZI2 LabOne firmware to 25.x.
- Install scripts pin `zhinst>=24,<26` (covers both firmware generations in one environment).
- `poll()` call uses the old positional-argument form (`daq.poll(t, ms, 0, True)`) which works with `zhinst.ziPython` (the C extension). If ever migrating to `zhinst.core`, change to keyword arguments: `daq.poll(t, ms, flat=True)`.

### ZI / ZI2 — idle-server zero outputs
With short integration times and no Jive panel open, `Start()` occasionally returns 0 for all channels. Root cause: the ZI data server pauses sample delivery when the API connection is idle. Jive's regular attribute polling (`timeconstant`, `filterorder`, `settlingtime`) happened to keep the server warm. Fix: `ThreadZI`/`ThreadZI2` now call `daq.getDouble('/.../demods/0/rate')` inside the lock immediately before the flush poll, ensuring the server is streaming before the collection window starts. A `warn_stream` is emitted if any demod returns empty data, so the problem is visible in the device logs rather than silently producing 0.

### ZI / ZI2 — what still needs attention
- **Update ZI2 firmware**: upgrade from LabOne 24.10.6 to 25.x so both instruments share the same API version and `AllowVersionMismatch` can be set back to `False`.

---

## What Still Needs Attention

- **D02 firmware on Keithley unit 1**: The real fix is updating to D04. The AutoReconnect in Socket provides a software mitigation but the firmware drop is the root cause.
- **Network switch/router timeout**: Both Keithleys dropping connections suggests a network device may be killing idle TCP sessions. TCP keepalives (already attempted but reverted due to other bugs) or periodic heartbeat commands would help if confirmed.
- **ANC300 position counter**: the `px/py/pz` attributes track a relative step counter that resets to 0 on server restart. There is no absolute position feedback — the counter drifts if steps are missed due to a communication error.
- **Magnet zero-guards**: `HallSensitivity_*` and `AmperePerVolt_*` are mandatory properties, but there is no runtime guard against a user setting them to 0 via Jive. Consider adding checks in `init_device`.
- **DG645 dev_state()**: polls `LERR?` on every state query, which can be frequent. If the state polling overhead becomes a problem, cache the last known state and only re-query after a timeout.

---

## Recent Changes (June 2026) — Server Reliability & PyHysteresis Source Selection

All on branch `claude/app-review-suggestions-jozwry`. Compile-checked
(`python -m py_compile`); only `tango_servers_remade/` + `tango_servers_new/`
are in use (never `tango_servers_old/`). Deployed and verified on hardware:
the PLC `HystSource` change + new PyHysteresis work.

### Socket (remade)
- `_connect()` clears `self._sock = None` before reconnecting, so a failed
  reconnect (e.g. Keithley TIME_WAIT) no longer leaves a dangling closed handle
  whose `EBADF` errors permanently defeat AutoReconnect.
- `recv()` returning `b''` (orderly peer close — the Keithley silent-drop case)
  is now treated as a connection error via `_peer_closed()` → disconnect/reconnect
  + `DevFailed`. Partial reads that already received data keep the old behaviour.

### AttoDRY (remade)
- `Connect()` restarts the daemon listener it stops for the port rebind (a manual
  Connect from Jive used to freeze all readbacks forever); `Disconnect()` stops it
  cleanly first. Daemon logs + sets FAULT when it dies unexpectedly.
- Toggle writes (field / temperature / persistent-mode control) only send the
  toggle command when the requested value differs from the cached readback —
  writing the current value no longer flips the hardware state (persistent mode!).
- `AttoDRYCheck` only tests setpoints actually written since startup, so a
  field-only write after a restart no longer wedges the device in MOVING waiting
  for the default 0.0 K temperature target. **Pairs with the Samba FIELD ramp-wait.**

### ANC300 (remade)
- Write commands (`setf`/`setv`/`setm`/`stepu`/`stepd`) drain their echo + OK/ERROR
  reply (tolerant, bounded by `Readtimeout`) so replies no longer pile up and
  desync later `getf`/`getv`/`getm` reads; queries drain stale bytes first. An
  explicit `ERROR` raises (rejected writes no longer update caches).

### AdsBridge2 (new)
- `self.lock` + `self.plc = None` created **before** the connection attempt, so a
  failed init leaves `Reconnect` usable (it now rebuilds the connection when
  `plc is None`); `delete_device` guarded.
- `ReadRealArray` / `ReadLongIntArray` raise `DevFailed` instead of returning
  `[-10.0]*n` filler and latching FAULT forever (matches the DoubleInBeckhoffAverage fix).

### PyKeithley / PyKeithley2 (remade)
- Track `_wave_running`; writing `frequency` while a sine wave runs re-arms the
  wave (same approach as PyKeithleyPulse) instead of silently keeping the old
  frequency until the next amplitude write. No SCPI sequences changed.

### PyRelais (remade)
- If the unground write in the `finally` path also fails, set FAULT with
  "relay may still be grounded" and raise an error carrying **both** failures
  instead of masking the original; `switchvar` cache updates only after success.

### Magnet (remade)
- Current writes reject (not clamp) setpoints whose computed DAC voltage exceeds
  ±10 V, reported in **Ampere** (`±10 V × AmperePerVolt`), matching ANM200's guard.
- Restored memorized `corr_polar` / `corr_longitudinal` (`memorized=True,
  hw_memorized=True`) — the C++ XMI had them memorized; the Python port had lost
  it, so the correction factors silently reset to 1.0 on every restart.

### ZI / ZI2 (new) — Start race + failed-acquisition state
- `Start()` sets `RUNNING` synchronously before `thread.start()` so a fast
  double-Start cannot spawn two acquisition threads.
- A failed acquisition ends in **FAULT** (with a status) instead of a clean
  RUNNING→ON that let the scan engine read stale values as a good point.
- The packaged `ZI_DAQ/` / `ZI2_DAQ/` copies were stale v4 snapshots —
  regenerated from the v5 sources via each install script's copy+sed recipe.

### PyHysteresis (new) — source selection, per-cycle retention, engine interlock
- **Selectable sources**: memorized `source1`–`source6` attributes (1–6 =
  AnalogIn1–6, 11–16 = ELM1–6) write `MAIN.HystSource1–6`, re-pushed at every
  `Start()`. **Requires the PLC change** in `PLC_source_selection.md` (HystSource
  selectors + a clamped `HystSrc[1..16]` pool indexed by the six recording lines;
  defaults preserve the old AnalogIn1–6 behaviour, so **old/unmodified servers
  still work unchanged**). On PLC programs without the symbols the write raises a
  clear error.
- **Single-engine interlock**: `Start()` reads `MAIN.HystRunning` first and raises
  "Hysteresis engine busy" — the polar & longitudinal devices are instances of one
  class sharing one PLC engine and cannot run simultaneously (a second Start used
  to reset the running loop's arrays and corrupt both). Sequential use only.
- **Per-cycle retention**: each cycle's raw half-loops are kept (`_cyc[ch]`).
  New commands `GetNumberOfCycles`, `GetCycle(n)` (7 blocks of `2×NumberOfPoints`:
  field + result1–6), `SetExcludedCycles(short[])`, `RecomputeAverage()` —
  inspect individual scans and drop a bad one from the average without
  re-measuring. Averaging + Hc/Hshift/Mr/Ms derivation extracted into one shared
  `_average_and_derive(included)` used by both the live loop and recompute
  (verified numerically identical to the original inline math for the all-cycles case).

### Housekeeping
- Removed 17 tracked `__pycache__/*.pyc`; added `.gitignore` (bytecode, build/, egg-info).

---

## Recent Changes (July 2026) — AdsBridge2 Auto-Reconnect & Keepalive Watchdog

Branch `claude/magnet-tango-network-issues-875e80`. Background: the magnet
panel showed `-----` (all reads throwing) while AdsBridge2 and the Magnet
device stayed green, reproducibly ~5 minutes after a manual restart —
the ADS TCP session to the Beckhoff dies and nothing ever rebuilt it.

- `_ads_call()` wraps every command: on failure → reconnect → retry once →
  only then raise. ADS err 1808 (symbol not found) exempted from retry.
- Keepalive watchdog thread (`KeepaliveInterval` property, default 10 s,
  0 = off): ADS `read_state()` when the lock is free; reconnects a dead
  link between commands; self-disables after 3 consecutive `read_state`
  failures on *fresh* connections (quirky target protection).
- New `AutoReconnect` bool property (default True) gates both layers.
- Status string counts reconnects with timestamps — a steadily climbing
  counter is the diagnostic for a periodic session-killer in the network
  path (switch idle timeout, PLC router).
- `init_device` no longer throws when the PLC is unreachable — starts
  FAULT and self-heals. `Reconnect` command kept (now uses the shared
  `_reconnect_locked`). `delete_device` stops the watchdog cleanly
  (Init-safe). Both new properties documented in `AdsBridge2.xmi`.
- Headless behavior test (stubbed pyads/tango): retry-once semantics,
  1808 exemption, AutoReconnect=False, keepalive repair, FAULT clearing,
  failed-init self-heal — 17 checks. Not committed (stub scaffolding);
  `py_compile` clean.
