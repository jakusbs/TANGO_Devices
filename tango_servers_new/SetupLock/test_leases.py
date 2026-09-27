from concurrent.futures import ThreadPoolExecutor
import threading
import unittest

from lease_store import LeaseStore


class LeaseTests(unittest.TestCase):
    def test_simultaneous_clients_have_one_winner(self):
        store = LeaseStore()
        barrier = threading.Barrier(16)
        def acquire(owner):
            barrier.wait()
            return owner, store.acquire("Green", owner)["acquired"]
        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(acquire, map(str, range(16))))
        winners = [owner for owner, ok in results if ok]
        self.assertEqual(len(winners), 1)
        for owner, ok in results:
            if not ok:
                self.assertFalse(store.release("Green", owner))
        self.assertEqual(store.status("Green")["owner"], winners[0])

    def test_owner_renewal_and_expiry(self):
        now = [0.]
        store = LeaseStore(clock=lambda: now[0])
        self.assertTrue(store.acquire("Cryo", "A", 60)["acquired"])
        now[0] = 50.
        self.assertTrue(store.renew("Cryo", "A", 60))
        self.assertFalse(store.renew("Cryo", "B", 60))
        now[0] = 100.
        self.assertFalse(store.acquire("Cryo", "B")["acquired"])
        now[0] = 111.
        self.assertTrue(store.acquire("Cryo", "B")["acquired"])
        self.assertFalse(store.release("Cryo", "A"))
        self.assertTrue(store.release("Cryo", "B"))

    def test_legacy_attributes_cannot_clear_atomic_lease(self):
        store = LeaseStore()
        store.acquire("IR", "A")
        with self.assertRaises(ValueError):
            store.legacy_write("IR", "busy", False)
        self.assertEqual(store.status("IR")["owner"], "A")

    def test_new_client_respects_legacy_owner(self):
        store = LeaseStore()
        store.legacy_write("Green", "info", "legacy")
        store.legacy_write("Green", "busy", True)
        self.assertFalse(store.acquire("Green", "new")["acquired"])
        store.legacy_write("Green", "busy", False)
        self.assertTrue(store.acquire("Green", "new")["acquired"])


if __name__ == "__main__":
    unittest.main()
