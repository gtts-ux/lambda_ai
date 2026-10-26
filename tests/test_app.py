import asyncio
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from unittest.mock import patch
from pathlib import Path
import tempfile
from threading import Event
import unittest

from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from lambda_cli.cli import main
from lambda_cli.engine import DEFAULT_MODEL, Engine, Settings, prompt_for
from lambda_cli.session import Session
from lambda_cli.tui import TerminalApp


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.env = patch.dict(os.environ, {"LAMBDA_DATA_HOME": cls.directory.name})
        cls.env.start()
        cls.engine = Engine()

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.directory.cleanup()

    def test_bundle_checksum_and_no_optimizer(self):
        import numpy as np
        manifest = json.loads(DEFAULT_MODEL.with_suffix(".json").read_text())
        self.assertEqual(hashlib.sha256(DEFAULT_MODEL.read_bytes()).hexdigest(), manifest["sha256"])
        with np.load(DEFAULT_MODEL, allow_pickle=False) as data:
            self.assertEqual(set(data.files), {"metadata", "E", "W1", "b1", "W2", "b2", "W3", "b3"})
        self.assertEqual(self.engine.parameter_count, manifest["parameters"])
        self.assertTrue(all(not w.flags.writeable for w in self.engine.weights.values()))

    def test_tokenizer_preserves_whitespace_and_punctuation(self):
        for text in ["Hello, world!", "Question: Cat?\nAnswer: Yes.\n\n", "  A\tB  "]:
            self.assertEqual(self.engine.tokenizer.decode(self.engine.tokenizer.encode(text)), text)

    def test_generation_is_reproducible_and_streams_actual_tokens(self):
        updates = []
        settings = Settings(seed=7, max_tokens=80)
        before = hashlib.sha256(DEFAULT_MODEL.read_bytes()).hexdigest()
        first = self.engine.generate(prompt_for("What is a cat?"), settings,
                                     on_text=lambda text, count: updates.append((text, count)))
        second = self.engine.generate(prompt_for("What is a cat?"), settings)
        self.assertEqual(first.text, second.text)
        self.assertEqual(first.generated, second.generated)
        self.assertEqual(updates[-1], (first.text, len(first.generated)))
        self.assertTrue(all("\nQuestion:" not in text and "\n\n" not in text for text, _ in updates))
        raw = self.engine.tokenizer.decode([t.id for t in first.generated])
        self.assertTrue(raw.lstrip().startswith(first.text))
        self.assertEqual(first.context_used, min(len(first.prompt_ids), self.engine.context))
        self.assertEqual(before, hashlib.sha256(DEFAULT_MODEL.read_bytes()).hexdigest())

    def test_cancel_and_context_truncation_are_reported(self):
        cancelled = Event()
        cancelled.set()
        prompt = prompt_for("kot " * 150)
        result = self.engine.generate(prompt, cancel=cancelled)
        self.assertEqual(result.finish_reason, "cancelled")
        self.assertEqual(len(result.generated), 0)
        self.assertEqual(result.context_used, self.engine.context)
        self.assertEqual(result.context_dropped, len(result.prompt_ids)-self.engine.context)

    def test_invalid_settings_and_characters_are_explained(self):
        for settings in [Settings(temperature=float("nan")), Settings(max_tokens=0), Settings(top_k=-1)]:
            with self.assertRaises(ValueError):
                settings.validate()
        with self.assertRaisesRegex(ValueError, "does not support the character"):
            self.engine.tokenizer.encode("🙂")

    def test_session_export_is_explicit_and_never_overwrites(self):
        session = Session(self.engine)
        session.add_user("Hello!")
        result = self.engine.generate(prompt_for("Hello!"), Settings(seed=7, max_tokens=40))
        session.complete(result)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "conversation with spaces.json"
            session.command("/save " + str(path))
            exported = json.loads(path.read_text())
            self.assertEqual(exported["turns"][0]["generated_tokens"], len(result.generated))
            with self.assertRaises(FileExistsError):
                session.command("/save " + str(path))
        session.command("/new")
        self.assertEqual(session.totals()["turns"], 0)

    def test_failed_setting_does_not_replace_previous_setting(self):
        session = Session(self.engine)
        with self.assertRaises(ValueError):
            session.command("/temperature -1")
        self.assertEqual(session.settings.temperature, 0.4)
        session.command("/limit 50")
        self.assertEqual(session.settings.max_tokens, 50)

    def test_scriptable_commands_return_json(self):
        for arguments in [["info", "--json"], ["tokens", "What is a cat?", "--json"],
                          ["ask", "Hello!", "--seed", "7", "--json"]]:
            stream = io.StringIO()
            with redirect_stdout(stream):
                self.assertEqual(main(arguments), 0)
            value = json.loads(stream.getvalue())
            self.assertIsInstance(value, dict)


class TerminalTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"LAMBDA_DATA_HOME": self.directory.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    async def test_tabs_streaming_and_exit_in_full_screen(self):
        with create_pipe_input() as pipe:
            with create_app_session(input=pipe, output=DummyOutput()):
                session = Session(Engine(), Settings(seed=7, max_tokens=80))
                ui = TerminalApp(session)
                task = asyncio.create_task(ui.app.run_async())
                try:
                    await asyncio.sleep(0.1)
                    pipe.send_text("Hello!\r")
                    for _ in range(100):
                        await asyncio.sleep(0.03)
                        if session.turns:
                            break
                    self.assertEqual(len(session.turns), 1)
                    pipe.send_text("\x1bOQ")  # F2
                    await asyncio.sleep(0.1)
                    self.assertEqual(ui.view, "tokens")
                    self.assertIn("ACTUALLY SAMPLED TOKENS", ui.body.text)
                    pipe.send_text("\x1bOR")  # F3
                    await asyncio.sleep(0.1)
                    self.assertEqual(ui.view, "model")
                    self.assertIn("MATRICES", ui.body.text)
                    pipe.send_text("\x04")
                    await asyncio.wait_for(task, timeout=3)
                finally:
                    if not task.done():
                        ui.close()
                        await task


if __name__ == "__main__":
    unittest.main()
