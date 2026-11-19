from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import io

from lambda_cli.engine import DEFAULT_MODEL, Engine
from lambda_cli.models import ModelManager, atomic_json, validate_catalog
from lambda_cli.quota import ALLOWANCE, WINDOW_SECONDS, Quota, QuotaExceeded
from lambda_cli.session import Session


class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.now = 1000.0
        self.path = Path(self.directory.name)/"usage.sqlite3"
        self.quota = Quota(self.path, clock=lambda:self.now)

    def test_persists_blocks_and_resets_after_ten_hours(self):
        reservation = self.quota.reserve(20, ALLOWANCE-20)
        self.quota.complete(reservation, ALLOWANCE)
        other = Quota(self.path, clock=lambda:self.now)
        self.assertEqual(other.status()["remaining"],0)
        with self.assertRaises(QuotaExceeded):
            other.reserve(1,1)
        self.now += WINDOW_SECONDS-1
        self.assertEqual(other.status()["remaining"],0)
        self.now += 1
        self.assertEqual(other.status()["remaining"],ALLOWANCE)
        self.assertIsNone(other.status()["resets_at"])

    def test_unused_reservation_is_refunded_and_output_is_capped(self):
        first = self.quota.reserve(10,ALLOWANCE-15)
        self.quota.complete(first,ALLOWANCE-15)
        second = self.quota.reserve(5,100)
        self.assertEqual(second.max_output,10)
        self.quota.complete(second,9)
        self.assertEqual(self.quota.status()["remaining"],6)
        self.quota.complete(second,9)  # Settlement is idempotent.
        self.assertEqual(self.quota.status()["remaining"],6)

    def test_parallel_process_like_connections_cannot_overspend(self):
        def reserve(_):
            try:
                return self.quota.reserve(0,200000)
            except QuotaExceeded:
                return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            reservations = list(pool.map(reserve,range(8)))
        self.assertEqual(sum(r is not None for r in reservations),5)
        self.assertEqual(self.quota.status()["used"],ALLOWANCE)

    def test_new_session_and_model_selection_do_not_reset_allowance(self):
        reservation = self.quota.reserve(10,20)
        self.quota.complete(reservation,25)
        session = Session(Engine(),quota=self.quota,manager=ModelManager(Path(self.directory.name)/"models"))
        session.command("/new")
        session.model_action("use:lambda-1.0")
        self.assertEqual(self.quota.status()["used"],25)

    def test_chat_reserves_and_charges_actual_tokens(self):
        session = Session(Engine(),quota=self.quota,manager=ModelManager(Path(self.directory.name)/"models"))
        result = session.generate("Hello!")
        self.assertEqual(self.quota.status()["used"],result.context_used+len(result.generated))
        self.assertEqual(result.charged_tokens,self.quota.status()["used"])

    def test_interrupted_generation_charges_partial_output(self):
        engine = Engine()
        session = Session(engine,quota=self.quota,manager=ModelManager(Path(self.directory.name)/"models"))
        def interrupted(prompt, settings, progress, cancel):
            progress("Hello",3)
            raise KeyboardInterrupt()
        with patch.object(engine,"generate",side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                session.generate("Hello!")
        from lambda_cli.engine import prompt_for
        expected = min(engine.context,len(engine.tokenizer.encode(prompt_for("Hello!"))))+3
        self.assertEqual(self.quota.status()["used"],expected)


class ModelUpdateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.manager = ModelManager(self.directory.name)

    def test_local_experiment_survives_catalog_refresh_without_public_download(self):
        root=Path(self.directory.name);(root/'models').mkdir()
        path=root/'models/local.npz';path.write_bytes(DEFAULT_MODEL.read_bytes())
        state=self.manager.state()
        state['installed']['lambda-2.5']=dict(filename=path.name,revision=1,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),local_only=True,name='lambda 2.5',min_app_version='0.8.3')
        atomic_json(root/'models.json',state)
        with patch('lambda_cli.models.urlopen',return_value=io.BytesIO(json.dumps(self.manager.bundled).encode())):
            self.manager.refresh_catalog()
        item=next(e for e in self.manager.entries() if e['id']=='lambda-2.5')
        self.assertTrue(item['local_only']);self.assertFalse(item['update_available'])
        with patch('lambda_cli.models.urlopen') as download:
            self.assertEqual(self.manager.install('lambda-2.5'),path)
            download.assert_not_called()
            path.unlink()
            with self.assertRaises(ValueError):self.manager.install('lambda-2.5')
            download.assert_not_called()

    def test_catalog_contains_owner_approved_models(self):
        entries = self.manager.entries()
        self.assertEqual([(e["id"],e["name"]) for e in entries],
                         [("lambda-1.0","lambda mercury 1.0"),("lambda-1.5","lambda mercury 1.5"),
                      ("lambda-1.6","lambda mercury 1.6"),("lambda-2","lambda venus 2"),("lambda-2.1","lambda venus 2.1"),("lambda-2.2","lambda venus 2.2"),("lambda-2.4","lambda venus 2.4"),("lambda-2.5.1","lambda venus 2.5.1"),("lambda-2.5.2","lambda venus 2.5.2"),("lambda-code-3","lambda code 3"),("lambda-terra-4.1-demo","lambda terra 4.1 demo"),("lambda-terra-4.1","lambda terra 4.1")])
        self.assertEqual(self.manager.resolve(),DEFAULT_MODEL)

    def revision(self):
        catalog = deepcopy(self.manager.bundled)
        entry = catalog["models"][0]
        entry["revision"] += 1
        content = DEFAULT_MODEL.read_bytes()
        entry["bytes"] = len(content)
        entry["sha256"] = hashlib.sha256(content).hexdigest()
        atomic_json(Path(self.directory.name)/"catalog.json",catalog)
        return catalog, content

    def test_download_validates_and_installs_without_changing_original(self):
        catalog,content = self.revision()
        with patch("lambda_cli.models.urlopen",return_value=io.BytesIO(content)):
            path = self.manager.install("lambda-1.0")
        self.assertEqual(path.read_bytes(),content)
        self.assertEqual(Engine(path).parameter_count,747008)
        self.assertEqual(self.manager.entries()[0]["installed_revision"],2)
        self.assertEqual(self.manager.activate("lambda-1.0").path,path.resolve())

    def test_bad_checksum_preserves_previous_model(self):
        catalog,content = self.revision()
        catalog["models"][0]["sha256"] = "0"*64
        atomic_json(Path(self.directory.name)/"catalog.json",catalog)
        with patch("lambda_cli.models.urlopen",return_value=io.BytesIO(content)):
            with self.assertRaisesRegex(ValueError,"checksum"):
                self.manager.install("lambda-1.0")
        self.assertEqual(self.manager.resolve(),DEFAULT_MODEL)
        self.assertFalse(list((Path(self.directory.name)/"models").glob("*.tmp")))

    def test_catalog_rejects_traversal_and_unknown_versions(self):
        catalog = deepcopy(self.manager.bundled)
        catalog["models"][0]["id"] = "../../outside"
        with self.assertRaises(ValueError):
            validate_catalog(catalog)
        catalog = deepcopy(self.manager.bundled)
        catalog["models"][0]["min_app_version"] = "99.0.0"
        atomic_json(Path(self.directory.name)/"catalog.json",catalog)
        with self.assertRaisesRegex(ValueError,"requires"):
            self.manager.install("lambda-1.0")


if __name__ == "__main__":
    unittest.main()
