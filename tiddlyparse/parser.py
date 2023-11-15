import bisect
import html
import json
import tempfile
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from enum import Enum
from json.decoder import JSONDecodeError
from pathlib import Path
from typing import (
    Literal,
    Mapping,
    MutableMapping,
    MutableSequence,
    Optional,
    Sequence,
    Union,
)

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
from bs4.formatter import Formatter, HTMLFormatter


class FileFormat(Enum):
    # Format for 5.1.23 and earlier
    DIV = 1
    # Format from 5.2.0
    JSON = 2


class UnknownTiddlywikiFormatError(ValueError):
    pass


class TiddlerNotFoundError(KeyError):
    pass


class DivHtmlFormatter(HTMLFormatter):
    def __init__(self) -> None:
        super().__init__(entity_substitution=self._entity_substitution)

    def _entity_substitution(self, s: str) -> str:
        return html.escape(s).replace("&#x27;", "'")


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
        if key.startswith("_") and key != "_canonical_uri":
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

    @property
    def original_title(self) -> Optional[str]:
        return self.stored_values.get("title")

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

    def fixup(self) -> None:
        """Ensure the tiddler has the required properties to add to the wiki."""
        # mypy fails on the following two lines and can't figure out that
        # `__getattr__` has declared these to be strings. So need to ignore
        # those lines.
        modified = self.modified  # type: ignore
        created: str = self.created  # type: ignore
        if not modified:
            self.modified = self._get_current_timestamp()
        if not created:
            self.created = self._get_current_timestamp()

    def _get_current_timestamp(self) -> str:
        return time.strftime("%Y%m%d%H%M%S000", time.gmtime())


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
            for key, value in self._el.attrs.items():
                values[key] = value

            text_tag = self._el("pre")[0]
            if not isinstance(text_tag, Tag):
                raise UnknownTiddlywikiFormatError(
                    f"Could not find text for tiddler {self.title!r}"
                )
            values["text"] = text_tag.string or ""

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

    _tiddlers: MutableSequence[Tiddler]
    _changes: MutableSequence[str]
    _deletions: MutableSequence[str]
    _soup: BeautifulSoup
    _root: Tag

    def __init__(self) -> None:
        self._tiddlers = []
        self._changes = []
        self._deletions = []

    @classmethod
    @abstractmethod
    def is_format(cls, file: Path, soup: BeautifulSoup) -> bool:
        pass

    def items(self) -> Iterator[Tiddler]:
        for tiddler in self._tiddlers:
            yield tiddler

    def add(self, tiddler: Tiddler, *, track_modified: bool = True) -> None:
        if track_modified:
            tiddler.fixup()

        # Insert the tiddler in the correct place of the list. The list is
        # sorted, but not yet in an entirely predictable way. Thus we first
        # do the search for existing tiddlers in a brute-force manner.
        existing_index = None
        for idx, original_tiddler in enumerate(self._tiddlers):
            if original_tiddler.title == tiddler.original_title:
                existing_index = idx
                break
        if existing_index is None:
            # Bisect insert to put the new tiddler in the right place
            bisect.insort(self._tiddlers, tiddler, key=lambda t: t.title)
        else:
            self._tiddlers[existing_index] = tiddler

        if tiddler.title not in self._changes:
            self._changes.append(tiddler.title)

    def remove(self, tiddler: Tiddler) -> None:
        tiddlers = [t for t in self._tiddlers if t.title != tiddler.original_title]
        if tiddler.original_title not in self._deletions:
            self._deletions.append(tiddler.title)
        self._tiddlers = tiddlers

    @property
    def changes(self) -> Sequence[str]:
        return self._changes

    @property
    def deletions(self) -> Sequence[str]:
        return self._deletions

    @abstractmethod
    def save(self) -> None:
        self.dump_to_file()

        self._changes = []
        self._deletions = []

    def dump_to_file(self) -> None:
        """Dump the file back out.

        This is slightly complex purely because we want to retain as much
        formatting and whitespace as possible. So any markup except the root
        tag and its content is copied verbatim.

        To know where we need to stop/restart the copying, we use the
        `sourceline` and `sourcepos` properties of the root tag.
        """
        root = self._root
        root_next_strings = []

        if not isinstance(root, Tag):
            raise UnknownTiddlywikiFormatError("Expected root to be a tag.")

        root_next = self._root.next_sibling
        while root_next and not isinstance(root_next, Tag):
            root_next_strings.append(
                getattr(root_next, "PREFIX", "")
                + str(root_next)
                + getattr(root_next, "SUFFIX", "")
            )
            root_next = root_next.next_sibling

        copy_until_line = root.sourceline
        copy_until_pos = root.sourcepos or 0
        if not isinstance(root_next, Tag):
            raise UnknownTiddlywikiFormatError("Could not find tag after wiki content.")

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
                        # output += self._root.decode(formatter="minimal")
                        output += self._root.decode(
                            formatter=self._get_html_formatter()
                        )
                    elif idx + 1 == copy_from_line:
                        output = "".join(root_next_strings)
                        output += line[copy_from_pos:]
                    elif idx + 1 > copy_from_line:
                        output = line
                    if output is not None:
                        outf.write(output)

            tmpf.rename(self.filename)

    def _get_html_formatter(self) -> Union[str, Formatter]:
        return "minimal"

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

    def search(
        self, **query: Mapping[str, Union[str, Literal[True]]]
    ) -> Sequence[Tiddler]:
        ret = []
        for tiddler in self._tiddlers:
            if self._tiddler_matches(tiddler, **query):
                ret.append(tiddler)
        return ret

    def _tiddler_matches(
        self, tiddler: Tiddler, **query: Mapping[str, Union[str, Literal[True]]]
    ) -> bool:
        matches = 0
        for key, value in query.items():
            if isinstance(value, bool) and value is True and getattr(tiddler, key):
                matches += 1
            elif isinstance(value, str) and getattr(tiddler, key) == value:
                matches += 1
        matched = matches == len(query)
        return matched

    @abstractmethod
    def new_tiddler(self, title: str) -> Tiddler:
        pass


class JsonTiddlyParser(TiddlyParser):
    fileformat: FileFormat = FileFormat.JSON

    def __init__(self, file: Path, soup: BeautifulSoup):
        super().__init__()

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
        # We manually encode each row, so that we can separate every list item
        # with a newline.
        out = ["["]
        for idx, tiddler in enumerate(self._tiddlers):
            if idx > 0:
                out.append(",")
            out.append("\n")
            json_tiddler = json.dumps(
                tiddler.to_dict(), separators=(",", ":"), ensure_ascii=False
            )
            json_tiddler = json_tiddler.replace("<", "\\u003C")
            out.append(json_tiddler)
        out.append("\n]")
        tiddlers_json = "".join(out)
        self._root.string = tiddlers_json

        super().save()

    def __len__(self) -> int:
        return len(self._tiddlers)

    def new_tiddler(self, title: str) -> Tiddler:
        return JsonTiddler(title=title)

    @staticmethod
    def _get_container(soup: BeautifulSoup) -> Union[Tag, NavigableString, None]:
        return soup.find("script", class_="tiddlywiki-tiddler-store")

    def _load_tiddlers(self) -> MutableSequence[Tiddler]:
        tiddlers: list[Tiddler] = []
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
            tid = JsonTiddler(tiddler)
            tiddlers.append(tid)
        return tiddlers


class DivTiddlyParser(TiddlyParser):
    fileformat: FileFormat = FileFormat.DIV

    # Keep track of changes for persisting later
    _new_tiddlers: MutableMapping[str, Tiddler]
    _modified_tiddlers: MutableMapping[str, Tiddler]

    def __init__(self, file: Path, soup: BeautifulSoup):
        super().__init__()

        self.fileformat = FileFormat.DIV
        self.filename = file
        self._soup = soup
        root = self._get_container(soup)
        if not isinstance(root, Tag):
            raise UnknownTiddlywikiFormatError("Could not find root element.")
        self._root = root
        self._tiddlers = self._load_tiddlers()
        self._new_tiddlers = {}
        self._modified_tiddlers = {}

    @classmethod
    def is_format(cls, file: Path, soup: BeautifulSoup) -> bool:
        return bool(cls._get_container(soup))

    def save(self) -> None:
        dumped = set()

        for container in self._root("div"):
            if isinstance(container, Tag):
                container_title = container["title"]
                if isinstance(container_title, str):
                    if container_title in self._deletions:
                        container.extract()
                    elif container_title in self._modified_tiddlers:
                        tiddler = self._modified_tiddlers[container_title]
                        container.replace_with(self._dump_tiddler(tiddler))
                        dumped.add(container_title)

        # Ensure all tiddlers that were modified were found in the original list
        for title, tiddler in self._modified_tiddlers.items():
            assert title in dumped

        for title, tiddler in self._new_tiddlers.items():
            assert title not in dumped
            self._root.append(self._dump_tiddler(tiddler))

        super().save()

        self._new_tiddlers = {}
        self._modified_tiddlers = {}

    def __len__(self) -> int:
        return len(self._tiddlers)

    def add(self, tiddler: Tiddler, *, track_modified: bool = True) -> None:
        title = tiddler.original_title or tiddler.title
        if title in self._new_tiddlers:
            self._new_tiddlers[title] = tiddler
        elif title in self._modified_tiddlers:
            self._modified_tiddlers[title] = tiddler
        elif title in [t.original_title for t in self._tiddlers]:
            self._modified_tiddlers[title] = tiddler
        else:
            self._new_tiddlers[title] = tiddler

        super().add(tiddler=tiddler, track_modified=track_modified)

    def new_tiddler(self, title: str) -> Tiddler:
        return DivTiddler(title=title)

    @staticmethod
    def _get_container(soup: BeautifulSoup) -> Union[Tag, NavigableString, None]:
        return soup.find("div", id="storeArea")

    def _load_tiddlers(self) -> MutableSequence[Tiddler]:
        tiddlers: list[Tiddler] = []
        for container in self._root("div"):
            if isinstance(container, Tag):
                tiddlers.append(DivTiddler(container))
        return tiddlers

    def _get_html_formatter(self) -> Union[str, Formatter]:
        return DivHtmlFormatter()

    def _dump_tiddler(self, tiddler: Tiddler) -> Tag:
        tag = self._soup.new_tag("div")
        data = tiddler.to_dict()
        for key, value in data.items():
            if key == "text":
                pre = self._soup.new_tag("pre")
                pre.string = value
                tag.append(self._soup.new_string("\n"))
                tag.append(pre)
                tag.append(self._soup.new_string("\n"))
            else:
                tag[key] = value
        return tag


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
