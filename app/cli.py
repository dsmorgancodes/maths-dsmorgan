from pathlib import Path

import click
from flask import current_app
from flask.cli import with_appcontext

from app.catalog import METADATA_FILE, CatalogError, read_entry


@click.command("check-content")
@with_appcontext
def check_content():
    """Validate every entry.toml in content/, including drafts."""
    content_dir = Path(current_app.config["SOURCE_DIR"])
    errors = []
    counts = {"published": 0, "draft": 0}
    for metadata in sorted(content_dir.glob(f"*/*/{METADATA_FILE}")):
        try:
            entry = read_entry(metadata.parent)
        except CatalogError as error:
            errors.append(str(error))
            continue
        counts["published" if entry.published else "draft"] += 1

    for error in errors:
        click.echo(f"error: {error}", err=True)
    if errors:
        raise SystemExit(1)
    click.echo(f"{counts['published']} published, {counts['draft']} drafts.")
