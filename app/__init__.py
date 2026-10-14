from pathlib import Path

from flask import Flask, render_template

from app.cli import check_content
from app.pages import pages


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SITE_URL="https://maths.dsmorgan.com",
        MAIN_SITE_URL="https://dsmorgan.com",
        CONTENT_DIR=Path(app.root_path).parent / "content",
        # Local preview only: list and serve unpublished entries too.
        SHOW_DRAFTS=False,
    )
    app.config.from_prefixed_env()
    if test_config is not None:
        app.config.update(test_config)
    app.config["CONTENT_DIR"] = Path(app.config["CONTENT_DIR"]).resolve()

    app.register_blueprint(pages)
    app.cli.add_command(check_content)

    @app.errorhandler(404)
    def not_found(error):
        return render_template("404.html"), 404

    return app
