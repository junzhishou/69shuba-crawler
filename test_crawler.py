import tempfile
import unittest
from pathlib import Path

from crawler import (
    Chapter,
    build_outputs,
    decode_html,
    is_valid_chapter_file,
    parse_book_page,
    parse_chapter_text,
    target_to_book_url,
)


class CrawlerTests(unittest.TestCase):
    def test_target_accepts_id_and_full_url(self):
        expected = ("83216", "https://www.69shuba.com/book/83216/")
        self.assertEqual(target_to_book_url("83216"), expected)
        self.assertEqual(target_to_book_url("https://www.69shuba.com/book/83216/"), expected)
        with self.assertRaises(ValueError):
            target_to_book_url("https://example.com/book/83216/")

    def test_decode_html_prefers_meta_charset(self):
        raw = '<meta charset="gbk"><title>捞尸人</title>'.encode("gbk")
        self.assertIn("捞尸人", decode_html(raw, "text/html; charset=UTF-8"))

    def test_catalog_filters_noise_and_reverses(self):
        html = """
        <title>捞尸人最新章节列表,捞尸人无弹窗广告-69书吧</title>
        <div id="catalog"><ul>
          <li><a href="#">书签</a></li>
          <li><a href="/txt/83216/3">第3章</a></li>
          <li><a href="/txt/83216/2">请假一天</a></li>
          <li><a href="https://www.69shuba.com/txt/83216/1">第1章</a></li>
          <li><a href="/txt/99999/1">其他书</a></li>
        </ul></div>
        """
        title, chapters = parse_book_page(
            html, "83216", "https://www.69shuba.com/book/83216/"
        )
        self.assertEqual(title, "捞尸人")
        self.assertEqual([chapter.title for chapter in chapters], ["第1章", "请假一天", "第3章"])
        self.assertEqual([chapter.serial for chapter in chapters], [1, 2, 3])

    def test_chapter_parser_removes_metadata_and_duplicate_title(self):
        html = """
        <div class="txtnav">
          <h1>第1章</h1><div class="txtinfo">日期 作者</div><div id="txtright">广告</div>
          第1章<br><br>第一段。<br><br>第二段。
        </div>
        """
        self.assertEqual(parse_chapter_text(html, "第1章"), "第一段。\n\n第二段。")

    def test_outputs_require_every_chapter(self):
        chapters = [Chapter(1, "第1章", "u1"), Chapter(2, "第2章", "u2")]
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "书名"
            directory.mkdir()
            (directory / "00001_第1章.txt").write_text("正文" * 100, encoding="utf-8")
            with self.assertRaises(RuntimeError):
                build_outputs(directory, "书名", chapters)

    def test_short_nonempty_notice_is_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "notice.txt"
            path.write_text("请假一天。\n", encoding="utf-8")
            self.assertTrue(is_valid_chapter_file(path))


if __name__ == "__main__":
    unittest.main()
