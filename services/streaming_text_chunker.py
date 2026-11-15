import re

_HARD_BOUNDARIES = frozenset("。！？!?；;\n")
_SOFT_BOUNDARIES = frozenset("，,、：:")
_MARKDOWN_LINK = re.compile(r"!?\[([^\]]+)\]\([^)]*\)")
_HTML_TAG = re.compile(r"<[^>]+>")
_LIST_PREFIX = re.compile(r"(?m)^\s*(?:#{1,6}|[-+*>]|\d+[.)])\s*")
_MARKDOWN_MARKER = re.compile(r"[*_~`]+")
_WHITESPACE = re.compile(r"\s+")


def clean_text_for_speech(text: str) -> str:
    text = _MARKDOWN_LINK.sub(r"\1", text)
    text = _HTML_TAG.sub("", text)
    text = _LIST_PREFIX.sub("", text)
    text = _MARKDOWN_MARKER.sub("", text)
    return _WHITESPACE.sub(" ", text).strip()


class StreamingTextChunker:
    def __init__(
        self,
        *,
        min_chars: int = 12,
        soft_boundary_chars: int = 40,
        max_chars: int = 100,
    ) -> None:
        self._min_chars = min_chars
        self._soft_boundary_chars = soft_boundary_chars
        self._max_chars = max_chars
        self._buffer = ""
        self._fence_tail = ""
        self._in_code_block = False

    def feed(self, delta: str) -> list[str]:
        self._buffer += self._filter_code_blocks(delta)
        return self._take_ready_chunks()

    def finish(self) -> list[str]:
        if not self._in_code_block:
            self._buffer += self._fence_tail
        self._fence_tail = ""

        chunks = self._take_ready_chunks()
        final_text = clean_text_for_speech(self._buffer)
        self._buffer = ""
        if final_text:
            chunks.append(final_text)
        return chunks

    def _take_ready_chunks(self) -> list[str]:
        chunks: list[str] = []

        while boundary := self._find_boundary():
            raw_text = self._buffer[:boundary]
            self._buffer = self._buffer[boundary:]
            cleaned_text = clean_text_for_speech(raw_text)
            if cleaned_text:
                chunks.append(cleaned_text)

        return chunks

    def _find_boundary(self) -> int | None:
        for index, character in enumerate(self._buffer):
            length = index + 1
            if length >= self._min_chars and character in _HARD_BOUNDARIES:
                return length
            if length >= self._soft_boundary_chars and character in _SOFT_BOUNDARIES:
                return length

        if len(self._buffer) < self._max_chars:
            return None

        for index in range(self._max_chars - 1, self._min_chars - 1, -1):
            if self._buffer[index] in _SOFT_BOUNDARIES or self._buffer[index].isspace():
                return index + 1

        return self._max_chars

    def _filter_code_blocks(self, delta: str) -> str:
        source = self._fence_tail + delta
        self._fence_tail = ""
        output: list[str] = []
        index = 0

        while index < len(source):
            if source.startswith("```", index):
                self._in_code_block = not self._in_code_block
                if self._in_code_block:
                    output.append(" 以下是代码示例。 ")
                index += 3
                continue

            remaining = source[index:]
            if remaining in {"`", "``"}:
                self._fence_tail = remaining
                break

            if not self._in_code_block:
                output.append(source[index])
            index += 1

        return "".join(output)
