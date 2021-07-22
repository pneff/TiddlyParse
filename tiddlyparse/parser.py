import json
from abc import ABC, abstractmethod
from enum import Enum
from json.decoder import JSONDecodeError
from pathlib import Path
from typing import Mapping, Sequence, Union

from bs4 import BeautifulSoup
from bs4.element import NavigableString, PageElement, Tag


class FileFormat(Enum):
    # Format for 5.1.23 and earlier
    DIV = 1
    # Format from 5.2.0
    JSON = 2


class UnknownTiddlywikiFormatError(ValueError):
    pass


class Tiddler:
    pass


class DivTiddler(Tiddler):
    def __init__(self, el: PageElement):
        pass


class JsonTiddler(Tiddler):
    def __init__(self, tiddler: Mapping[str, str]):
        pass


class TiddlyParser(ABC):
    filename: Path
    fileformat: FileFormat

    _soup: BeautifulSoup

    @classmethod
    @abstractmethod
    def is_format(cls, file: Path, soup: BeautifulSoup) -> bool:
        pass

    @abstractmethod
    def __len__(self) -> int:
        pass


class JsonTiddlyParser(TiddlyParser):
    fileformat: FileFormat = FileFormat.JSON

    _root: Tag
    _tiddlers: Sequence[Tiddler]

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

    def __len__(self) -> int:
        return len(self._tiddlers)

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

    _root: Tag
    _tiddlers: Sequence[Tiddler]

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

    def __len__(self) -> int:
        return len(self._tiddlers)

    @staticmethod
    def _get_container(soup: BeautifulSoup) -> Union[Tag, NavigableString, None]:
        return soup.find("div", id="storeArea")

    def _load_tiddlers(self) -> Sequence[Tiddler]:
        tiddlers = []
        for container in self._root("div"):
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
