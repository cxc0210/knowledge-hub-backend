from unittest import TestCase

from services.streaming_text_chunker import StreamingTextChunker


class StreamingTextChunkerTests(TestCase):
    def test_emits_complete_chinese_sentences(self) -> None:
        chunker = StreamingTextChunker(min_chars=6)

        first = chunker.feed("FastAPI支持异步请求。下一句话还")
        remaining = chunker.finish()

        self.assertEqual(first, ["FastAPI支持异步请求。"])
        self.assertEqual(remaining, ["下一句话还"])

    def test_forces_a_boundary_for_long_text_without_punctuation(self) -> None:
        chunker = StreamingTextChunker(
            min_chars=4,
            soft_boundary_chars=8,
            max_chars=12,
        )

        chunks = chunker.feed("这是一个没有任何标点而且很长的文本内容")

        self.assertTrue(chunks)
        self.assertLessEqual(len(chunks[0]), 12)

    def test_skips_fenced_code_blocks(self) -> None:
        chunker = StreamingTextChunker(min_chars=6)

        chunks = chunker.feed("介绍如下：\n```python\nprint('secret')\n```\n执行完成。")
        chunks.extend(chunker.finish())
        speech_text = "".join(chunks)

        self.assertNotIn("print", speech_text)
        self.assertNotIn("secret", speech_text)
        self.assertIn("以下是代码示例", speech_text)
