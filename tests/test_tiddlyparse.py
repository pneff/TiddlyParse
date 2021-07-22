from pathlib import Path

from tiddlyparse import __version__, parse
from tiddlyparse.parser import FileFormat

FIXTURES = Path(__file__).parent / "fixtures"


def test_version():
    assert __version__ == "0.1.0"


def test_parse_div_format():
    fixture_name = FIXTURES / "empty-5.1.23.html"
    wiki = parse(file=fixture_name)
    assert wiki.fileformat == FileFormat.DIV
    # assert len(wiki) == 2103


def test_parse_json_format():
    fixture_name = FIXTURES / "empty-5.2.0.html"
    wiki = parse(file=fixture_name)
    assert wiki.fileformat == FileFormat.JSON
    # assert len(wiki) == 2130
