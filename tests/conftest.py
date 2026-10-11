import pytest

from app import create_app


@pytest.fixture
def content(tmp_path):
    root = tmp_path / "content"
    root.mkdir()

    def write(collection, slug, text):
        directory = root / collection / slug
        directory.mkdir(parents=True)
        (directory / "entry.toml").write_text(text, encoding="utf-8")
        return directory

    write.root = root
    return write


@pytest.fixture
def app(content):
    return create_app({"TESTING": True, "CONTENT_DIR": content.root})


@pytest.fixture
def client(app):
    return app.test_client()
