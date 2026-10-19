"""Run: python -m unittest discover -s lite -v"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import netmon


class NetMonTests(unittest.TestCase):
    def test_configuration_rejects_bad_inputs(self):
        for change in [{"interval_seconds": True}, {"interval_seconds": float("nan")},
                       {"timeout_ms": 0}, {"devices": []},
                       {"devices": [None]},
                       {"devices": [{"name": "x", "address": 1}]},
                       {"devices": [{"name": "bad", "address": "-n 100"}]},
                       {"devices": [{"name": "x", "address": "127.0.0.1"}] * 2}]:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                config = {"devices": [{"name": "Local", "address": "127.0.0.1"}], **change}
                path = Path(folder) / "devices.json"
                path.write_text(json.dumps(config))
                with self.assertRaises((ValueError, TypeError)):
                    netmon.load_config(path)

    def test_example_config(self):
        self.assertEqual(netmon.load_config(Path(__file__).with_name("devices.example.json"))[0], 5)

    @patch("netmon.subprocess.run")
    def test_reply(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "Reply from 127.0.0.1: bytes=32 time<1ms TTL=128", "")
        row = netmon.probe({"name": "Local", "address": "127.0.0.1"}, 1000)
        self.assertEqual(row["status"], "up")
        self.assertEqual(row["latency_ms"], 1)
        self.assertIsInstance(run.call_args.args[0], list)
        self.assertNotIn("shell", run.call_args.kwargs)

    @patch("netmon.subprocess.run")
    def test_unreachable_is_down_even_with_success_exit(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "Destination host unreachable.", "")
        self.assertEqual(netmon.probe({"address": "192.0.2.1"}, 1000)["status"], "down")

    @patch("netmon.subprocess.run")
    def test_local_failure_is_error(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, "Unable to contact IP driver. General failure.", "")
        self.assertEqual(netmon.probe({"address": "127.0.0.1"}, 1000)["status"], "error")

    @patch("netmon.subprocess.run", side_effect=subprocess.TimeoutExpired("ping", 3))
    def test_process_deadline_is_error(self, run):
        self.assertEqual(netmon.probe({"address": "127.0.0.1"}, 1000)["status"], "error")

    @patch("netmon.probe")
    def test_failure_does_not_lose_last_success_or_other_devices(self, probe):
        probe.side_effect = lambda device, timeout: dict(device, status="down", checked_at="now")
        devices = [{"name": "a", "address": "127.0.0.1"}, {"name": "b", "address": "127.0.0.2"}]
        with ThreadPoolExecutor(2) as executor:
            rows = netmon.collect(devices, 1000, {"127.0.0.1": {"last_success_at": "earlier"}}, executor)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["last_success_at"], "earlier")
        self.assertIsNone(rows[1]["last_success_at"])

    def test_atomic_publication_replaces_complete_document(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "published" / "status.json"
            netmon.publish(path, {"devices": []})
            netmon.publish(path, {"devices": [{"status": "up"}]})
            self.assertEqual(json.loads(path.read_text())["devices"][0]["status"], "up")
            self.assertFalse(path.with_suffix(".tmp").exists())


if __name__ == "__main__":
    unittest.main()
