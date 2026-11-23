"""Unit tests for MonorepoDetector across JS/TS, Rust, JVM, Go, and Python ecosystems."""

import json
import tempfile
from pathlib import Path
import pytest
import yaml

from app.services.workspace_service import MonorepoDetector


@pytest.fixture
def detector():
    return MonorepoDetector()


def test_detect_npm_turborepo_workspace(detector, tmp_path):
    """Verify detection of Turborepo / NPM workspaces with internal cross-package dependencies."""
    # Root package.json
    root_pkg = {
        "name": "devora-monorepo",
        "workspaces": ["packages/*", "apps/*"],
    }
    (tmp_path / "package.json").write_text(json.dumps(root_pkg), encoding="utf-8")
    (tmp_path / "turbo.json").write_text("{}", encoding="utf-8")

    # Package 1: packages/core
    core_dir = tmp_path / "packages" / "core"
    core_dir.mkdir(parents=True)
    core_pkg = {
        "name": "@devora/core",
        "version": "1.0.0",
        "dependencies": {"lodash": "^4.17.21"},
    }
    (core_dir / "package.json").write_text(json.dumps(core_pkg), encoding="utf-8")
    (core_dir / "index.ts").write_text("export const version = '1.0.0';", encoding="utf-8")
    (core_dir / "tsconfig.json").write_text("{}", encoding="utf-8")

    # Package 2: apps/web (depends on @devora/core)
    web_dir = tmp_path / "apps" / "web"
    web_dir.mkdir(parents=True)
    web_pkg = {
        "name": "@devora/web",
        "version": "1.0.0",
        "dependencies": {
            "@devora/core": "*",
            "react": "^18.2.0",
        },
    }
    (web_dir / "package.json").write_text(json.dumps(web_pkg), encoding="utf-8")
    (web_dir / "page.tsx").write_text("import { version } from '@devora/core';", encoding="utf-8")

    workspaces = detector.detect(tmp_path)
    assert len(workspaces) == 1
    ws = workspaces[0]
    assert ws.workspace_type == "turborepo"
    assert ws.packages_count == 2

    pkg_map = {p.name: p for p in ws.packages}
    assert "@devora/core" in pkg_map
    assert "@devora/web" in pkg_map

    core = pkg_map["@devora/core"]
    assert core.language == "typescript"
    assert core.internal_dependencies == []
    assert "lodash" in core.external_dependencies
    assert core.files_count >= 2

    web = pkg_map["@devora/web"]
    assert "@devora/core" in web.internal_dependencies
    assert "react" in web.external_dependencies


def test_detect_pnpm_workspace(detector, tmp_path):
    """Verify detection of pnpm workspaces using pnpm-workspace.yaml."""
    pnpm_yaml = {
        "packages": ["crates/*", "services/*"],
    }
    (tmp_path / "pnpm-workspace.yaml").write_text(yaml.dump(pnpm_yaml), encoding="utf-8")

    svc_dir = tmp_path / "services" / "auth"
    svc_dir.mkdir(parents=True)
    (svc_dir / "package.json").write_text(json.dumps({"name": "auth-service"}), encoding="utf-8")

    workspaces = detector.detect(tmp_path)
    assert len(workspaces) == 1
    assert workspaces[0].workspace_type == "pnpm"
    assert workspaces[0].packages_count == 1
    assert workspaces[0].packages[0].name == "auth-service"


def test_detect_cargo_workspace(detector, tmp_path):
    """Verify detection of Rust Cargo workspaces."""
    root_cargo = """[workspace]
members = [
    "crates/engine",
    "crates/cli",
]
"""
    (tmp_path / "Cargo.toml").write_text(root_cargo, encoding="utf-8")

    engine_dir = tmp_path / "crates" / "engine"
    engine_dir.mkdir(parents=True)
    engine_cargo = """[package]
name = "devora-engine"
version = "0.2.0"
edition = "2021"

[dependencies]
serde = "1.0"
"""
    (engine_dir / "Cargo.toml").write_text(engine_cargo, encoding="utf-8")

    cli_dir = tmp_path / "crates" / "cli"
    cli_dir.mkdir(parents=True)
    cli_cargo = """[package]
name = "devora-cli"
version = "0.2.0"
edition = "2021"

[dependencies]
devora-engine = { path = "../engine" }
clap = "4.0"
"""
    (cli_dir / "Cargo.toml").write_text(cli_cargo, encoding="utf-8")

    workspaces = detector.detect(tmp_path)
    assert len(workspaces) == 1
    ws = workspaces[0]
    assert ws.workspace_type == "cargo"
    assert ws.packages_count == 2

    pkgs = {p.name: p for p in ws.packages}
    assert "devora-engine" in pkgs
    assert "devora-cli" in pkgs
    assert "devora-engine" in pkgs["devora-cli"].internal_dependencies
    assert "clap" in pkgs["devora-cli"].external_dependencies


def test_detect_maven_multi_module(detector, tmp_path):
    """Verify detection of Maven multi-module projects."""
    root_pom = """<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.devora</groupId>
    <artifactId>parent</artifactId>
    <version>1.0.0</version>
    <packaging>pom</packaging>
    <modules>
        <module>common</module>
        <module>service</module>
    </modules>
</project>"""
    (tmp_path / "pom.xml").write_text(root_pom, encoding="utf-8")

    common_dir = tmp_path / "common"
    common_dir.mkdir()
    (common_dir / "pom.xml").write_text("""<project>
    <artifactId>common-lib</artifactId>
    <version>1.0.0</version>
</project>""", encoding="utf-8")

    service_dir = tmp_path / "service"
    service_dir.mkdir()
    (service_dir / "pom.xml").write_text("""<project>
    <artifactId>backend-service</artifactId>
    <version>1.0.0</version>
    <dependencies>
        <dependency>
            <artifactId>common-lib</artifactId>
        </dependency>
    </dependencies>
</project>""", encoding="utf-8")

    workspaces = detector.detect(tmp_path)
    assert len(workspaces) == 1
    ws = workspaces[0]
    assert ws.workspace_type == "maven"
    assert ws.packages_count == 2

    pkgs = {p.name: p for p in ws.packages}
    assert "common-lib" in pkgs
    assert "backend-service" in pkgs
    assert "common-lib" in pkgs["backend-service"].internal_dependencies


def test_detect_go_workspaces(detector, tmp_path):
    """Verify detection of Go go.work workspaces."""
    go_work_content = """go 1.22

use (
    ./shared
    ./server
)
"""
    (tmp_path / "go.work").write_text(go_work_content, encoding="utf-8")

    shared_dir = tmp_path / "shared"
    shared_dir.mkdir()
    (shared_dir / "go.mod").write_text("module github.com/devora/shared\n\ngo 1.22\n", encoding="utf-8")

    server_dir = tmp_path / "server"
    server_dir.mkdir()
    (server_dir / "go.mod").write_text("""module github.com/devora/server

go 1.22

require github.com/devora/shared v0.0.0
""", encoding="utf-8")

    workspaces = detector.detect(tmp_path)
    assert len(workspaces) == 1
    ws = workspaces[0]
    assert ws.workspace_type == "go_work"
    assert ws.packages_count == 2

    pkgs = {p.name: p for p in ws.packages}
    assert "github.com/devora/shared" in pkgs
    assert "github.com/devora/server" in pkgs
    assert "github.com/devora/shared" in pkgs["github.com/devora/server"].internal_dependencies


def test_detect_python_uv_workspace(detector, tmp_path):
    """Verify detection of Python UV / pyproject workspaces."""
    root_pyproject = """[project]
name = "devora-py"
version = "0.1.0"

[tool.uv.workspace]
members = ["libs/*"]
"""
    (tmp_path / "pyproject.toml").write_text(root_pyproject, encoding="utf-8")

    lib_dir = tmp_path / "libs" / "utils"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text("""[project]
name = "devora-utils"
version = "0.1.0"
dependencies = ["pydantic>=2.0"]
""", encoding="utf-8")

    workspaces = detector.detect(tmp_path)
    assert len(workspaces) == 1
    ws = workspaces[0]
    assert ws.workspace_type == "uv"
    assert ws.packages_count == 1
    assert ws.packages[0].name == "devora-utils"
    assert "pydantic" in ws.packages[0].external_dependencies
