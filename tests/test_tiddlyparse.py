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
def json_wiki():
    fixture_name = FIXTURES / "empty-5.2.0.html"
    wiki = parse(file=fixture_name)
    yield wiki


def test_version():
    assert __version__ == "0.1.0"


def test_parse_div_format(div_wiki):
    assert div_wiki.fileformat == FileFormat.DIV


def test_parse_div_length(div_wiki):
    assert len(div_wiki) == 4


def test_parse_json_format(json_wiki):
    assert json_wiki.fileformat == FileFormat.JSON


def test_parse_json_length(json_wiki):
    assert len(json_wiki) == 7
