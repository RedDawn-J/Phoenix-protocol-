#!/usr/bin/env python3
"""Sovereign Shards language compiler and bounded local runtime."""
from __future__ import annotations

import argparse
import ast
import json
import operator
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

IR_VERSION = 1
MAX_SOURCE_BYTES = 500_000
MAX_COLLECTION_ITEMS = 10_000


class ShardError(ValueError):
    """A source, compilation, or runtime error with a useful location."""


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    column: int


@dataclass
class Node:
    kind: str
    value: Any = None
    children: list["Node"] | None = None
    line: int = 0


TOKEN_PATTERN = re.compile(
    r"(?P<space>[ \t\r\n]+)|(?P<comment>//[^\n]*|\#[^\n]*)|"
    r"(?P<number>\d+(?:\.\d+)?)|"
    r"(?P<string>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')|"
    r"(?P<identifier>[A-Za-z_]\w*)|"
    r"(?P<operator>==|!=|<=|>=|&&|\|\||[+\-*/%<>=!;,(){}])"
)


class Lexer:
    def __init__(self, source: str):
        self.source = source

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        line = 1
        column = 1
        position = 0
        while position < len(self.source):
            match = TOKEN_PATTERN.match(self.source, position)
            if match is None:
                raise ShardError(f"line {line}:{column}: unexpected character {self.source[position]!r}")
            value = match.group(0)
            kind = match.lastgroup or ""
            if kind not in {"space", "comment"}:
                tokens.append(Token(kind, value, line, column))
            line_count = value.count("\n")
            if line_count:
                line += line_count
                column = len(value.rsplit("\n", 1)[-1]) + 1
            else:
                column += len(value)
            position = match.end()
        tokens.append(Token("eof", "", line, column))
        return tokens


class Parser:
    PRECEDENCE = {
        "or": 1, "||": 1, "and": 2, "&&": 2,
        "==": 3, "!=": 3, "<": 4, "<=": 4, ">": 4, ">=": 4,
        "+": 5, "-": 5, "*": 6, "/": 6, "%": 6,
    }

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.position = 0

    def current(self) -> Token:
        return self.tokens[self.position]

    def advance(self) -> Token:
        token = self.current()
        if token.kind != "eof":
            self.position += 1
        return token

    def accept(self, value: str) -> bool:
        if self.current().value == value:
            self.advance()
            return True
        return False

    def require(self, value: str) -> Token:
        token = self.current()
        if token.value != value:
            raise ShardError(f"line {token.line}:{token.column}: expected {value!r}, got {token.value!r}")
        return self.advance()

    def parse(self) -> Node:
        functions: list[Node] = []
        statements: list[Node] = []
        while self.current().kind != "eof":
            if self.current().value == "fn":
                functions.append(self.parse_function())
            else:
                statements.append(self.parse_statement())
        return Node("module", children=[Node("functions", children=functions), Node("block", children=statements)])

    def parse_function(self) -> Node:
        start = self.require("fn")
        name = self.require_identifier()
        self.require("(")
        params: list[Node] = []
        if not self.accept(")"):
            while True:
                params.append(Node("parameter", self.require_identifier().value))
                if self.accept(")"):
                    break
                self.require(",")
        body = self.parse_block()
        return Node("function", name.value, [Node("parameters", children=params), body], start.line)

    def require_identifier(self) -> Token:
        token = self.current()
        if token.kind != "identifier":
            raise ShardError(f"line {token.line}:{token.column}: expected an identifier")
        return self.advance()

    def parse_block(self) -> Node:
        self.require("{")
        statements: list[Node] = []
        while self.current().value != "}":
            if self.current().kind == "eof":
                token = self.current()
                raise ShardError(f"line {token.line}:{token.column}: unterminated block")
            statements.append(self.parse_statement())
        self.require("}")
        return Node("block", children=statements)

    def parse_statement(self) -> Node:
        token = self.current()
        if self.accept("let"):
            name = self.require_identifier()
            self.require("=")
            expression = self.parse_expression()
            self.require(";")
            return Node("let", name.value, [expression], token.line)
        if self.accept("return"):
            expression = None if self.current().value == ";" else self.parse_expression()
            self.require(";")
            return Node("return", children=[expression] if expression else [], line=token.line)
        if self.accept("if"):
            condition = self.parse_expression()
            then_block = self.parse_block()
            else_block = self.parse_block() if self.accept("else") else Node("block", children=[])
            return Node("if", children=[condition, then_block, else_block], line=token.line)
        if self.accept("while"):
            condition = self.parse_expression()
            body = self.parse_block()
            return Node("while", children=[condition, body], line=token.line)
        if self.current().kind == "identifier" and self.tokens[self.position + 1].value == "=":
            name = self.advance()
            self.advance()
            expression = self.parse_expression()
            self.require(";")
            return Node("assign", name.value, [expression], token.line)
        expression = self.parse_expression()
        self.require(";")
        return Node("expression", children=[expression], line=token.line)

    def parse_expression(self, minimum: int = 1) -> Node:
        left = self.parse_prefix()
        while True:
            operator_token = self.current()
            precedence = self.PRECEDENCE.get(operator_token.value)
            if precedence is None or precedence < minimum:
                break
            self.advance()
            right = self.parse_expression(precedence + 1)
            left = Node("binary", operator_token.value, [left, right], operator_token.line)
        return left

    def parse_prefix(self) -> Node:
        token = self.advance()
        if token.value in {"!", "not", "-"}:
            return Node("unary", token.value, [self.parse_expression(7)], token.line)
        if token.value == "(":
            expression = self.parse_expression()
            self.require(")")
            return expression
        if token.kind == "number":
            value: int | float = float(token.value) if "." in token.value else int(token.value)
            return Node("literal", value, line=token.line)
        if token.kind == "string":
            try:
                value = ast.literal_eval(token.value)
            except (SyntaxError, ValueError) as exc:
                raise ShardError(f"line {token.line}: malformed string literal") from exc
            return Node("literal", value, line=token.line)
        if token.kind == "identifier":
            if token.value in {"true", "false", "null"}:
                literal = {"true": True, "false": False, "null": None}[token.value]
                return Node("literal", literal, line=token.line)
            if self.accept("("):
                args: list[Node] = []
                if not self.accept(")"):
                    while True:
                        args.append(self.parse_expression())
                        if self.accept(")"):
                            break
                        self.require(",")
                return Node("call", token.value, args, token.line)
            return Node("name", token.value, line=token.line)
        raise ShardError(f"line {token.line}:{token.column}: expected an expression")


def compile_source(source: str) -> dict[str, Any]:
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ShardError(f"source exceeds {MAX_SOURCE_BYTES} bytes")
    tree = Parser(Lexer(source).tokenize()).parse()
    return {"format": "sovereign-shards-ir", "version": IR_VERSION, "tree": asdict(tree)}


def _node(value: dict[str, Any] | None) -> Node | None:
    if value is None:
        return None
    children = [_node(child) for child in value.get("children") or []]
    return Node(value["kind"], value.get("value"), [child for child in children if child is not None], value.get("line", 0))


class _ReturnSignal(Exception):
    def __init__(self, value: Any):
        self.value = value


class Runtime:
    BINARY: dict[str, Callable[[Any, Any], Any]] = {
        "+": operator.add, "-": operator.sub, "*": operator.mul,
        "/": operator.truediv, "%": operator.mod,
        "==": operator.eq, "!=": operator.ne, "<": operator.lt,
        "<=": operator.le, ">": operator.gt, ">=": operator.ge,
    }

    def __init__(self, ir: dict[str, Any], max_steps: int):
        if ir.get("format") != "sovereign-shards-ir" or ir.get("version") != IR_VERSION:
            raise ShardError("unsupported Sovereign Shards IR format or version")
        tree = _node(ir.get("tree"))
        if tree is None or tree.kind != "module" or len(tree.children or []) != 2:
            raise ShardError("compiled artifact has an invalid module tree")
        self.functions = {function.value: function for function in tree.children[0].children or []}
        self.module_body = tree.children[1]
        if len(self.functions) != len(tree.children[0].children or []):
            raise ShardError("duplicate function name")
        self.steps_left = max_steps
        self.call_depth = 0

    def _tick(self, line: int) -> None:
        self.steps_left -= 1
        if self.steps_left < 0:
            raise ShardError(f"line {line}: execution step limit exceeded")

    def run(self) -> Any:
        global_scope: dict[str, Any] = {}
        self.execute_block(self.module_body, global_scope, global_scope, False)
        if "main" in self.functions:
            return self.call_function("main", [], global_scope)
        return None

    def execute_block(self, block: Node, scope: dict[str, Any], global_scope: dict[str, Any], in_function: bool) -> None:
        for statement in block.children or []:
            self._tick(statement.line)
            kind = statement.kind
            if kind == "let":
                scope[statement.value] = self.evaluate(statement.children[0], scope, global_scope)
            elif kind == "assign":
                if not self._assign(scope, statement.value, self.evaluate(statement.children[0], scope, global_scope)):
                    raise ShardError(f"line {statement.line}: variable {statement.value!r} is not defined")
            elif kind == "expression":
                self.evaluate(statement.children[0], scope, global_scope)
            elif kind == "return":
                if not in_function:
                    raise ShardError(f"line {statement.line}: return outside a function")
                result = self.evaluate(statement.children[0], scope, global_scope) if statement.children else None
                raise _ReturnSignal(result)
            elif kind == "if":
                branch = statement.children[1] if self.evaluate(statement.children[0], scope, global_scope) else statement.children[2]
                self.execute_block(branch, scope, global_scope, in_function)
            elif kind == "while":
                while self.evaluate(statement.children[0], scope, global_scope):
                    self._tick(statement.line)
                    self.execute_block(statement.children[1], scope, global_scope, in_function)
            else:
                raise ShardError(f"line {statement.line}: unsupported statement {kind}")

    @staticmethod
    def _assign(scope: dict[str, Any], name: str, value: Any) -> bool:
        if name in scope:
            scope[name] = value
            return True
        parent = scope.get("__parent_scope__")
        if isinstance(parent, dict):
            return Runtime._assign(parent, name, value)
        return False

    def evaluate(self, expression: Node, scope: dict[str, Any], global_scope: dict[str, Any]) -> Any:
        self._tick(expression.line)
        if expression.kind == "literal":
            return expression.value
        if expression.kind == "name":
            if expression.value in scope:
                return scope[expression.value]
            if expression.value in global_scope:
                return global_scope[expression.value]
            raise ShardError(f"line {expression.line}: variable {expression.value!r} is not defined")
        if expression.kind == "unary":
            value = self.evaluate(expression.children[0], scope, global_scope)
            if expression.value in {"!", "not"}:
                return not value
            if expression.value == "-" and isinstance(value, (int, float)) and not isinstance(value, bool):
                return -value
            raise ShardError(f"line {expression.line}: unary minus expects a number")
        if expression.kind == "binary":
            left = self.evaluate(expression.children[0], scope, global_scope)
            if expression.value in {"and", "&&"}:
                return bool(left) and bool(self.evaluate(expression.children[1], scope, global_scope))
            if expression.value in {"or", "||"}:
                return bool(left) or bool(self.evaluate(expression.children[1], scope, global_scope))
            right = self.evaluate(expression.children[1], scope, global_scope)
            try:
                return self.BINARY[expression.value](left, right)
            except (KeyError, TypeError, ZeroDivisionError) as exc:
                raise ShardError(f"line {expression.line}: invalid operation {expression.value!r}: {exc}") from exc
        if expression.kind == "call":
            args = [self.evaluate(arg, scope, global_scope) for arg in expression.children or []]
            return self.call_function(expression.value, args, global_scope)
        raise ShardError(f"line {expression.line}: unsupported expression {expression.kind}")

    def call_function(self, name: str, args: list[Any], global_scope: dict[str, Any]) -> Any:
        builtins: dict[str, Callable[..., Any]] = {
            "print": print,
            "len": len,
            "str": str,
            "int": int,
            "range": self._safe_range,
        }
        if name in builtins:
            try:
                return builtins[name](*args)
            except (TypeError, ValueError) as exc:
                raise ShardError(f"invalid call to {name}: {exc}") from exc
        function = self.functions.get(name)
        if function is None:
            raise ShardError(f"function {name!r} is not defined")
        parameters = function.children[0].children or []
        if len(args) != len(parameters):
            raise ShardError(f"function {name} expects {len(parameters)} argument(s), got {len(args)}")
        self.call_depth += 1
        if self.call_depth > 64:
            self.call_depth -= 1
            raise ShardError("function call depth limit exceeded")
        scope = {parameter.value: value for parameter, value in zip(parameters, args)}
        try:
            self.execute_block(function.children[1], scope, global_scope, True)
        except _ReturnSignal as result:
            return result.value
        finally:
            self.call_depth -= 1
        return None

    @staticmethod
    def _safe_range(*args: int) -> list[int]:
        if not 1 <= len(args) <= 3 or any(not isinstance(value, int) or isinstance(value, bool) for value in args):
            raise TypeError("range expects one to three integer arguments")
        values = list(range(*args))
        if len(values) > MAX_COLLECTION_ITEMS:
            raise ValueError(f"range is limited to {MAX_COLLECTION_ITEMS} items")
        return values


def run_ir(ir: dict[str, Any], max_steps: int = 100_000) -> Any:
    return Runtime(ir, max_steps).run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile and run the Sovereign Shards language.")
    parser.add_argument("command", choices=["check", "compile", "run"])
    parser.add_argument("source", type=Path, help=".shard source or compiled .ssir.json artifact")
    parser.add_argument("-o", "--output", type=Path, help="compiled IR output path (compile command)")
    parser.add_argument("--max-steps", type=int, default=100_000, help="runtime instruction budget")
    args = parser.parse_args(argv)
    if args.max_steps < 1:
        parser.error("--max-steps must be positive")
    try:
        if args.command == "run" and args.source.suffix == ".json":
            ir = json.loads(args.source.read_text(encoding="utf-8"))
        else:
            source = args.source.read_text(encoding="utf-8")
            ir = compile_source(source)
        if args.command == "check":
            print(f"OK · {args.source} parses")
        elif args.command == "compile":
            output = args.output or args.source.with_suffix(".ssir.json")
            output.write_text(json.dumps(ir, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"OK · compiled {args.source} -> {output}")
        else:
            run_ir(ir, args.max_steps)
        return 0
    except (OSError, json.JSONDecodeError, ShardError) as exc:
        print(f"FAIL · {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
