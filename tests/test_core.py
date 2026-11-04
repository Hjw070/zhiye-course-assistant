"""重点验证检索出处、无结果行为和模型协议。运行 python -m unittest discover -s tests -v。"""
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from core import SearchEngine, build_messages, extract_answer, model_answer, read_document, split_document


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.engine = SearchEngine()
        root = Path(__file__).resolve().parents[1]
        for path in (root / "data").glob("*.md"):
            self.engine.add(path.name, read_document(path))

    def test_questions_and_traceable_lines(self):
        for question, keyword, source in [
            ("如何缓解过拟合？", "正则化", "机器学习入门.md"),
            ("精确率与召回率有什么区别？", "TP / (TP + FN)", "机器学习入门.md"),
            ("什么是机会成本？", "放弃", "跨学科知识卡.md"),
        ]:
            with self.subTest(question=question):
                hit = self.engine.search(question)[0]
                self.assertEqual(hit.chunk.source, source)
                self.assertIn(keyword, hit.chunk.text)
                original = self.engine.documents[source].splitlines()
                self.assertEqual(hit.chunk.text, "\n".join(original[hit.chunk.start_line - 1:hit.chunk.end_line]))

    def test_unknown_question_is_not_answered(self):
        self.assertEqual(self.engine.search("火星上有多少家咖啡馆？"), [])
        self.assertIn("未检索到", extract_answer([]))

    def test_new_document_is_immediately_searchable(self):
        self.engine.add("我的资料.txt", "番茄种植需要充足阳光，浇水保持适度。")
        self.assertEqual(self.engine.search("番茄种植需要什么？")[0].chunk.source, "我的资料.txt")

    def test_reimport_updates_without_duplicating(self):
        self.engine.add("课堂.txt", "番茄种植")
        self.engine.add("课堂.txt", "海洋生态系统")
        self.assertFalse(self.engine.search("番茄种植"))
        self.assertEqual(self.engine.search("海洋生态系统")[0].chunk.text, "海洋生态系统")

    def test_empty_library_and_empty_question(self):
        self.assertEqual(SearchEngine().search("任何问题"), [])
        self.assertEqual(self.engine.search(""), [])

    def test_long_line_and_original_line_numbers(self):
        chunks = split_document("long.txt", "\n" + "缓存" * 600, limit=480)
        self.assertTrue(all(len(c.text) <= 480 for c in chunks))
        self.assertTrue(all(c.start_line == c.end_line == 2 for c in chunks))
        self.assertEqual("".join(c.text for c in chunks), "缓存" * 600)

    def test_text_encodings_and_invalid_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "note.txt"
            path.write_bytes("中文资料".encode("gb18030"))
            self.assertEqual(read_document(path), "中文资料")
            path.write_text("中文资料", encoding="utf-8-sig")
            self.assertEqual(read_document(path), "中文资料")
            for content in [b"", b"\x00\x01", b"a" * (1024 * 1024 + 1)]:
                path.write_bytes(content)
                with self.assertRaises(ValueError):
                    read_document(path)


class InterfaceTests(unittest.TestCase):
    def test_model_protocol_with_local_stub(self):
        seen = {}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                seen["path"] = self.path
                seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                seen["auth"] = self.headers.get("Authorization")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"choices": [{"message": {"content": "根据资料，缓存利用局部性。[1]"}}]}, ensure_ascii=False).encode())

            def log_message(self, *args):
                pass

        engine = SearchEngine()
        engine.add("课程.txt", "缓存利用时间局部性和空间局部性。")
        hits = engine.search("缓存利用什么？")
        with HTTPServer(("127.0.0.1", 0), Handler) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                answer = model_answer("缓存利用什么？", hits, f"http://127.0.0.1:{server.server_port}/v1", "test-secret", "test-model")
                self.assertIn("[1]", answer)
                self.assertEqual(seen["path"], "/v1/chat/completions")
                self.assertEqual(seen["auth"], "Bearer test-secret")
                self.assertEqual(seen["body"]["model"], "test-model")
                self.assertIn("缓存利用时间局部性", seen["body"]["messages"][1]["content"])
                self.assertNotIn("test-secret", json.dumps(seen["body"]))
            finally:
                server.shutdown()
                worker.join()

    def test_rejects_unsafe_or_malformed_endpoints(self):
        engine = SearchEngine()
        engine.add("课程", "缓存利用局部性。")
        hits = engine.search("缓存")
        for url in ["http://example.com/v1", "https://user:password@example.com", "file:///etc/passwd", "https://example.com/v1?key=secret"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                model_answer("缓存", hits, url, "", "model")


if __name__ == "__main__":
    unittest.main()
