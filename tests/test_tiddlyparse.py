import re
import shutil
from pathlib import Path

from pytest import fixture
from tiddlyparse import __version__, parse
from tiddlyparse.parser import FileFormat

FIXTURES = Path(__file__).parent / "fixtures"


@fixture
def div_file_name():
    yield FIXTURES / "empty-5.1.23.html"


@fixture
def div_wiki(div_file_name):
    wiki = parse(file=div_file_name)
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


def test_div_tiddler_search_by_set_value(div_wiki):
    tiddlers = div_wiki.search(author=True)
    assert len(tiddlers) == 3
    assert tiddlers[0].title == "$:/core"
    assert tiddlers[1].title == "$:/themes/tiddlywiki/snowwhite"
    assert tiddlers[2].title == "$:/themes/tiddlywiki/vanilla"


def test_div_write(div_file_name, tmp_path):
    fixture_name = tmp_path / "wiki.html"
    shutil.copy(div_file_name, fixture_name)

    wiki = parse(fixture_name)
    tiddler = wiki.get_or_create("my_new_tiddler")
    tiddler.text = "This is a test for a new tiddler."
    wiki.add(tiddler)
    wiki.save()

    wiki2 = parse(fixture_name)
    tiddler2 = wiki2["my_new_tiddler"]
    assert tiddler2.text == "This is a test for a new tiddler."


def test_div_write_no_modification(div_file_name, tmp_path):
    fixture_name = tmp_path / "wiki.html"
    shutil.copy(div_file_name, fixture_name)

    wiki = parse(fixture_name)
    wiki.save()

    orig_content = div_file_name.open().read()
    new_content = fixture_name.open().read()

    # I have not figured out how to correctly retain the double-newlines in
    # some cases, especially at the end of the storeArea. So compare after
    # normalising all double-newlines.
    orig_content = re.sub("\n+", "\n", orig_content)
    new_content = re.sub("\n+", "\n", new_content)

    assert orig_content == new_content


def test_div_noop_modification_write_no_modification(div_file_name, tmp_path):
    """Ensure that adding a Tiddler without modifications doesn't change the file."""
    fixture_name = Path("/tmp/wiki") / "wiki.html"
    shutil.copy(div_file_name, fixture_name)

    wiki = parse(fixture_name)
    tiddler = wiki["$:/isEncrypted"]
    wiki.add(tiddler)
    wiki.save()

    orig_content = div_file_name.open().read()
    new_content = fixture_name.open().read()

    # I have not figured out how to correctly retain the double-newlines in
    # some cases, especially at the end of the storeArea. So compare after
    # normalising all double-newlines.
    orig_content = re.sub("\n+", "\n", orig_content)
    new_content = re.sub("\n+", "\n", new_content)

    assert orig_content == new_content


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


def test_json_tiddler_search_by_set_value(json_wiki):
    tiddlers = json_wiki.search(author=True)
    assert len(tiddlers) == 3
    assert tiddlers[0].title == "$:/core"
    assert tiddlers[1].title == "$:/themes/tiddlywiki/snowwhite"
    assert tiddlers[2].title == "$:/themes/tiddlywiki/vanilla"


def test_json_tiddler_search_by_specific_value(json_wiki):
    tiddlers = json_wiki.search(name="Snow White")
    assert len(tiddlers) == 1
    assert tiddlers[0].title == "$:/themes/tiddlywiki/snowwhite"


def test_json_tiddler_search_by_multiple_values_matching(json_wiki):
    tiddlers = json_wiki.search(name="Snow White", author=True)
    assert len(tiddlers) == 1
    assert tiddlers[0].title == "$:/themes/tiddlywiki/snowwhite"


def test_json_tiddler_search_by_multiple_values_not_matching(json_wiki):
    tiddlers = json_wiki.search(name="Snow White", author="Anonymous")
    assert len(tiddlers) == 0


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


def test_json_write_no_modification(json_file_name, tmp_path):
    fixture_name = tmp_path / "wiki.html"
    shutil.copy(json_file_name, fixture_name)

    wiki = parse(fixture_name)
    wiki.save()

    orig_content = json_file_name.open().read()
    new_content = fixture_name.open().read()
    assert orig_content == new_content
