# SetupLock 2.0

Atomic, renewable ownership of Green, IR and Cryo. The existing six Busy/Info attributes remain available for monitoring and older clients.

| Command | JSON input | Result |
| --- | --- | --- |
| AcquireLease | `setup`, `owner`, optional `ttl` | JSON `acquired`, current `owner`, and `ttl` on success |
| RenewLease | same fields | true only for the current unexpired owner |
| ReleaseLease | `setup`, `owner` | true only when this owner was released |

Setup names are case-insensitive. Owners must be unique nonempty tokens of at most 512 characters. TTL is 30–3600 seconds (default 180). Expiration uses a monotonic clock. All ownership operations are serialized by one mutex. An expired owner cannot renew or release a successor. Legacy attribute writes cannot override an active atomic lease.

## Coordinated rollout

1. Stop acquisition on all Samba workstations. Install this folder (`python -m pip install .`) in the existing device-server environment and restart the existing Setup_lock server instance.
2. Upgrade all clients to Samba 13.31. Keep the device registration `hpp-N42/samba/lock` unchanged.
3. On idle rigs, verify that two workstations cannot acquire one setup, that the winner can renew/release it, and that a lost renewal pauses the upgraded client. Then perform a supervised short acquisition and close while stopping.

The accompanying Samba change renews every 30 seconds and displays Lease active, Advisory lock or Unprotected. Old clients remain advisory; their former fail-open behavior prevents claiming atomic exclusion in mixed deployments. A server restart clears in-memory leases, so restart only while idle. Leases do not terminate autonomous hardware operations or replace hardware interlocks.

The Pogo XMI includes the new command declarations; imports, initialization and command bodies are in protected regions. Keep `lease_store.py` alongside `SetupLock.py` when distributing the server.

## Validation

```sh
python -m unittest discover -s . -v
```

`test_leases.py` runs without TANGO or hardware and covers simultaneous acquisition, owner checks, expiry and legacy compatibility. `test_tango_api.py` uses PyTango's local DeviceTestContext with no laboratory database. CI runs both. The restricted development sandbox denies TANGO native interface enumeration, so the network command test must run in CI or a normal local environment.
