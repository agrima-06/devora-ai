"""Unit tests for CodeParserService (Python AST + Tree-sitter)."""
import tempfile
from pathlib import Path
import pytest
from app.services.parser_service import CodeParserService


def test_parser_python_ast():
    code = '''"""Module docstring."""
import os
from datetime import datetime

class UserService:
    """Service handling user accounts."""

    def __init__(self, db):
        self.db = db

    def get_user(self, user_id: str) -> dict:
        """Fetch user by ID."""
        return self.db.find(user_id)

def calculate_metric(a: int, b: int) -> int:
    """Calculate sum."""
    return a + b
'''
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "service.py"
        file_path.write_text(code)

        parser = CodeParserService()
        res = parser.parse_file(file_path, "service.py", "Python")

        assert "UserService" in res["summary"]
        assert "os" in res["imports"]
        assert any("datetime" in imp for imp in res["imports"])

        symbols = {s["name"]: s for s in res["symbols"]}
        assert "UserService" in symbols
        assert symbols["UserService"]["type"] == "class"
        assert "Service handling user accounts." in symbols["UserService"]["docstring"]

        assert any("get_user" in name for name in symbols)
        method_sym = next(s for name, s in symbols.items() if "get_user" in name)
        assert method_sym["type"] == "method"
        assert method_sym["start_line"] > symbols["UserService"]["start_line"]

        assert "calculate_metric" in symbols
        assert symbols["calculate_metric"]["type"] == "function"
        assert "calculate_metric" in symbols["calculate_metric"]["signature"]


def test_parser_typescript_tree_sitter():
    code = '''import React from 'react';

export interface UserProps {
    id: string;
    name: string;
}

export class UserCard {
    constructor(private props: UserProps) {}

    renderDetails() {
        return this.props.name;
    }
}

export function formatUserName(user: UserProps): string {
    return user.name.toUpperCase();
}
'''
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "card.ts"
        file_path.write_text(code)

        parser = CodeParserService()
        res = parser.parse_file(file_path, "card.ts", "TypeScript")

        names = [s["name"] for s in res["symbols"]]
        assert "UserCard" in names or "formatUserName" in names


def test_parser_go_tree_sitter():
    code = '''package main

import "fmt"

type Server struct {
    port int
}

func (s *Server) Start() error {
    fmt.Println("Server starting")
    return nil
}

func Add(a int, b int) int {
    return a + b
}
'''
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "main.go"
        file_path.write_text(code)

        parser = CodeParserService()
        res = parser.parse_file(file_path, "main.go", "Go")

        names = [s["name"] for s in res["symbols"]]
        assert "Add" in names or "Start" in names or "Server" in names


def test_parser_handles_syntax_errors_gracefully():
    corrupted_code = "def invalid_syntax( broken {"
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "broken.py"
        file_path.write_text(corrupted_code)

        parser = CodeParserService()
        res = parser.parse_file(file_path, "broken.py", "Python")

        # Must not crash, should return empty or partial structure
        assert isinstance(res["symbols"], list)
        assert res["rel_path"] == "broken.py"
