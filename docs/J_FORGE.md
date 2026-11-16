# J-Forge and Sovereign Shards Language

J-Forge is the first Sovereign Shards product-generation layer. It has two connected deliverables:

1. A custom language toolchain for `.shard` source files.
2. A product-spec compiler that creates validated starter products.

This is an initial, dependency-free compiler milestone—not a claim that one release already replaces every commercial application builder or native platform compiler. J-Forge generates real files and validates them; native targets still use their target toolchains.

## Sovereign Shards language v0

The first language subset is deliberately small and auditable. It supports:

- functions and parameters
- `let` declarations and assignment
- `if` / `else` and bounded `while` loops
- `return`
- integer, float, string, boolean, and `null` values
- arithmetic, comparison, and logical operators
- function calls and a small set of built-ins: `print`, `len`, `str`, `int`, and bounded `range`

Statements end with semicolons. Blocks use braces. Imports, filesystem access, and shell access are not part of this language runtime.

Example `hello.shard`:

```text
fn greet(name) {
    print("Hello, " + name);
}

fn main() {
    greet("Sovereign Shards");
}
```

Check, compile to portable Sovereign Shards IR, and run:

```bash
python scripts/shardsc.py check hello.shard
python scripts/shardsc.py compile hello.shard
python scripts/shardsc.py run hello.shard
python scripts/shardsc.py run hello.ssir.json
```

The runtime enforces an instruction/step budget and call-depth limit. This is a bounded language runtime, not a security sandbox for arbitrary native processes. The emitted `.ssir.json` is a versioned portable intermediate representation, not a native machine-code executable.

## Product-spec compiler

J-Forge accepts JSON specs and currently generates three starter types: static websites, Python CLI applications, and Sovereign Shards programs. Output files are real and can be edited, tested, and built with local toolchains.

Example `product.json`:

```json
{
  "name": "field-notes",
  "kind": "website",
  "title": "Field Notes",
  "description": "A small place for observations and ideas.",
  "heading": "Notice more.",
  "body": "Capture what matters."
}
```

Generate into a new workspace folder:

```bash
python scripts/j_forge.py product.json --output ./build/field-notes
```

Supported `kind` values:

- `website` — `index.html` and `README.md`
- `python-cli` — `main.py` and `README.md`; optional `source` must parse as Python
- `shards-app` — `main.shard` and `README.md`; `source` is required and must compile

Existing generated files are not replaced unless `--overwrite` is passed. The tool validates HTML structure, Python syntax, or Shards syntax before writing. HTML text fields are escaped before insertion.

## Falsification-first build gate

J-Forge treats generated output as a hypothesis, not a success claim:

1. Validate the product spec and allowed target kind.
2. Generate complete artifacts in the chosen output directory.
3. Run a target-specific syntax/structure check.
4. Stop with a failure if validation finds a counterexample.
5. Report exactly which artifacts were written and which gates passed.

This first gate checks structural validity. It does not claim that a website meets a design brief, a Python CLI behaves correctly for all inputs, or an application is production-ready. Add functional tests and run the relevant local build command for that claim.

## Windows release direction

The Windows installer should package J-Forge and the Shards runtime, guide the user through workspace and model setup, and expose advanced toolchain setup only when needed. This first compiler milestone is standard-library Python and is not yet a signed Windows installer. Installation and packaging remain a release milestone.

## Current boundaries

- No web search is performed by either compiler. Research should be an explicit, separately audited opt-in capability.
- Product generation is template/spec based at this milestone. It does not yet autonomously design arbitrary products or replace a human's acceptance testing.
- Python/native builds use locally installed toolchains; J-Forge does not bundle every platform compiler.
- The Sovereign Shards language has no network, filesystem, or shell built-ins.

## Tests

```bash
python -m unittest tests.test_j_forge
```
