"""
Project dependency detection and documentation import functionality.

This module provides functionality to detect project types, parse dependency files,
and import documentation for project dependencies.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, TypedDict, Union

import toml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from docvault.core.exceptions import LibraryNotFoundError, VersionNotFoundError
from docvault.core.library_manager import LibraryManager

console = Console()


class Dependency(TypedDict):
    """Represents a project dependency with name and version information."""

    name: str
    version: str
    source_file: str


class ProjectManager:
    """Manages project dependency detection and documentation import."""

    # Mapping of file patterns to their respective parsers
    FILE_PATTERNS = {
        # Python
        "requirements.txt": "parse_requirements_txt",
        "pyproject.toml": "parse_pyproject_toml",
        "setup.py": "parse_setup_py",
        "Pipfile": "parse_pipfile",
        "setup.cfg": "parse_setup_cfg",
        # Node.js
        "package.json": "parse_package_json",
        "yarn.lock": "parse_yarn_lock",
        "package-lock.json": "parse_package_lock_json",
        # Rust
        "Cargo.toml": "parse_cargo_toml",
        # Go
        "go.mod": "parse_go_mod",
        # Ruby
        "Gemfile": "parse_gemfile",
        "Gemfile.lock": "parse_gemfile_lock",
        # PHP
        "composer.json": "parse_composer_json",
        "composer.lock": "parse_composer_lock",
    }

    @classmethod
    def detect_project_type(cls, path: Union[str, Path]) -> str:
        """Detect the project type based on files in the directory."""
        path = Path(path)
        if not path.is_dir():
            raise ValueError(f"Directory not found: {path}")

        # Check for project files
        for file_pattern in cls.FILE_PATTERNS:
            if (path / file_pattern).exists():
                return cls._get_project_type_from_file(file_pattern)

        # If no specific project file is found, try to infer from directory contents
        if (path / "__init__.py").exists():
            return "python"
        if (path / "node_modules").exists():
            return "nodejs"

        return "unknown"

    @classmethod
    def _get_project_type_from_file(cls, filename: str) -> str:
        """Map a filename to a project type."""
        if filename in [
            "requirements.txt",
            "pyproject.toml",
            "setup.py",
            "Pipfile",
            "setup.cfg",
        ]:
            return "python"
        elif filename in ["package.json", "yarn.lock", "package-lock.json"]:
            return "nodejs"
        elif filename == "Cargo.toml":
            return "rust"
        elif filename == "go.mod":
            return "go"
        elif filename in ["Gemfile", "Gemfile.lock"]:
            return "ruby"
        elif filename in ["composer.json", "composer.lock"]:
            return "php"
        return "unknown"

    @classmethod
    def find_dependency_files(cls, path: Union[str, Path]) -> List[Path]:
        """Find all dependency files in the given directory."""
        path = Path(path)
        if not path.is_dir():
            raise ValueError(f"Directory not found: {path}")

        found_files = []
        for file_pattern in cls.FILE_PATTERNS:
            file_path = path / file_pattern
            if file_path.exists():
                found_files.append(file_path)

        return found_files

    @classmethod
    def parse_dependencies(cls, file_path: Union[str, Path]) -> List[Dependency]:
        """Parse dependencies from a project file."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        parser_name = cls.FILE_PATTERNS.get(file_path.name)
        if not parser_name:
            return []

        parser = getattr(cls, parser_name, None)
        if not parser:
            console.print(f"[yellow]Warning: No parser for {file_path}[/]")
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                deps = parser(cls, content)

            # Add source file information
            for dep in deps:
                dep["source_file"] = str(file_path)

            return deps
        except Exception as e:
            console.print(f"[red]Error parsing {file_path}: {e}[/]")
            return []

    # Parser methods for different file types

    def parse_requirements_txt(self, content: str) -> List[Dependency]:
        """Parse Python requirements.txt file."""
        deps = []
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Handle -r requirements.txt includes
            if line.startswith("-r "):
                # TODO: Handle includes
                continue

            # Remove version constraints and comments
            pkg = (
                line.split("==", 1)[0]
                .split(">", 1)[0]
                .split("<", 1)[0]
                .split("~", 1)[0]
                .strip()
            )
            if pkg:
                deps.append({"name": pkg, "version": ""})
        return deps

    def parse_pyproject_toml(self, content: str) -> List[Dependency]:
        """Parse Python pyproject.toml file."""
        try:
            data = toml.loads(content)
            deps = []

            # Check for [project.dependencies]
            if "project" in data and "dependencies" in data["project"]:
                for dep in data["project"]["dependencies"]:
                    pkg = (
                        dep.split(">", 1)[0]
                        .split("<", 1)[0]
                        .split("~", 1)[0]
                        .split("=")[0]
                        .strip()
                    )
                    if pkg:
                        deps.append({"name": pkg, "version": ""})

            # Check for [tool.poetry.dependencies]
            if (
                "tool" in data
                and "poetry" in data["tool"]
                and "dependencies" in data["tool"]["poetry"]
            ):
                for pkg, version in data["tool"]["poetry"]["dependencies"].items():
                    if pkg.lower() != "python":
                        ver = str(version) if isinstance(version, str) else ""
                        deps.append({"name": pkg, "version": ver})

            return deps
        except Exception as e:
            console.print(f"[red]Error parsing pyproject.toml: {e}")
            return []

    def parse_package_json(self, content: str) -> List[Dependency]:
        """Parse Node.js package.json file."""
        try:
            data = json.loads(content)
            deps = []

            for dep_type in ["dependencies", "devDependencies", "peerDependencies"]:
                if dep_type in data:
                    for pkg, version in data[dep_type].items():
                        ver = version.replace("^", "").replace("~", "").split(" ")[0]
                        deps.append({"name": pkg, "version": ver})

            return deps
        except Exception as e:
            console.print(f"[red]Error parsing package.json: {e}")
            return []

    # Add more parser methods for other file types as needed

    @classmethod
    def import_documentation(
        cls,
        path: Union[str, Path],
        project_type: Optional[str] = None,
        include_dev: bool = False,
        force: bool = False,
    ) -> Dict[str, List[Dict]]:
        """Import documentation for all dependencies in a project."""
        path = Path(path).resolve()
        if not path.exists():
            raise ValueError(f"Path not found: {path}")

        if path.is_file():
            # If a specific file is provided, just parse that file
            dep_files = [path]
            project_type = project_type or cls._get_project_type_from_file(path.name)
        else:
            # If a directory is provided, find all dependency files
            dep_files = cls.find_dependency_files(path)
            project_type = project_type or cls.detect_project_type(path)

        if not dep_files:
            console.print("[yellow]No dependency files found in the specified path.[/]")
            return {}

        console.print(f"[bold]Found {len(dep_files)} dependency files in {path}:[/]")
        for dep_file in dep_files:
            console.print(f"  - {dep_file.relative_to(path)}")

        # Parse all dependencies
        all_deps: List[Dependency] = []
        for dep_file in dep_files:
            deps = cls.parse_dependencies(dep_file)
            all_deps.extend(deps)

        if not all_deps:
            console.print("[yellow]No dependencies found in the project files.[/]")
            return {}

        # Remove duplicates (keep first occurrence)
        unique_deps = []
        seen = set()
        for dep in all_deps:
            if dep["name"].lower() not in seen:
                seen.add(dep["name"].lower())
                unique_deps.append(dep)

        console.print(f"\n[bold]Found {len(unique_deps)} unique dependencies:[/]")
        for dep in unique_deps:
            ver = f" ({dep['version']})" if dep["version"] else ""
            console.print(f"  - {dep['name']}{ver}")

        # Import documentation for each dependency
        results = {"success": [], "failed": [], "skipped": []}

        library_manager = LibraryManager()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task(
                "Importing documentation...", total=len(unique_deps)
            )

            for dep in unique_deps:
                progress.update(task, description=f"Importing {dep['name']}...")

                try:
                    # Check if documentation already exists
                    if not force and library_manager.documentation_exists(
                        dep["name"], dep["version"] or "latest"
                    ):
                        results["skipped"].append(
                            {
                                "name": dep["name"],
                                "version": dep["version"] or "latest",
                                "reason": "Documentation already exists",
                                "source": dep.get("source_file", "unknown"),
                            }
                        )
                        progress.advance(task)
                        continue

                    # Try to fetch documentation
                    docs = library_manager.get_library_docs(
                        dep["name"], dep["version"] or "latest"
                    )
                    if docs:
                        results["success"].append(
                            {
                                "name": dep["name"],
                                "version": dep["version"] or "latest",
                                "source": dep.get("source_file", "unknown"),
                            }
                        )
                    else:
                        results["failed"].append(
                            {
                                "name": dep["name"],
                                "version": dep["version"] or "latest",
                                "reason": "No documentation found",
                                "source": dep.get("source_file", "unknown"),
                            }
                        )

                except LibraryNotFoundError:
                    results["failed"].append(
                        {
                            "name": dep["name"],
                            "version": dep["version"] or "latest",
                            "reason": "Library not found",
                            "source": dep.get("source_file", "unknown"),
                        }
                    )
                except VersionNotFoundError:
                    results["failed"].append(
                        {
                            "name": dep["name"],
                            "version": dep["version"] or "latest",
                            "reason": "Version not found",
                            "source": dep.get("source_file", "unknown"),
                        }
                    )
                except Exception as e:
                    results["failed"].append(
                        {
                            "name": dep["name"],
                            "version": dep["version"] or "latest",
                            "reason": str(e),
                            "source": dep.get("source_file", "unknown"),
                        }
                    )

                progress.advance(task)

        return results
