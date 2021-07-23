import json
import tempfile
from abc import ABC, abstractmethod
from enum import Enum
from json.decoder import JSONDecodeError
from pathlib import Path
from typing import Mapping, MutableMapping, Optional, Sequence, Union

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag


class FileFormat(Enum):
    # Format for 5.1.23 and earlier
    DIV = 1
    # Format from 5.2.0
    JSON = 2


class UnknownTiddlywikiFormatError(ValueError):
    pass


class TiddlerNotFoundError(KeyError):
    pass


class Tiddler:
    _properties: MutableMapping[str, str]

    def __getattr__(self, key: str) -> str:
        if key in self._properties:
            return self._properties[key]
        elif key in self.stored_values:
            return self.stored_values[key]
        else:
            return ""

    def __setattr__(self, key: str, value: str) -> None:
        if key.startswith("_"):
            object.__setattr__(self, key, value)
        else:
            self._properties[key] = value

    @property
    @abstractmethod
    def stored_values(self) -> Mapping[str, str]:
        """Return the original values present in the document.

        Overwritten values are not reflected here. To get the current value,
        use the properties instead.
        """
        pass

    def to_dict(self) -> Mapping[str, str]:
        ret = {}
        # Loop first over the stored values, then over the manually defined
        # ones. This ensures we retain the order of keys where possible.
        for key, value in self.stored_values.items():
            if key in self._properties:
                ret[key] = self._properties[key]
            else:
                ret[key] = value
        for key, value in self._properties.items():
            if key not in ret:
                ret[key] = value
        return ret


class DivTiddler(Tiddler):
    _el: Optional[Tag]

    _stored_values: Optional[Mapping[str, str]]

    def __init__(self, el: Optional[Tag] = None, title: Optional[str] = None):
        self._properties = {}
        self._stored_values = None

        if el:
            title_ = el["title"]
            if not isinstance(title_, str):
                raise UnknownTiddlywikiFormatError(
                    f"Got invalid title value for tiddler: {title!r}"
                )
            self._title = title_
            self._el = el
        elif title:
            self.title = title
            self._properties["title"] = title
            self._el = None
        else:
            raise ValueError("Need el or title")

    @property
    def stored_values(self) -> Mapping[str, str]:
        if self._stored_values is not None:
            return self._stored_values

        values = {"text": ""}
        if self._el:
            tag = self._el("pre")[0]
            if not isinstance(tag, Tag):
                raise UnknownTiddlywikiFormatError(
                    f"Could not find text for tiddler {self.title!r}"
                )
            values["text"] = tag.string or ""
            values["title"] = self._title
        self._stored_values = values
        return values


class JsonTiddler(Tiddler):
    _tiddler: Optional[Mapping[str, str]]

    def __init__(
        self, tiddler: Optional[Mapping[str, str]] = None, title: Optional[str] = None
    ):
        self._properties = {}

        if tiddler:
            assert title is None or tiddler["title"] == title
            self._tiddler = tiddler
        elif title:
            self.title = title
            self._tiddler = None
        else:
            raise ValueError("Need el or title")

    @property
    def stored_values(self) -> Mapping[str, str]:
        return self._tiddler or {}


class TiddlyParser(ABC):
    filename: Path
    fileformat: FileFormat

    _tiddlers: Sequence[Tiddler]
    _soup: BeautifulSoup
    _root: Tag

    @classmethod
    @abstractmethod
    def is_format(cls, file: Path, soup: BeautifulSoup) -> bool:
        pass

    def add(self, tiddler: Tiddler) -> None:
        tiddlers = [t for t in self._tiddlers if t.title != tiddler.title]
        tiddlers.append(tiddler)
        self._tiddlers = tiddlers
        print("add", tiddler.to_dict(), tiddler.__dict__)

    @abstractmethod
    def save(self) -> None:
        pass

    def dump_to_file(self) -> None:
        """Dump the file back out.

        This is slightly complex purely because we want to retain as much
        formatting and whitespace as possible. So any markup except the root
        tag and its content is copied verbatim.

        To know where we need to stop/restart the copying, we use the
        `sourceline` and `sourcepos` properties of the root tag.
        """
        root = self._root
        root_next = self._root.next_sibling
        if not isinstance(root, Tag):
            raise UnknownTiddlywikiFormatError("Expected root to be a tag.")
        if not isinstance(root_next, Tag):
            print("root", repr(root)[0:200])
            print("next", repr(root_next)[0:200])
            raise UnknownTiddlywikiFormatError("Expected next element to be a tag.")

        copy_until_line = root.sourceline
        copy_until_pos = root.sourcepos or 0
        copy_from_line = root_next.sourceline
        copy_from_pos = root_next.sourcepos or 0
        if not copy_until_line or not copy_from_line:
            raise UnknownTiddlywikiFormatError(
                "Could not find source lines of root tags."
            )

        with tempfile.TemporaryDirectory() as tmpd:
            tmpf = Path(tmpd) / "new.html"

            with self.filename.open() as origf, tmpf.open("w") as outf:
                for idx, line in enumerate(origf):
                    output = None
                    if idx + 1 < copy_until_line:
                        output = line
                    elif idx + 1 == copy_until_line:
                        output = line[:copy_until_pos]
                        output += self._root.prettify(formatter="minimal").rstrip("\n")
                    elif idx + 1 == copy_from_line:
                        output = line[copy_from_pos:]
                    elif idx + 1 > copy_from_line:
                        output = line
                    if output is not None:
                        outf.write(output)

            tmpf.rename(self.filename)

    @abstractmethod
    def __len__(self) -> int:
        pass

    def get(self, title: str) -> Union[Tiddler, None]:
        for tiddler in self._tiddlers:
            if tiddler.title == title:
                return tiddler
        return None

    def get_or_create(self, title: str) -> Tiddler:
        tiddler = self.get(title)
        if not tiddler:
            tiddler = self.new_tiddler(title)
        return tiddler

    def __getitem__(self, title: str) -> Tiddler:
        tiddler = self.get(title)
        if tiddler:
            return tiddler
        else:
            raise TiddlerNotFoundError(f"Could not find tiddler {title}")

    @abstractmethod
    def new_tiddler(self, title: str) -> Tiddler:
        pass


class JsonTiddlyParser(TiddlyParser):
    fileformat: FileFormat = FileFormat.JSON

    def __init__(self, file: Path, soup: BeautifulSoup):
        self.fileformat = FileFormat.JSON
        self.filename = file
        self._soup = soup
        root = self._get_container(soup)
        if not isinstance(root, Tag):
            raise UnknownTiddlywikiFormatError("Could not find root element.")
        self._root = root
        self._tiddlers = self._load_tiddlers()

    @classmethod
    def is_format(cls, file: Path, soup: BeautifulSoup) -> bool:
        return bool(cls._get_container(soup))

    def save(self) -> None:
        tiddlers = sorted(self._tiddlers, key=lambda t: t.title.lower())
        # We manually encode each row, so that we can separate every list item
        # with a newline.
        out = ["["]
        for idx, tiddler in enumerate(tiddlers):
            if idx > 0:
                out.append(",")
            out.append("\n")
            json_tiddler = json.dumps(
                tiddler.to_dict(), separators=(",", ":"), ensure_ascii=False
            )
            json_tiddler = json_tiddler.replace("<", "\\u003C")
            out.append(json_tiddler)
        out.append("]")
        out.append("\n")
        tiddlers_json = "".join(out)
        print(repr(tiddlers_json[0:50]))
        print(repr(tiddlers_json[-50:]))
        self._root.string = tiddlers_json
        self.dump_to_file()

    def __len__(self) -> int:
        return len(self._tiddlers)

    def new_tiddler(self, title: str) -> Tiddler:
        return JsonTiddler(title=title)

    @staticmethod
    def _get_container(soup: BeautifulSoup) -> Union[Tag, NavigableString, None]:
        return soup.find("script", class_="tiddlywiki-tiddler-store")

    def _load_tiddlers(self) -> Sequence[Tiddler]:
        tiddlers = []
        text = self._root.string
        if not text:
            raise UnknownTiddlywikiFormatError("No tiddler content found.")
        try:
            raw_tiddlers = json.loads(text)
        except JSONDecodeError:
            raise UnknownTiddlywikiFormatError(
                f"Could not parse the JSON tiddler with the text {text[0:100]!r}"
            )
        for tiddler in raw_tiddlers:
            tiddlers.append(JsonTiddler(tiddler))
        return tiddlers


class DivTiddlyParser(TiddlyParser):
    fileformat: FileFormat = FileFormat.DIV

    def __init__(self, file: Path, soup: BeautifulSoup):
        self.fileformat = FileFormat.DIV
        self.filename = file
        self._soup = soup
        root = self._get_container(soup)
        if not isinstance(root, Tag):
            raise UnknownTiddlywikiFormatError("Could not find root element.")
        self._root = root
        self._tiddlers = self._load_tiddlers()

    @classmethod
    def is_format(cls, file: Path, soup: BeautifulSoup) -> bool:
        return bool(cls._get_container(soup))

    def save(self) -> None:
        pass

    def __len__(self) -> int:
        return len(self._tiddlers)

    def new_tiddler(self, title: str) -> Tiddler:
        return DivTiddler(title=title)

    @staticmethod
    def _get_container(soup: BeautifulSoup) -> Union[Tag, NavigableString, None]:
        return soup.find("div", id="storeArea")

    def _load_tiddlers(self) -> Sequence[Tiddler]:
        tiddlers = []
        for container in self._root("div"):
            if isinstance(container, Tag):
                tiddlers.append(DivTiddler(container))
        return tiddlers


def parse(file: Path) -> TiddlyParser:
    """Parse the Wiki file and return a parser for the detected format."""
    with open(file) as fp:
        soup = BeautifulSoup(fp, "html.parser")

    if JsonTiddlyParser.is_format(file, soup):
        return JsonTiddlyParser(file, soup)
    elif DivTiddlyParser.is_format(file, soup):
        return DivTiddlyParser(file, soup)
    else:
        raise UnknownTiddlywikiFormatError("Could not find any store area in the wiki.")
