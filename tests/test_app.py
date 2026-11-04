"""窗口处理流程集成测试；系统文件选择框用预定路径代替。需要 Tk 图形环境。"""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app import App, ROOT


class AppFlowTests(unittest.TestCase):
    def setUp(self):
        self.app = App()
        self.app.withdraw()

    def tearDown(self):
        self.app.destroy()

    def wait_for_answer(self):
        deadline = time.monotonic() + 5
        while self.app.busy and time.monotonic() < deadline:
            self.app.update()
            time.sleep(0.01)
        self.assertFalse(self.app.busy, "问答任务未在期限内完成")

    def test_import_ask_export_flow(self):
        example = str(ROOT / "examples" / "我的课程笔记.txt")
        with patch("app.filedialog.askopenfilenames", return_value=(example,)):
            self.app.import_files()
        self.assertEqual(len(self.app.engine.documents), 3)
        self.app.ask_example("番茄种植需要什么？")
        self.wait_for_answer()
        self.assertIn("充足阳光", self.app.answer_box.get("1.0", "end"))
        self.assertIn("我的课程笔记.txt", self.app.source_box.get("1.0", "end"))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "记录.md"
            with patch("app.filedialog.asksaveasfilename", return_value=str(path)):
                self.app.export()
            exported = path.read_text(encoding="utf-8")
            self.assertIn("番茄种植需要什么", exported)
            self.assertIn("充足阳光", exported)
            self.assertIn("离线检索", exported)

    def test_model_failure_falls_back_and_unlocks_ui(self):
        self.app.api = {"base": "https://example.invalid/v1", "model": "test", "key": "example-secret"}
        self.app.use_model.set(True)
        with patch("app.model_answer", side_effect=ValueError("测试模拟连接失败")):
            self.app.ask_example("如何缓解过拟合？")
            self.wait_for_answer()
        answer = self.app.answer_box.get("1.0", "end")
        self.assertIn("接口失败回退", answer)
        self.assertIn("正则化", answer)
        self.assertNotIn("example-secret", answer)
        self.assertEqual(str(self.app.ask_button["state"]), "normal")


if __name__ == "__main__":
    unittest.main()
