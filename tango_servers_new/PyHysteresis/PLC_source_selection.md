# PLC change: selectable hysteresis sources (HystSource1..6)

Companion change to the `source1..source6` attributes of the PyHysteresis
TANGO server. Until this is compiled into the PLC, the hysteresis engine
keeps its hard-wired behaviour (HystResult1..6 record AnalogIn1..6) and
writing the TANGO `sourceN` attributes raises a clear error.

Selector values: `1..6` = AnalogIn1..6 (old behaviour), `11..16` = ELM1..6.

Apply in **TwinCAT PLC Control** (TwinCAT 2.11, CX-16FC90) on the Windows PC:

## 1. Declarations — MAIN, VAR block (near the other Hyst* variables)

```
	(* ---- Hysteresis source selection ------------------------------------ *)
	(* Which signal is recorded into each HystResult array:
	   1..6  = AnalogIn1..AnalogIn6  (default = old hard-wired behaviour)
	   11..16 = ELM1..ELM6
	   Written over ADS by the PyHysteresis TANGO server (source1..source6). *)
	HystSource1 : INT := 1;
	HystSource2 : INT := 2;
	HystSource3 : INT := 3;
	HystSource4 : INT := 4;
	HystSource5 : INT := 5;
	HystSource6 : INT := 6;
	HystSrc : ARRAY[1..16] OF LREAL;	(* source pool, refreshed every cycle *)
```

## 2. Cyclic code — directly BEFORE the six recording lines

Search MAIN for `HystResult1[HystIndex/HystAverages` to find the recording
block, and insert this immediately above it:

```
		(* clamp selectors so a bad ADS write can never index out of range;
		   invalid values fall back to the channel's old hard-wired input *)
		IF (HystSource1 < 1) OR (HystSource1 > 16) THEN HystSource1 := 1; END_IF
		IF (HystSource2 < 1) OR (HystSource2 > 16) THEN HystSource2 := 2; END_IF
		IF (HystSource3 < 1) OR (HystSource3 > 16) THEN HystSource3 := 3; END_IF
		IF (HystSource4 < 1) OR (HystSource4 > 16) THEN HystSource4 := 4; END_IF
		IF (HystSource5 < 1) OR (HystSource5 > 16) THEN HystSource5 := 5; END_IF
		IF (HystSource6 < 1) OR (HystSource6 > 16) THEN HystSource6 := 6; END_IF

		(* refresh the source pool (7..10 stay 0 = unused) *)
		HystSrc[1]  := AnalogIn1;	HystSrc[2]  := AnalogIn2;
		HystSrc[3]  := AnalogIn3;	HystSrc[4]  := AnalogIn4;
		HystSrc[5]  := AnalogIn5;	HystSrc[6]  := AnalogIn6;
		HystSrc[11] := ELM1;		HystSrc[12] := ELM2;
		HystSrc[13] := ELM3;		HystSrc[14] := ELM4;
		HystSrc[15] := ELM5;		HystSrc[16] := ELM6;
```

## 3. Replace the six recording lines

Old:

```
		HystResult1[HystIndex/HystAverages+1] := HystResult1[HystIndex/HystAverages+1] + AnalogIn1/INT_TO_LREAL(HystAverages);
		(* ... AnalogIn2..AnalogIn6 for HystResult2..6 ... *)
```

New:

```
		HystResult1[HystIndex/HystAverages+1] := HystResult1[HystIndex/HystAverages+1] + HystSrc[HystSource1]/INT_TO_LREAL(HystAverages);
		HystResult2[HystIndex/HystAverages+1] := HystResult2[HystIndex/HystAverages+1] + HystSrc[HystSource2]/INT_TO_LREAL(HystAverages);
		HystResult3[HystIndex/HystAverages+1] := HystResult3[HystIndex/HystAverages+1] + HystSrc[HystSource3]/INT_TO_LREAL(HystAverages);
		HystResult4[HystIndex/HystAverages+1] := HystResult4[HystIndex/HystAverages+1] + HystSrc[HystSource4]/INT_TO_LREAL(HystAverages);
		HystResult5[HystIndex/HystAverages+1] := HystResult5[HystIndex/HystAverages+1] + HystSrc[HystSource5]/INT_TO_LREAL(HystAverages);
		HystResult6[HystIndex/HystAverages+1] := HystResult6[HystIndex/HystAverages+1] + HystSrc[HystSource6]/INT_TO_LREAL(HystAverages);
```

The zero-initialisation block (`HystResult1[HystIndex] := 0;` ...) above it
stays unchanged. Do NOT touch the commented-out AnalogOut1 test line.

## 4. Build, download, persist

1. Project → Rebuild all (must compile with 0 errors).
2. Online → Login → Download.
3. Online → **Create Boot Project** (so the change survives a CX reboot).
4. Verify over ADS (e.g. Jive → AdsBridge2 → `ReadShort` `MAIN.HystSource1`
   should return 1).
5. Archive the new `.pro`/`.tpy` snapshot into
   `tango_servers_old/software_windows/Beckhoff/` like the previous versions.

## 5. Use

In Jive (or Samba) on the PyHysteresis device, e.g. record ELM2 into
result1: write attribute `source1 = 12`. Values are memorized in the TANGO
DB and re-pushed to the PLC at every `Start()`, so they survive both TANGO
server restarts and PLC reboots.

Note: the live ELM1..6 values are the right sources here — the hysteresis
engine performs its own per-point averaging (HystAverages), so no
pre-averaged variable is needed.
