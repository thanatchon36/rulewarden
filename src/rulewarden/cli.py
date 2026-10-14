"""Command-line entry point."""

import click

from rulewarden import __version__


@click.group()
@click.version_option(__version__, prog_name="rulewarden")
def main() -> None:
    """Deterministic runtime assurance for AI coding agents."""
