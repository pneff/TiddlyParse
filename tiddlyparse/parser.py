from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Union

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag


class FileFormat(Enum):
    # Format for 5.1.23 and earlier
    DIV = 1
    # Format from 5.2.0
    JSON = 2


class UnknownTiddlywikiFormatError(ValueError):
    pass


class TiddlyParser(ABC):
    filename: Path
    fileformat: FileFormat

    _soup: BeautifulSoup

    @classmethod
    @abstractmethod
    def is_format(cls, file: Path, soup: BeautifulSoup) -> bool:
        pass


class JsonTiddlyParser(TiddlyParser):
    fileformat: FileFormat = FileFormat.JSON

    def __init__(self, file: Path, soup: BeautifulSoup):
        self.fileformat = FileFormat.JSON
        self.filename = file
        self._soup = soup
        self._root = self._get_container(soup)

    @classmethod
    def is_format(cls, file: Path, soup: BeautifulSoup) -> bool:
        return bool(cls._get_container(soup))

    @staticmethod
    def _get_container(soup: BeautifulSoup) -> Union[Tag, NavigableString, None]:
        return soup.find("script", class_="tiddlywiki-tiddler-store")


class DivTiddlyParser(TiddlyParser):
    fileformat: FileFormat = FileFormat.DIV

    def __init__(self, file: Path, soup: BeautifulSoup):
        self.fileformat = FileFormat.DIV
        self.filename = file
        self._soup = soup
        self._root = self._get_container(soup)

    @classmethod
    def is_format(cls, file: Path, soup: BeautifulSoup) -> bool:
        return bool(cls._get_container(soup))

    @staticmethod
    def _get_container(soup: BeautifulSoup) -> Union[Tag, NavigableString, None]:
        return soup.find("div", id="storeArea")


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
