"""运行：python app.py。无需第三方依赖。"""
from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from core import SearchEngine, export_entry, extract_answer, format_sources, model_answer, read_document

ROOT = Path(__file__).resolve().parent
BG = "#f3f6f7"
INK = "#18363e"
TEAL = "#007f80"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("知页 · 课程资料问答助手")
        self.geometry("1120x820")
        self.minsize(980, 780)
        self.configure(bg=BG)
        self.option_add("*Font", ("Microsoft YaHei UI", 10))
        self.engine = SearchEngine()
        self.events = queue.Queue()
        self.history = []
        self.busy = False
        self.api = {"base": os.getenv("ZHIYE_API_BASE", ""), "key": os.getenv("ZHIYE_API_KEY", ""), "model": os.getenv("ZHIYE_MODEL", "")}
        self.use_model = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="准备就绪。先点击示例问题体验。")
        self._build_ui()
        self.load_demo()
        self._poll_id = self.after(100, self._poll)

    def destroy(self):
        if getattr(self, "_poll_id", None):
            self.after_cancel(self._poll_id)
            self._poll_id = None
        super().destroy()

    def _build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", padding=(12, 5), font=("Microsoft YaHei UI", 10))
        style.configure("Accent.TButton", background=TEAL, foreground="white")
        style.map("Accent.TButton", background=[("active", "#006b6c"), ("disabled", "#aac6c7")])
        style.configure("TCheckbutton", background=BG)
        style.configure("TNotebook.Tab", padding=(16, 8))
        head = tk.Frame(self, bg=INK, padx=26, pady=18)
        head.pack(fill="x")
        tk.Label(head, text="知页", bg=INK, fg="white", font=("Microsoft YaHei UI", 25, "bold")).pack(side="left")
        tk.Label(head, text="课程资料问答助手\n高级组 · 跨域知识探索", bg=INK, fg="#c4e6e8", justify="left", padx=18).pack(side="left")
        tk.Label(head, text="本地资料 · 原文溯源", bg=INK, fg="#7bdbce").pack(side="right")
        footer = tk.Frame(self, bg="#e5ecee", padx=22, pady=9)
        footer.pack(side="bottom", fill="x")
        tk.Label(footer, textvariable=self.status, bg="#e5ecee", fg=INK, anchor="w").pack(fill="x")
        body = tk.Frame(self, bg=BG, padx=22, pady=16)
        body.pack(fill="both", expand=True)
        left = tk.Frame(body, bg=BG, width=250)
        left.pack(side="left", fill="y", padx=(0, 22))
        left.pack_propagate(False)
        tk.Label(left, text="01  资料库", bg=BG, fg=INK, font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w", pady=(0, 10))
        self.library = tk.Listbox(left, bg="white", fg=INK, relief="flat", borderwidth=0, activestyle="none", height=5, font=("Microsoft YaHei UI", 10), exportselection=False)
        self.library.pack(fill="x")
        self.stats = tk.Label(left, text="", bg=BG, fg="#657e86", anchor="w")
        self.stats.pack(fill="x", pady=(8, 12))
        self.import_button = ttk.Button(left, text="＋ 导入 TXT / Markdown", command=self.import_files)
        self.import_button.pack(fill="x", pady=3)
        self.demo_button = ttk.Button(left, text="恢复演示资料", command=self.restore_demo)
        self.demo_button.pack(fill="x", pady=3)
        tk.Label(left, text="试试这些问题", bg=BG, fg=INK, font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", pady=(16, 8))
        self.example_buttons = []
        for question in ["如何缓解过拟合？", "精确率与召回率有什么区别？", "什么是机会成本？", "火星上有多少家咖啡馆？"]:
            button = ttk.Button(left, text=question, command=lambda q=question: self.ask_example(q))
            button.pack(fill="x", pady=3)
            self.example_buttons.append(button)
        tk.Label(left, text="回答方式", bg=BG, fg=INK, font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", pady=(14, 6))
        self.mode_check = ttk.Checkbutton(left, text="使用大模型组织回答", variable=self.use_model)
        self.mode_check.pack(anchor="w")
        self.config_button = ttk.Button(left, text="配置可选模型接口", command=self.configure_api)
        self.config_button.pack(fill="x", pady=8)
        tk.Label(left, text="默认：离线检索 + 原文摘录\n模型模式会发送问题和相关片段\n至你配置的接口，密钥不写入文件。", bg=BG, fg="#657e86", justify="left", font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(2, 0))

        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        tk.Label(right, text="02  提出问题", bg=BG, fg=INK, font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w", pady=(0, 10))
        self.question = tk.Text(right, height=3, wrap="word", bg="white", fg=INK, relief="flat", padx=12, pady=10, undo=True)
        self.question.pack(fill="x")
        self.question.bind("<Control-Return>", lambda event: self.ask())
        actions = tk.Frame(right, bg=BG)
        actions.pack(fill="x", pady=10)
        self.ask_button = ttk.Button(actions, text="查找答案  →", style="Accent.TButton", command=self.ask)
        self.ask_button.pack(side="left")
        tk.Label(actions, text="Ctrl + Enter", bg=BG, fg="#657e86").pack(side="left", padx=12)
        self.export_button = ttk.Button(actions, text="导出本次会话", command=self.export)
        self.export_button.pack(side="right")
        self.result_label = tk.Label(right, text="03  回答与出处", bg=BG, fg=INK, font=("Microsoft YaHei UI", 13, "bold"))
        self.result_label.pack(anchor="w", pady=(10, 10))
        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)
        self.answer_box = self._output(self.tabs)
        self.source_box = self._output(self.tabs)
        self.tabs.add(self.answer_box, text="回答")
        self.tabs.add(self.source_box, text="原文与出处")
        self._write(self.answer_box, "欢迎使用知页。\n\n左侧已加载两份自编演示资料。点击示例问题，即可查看相关原文；在「原文与出处」页签中可核对文件名和行号。\n\n也可以导入自己的 TXT / Markdown 资料。\n\n当前默认使用离线检索模式，不需要联网或 API Key。")
        self._write(self.source_box, "提问后会显示相关片段及原始行号。")

    def _output(self, parent):
        box = ScrolledText(parent, wrap="word", bg="white", fg=INK, relief="flat", padx=18, pady=16, font=("Microsoft YaHei UI", 11), spacing1=3, spacing3=8)
        box.configure(state="disabled")
        return box

    def _write(self, box, text):
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")

    def load_demo(self):
        self.engine = SearchEngine()
        for path in sorted((ROOT / "data").glob("*.md")):
            self.engine.add(path.name, read_document(path))
        self.refresh_library()

    def restore_demo(self):
        if self.busy:
            return
        self.load_demo()
        self.status.set("已恢复演示资料；之前导入的资料已从本次内存资料库中移除。")

    def refresh_library(self):
        self.library.delete(0, "end")
        for name in self.engine.documents:
            self.library.insert("end", "  " + name)
        self.stats.configure(text=f"{len(self.engine.documents)} 份资料 · {len(self.engine.chunks)} 个片段")

    def import_files(self):
        if self.busy:
            return
        paths = filedialog.askopenfilenames(title="导入课程资料", filetypes=[("文本资料", "*.txt *.md")])
        failures = []
        success = 0
        for name in paths:
            path = Path(name)
            try:
                # 保留绝对路径作为内部标识，避免不同目录的同名文件互相覆盖。
                self.engine.add(str(path.resolve()), read_document(path))
                success += 1
            except (OSError, ValueError) as exc:
                failures.append(f"{path.name}：{exc}")
        self.refresh_library()
        if paths:
            self.status.set(f"已导入 {success} 份资料。重复导入同一路径会更新内容。")
        if failures:
            messagebox.showwarning("部分资料未导入", "\n".join(failures))

    def ask_example(self, question):
        if self.busy:
            return
        self.question.delete("1.0", "end")
        self.question.insert("1.0", question)
        self.ask()

    def _set_busy(self, busy):
        self.busy = busy
        for widget in [self.ask_button, self.import_button, self.demo_button, self.config_button, self.mode_check, *self.example_buttons]:
            widget.configure(state="disabled" if busy else "normal")

    def ask(self):
        if self.busy:
            return
        question = self.question.get("1.0", "end").strip()
        if not question:
            self.status.set("请先输入问题。")
            self.question.focus_set()
            return
        if len(question) > 2000:
            self.status.set("问题请控制在 2000 字以内。")
            return
        enabled = self.use_model.get()
        if enabled and not (self.api["base"] and self.api["model"]):
            self.status.set("请先配置接口地址与模型名，或取消勾选以使用离线模式。")
            return
        hits = self.engine.search(question)
        api = self.api.copy()
        self._set_busy(True)
        self.status.set("正在检索并生成回答……" if enabled else "正在检索资料……")

        def work():
            try:
                mode = "大模型 + 资料检索" if enabled and hits else "离线检索 · 原文摘录"
                answer = model_answer(question, hits, api["base"], api["key"], api["model"]) if enabled and hits else extract_answer(hits)
                self.events.put(("result", question, answer, hits, mode))
            except Exception as exc:
                message = str(exc) if isinstance(exc, ValueError) else "处理失败，请检查资料或接口配置。"
                # 错误回退也明确标记为离线摘录。
                self.events.put(("result", question, f"模型未能完成回答：{message}\n\n已回退到离线检索：\n\n" + extract_answer(hits), hits, "离线检索（接口失败回退）"))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                _, question, answer, hits, mode = self.events.get_nowait()
                sources = format_sources(hits)
                self._write(self.answer_box, f"模式：{mode}\n问题：{question}\n\n{answer}\n\n—— 来源 ——\n" + "\n".join(f"[{i}] {h.chunk.source} · 第 {h.chunk.start_line}–{h.chunk.end_line} 行" for i, h in enumerate(hits, 1)))
                self._write(self.source_box, sources)
                self.tabs.select(self.answer_box)
                self.result_label.configure(text=f"03  回答与出处 · {len(hits)} 个相关片段")
                self.history.append(export_entry(question, answer, hits, mode))
                self.status.set(f"完成 · {mode} · 检索相似度不代表答案正确率，请核对原文。")
                self._set_busy(False)
        except queue.Empty:
            pass
        self._poll_id = self.after(100, self._poll)

    def export(self):
        if not self.history:
            self.status.set("还没有问答记录，请先提问。")
            return
        name = filedialog.asksaveasfilename(title="导出问答记录", defaultextension=".md", initialfile="知页问答记录.md", filetypes=[("Markdown", "*.md")])
        if name:
            try:
                Path(name).write_text("# 知页 · 问答记录\n\n" + "\n---\n\n".join(self.history), encoding="utf-8")
                self.status.set("问答记录已导出。")
            except OSError as exc:
                messagebox.showerror("导出失败", str(exc))

    def configure_api(self):
        if self.busy:
            return
        dialog = tk.Toplevel(self)
        dialog.title("可选模型接口（仅保存在本次进程内存中）")
        dialog.geometry("640x365")
        dialog.transient(self)
        dialog.grab_set()
        frame = tk.Frame(dialog, padx=24, pady=18)
        frame.pack(fill="both", expand=True)
        entries = {}
        for key, label in [("base", "接口基础地址（含 /v1 或服务商规定的前缀）"), ("model", "模型名称（由你的服务商提供）"), ("key", "API Key（本地服务可留空）")]:
            tk.Label(frame, text=label, anchor="w").pack(fill="x", pady=(4, 3))
            value = tk.StringVar(value=self.api[key])
            entries[key] = value
            tk.Entry(frame, textvariable=value, show="*" if key == "key" else "", relief="solid", borderwidth=1).pack(fill="x", ipady=5)
        tk.Label(frame, text="启用后，问题与检索到的片段将发送至此接口。\n关闭程序后清除本次填写的信息；导出记录不含密钥。", justify="left", fg="#657e86").pack(anchor="w", pady=12)

        def save():
            self.api = {key: value.get().strip() for key, value in entries.items()}
            self.status.set("接口已配置在内存中；勾选「使用大模型组织回答」后生效。")
            dialog.destroy()
        ttk.Button(frame, text="应用本次配置", command=save).pack(anchor="e")


if __name__ == "__main__":
    App().mainloop()
