"""Zurich Instruments MFLI lock-in TANGO servers — one source for ZI and ZI2.

Console scripts (see pyproject.toml): ``ZI_DAQ`` serves class ``ZI`` (Green,
dev4855) and ``ZI2_DAQ`` serves class ``ZI2`` (IR, dev30933).
"""
from .device import ZILockin, ZI, ZI2, SETTLE_99, main_zi, main_zi2
from .thread import AcquisitionThread, MIN_COLLECT

__all__ = ["ZILockin", "ZI", "ZI2", "SETTLE_99", "AcquisitionThread",
           "MIN_COLLECT", "main_zi", "main_zi2"]
