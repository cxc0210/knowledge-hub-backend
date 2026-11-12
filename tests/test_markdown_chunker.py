from unittest import TestCase

from services.markdown_chunker import EmptyMarkdownError, MarkdownChunker


class MarkdownChunkerTests(TestCase):
    def setUp(self) -> None:
        self.chunker = MarkdownChunker(
            target_chars=40,
            max_chars=60,
            min_chars=10,
            context_chars=8,
        )

    def test_splits_by_heading_and_character_limit(self) -> None:
        markdown = """# 用户系统

## 权限管理

第一句话说明角色权限。第二句话说明用户角色。第三句话说明权限校验。第四句话说明访问控制。

## 登录管理

登录成功后生成令牌。令牌过期后需要重新登录。
"""

        chunks = self.chunker.split(
            document_id=100001,
            title="用户系统设计",
            markdown=markdown,
        )

        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(chunk.char_count <= 60 for chunk in chunks))
        self.assertEqual(chunks[0].heading, "权限管理")
        self.assertEqual(chunks[-1].heading, "登录管理")
        self.assertEqual(
            chunks[0].heading_path,
            "用户系统 > 权限管理",
        )
        self.assertNotIn("上文：", chunks[0].embedding_content)
        self.assertIn("上文：", chunks[1].embedding_content)

    def test_generates_stable_chunk_ids(self) -> None:
        arguments = {
            "document_id": 100001,
            "title": "测试文档",
            "markdown": "# 标题\n\n这是一段稳定的文档内容。",
        }

        first = self.chunker.split(**arguments)
        second = self.chunker.split(**arguments)

        self.assertEqual(
            [chunk.chunk_id for chunk in first],
            [chunk.chunk_id for chunk in second],
        )

    def test_preserves_table_header_when_splitting(self) -> None:
        markdown = """# 表格

| 名称 | 描述 |
| --- | --- |
| 用户 | 用户信息用户信息用户信息用户信息 |
| 角色 | 角色信息角色信息角色信息角色信息 |
| 权限 | 权限信息权限信息权限信息权限信息 |
"""
        chunks = self.chunker.split(
            document_id=100001,
            title="表格测试",
            markdown=markdown,
        )

        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(
            all(chunk.content.startswith("| 名称 | 描述 |") for chunk in chunks),
        )

    def test_rejects_empty_markdown(self) -> None:
        with self.assertRaises(EmptyMarkdownError):
            self.chunker.split(
                document_id=100001,
                title="空文档",
                markdown=" \n ",
            )

    def test_rejects_markdown_without_indexable_text(self) -> None:
        with self.assertRaises(EmptyMarkdownError):
            self.chunker.split(
                document_id=100001,
                title="只有标题",
                markdown="# 一级标题\n\n## 二级标题",
            )
