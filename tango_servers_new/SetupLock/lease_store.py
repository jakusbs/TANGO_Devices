"""Thread-safe setup leases, independent of TANGO for deterministic testing."""
from dataclasses import dataclass
import threading
import time


@dataclass
class Lease:
    owner: str = ""
    deadline: float | None = None
    legacy: bool = False
    busy: bool = False


class LeaseStore:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._mutex = threading.RLock()
        self._leases = {name: Lease() for name in ("green", "ir", "cryo")}

    def _get(self, setup):
        key = str(setup).lower()
        if key not in self._leases:
            raise ValueError("Unknown setup")
        lease = self._leases[key]
        if lease.deadline is not None and lease.deadline <= self._clock():
            lease = self._leases[key] = Lease()
        return lease

    @staticmethod
    def _request(owner, ttl):
        if not isinstance(owner, str) or not owner.strip() or len(owner) > 512:
            raise ValueError("A nonempty owner token (at most 512 characters) is required")
        ttl = float(ttl)
        if not 30 <= ttl <= 3600:
            raise ValueError("Lease duration must be 30–3600 seconds")
        return ttl

    def acquire(self, setup, owner, ttl=180):
        ttl = self._request(owner, ttl)
        with self._mutex:
            lease = self._get(setup)
            if lease.busy and (lease.legacy or lease.owner != owner):
                return {"acquired": False, "owner": lease.owner}
            lease.owner, lease.busy, lease.legacy = owner, True, False
            lease.deadline = self._clock() + ttl
            return {"acquired": True, "owner": owner, "ttl": ttl}

    def renew(self, setup, owner, ttl=180):
        ttl = self._request(owner, ttl)
        with self._mutex:
            lease = self._get(setup)
            if not lease.busy or lease.legacy or lease.owner != owner:
                return False
            lease.deadline = self._clock() + ttl
            return True

    def release(self, setup, owner):
        with self._mutex:
            lease = self._get(setup)
            if not lease.busy or lease.legacy or lease.owner != owner:
                return False
            self._leases[str(setup).lower()] = Lease()
            return True

    def status(self, setup):
        with self._mutex:
            lease = self._get(setup)
            return {"busy": lease.busy, "owner": lease.owner,
                    "legacy": lease.legacy,
                    "remaining": max(0., lease.deadline - self._clock())
                    if lease.deadline is not None else None}

    def legacy_write(self, setup, field, value):
        """Retain old attributes without letting them overwrite active leases."""
        with self._mutex:
            lease = self._get(setup)
            if lease.busy and not lease.legacy:
                raise ValueError("An active lease requires an owner-checked ReleaseLease")
            lease.legacy = True
            if field == "busy":
                lease.busy = bool(value)
                if not value:
                    lease.owner = ""
            elif field == "info":
                lease.owner = str(value)
            else:
                raise ValueError("Unknown legacy field")
