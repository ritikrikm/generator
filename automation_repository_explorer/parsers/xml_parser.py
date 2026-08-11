"""XML parser backed by lxml with external-entity/network resolution disabled."""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from automation_repository_explorer.models.domain import PropertyEntry, SourceLocation
from automation_repository_explorer.parsers.base import ParseResult, RepositoryParser


class XmlParser(RepositoryParser[PropertyEntry]):
    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".xml"})

    def parse(self, file_path: Path) -> ParseResult[PropertyEntry]:
        parser = etree.XMLParser(
            resolve_entities=False,
            no_network=True,
            load_dtd=False,
            recover=False,
        )
        tree = etree.parse(str(file_path), parser)
        root = tree.getroot()
        entries: list[PropertyEntry] = []
        self._walk(root, file_path, f"/{_local_name(root.tag)}", entries)
        return ParseResult(file_path=file_path, items=tuple(entries))

    def _walk(
        self,
        element: etree._Element,
        file_path: Path,
        path: str,
        entries: list[PropertyEntry],
    ) -> None:
        line = int(element.sourceline or 1)
        for name, value in element.attrib.items():
            entries.append(
                PropertyEntry(
                    key=f"{path}/@{_local_name(name)}",
                    value=value,
                    location=SourceLocation(file_path, line),
                )
            )

        text = (element.text or "").strip()
        children = tuple(child for child in element if isinstance(child.tag, str))
        if text and not children:
            entries.append(
                PropertyEntry(
                    key=path,
                    value=text,
                    location=SourceLocation(file_path, line),
                )
            )

        sibling_counts: dict[str, int] = {}
        for child in children:
            name = _local_name(child.tag)
            sibling_counts[name] = sibling_counts.get(name, 0) + 1
            child_path = f"{path}/{name}[{sibling_counts[name]}]"
            self._walk(child, file_path, child_path, entries)


def _local_name(tag: str) -> str:
    return etree.QName(tag).localname
