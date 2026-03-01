"""DOT parser: lexer + recursive descent parser for the supported subset."""

from __future__ import annotations

import re
from typing import Any

from attractor.pipeline.graph import Edge, Graph, Node, _coerce_value


class ParseError(Exception):
    def __init__(self, message: str, line: int = 0, col: int = 0):
        super().__init__(message)
        self.line = line
        self.col = col


class TokenType:
    DIGRAPH = "DIGRAPH"
    GRAPH = "GRAPH"
    SUBGRAPH = "SUBGRAPH"
    NODE = "NODE"
    EDGE = "EDGE"
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
    SEMICOLON = "SEMICOLON"
    COMMA = "COMMA"
    EQUALS = "EQUALS"
    ARROW = "ARROW"
    ID = "ID"
    STRING = "STRING"
    EOF = "EOF"


class Token:
    def __init__(self, type: str, value: str, line: int = 0, col: int = 0):
        self.type = type
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self) -> str:
        return f"Token({self.type}, {self.value!r})"


def _strip_comments(text: str) -> str:
    result: list[str] = []
    i = 0
    in_string = False
    string_char = ""
    while i < len(text):
        if in_string:
            if text[i] == "\\" and i + 1 < len(text):
                result.append(text[i : i + 2])
                i += 2
                continue
            if text[i] == string_char:
                in_string = False
            result.append(text[i])
            i += 1
        elif text[i] == '"':
            in_string = True
            string_char = '"'
            result.append(text[i])
            i += 1
        elif text[i : i + 2] == "//":
            while i < len(text) and text[i] != "\n":
                i += 1
        elif text[i : i + 2] == "/*":
            i += 2
            while i < len(text) - 1:
                if text[i : i + 2] == "*/":
                    i += 2
                    break
                i += 1
            else:
                i = len(text)
        else:
            result.append(text[i])
            i += 1
    return "".join(result)


_KEYWORDS = {"digraph", "graph", "subgraph", "node", "edge", "strict"}
_ID_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")
_NUM_RE = re.compile(r"-?(?:\d+\.?\d*|\.\d+)")


def tokenize(text: str) -> list[Token]:
    text = _strip_comments(text)
    tokens: list[Token] = []
    i = 0
    line = 1
    col = 1

    while i < len(text):
        ch = text[i]

        if ch in (" ", "\t", "\r"):
            i += 1
            col += 1
            continue
        if ch == "\n":
            i += 1
            line += 1
            col = 1
            continue

        if ch == "{":
            tokens.append(Token(TokenType.LBRACE, "{", line, col))
            i += 1
            col += 1
        elif ch == "}":
            tokens.append(Token(TokenType.RBRACE, "}", line, col))
            i += 1
            col += 1
        elif ch == "[":
            tokens.append(Token(TokenType.LBRACKET, "[", line, col))
            i += 1
            col += 1
        elif ch == "]":
            tokens.append(Token(TokenType.RBRACKET, "]", line, col))
            i += 1
            col += 1
        elif ch == ";":
            tokens.append(Token(TokenType.SEMICOLON, ";", line, col))
            i += 1
            col += 1
        elif ch == ",":
            tokens.append(Token(TokenType.COMMA, ",", line, col))
            i += 1
            col += 1
        elif ch == "=":
            tokens.append(Token(TokenType.EQUALS, "=", line, col))
            i += 1
            col += 1
        elif text[i : i + 2] == "->":
            tokens.append(Token(TokenType.ARROW, "->", line, col))
            i += 2
            col += 2
        elif text[i : i + 2] == "--":
            raise ParseError("Undirected graphs (--) are not supported", line, col)
        elif ch == '"':
            start_line, start_col = line, col
            i += 1
            col += 1
            parts: list[str] = []
            while i < len(text) and text[i] != '"':
                if text[i] == "\\":
                    i += 1
                    col += 1
                    if i < len(text):
                        parts.append(text[i])
                else:
                    if text[i] == "\n":
                        line += 1
                        col = 0
                    parts.append(text[i])
                i += 1
                col += 1
            if i >= len(text):
                raise ParseError("Unterminated string", start_line, start_col)
            i += 1
            col += 1
            tokens.append(Token(TokenType.STRING, "".join(parts), start_line, start_col))
        else:
            m = _ID_RE.match(text, i)
            if m:
                word = m.group()
                tok_type = TokenType.ID
                wlower = word.lower()
                if wlower == "digraph":
                    tok_type = TokenType.DIGRAPH
                elif wlower == "graph":
                    tok_type = TokenType.GRAPH
                elif wlower == "subgraph":
                    tok_type = TokenType.SUBGRAPH
                elif wlower == "node":
                    tok_type = TokenType.NODE
                elif wlower == "edge":
                    tok_type = TokenType.EDGE
                elif wlower == "strict":
                    raise ParseError("'strict' modifier is not supported", line, col)
                tokens.append(Token(tok_type, word, line, col))
                i = m.end()
                col += len(word)
            else:
                m = _NUM_RE.match(text, i)
                if m:
                    tokens.append(Token(TokenType.ID, m.group(), line, col))
                    i = m.end()
                    col += len(m.group())
                else:
                    raise ParseError(f"Unexpected character: {ch!r}", line, col)

    tokens.append(Token(TokenType.EOF, "", line, col))
    return tokens


class Parser:
    def __init__(self, tokens: list[Token]):
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, type: str) -> Token:
        tok = self._advance()
        if tok.type != type:
            raise ParseError(
                f"Expected {type}, got {tok.type} ({tok.value!r})",
                tok.line,
                tok.col,
            )
        return tok

    def _match(self, type: str) -> Token | None:
        if self._peek().type == type:
            return self._advance()
        return None

    def parse(self) -> Graph:
        graphs: list[Graph] = []

        while self._peek().type != TokenType.EOF:
            if self._peek().type == TokenType.DIGRAPH:
                graphs.append(self._parse_digraph())
            else:
                raise ParseError(
                    f"Expected 'digraph', got {self._peek().value!r}",
                    self._peek().line,
                    self._peek().col,
                )

        if len(graphs) == 0:
            raise ParseError("Empty input: no digraph found")
        if len(graphs) > 1:
            raise ParseError("Multiple digraph blocks are not supported")

        return graphs[0]

    def _parse_digraph(self) -> Graph:
        self._expect(TokenType.DIGRAPH)
        if self._peek().type in (TokenType.ID, TokenType.STRING):
            self._advance()
        self._expect(TokenType.LBRACE)

        graph = Graph()
        self._node_defaults: dict[str, Any] = {}
        self._edge_defaults: dict[str, Any] = {}

        while self._peek().type != TokenType.RBRACE:
            self._parse_statement(graph)
            self._match(TokenType.SEMICOLON)

        self._expect(TokenType.RBRACE)
        return graph

    def _parse_statement(self, graph: Graph) -> None:
        tok = self._peek()

        if tok.type == TokenType.GRAPH:
            self._advance()
            attrs = self._parse_attrs()
            graph.attrs.update(attrs)
            return

        if tok.type == TokenType.NODE:
            self._advance()
            attrs = self._parse_attrs()
            self._node_defaults.update(attrs)
            return

        if tok.type == TokenType.EDGE:
            self._advance()
            attrs = self._parse_attrs()
            self._edge_defaults.update(attrs)
            return

        if tok.type == TokenType.SUBGRAPH:
            self._parse_subgraph(graph)
            return

        if tok.type in (TokenType.ID, TokenType.STRING):
            self._parse_node_or_edge(graph)
            return

        raise ParseError(f"Unexpected token: {tok.value!r}", tok.line, tok.col)

    def _parse_subgraph(self, graph: Graph) -> None:
        self._expect(TokenType.SUBGRAPH)
        sg_name = ""
        if self._peek().type in (TokenType.ID, TokenType.STRING):
            sg_name = self._advance().value
        self._expect(TokenType.LBRACE)

        local_defaults = dict(self._node_defaults)
        css_class: str | None = None

        if sg_name.startswith("cluster_"):
            css_class = sg_name[len("cluster_") :]

        while self._peek().type != TokenType.RBRACE:
            tok = self._peek()
            if tok.type == TokenType.NODE:
                self._advance()
                attrs = self._parse_attrs()
                local_defaults.update(attrs)
            elif tok.type in (TokenType.ID, TokenType.STRING):
                self._parse_node_or_edge(graph, extra_attrs=local_defaults, css_class=css_class)
            elif tok.type == TokenType.GRAPH:
                self._advance()
                attrs = self._parse_attrs()
                if "label" in attrs and not css_class:
                    css_class = attrs["label"]
            else:
                self._advance()
            self._match(TokenType.SEMICOLON)

        self._expect(TokenType.RBRACE)

    def _parse_node_or_edge(
        self,
        graph: Graph,
        extra_attrs: dict[str, Any] | None = None,
        css_class: str | None = None,
    ) -> None:
        node_ids: list[str] = []
        first_id = self._advance().value
        node_ids.append(first_id)

        while self._peek().type == TokenType.ARROW:
            self._advance()
            nxt = self._advance()
            if nxt.type not in (TokenType.ID, TokenType.STRING):
                raise ParseError(
                    f"Expected node ID after '->', got {nxt.type}",
                    nxt.line,
                    nxt.col,
                )
            node_ids.append(nxt.value)

        attrs = self._parse_attrs() if self._peek().type == TokenType.LBRACKET else {}

        if len(node_ids) == 1:
            merged = {**self._node_defaults}
            if extra_attrs:
                merged.update(extra_attrs)
            merged.update(attrs)
            coerced = {
                k: _coerce_value(str(v)) if isinstance(v, str) else v for k, v in merged.items()
            }
            node = Node(id=node_ids[0], attrs=coerced, css_class=css_class)
            graph.add_node(node)
        else:
            for nid in node_ids:
                if nid not in graph.nodes:
                    node_attrs = {**self._node_defaults}
                    if extra_attrs:
                        node_attrs.update(extra_attrs)
                    coerced = {
                        k: _coerce_value(str(v)) if isinstance(v, str) else v
                        for k, v in node_attrs.items()
                    }
                    graph.add_node(Node(id=nid, attrs=coerced, css_class=css_class))

            for i in range(len(node_ids) - 1):
                merged_edge = {**self._edge_defaults, **attrs}
                coerced = {
                    k: _coerce_value(str(v)) if isinstance(v, str) else v
                    for k, v in merged_edge.items()
                }
                graph.add_edge(Edge(source=node_ids[i], target=node_ids[i + 1], attrs=coerced))

    def _parse_attrs(self) -> dict[str, Any]:
        if self._peek().type != TokenType.LBRACKET:
            return {}
        self._advance()

        attrs: dict[str, Any] = {}
        while self._peek().type != TokenType.RBRACKET:
            key_tok = self._advance()
            if key_tok.type not in (TokenType.ID, TokenType.STRING):
                if key_tok.type == TokenType.COMMA:
                    continue
                if key_tok.type == TokenType.SEMICOLON:
                    continue
                raise ParseError(
                    f"Expected attribute name, got {key_tok.type}",
                    key_tok.line,
                    key_tok.col,
                )
            key = key_tok.value

            self._expect(TokenType.EQUALS)

            val_tok = self._advance()
            if val_tok.type == TokenType.STRING:
                attrs[key] = val_tok.value
            elif val_tok.type == TokenType.ID:
                attrs[key] = val_tok.value
            else:
                raise ParseError(
                    f"Expected attribute value, got {val_tok.type}",
                    val_tok.line,
                    val_tok.col,
                )

            if self._peek().type == TokenType.COMMA:
                self._advance()
            elif self._peek().type == TokenType.SEMICOLON:
                self._advance()

        self._expect(TokenType.RBRACKET)
        return attrs


def parse_dot(text: str) -> Graph:
    tokens = tokenize(text)
    parser = Parser(tokens)
    return parser.parse()
