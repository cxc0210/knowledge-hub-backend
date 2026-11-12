import hashlib
import re
from dataclasses import dataclass

from core.config import settings
from schemas.document_index import DocumentChunkData

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE_PATTERN = re.compile(r"^\s*(```+|~~~+)")
SENTENCE_PATTERN = re.compile(r".+?(?:[。！？；!?;]+|\n+|$)", re.DOTALL)
TABLE_SEPARATOR_PATTERN = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$",
)


class EmptyMarkdownError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class _MarkdownBlock:
    text: str
    heading_path: tuple[str, ...]


@dataclass(slots=True)
class _ChunkBuffer:
    parts: list[str]
    heading_path: tuple[str, ...]

    @property
    def content(self) -> str:
        return "\n\n".join(self.parts).strip()


class MarkdownChunker:
    def __init__(
        self,
        *,
        target_chars: int = settings.document_chunk_target_chars,
        max_chars: int = settings.document_chunk_max_chars,
        min_chars: int = settings.document_chunk_min_chars,
        context_chars: int = settings.document_chunk_context_chars,
    ) -> None:
        if not 0 < min_chars <= target_chars <= max_chars:
            raise ValueError(
                "chunk sizes must satisfy 0 < min <= target <= max",
            )
        if context_chars < 0:
            raise ValueError("context_chars must be non-negative")

        self.target_chars = target_chars
        self.max_chars = max_chars
        self.min_chars = min_chars
        self.context_chars = context_chars

    def split(
        self,
        *,
        document_id: int,
        title: str,
        markdown: str,
    ) -> list[DocumentChunkData]:
        normalized = markdown.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            raise EmptyMarkdownError("markdown content is empty")

        document_version = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        blocks = self._parse_blocks(normalized)
        base_chunks = self._combine_blocks(blocks)
        if not base_chunks:
            raise EmptyMarkdownError("markdown content has no indexable text")

        chunks: list[DocumentChunkData] = []
        for index, chunk in enumerate(base_chunks):
            content = chunk.content
            previous_context = ""
            if index > 0 and self.context_chars:
                previous_context = base_chunks[index - 1].content[-self.context_chars :]

            heading_path = " > ".join(chunk.heading_path) or None
            heading = chunk.heading_path[-1] if chunk.heading_path else None
            embedding_parts = [f"文档标题：{title}"]
            if heading_path:
                embedding_parts.append(f"章节：{heading_path}")
            if previous_context:
                embedding_parts.append(f"上文：{previous_context}")
            embedding_parts.append(f"正文：{content}")

            chunks.append(
                DocumentChunkData(
                    chunk_id=f"{document_id}:{document_version}:{index}",
                    document_id=document_id,
                    document_version=document_version,
                    chunk_index=index,
                    heading=heading,
                    heading_path=heading_path,
                    content=content,
                    embedding_content="\n".join(embedding_parts),
                    content_hash=hashlib.sha256(
                        content.encode("utf-8"),
                    ).hexdigest(),
                    char_count=len(content),
                ),
            )

        return chunks

    def _parse_blocks(self, markdown: str) -> list[_MarkdownBlock]:
        lines = markdown.splitlines()
        heading_levels: list[str | None] = [None] * 6
        blocks: list[_MarkdownBlock] = []
        paragraph: list[str] = []
        paragraph_path: tuple[str, ...] = ()

        def current_path() -> tuple[str, ...]:
            return tuple(item for item in heading_levels if item is not None)

        def flush_paragraph() -> None:
            nonlocal paragraph
            text = "\n".join(paragraph).strip()
            if text:
                blocks.extend(self._split_block(text, paragraph_path))
            paragraph = []

        line_index = 0
        while line_index < len(lines):
            line = lines[line_index]
            heading_match = HEADING_PATTERN.match(line)
            fence_match = FENCE_PATTERN.match(line)

            if heading_match:
                flush_paragraph()
                level = len(heading_match.group(1))
                heading_levels[level - 1] = heading_match.group(2).strip()
                for nested_level in range(level, len(heading_levels)):
                    heading_levels[nested_level] = None
                line_index += 1
                continue

            if fence_match:
                flush_paragraph()
                fence = fence_match.group(1)
                code_lines = [line]
                line_index += 1
                while line_index < len(lines):
                    code_line = lines[line_index]
                    code_lines.append(code_line)
                    line_index += 1
                    if code_line.strip().startswith(fence):
                        break
                blocks.extend(
                    self._split_block(
                        "\n".join(code_lines),
                        current_path(),
                    ),
                )
                continue

            if not line.strip():
                flush_paragraph()
                line_index += 1
                continue

            if not paragraph:
                paragraph_path = current_path()
            paragraph.append(line)
            line_index += 1

        flush_paragraph()
        return blocks

    def _split_block(
        self,
        text: str,
        heading_path: tuple[str, ...],
    ) -> list[_MarkdownBlock]:
        if len(text) <= self.max_chars:
            return [_MarkdownBlock(text=text, heading_path=heading_path)]

        if FENCE_PATTERN.match(text):
            parts = self._split_code_block(text)
        elif self._is_table(text):
            parts = self._split_table(text)
        else:
            parts = self._split_prose(text)

        return [
            _MarkdownBlock(text=part, heading_path=heading_path)
            for part in parts
            if part.strip()
        ]

    def _split_prose(self, text: str) -> list[str]:
        sentences = [
            match.group(0).strip()
            for match in SENTENCE_PATTERN.finditer(text)
            if match.group(0).strip()
        ]
        units: list[str] = []
        for sentence in sentences or [text]:
            if len(sentence) <= self.max_chars:
                units.append(sentence)
                continue
            units.extend(self._hard_split(sentence, self.max_chars))
        return self._pack_units(units)

    def _split_code_block(self, text: str) -> list[str]:
        lines = text.splitlines()
        opening = lines[0]
        fence_match = FENCE_PATTERN.match(opening)
        assert fence_match is not None
        fence = fence_match.group(1)
        closing = lines[-1] if lines[-1].strip().startswith(fence) else fence
        body = lines[1:-1] if lines[-1].strip().startswith(fence) else lines[1:]
        available = max(1, self.max_chars - len(opening) - len(closing) - 2)
        body_units: list[str] = []
        for line in body:
            if len(line) <= available:
                body_units.append(line)
            else:
                body_units.extend(self._hard_split(line, available))

        packed = self._pack_units(body_units, separator="\n", limit=available)
        return [f"{opening}\n{part}\n{closing}" for part in packed]

    def _split_table(self, text: str) -> list[str]:
        lines = text.splitlines()
        header = lines[:2]
        rows = lines[2:]
        header_text = "\n".join(header)
        available = max(1, self.max_chars - len(header_text) - 1)
        row_units: list[str] = []
        for row in rows:
            if len(row) <= available:
                row_units.append(row)
            else:
                row_units.extend(self._hard_split(row, available))

        packed = self._pack_units(row_units, separator="\n", limit=available)
        return [f"{header_text}\n{part}" for part in packed]

    def _combine_blocks(
        self,
        blocks: list[_MarkdownBlock],
    ) -> list[_ChunkBuffer]:
        chunks: list[_ChunkBuffer] = []
        current: _ChunkBuffer | None = None

        def flush() -> None:
            nonlocal current
            if current is not None and current.content:
                chunks.append(current)
            current = None

        for block in blocks:
            if current is None:
                current = _ChunkBuffer([block.text], block.heading_path)
                continue

            candidate_length = len(current.content) + 2 + len(block.text)
            heading_changed = current.heading_path != block.heading_path
            target_reached = len(current.content) >= self.target_chars
            if heading_changed or target_reached or candidate_length > self.max_chars:
                flush()
                current = _ChunkBuffer([block.text], block.heading_path)
            else:
                current.parts.append(block.text)

        flush()
        return self._merge_small_chunks(chunks)

    def _merge_small_chunks(
        self,
        chunks: list[_ChunkBuffer],
    ) -> list[_ChunkBuffer]:
        merged: list[_ChunkBuffer] = []
        for chunk in chunks:
            if (
                merged
                and len(chunk.content) < self.min_chars
                and merged[-1].heading_path == chunk.heading_path
                and len(merged[-1].content) + 2 + len(chunk.content) <= self.max_chars
            ):
                merged[-1].parts.extend(chunk.parts)
            else:
                merged.append(chunk)
        return merged

    def _pack_units(
        self,
        units: list[str],
        *,
        separator: str = "",
        limit: int | None = None,
    ) -> list[str]:
        effective_limit = limit or self.max_chars
        target = min(self.target_chars, effective_limit)
        parts: list[str] = []
        current = ""

        for unit in units:
            candidate = f"{current}{separator if current else ''}{unit}"
            if current and (len(candidate) > effective_limit or len(current) >= target):
                parts.append(current.strip())
                current = unit
            else:
                current = candidate

        if current.strip():
            parts.append(current.strip())
        return parts

    @staticmethod
    def _hard_split(text: str, max_chars: int) -> list[str]:
        return [
            text[index : index + max_chars] for index in range(0, len(text), max_chars)
        ]

    @staticmethod
    def _is_table(text: str) -> bool:
        lines = text.splitlines()
        return (
            len(lines) >= 2
            and "|" in lines[0]
            and TABLE_SEPARATOR_PATTERN.match(lines[1]) is not None
        )
