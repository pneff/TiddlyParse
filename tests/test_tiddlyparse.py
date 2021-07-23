import shutil
from pathlib import Path

from pytest import fixture
from tiddlyparse import __version__, parse
from tiddlyparse.parser import FileFormat

FIXTURES = Path(__file__).parent / "fixtures"


@fixture
def div_wiki():
    fixture_name = FIXTURES / "empty-5.1.23.html"
    wiki = parse(file=fixture_name)
    yield wiki


@fixture
def json_file_name():
    yield FIXTURES / "empty-5.2.0.html"


@fixture
def json_wiki(json_file_name):
    yield parse(file=json_file_name)


def test_version():
    assert __version__ == "0.1.0"


def test_parse_div_format(div_wiki):
    assert div_wiki.fileformat == FileFormat.DIV


def test_parse_div_length(div_wiki):
    assert len(div_wiki) == 4


def test_div_tiddler_by_title(div_wiki):
    tiddler = div_wiki["$:/isEncrypted"]
    assert tiddler.title == "$:/isEncrypted"
    assert tiddler.text == "no"


def test_parse_json_format(json_wiki):
    assert json_wiki.fileformat == FileFormat.JSON


def test_parse_json_length(json_wiki):
    assert len(json_wiki) == 7


def test_json_tiddler_by_title(json_wiki):
    tiddler = json_wiki["$:/isEncrypted"]
    assert tiddler.title == "$:/isEncrypted"
    assert tiddler.text == "no"


def test_json_get_tiddler_by_title(json_wiki):
    tiddler = json_wiki.get("$:/isEncrypted")
    assert tiddler.title == "$:/isEncrypted"


def test_json_get_new_tiddler_by_title(json_wiki):
    tiddler = json_wiki.get_or_create("new_tiddler")
    assert tiddler.title == "new_tiddler"


def test_json_write(json_file_name, tmp_path):
    fixture_name = tmp_path / "wiki.html"
    shutil.copy(json_file_name, fixture_name)

    wiki = parse(fixture_name)
    tiddler = wiki.get_or_create("my_new_tiddler")
    tiddler.text = "This is a test for a new tiddler."
    wiki.add(tiddler)
    wiki.save()

    wiki2 = parse(fixture_name)
    tiddler2 = wiki2["my_new_tiddler"]
    assert tiddler2.text == "This is a test for a new tiddler."
