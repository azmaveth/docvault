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
        """Parse Python requirements.txt file.

        Args:
            content: Contents of the requirements.txt file

        Returns:
            List of Dependency objects with name and version information

        Note:
            Handles various version specifiers: ==, >=, <=, >, <, ~=, !=
            Also handles comments and -r includes (recursively)
        """
        deps = []
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Handle -r requirements.txt includes
            if line.startswith("-r "):
                # TODO: Handle includes recursively
                continue

            # Remove any trailing comments
            line = line.split("#", 1)[0].strip()
            if not line:
                continue

            # Handle different version specifiers
            version = ""
            pkg = line

            # Handle == exact version
            if "==" in line:
                pkg, version = line.split("==", 1)
            # Handle >=, <=, >, <, ~=, !=
            elif ">=" in line:
                pkg, version = line.split(">=", 1)
                version = f">={version}"
            elif "<=" in line:
                pkg, version = line.split("<=", 1)
                version = f"<={version}"
            elif ">" in line and not line.startswith(">"):  # Handle > but not >>
                pkg, version = line.split(">", 1)
                version = f">{version}"
            elif "<" in line and not line.startswith("<"):  # Handle < but not <>
                pkg, version = line.split("<", 1)
                version = f"<{version}"
            elif "~=" in line:  # Compatible release (~=)
                pkg, version = line.split("~=", 1)
                version = f"~={version}"
            elif "!=" in line:  # Version exclusion (!=)
                pkg, version = line.split("!=", 1)
                version = f"!={version}"

            # Clean up package name (remove any whitespace and extras [ ])
            pkg = pkg.split("[", 1)[0].strip()

            if pkg:
                deps.append({"name": pkg, "version": version})
        return deps

    def parse_pyproject_toml(self, content: str) -> List[Dependency]:
        """Parse Python pyproject.toml file.

        Args:
            content: Contents of the pyproject.toml file

        Returns:
            List of Dependency objects with name and version information

        Note:
            Handles both PEP 621 (project.dependencies) and Poetry formats
            Supports version specifiers: ==, >=, <=, >, <, ~=, !=
        """
        try:
            data = toml.loads(content)
            deps = []

            def process_dependency_spec(spec: str) -> tuple[str, str]:
                """Process a dependency specification string into (name, version) tuple."""
                spec = spec.strip()
                if not spec:
                    return "", ""

                # Handle different version specifiers
                version = ""
                pkg = spec

                # Handle == exact version
                if "==" in spec:
                    pkg, version = spec.split("==", 1)
                # Handle >=, <=, >, <, ~=, !=
                elif ">=" in spec:
                    pkg, version = spec.split(">=", 1)
                    version = f">={version}"
                elif "<=" in spec:
                    pkg, version = spec.split("<=", 1)
                    version = f"<={version}"
                elif ">" in spec and not spec.startswith(">"):
                    pkg, version = spec.split(">", 1)
                    version = f">{version}"
                elif "<" in spec and not spec.startswith("<"):
                    pkg, version = spec.split("<", 1)
                    version = f"<{version}"
                elif "~=" in spec:  # Compatible release (~=)
                    pkg, version = spec.split("~=", 1)
                    version = f"~={version}"
                elif "!=" in spec:  # Version exclusion (!=)
                    pkg, version = spec.split("!=", 1)
                    version = f"!={version}"

                # Clean up package name (remove any whitespace and extras [ ])
                pkg = pkg.split("[", 1)[0].strip()

                return pkg, version.strip()

            # Check for PEP 621 [project.dependencies]
            if "project" in data and "dependencies" in data["project"]:
                for dep in data["project"]["dependencies"]:
                    pkg, version = process_dependency_spec(dep)
                    if pkg:
                        deps.append({"name": pkg, "version": version})

            # Check for [project.optional-dependencies]
            if "project" in data and "optional-dependencies" in data["project"]:
                for group_deps in data["project"]["optional-dependencies"].values():
                    for dep in group_deps:
                        pkg, version = process_dependency_spec(dep)
                        if pkg:
                            deps.append({"name": pkg, "version": version})

            # Check for Poetry [tool.poetry.dependencies]
            if (
                "tool" in data
                and "poetry" in data["tool"]
                and "dependencies" in data["tool"]["poetry"]
            ):
                for pkg, version_spec in data["tool"]["poetry"]["dependencies"].items():
                    if pkg.lower() == "python":
                        continue

                    if isinstance(version_spec, str):
                        pkg_clean, version = process_dependency_spec(
                            f"{pkg} {version_spec}"
                        )
                        if pkg_clean:
                            deps.append({"name": pkg_clean, "version": version})
                    elif isinstance(version_spec, dict) and "version" in version_spec:
                        deps.append({"name": pkg, "version": version_spec["version"]})
                    elif isinstance(version_spec, dict) and "git" in version_spec:
                        # Handle git dependencies
                        deps.append({"name": pkg, "version": ""})
                    else:
                        deps.append({"name": pkg, "version": ""})

            # Check for Poetry [tool.poetry.dev-dependencies]
            if (
                "tool" in data
                and "poetry" in data["tool"]
                and "dev-dependencies" in data["tool"]["poetry"]
            ):
                for pkg, version_spec in data["tool"]["poetry"][
                    "dev-dependencies"
                ].items():
                    if isinstance(version_spec, str):
                        pkg_clean, version = process_dependency_spec(
                            f"{pkg} {version_spec}"
                        )
                        if pkg_clean:
                            deps.append({"name": pkg_clean, "version": version})
                    else:
                        deps.append({"name": pkg, "version": ""})

            return deps

        except toml.TomlDecodeError as e:
            console.print(f"[red]Error parsing pyproject.toml: Invalid TOML - {e}")
            return []
        except Exception as e:
            console.print(f"[red]Error parsing pyproject.toml: {e}")
            return []

    def parse_package_json(self, content: str) -> List[Dependency]:
        """Parse Node.js package.json file.

        Args:
            content: Contents of the package.json file

        Returns:
            List of Dependency objects with name and version information

        Note:
            Handles npm version specifiers: ^, ~, >=, <=, >, <, =, x, *, ||
            Also handles git URLs and file paths
        """
        try:
            data = json.loads(content)
            deps = []

            # Define dependency types to process
            dep_types = [
                "dependencies",
                "devDependencies",
                "peerDependencies",
                "optionalDependencies",
            ]

            for dep_type in dep_types:
                if dep_type in data:
                    for pkg, version_spec in data[dep_type].items():
                        # Skip git URLs and file paths
                        if isinstance(version_spec, str) and (
                            version_spec.startswith(("git+", "git:", "git://"))
                            or version_spec.startswith(("http://", "https://"))
                            or version_spec.startswith(("file:", "link:"))
                            or "/" in version_spec
                            and not version_spec.startswith("@")
                        ):
                            deps.append({"name": pkg, "version": ""})
                            continue

                        # Handle version ranges and specifiers
                        version = str(version_spec).strip()

                        # Clean up common npm version specifiers
                        if (
                            version.startswith(("^", "~", ">", "<", "=", "x", "*"))
                            or "||" in version
                        ):
                            # Keep the version specifier as is for now
                            pass
                        elif version.startswith(("<=", ">=", ">", "<")):
                            # Keep comparison operators
                            pass
                        else:
                            # For exact versions or versions with other specifiers
                            version = version.split(" ")[0].strip()

                        deps.append({"name": pkg, "version": version})

            return deps

        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing package.json: Invalid JSON - {e}")
            return []
        except Exception as e:
            console.print(f"[red]Error parsing package.json: {e}")
            return []

    # Add more parser methods for other file types as needed

    @classmethod
    async def import_documentation(
        cls,
        path: Union[str, Path],
        project_type: Optional[str] = None,
        include_dev: bool = False,
        force: bool = False,
        skip_existing: Optional[bool] = None,
        verbose: int = 0,
    ) -> Dict[str, List[Dict]]:
        """Import documentation for all dependencies in a project.

        Args:
            path: Path to the project directory or specific dependency file
            project_type: Optional project type (python, nodejs, etc.)
            include_dev: Whether to include development dependencies
            force: Force re-import even if documentation exists

        Returns:
            Dictionary with 'success', 'failed', and 'skipped' lists
            containing information about the import results
        """
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
            return {"success": [], "failed": [], "skipped": []}

        console.print(f"[bold]Found {len(dep_files)} dependency files in {path}:[/]")
        for dep_file in dep_files:
            console.print(f"  - {dep_file.relative_to(path)}")

        # Parse all dependencies
        all_deps: List[Dependency] = []
        for dep_file in dep_files:
            try:
                deps = cls.parse_dependencies(dep_file)
                all_deps.extend(deps)
                console.print(
                    f"[green]Parsed {len(deps)} dependencies from {dep_file.name}[/]"
                )
            except Exception as e:
                console.print(f"[red]Error parsing {dep_file.name}: {e}")
                continue

        if not all_deps:
            console.print("[yellow]No dependencies found in the project files.[/]")
            return {"success": [], "failed": [], "skipped": []}

        # Remove duplicates (keep first occurrence with version if available)
        unique_deps = []
        seen = set()
        for dep in all_deps:
            dep_key = dep["name"].lower()
            if dep_key not in seen:
                seen.add(dep_key)
                unique_deps.append(dep)
            else:
                # If we already have this package but without a version, and this one has a version, update it
                existing = next(
                    (d for d in unique_deps if d["name"].lower() == dep_key), None
                )
                if existing and not existing.get("version") and dep.get("version"):
                    existing["version"] = dep["version"]

        console.print(f"\n[bold]Found {len(unique_deps)} unique dependencies:[/]")
        for dep in unique_deps:
            ver = f" ({dep['version']})" if dep.get("version") else " (latest)"
            source = f" from {dep.get('source_file', 'unknown')}"
            console.print(f"  - {dep['name']}{ver}{source}")

        # Import documentation for each dependency
        results = {"success": [], "failed": [], "skipped": []}
        library_manager = LibraryManager()

        for i, dep in enumerate(unique_deps):
            dep_name = dep["name"]
            version_spec = dep.get("version", "").strip()
            version_to_use = version_spec or "latest"
            source_file = dep.get("source_file", "unknown")

            # Print progress if verbose
            if verbose > 0:
                print(f"[{i+1}/{len(unique_deps)}] Importing {dep_name}...")

            try:
                # Skip empty package names
                if not dep_name.strip():
                    continue

                # Check if we should skip existing documentation
                if not force and (skip_existing is None or skip_existing):
                    doc_exists = library_manager.documentation_exists(
                        dep_name, version_to_use
                    )
                    if doc_exists:
                        results["skipped"].append(
                            {
                                "name": dep_name,
                                "version": version_to_use,
                                "reason": "Documentation already exists",
                                "source": source_file,
                            }
                        )
                        continue

                # Log version being used
                if version_spec:
                    console.print(
                        f"[cyan]Importing {dep_name} (version: {version_spec})...[/]"
                    )
                else:
                    console.print(f"[cyan]Importing {dep_name} (latest version)...[/]")

                # Try to fetch documentation
                try:
                    docs = await library_manager.get_library_docs(
                        dep_name, version_to_use
                    )

                    if docs:
                        results["success"].append(
                            {
                                "name": dep_name,
                                "version": version_to_use,
                                "source": source_file,
                            }
                        )
                        console.print(
                            f"[green]Successfully imported {dep_name} {version_to_use}[/]"
                        )
                    else:
                        error_msg = "No documentation found or could not be parsed"
                        results["failed"].append(
                            {
                                "name": dep_name,
                                "version": version_to_use,
                                "reason": error_msg,
                                "source": source_file,
                            }
                        )
                        console.print(
                            f"[yellow]{error_msg} for {dep_name} {version_to_use}[/]"
                        )

                except LibraryNotFoundError:
                    error_msg = f"Library '{dep_name}' not found"
                    results["failed"].append(
                        {
                            "name": dep_name,
                            "version": version_to_use,
                            "reason": error_msg,
                            "source": source_file,
                        }
                    )
                    console.print(f"[red]{error_msg}[/]")

                except VersionNotFoundError:
                    error_msg = f"Version '{version_to_use}' not found for {dep_name}"
                    results["failed"].append(
                        {
                            "name": dep_name,
                            "version": version_to_use,
                            "reason": error_msg,
                            "source": source_file,
                        }
                    )
                    console.print(f"[red]{error_msg}[/]")

                except Exception as e:
                    error_msg = str(e)
                    results["failed"].append(
                        {
                            "name": dep_name,
                            "version": version_to_use,
                            "reason": f"Error: {error_msg}",
                            "source": source_file,
                        }
                    )
                    console.print(f"[red]Error importing {dep_name}: {error_msg}[/]")

            except Exception as e:
                error_msg = str(e)
                results["failed"].append(
                    {
                        "name": dep_name,
                        "version": version_to_use,
                        "reason": f"Unexpected error: {error_msg}",
                        "source": source_file,
                    }
                )
                console.print(f"[red]Unexpected error with {dep_name}: {error_msg}[/]")

        # Print summary
        console.print("\n[bold]Import Summary:[/]")
        console.print(f"  [green]Successfully imported: {len(results['success'])}[/]")
        console.print(
            f"  [yellow]Skipped (already exists): {len(results['skipped'])}[/]"
        )
        console.print(f"  [red]Failed to import: {len(results['failed'])}[/]")

        if results["failed"]:
            console.print("\n[bold]Failed Imports:[/]")
            for fail in results["failed"][
                :5
            ]:  # Show first 5 failures to avoid flooding
                console.print(
                    f"  [red]{fail['name']} {fail['version']}: {fail['reason']}[/]"
                )
            if len(results["failed"]) > 5:
                console.print(f"  ... and {len(results['failed']) - 5} more")

        return results
