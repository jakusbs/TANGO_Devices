# ZurichInstruments_lockin — ZI / ZI2 MFLI servers from one source

| TANGO class | executable | instrument | defaults |
|---|---|---|---|
| `ZI`  | `ZI_DAQ`  | Green MFLI | `DeviceId=dev4855`,  `ZI_Host=192.168.1.62`  |
| `ZI2` | `ZI2_DAQ` | IR MFLI    | `DeviceId=dev30933`, `ZI_Host=192.168.1.144` |

`zi_lockin/device.py` holds the whole server (`ZILockin`); `ZI` and `ZI2`
only override the two property defaults.  `zi_lockin/thread.py` is the
acquisition thread (flush → collect `integrationtime` → numpy average → x1..y4).
Any instance can be pointed at another MFLI through its device properties
without editing code.

Deploy with `bash install.sh` in the environment the Tango Starter uses, then
restart the instance.  Tests: `python -m pytest tests/test_zi_lockin.py` from
the repository root (a fake `ziDAQServer`, no hardware).

History: until October 2026 this lived in `ZurichInstruments_lockin_correct_read/`
(ZI) and `ZurichInstruments_lockin2_correct_read/` (ZI2) as two copies that
differed only in names and defaults, plus two generated package copies.
