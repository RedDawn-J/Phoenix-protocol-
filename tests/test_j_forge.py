"""Tests for the Sovereign Shards compiler and J-Forge product generator."""
from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from scripts import j_forge, shardsc


class ShardsCompilerTests(unittest.TestCase):
    def test_compiles_and_runs_function_and_loop(self) -> None:
        source = '''
fn main() {
    let total = 0;
    let index = 0;
    while index < 3 {
        total = total + index;
        index = index + 1;
    }
    print("sum=" + str(total));
}
'''
        ir = shardsc.compile_source(source)
        output = StringIO()
        with redirect_stdout(output):
            shardsc.run_ir(ir)
        self.assertEqual(output.getvalue(), "sum=3\n")

    def test_compile_round_trip_to_json_artifact(self) -> None:
        ir = shardsc.compile_source('fn main() { print("ready"); }')
        decoded = json.loads(json.dumps(ir))
        output = StringIO()
        with redirect_stdout(output):
            shardsc.run_ir(decoded)
        self.assertEqual(output.getvalue(), "ready\n")

    def test_loop_is_bounded_by_step_budget(self) -> None:
        ir = shardsc.compile_source("fn main() { while true { } }")
        with self.assertRaisesRegex(shardsc.ShardError, "step limit"):
            shardsc.run_ir(ir, max_steps=20)

    def test_import_syntax_is_rejected(self) -> None:
        with self.assertRaisesRegex(shardsc.ShardError, "unexpected character"):
            shardsc.compile_source("import os;")

    def test_unknown_variable_is_reported(self) -> None:
        ir = shardsc.compile_source("fn main() { print(missing); }")
        with self.assertRaisesRegex(shardsc.ShardError, "not defined"):
            shardsc.run_ir(ir)


class JForgeTests(unittest.TestCase):
    def test_website_product_escapes_user_content_and_validates(self) -> None:
        files = j_forge.product_files({
            "name": "starter-site",
            "kind": "website",
            "title": "A < title",
            "description": "A & B",
            "body": "<script>no</script>",
        })
        self.assertIn("A &lt; title", files["index.html"])
        self.assertEqual(j_forge.validate_generated(files), [])

    def test_python_cli_product_parses(self) -> None:
        files = j_forge.product_files({"name": "tiny-tool", "kind": "python-cli", "description": "Hello"})
        self.assertIn("main.py", files)
        self.assertEqual(j_forge.validate_generated(files), [])

    def test_shards_product_compiles(self) -> None:
        files = j_forge.product_files({
            "name": "shards-tool",
            "kind": "shards-app",
            "source": 'fn main() { print("hello"); }',
        })
        self.assertIn("main.shard", files)
        self.assertEqual(j_forge.validate_generated(files), [])

    def test_overwrite_requires_explicit_flag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "README.md").write_text("existing", encoding="utf-8")
            with self.assertRaisesRegex(j_forge.ProductError, "refusing to overwrite"):
                j_forge.write_product({"README.md": "new"}, output, overwrite=False)

    def test_invalid_slug_is_rejected(self) -> None:
        with self.assertRaisesRegex(j_forge.ProductError, "project slug"):
            j_forge.product_files({"name": "../bad", "kind": "website"})


if __name__ == "__main__":
    unittest.main()
