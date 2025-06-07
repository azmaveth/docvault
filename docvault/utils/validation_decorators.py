"""Decorators for automatic input validation in CLI commands."""

import functools
from collections.abc import Callable

import click

from docvault.utils.validators import ValidationError, Validators


def validate_inputs(**validators: dict[str, Callable]) -> Callable:
    """Decorator to validate function inputs automatically.

    Usage:
        @validate_inputs(
            query=Validators.validate_search_query,
            doc_id=Validators.validate_document_id
        )
        def search_cmd(query, doc_id):
            ...

    Args:
        **validators: Mapping of parameter names to validator functions

    Returns:
        Decorated function that validates inputs before execution
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get bound arguments
            import inspect

            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            # Validate each specified parameter
            for param_name, validator in validators.items():
                if param_name in bound.arguments:
                    value = bound.arguments[param_name]
                    if value is not None:  # Skip None values
                        try:
                            bound.arguments[param_name] = validator(value)
                        except ValidationError as e:
                            # Convert to Click exception for nice error display
                            raise click.ClickException(str(e))

            # Call original function with validated arguments
            return func(*bound.args, **bound.kwargs)

        return wrapper

    return decorator


def validate_doc_id(func: Callable) -> Callable:
    """Decorator to validate document ID parameter.

    Assumes the parameter is named 'document_id' or 'doc_id'.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        import inspect

        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()

        # Check for common document ID parameter names
        for param_name in ["document_id", "doc_id"]:
            if param_name in bound.arguments:
                value = bound.arguments[param_name]
                if value is not None:
                    try:
                        bound.arguments[param_name] = Validators.validate_document_id(
                            value
                        )
                    except ValidationError as e:
                        raise click.ClickException(f"Invalid document ID: {e}")
                break

        return func(*bound.args, **bound.kwargs)

    return wrapper


def validate_search_query(func: Callable) -> Callable:
    """Decorator to validate search query parameter.

    Assumes the parameter is named 'query'.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        import inspect

        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()

        if "query" in bound.arguments and bound.arguments["query"]:
            try:
                bound.arguments["query"] = Validators.validate_search_query(
                    bound.arguments["query"]
                )
            except ValidationError as e:
                raise click.ClickException(f"Invalid search query: {e}")

        return func(*bound.args, **bound.kwargs)

    return wrapper


def validate_tags(func: Callable) -> Callable:
    """Decorator to validate tags parameter.

    Assumes the parameter is named 'tags'.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        import inspect

        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()

        if "tags" in bound.arguments and bound.arguments["tags"]:
            tags = bound.arguments["tags"]
            if isinstance(tags, tuple):
                tags = list(tags)

            try:
                validated_tags = []
                for tag in tags:
                    validated_tags.append(Validators.validate_tag(tag))
                bound.arguments["tags"] = validated_tags
            except ValidationError as e:
                raise click.ClickException(f"Invalid tag: {e}")

        return func(*bound.args, **bound.kwargs)

    return wrapper


def validate_file_path(func: Callable) -> Callable:
    """Decorator to validate file path parameters.

    Looks for parameters named 'path', 'file_path', 'file', etc.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        import inspect

        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()

        # Check for common file path parameter names
        path_params = ["path", "file_path", "file", "filename", "archive_path"]

        for param_name in path_params:
            if param_name in bound.arguments:
                value = bound.arguments[param_name]
                if value is not None:
                    try:
                        bound.arguments[param_name] = str(
                            Validators.validate_file_path(value)
                        )
                    except ValidationError as e:
                        raise click.ClickException(f"Invalid file path: {e}")

        return func(*bound.args, **bound.kwargs)

    return wrapper


def validate_url(func: Callable) -> Callable:
    """Decorator to validate URL parameters.

    Assumes the parameter is named 'url'.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        import inspect

        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()

        if "url" in bound.arguments and bound.arguments["url"]:
            try:
                bound.arguments["url"] = Validators.validate_url(bound.arguments["url"])
            except ValidationError as e:
                raise click.ClickException(f"Invalid URL: {e}")

        return func(*bound.args, **bound.kwargs)

    return wrapper


def safe_display(text: str, max_length: int = 100) -> str:
    """Safely format text for display in CLI output.

    Args:
        text: Text to display
        max_length: Maximum length before truncation

    Returns:
        Sanitized and possibly truncated text
    """
    return Validators.sanitize_for_display(text, max_length)
