"""Real command serialization over a local TANGO device, with no lab database."""
import json
import unittest
from tango.test_context import DeviceTestContext
from SetupLock import Setup_lock

class CommandTests(unittest.TestCase):
    def test_owner_checked_commands_and_legacy_attributes(self):
        with DeviceTestContext(Setup_lock, process=True, host='127.0.0.1') as proxy:
            owner = json.dumps({'setup': 'Green', 'owner': 'alpha', 'ttl': 180})
            other = json.dumps({'setup': 'Green', 'owner': 'beta', 'ttl': 180})
            self.assertTrue(json.loads(proxy.AcquireLease(owner))['acquired'])
            self.assertFalse(json.loads(proxy.AcquireLease(other))['acquired'])
            self.assertTrue(proxy.greenbusy)
            self.assertFalse(proxy.ReleaseLease(other))
            self.assertTrue(proxy.RenewLease(owner))
            with self.assertRaises(Exception):
                proxy.greenbusy = False
            self.assertTrue(proxy.ReleaseLease(owner))
            self.assertFalse(proxy.greenbusy)

if __name__ == '__main__':
    unittest.main()
