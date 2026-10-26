"""Full-screen terminal UI with streamed answers and live model metrics."""

import asyncio
from threading import Event

from prompt_toolkit import Application
from prompt_toolkit.application import get_app
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import ConditionalContainer, HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea

from . import __version__
from .session import HELP
from .quota import duration

STYLE = Style.from_dict({
    "": "bg:#101419 #d5dce5", "brand": "#8cf2c4 bold", "muted": "#85929e",
    "tab": "#85929e", "tab.active": "bg:#8cf2c4 #101419 bold", "rule": "#29333c",
    "frame.border": "#43515e", "frame.label": "#8cf2c4", "input": "bg:#192129 #eef4fa",
    "sidebar": "#a4b3c1 bg:#141b22", "status": "#8cf2c4 bg:#192129",
    "completion-menu.completion": "bg:#25313c #d5dce5",
    "completion-menu.completion.current": "bg:#8cf2c4 #101419",
    "scrollbar.background": "bg:#192129", "scrollbar.button": "bg:#43515e",
})


class TerminalApp:
    def __init__(self, session):
        self.session = session
        self.view = "chat"
        self.busy = False
        self.job = "generation"
        self.draft = ""
        self.live_count = 0
        self.notice = "Ready · enter a question or /help"
        self.cancel = Event()
        self.body = TextArea(read_only=True, focusable=False, scrollbar=True, wrap_lines=True)
        self.input = TextArea(
            height=2, prompt=" › ", multiline=False, wrap_lines=False, style="class:input",
            history=InMemoryHistory(), accept_handler=self.submit,
            completer=WordCompleter(["/chat", "/tokens", "/model", "/stats", "/temperature",
                                     "/limit", "/topk", "/new", "/save", "/update", "/intent", "/help", "/exit"]),
            complete_while_typing=True,
        )
        self.input.buffer.on_text_changed += self.input_changed
        header = Window(FormattedTextControl(self.header), height=3)
        tabs = Window(FormattedTextControl(self.tabs), height=2)
        sidebar = ConditionalContainer(
            Window(FormattedTextControl(self.sidebar), width=28, style="class:sidebar"),
            filter=Condition(lambda: get_app().output.get_size().columns >= 100),
        )
        root = HSplit([
            header, tabs, Window(height=1, char="─", style="class:rule"),
            VSplit([self.body, sidebar], padding=1),
            Window(height=1, char="─", style="class:rule"),
            Frame(self.input, title="Message or command"),
            Window(FormattedTextControl(self.status), height=1, style="class:status"),
            Window(FormattedTextControl(" F1 Chat  F2 Tokens  F3 Models  F4 Usage  ·  /help  ·  Ctrl+D exit"),
                   height=1, style="class:muted"),
        ])
        bindings = KeyBindings()
        for key, view in (("f1", "chat"), ("f2", "tokens"), ("f3", "model"), ("f4", "stats")):
            bindings.add(key)(lambda event, selected=view: self.select(selected))

        @bindings.add("c-d")
        def close(event):
            self.close()

        @bindings.add("c-c")
        def interrupt(event):
            if self.busy:
                self.cancel.set()
                self.notice = "Stopping…"
            else:
                self.input.buffer.reset()
                self.notice = "Input cleared. Ctrl+D exits."
            self.app.invalidate()

        @bindings.add("pageup")
        def page_up(event):
            self.body.buffer.cursor_up(count=max(1, self.app.output.get_size().rows-12))

        @bindings.add("pagedown")
        def page_down(event):
            self.body.buffer.cursor_down(count=max(1, self.app.output.get_size().rows-12))

        self.app = Application(layout=Layout(root, focused_element=self.input),
                               key_bindings=bindings, style=STYLE, full_screen=True,
                               mouse_support=True, refresh_interval=1.0,
                               min_redraw_interval=0.03)
        self.refresh()

    def header(self):
        quota = self.session.quota.status()
        reset = duration(quota['resets_in_seconds']) if quota['resets_in_seconds'] is not None else 'after first message'
        return [("class:brand", "\n  λ  L A M B D A"),
                ("class:muted", f"   v{__version__}   /   local English AI\n"
                 f"  {quota['remaining']:,} / 1,000,000 tokens left · reset {reset}")]

    def tabs(self):
        tabs = []
        for shortcut, name, view in (("F1", "Chat", "chat"), ("F2", "Tokens", "tokens"),
                                     ("F3", "Models", "model"), ("F4", "Usage", "stats")):
            tabs.append(("class:tab.active" if self.view == view else "class:tab", f"  {shortcut} {name}  "))
            tabs.append(("", " "))
        return tabs

    def sidebar(self):
        engine = self.session.engine
        totals = self.session.totals()
        result = self.session.last_result
        used = result.context_used if result else 0
        blocks = round(used / engine.context * 18)
        quota = self.session.quota.status()
        reset = duration(quota['resets_in_seconds']) if quota['resets_in_seconds'] is not None else "starts on first message"
        return [("class:brand", f"\n  {engine.metadata.get('name', 'lambda 1.0').upper()}\n\n"),
                ("", f"  {engine.parameter_count:,} parameters\n"
                     f"  {len(engine.tokenizer.tokens):,} vocabulary tokens\n  CPU · float32 · BPE\n\n"),
                ("class:brand", "  TOKEN ALLOWANCE\n"),
                ("", f"  {quota['remaining']:,} remaining\n  of {quota['allowance']:,} / 10h\n"
                     f"  Reset: {reset}\n\n"),
                ("class:brand", "  CONTEXT\n"),
                ("", f"  {'█'*blocks}{'░'*(18-blocks)}\n  {used}/{engine.context} tokens\n\n"),
                ("class:brand", "  SESSION\n"),
                ("", f"  Responses   {totals['turns']}\n  Input       {totals['input']} tok\n"
                     f"  Output      {totals['output']} tok\n\n"),
                ("class:brand", "  GENERATION\n"),
                ("", f"  Temperature {self.session.settings.temperature:g}\n"
                     f"  Limit       {self.session.settings.max_tokens}\n"
                     f"  Top-k       {self.session.settings.top_k}\n\n"),
                ("class:muted", "  Each question stands alone.\n  History is not model memory.")]

    def status(self):
        if self.busy:
            return (f" ● Generating…  {self.live_count} tokens  ·  Ctrl+C cancel" if self.job == "generation"
                    else " ● " + self.notice + " · Ctrl+C cancel")
        q = self.session.quota.status()
        return f" {self.notice}  ·  {q['remaining']:,} tokens left"

    def chat_text(self):
        if not self.session.messages:
            return ("\n  Chat with your own local model.\n\n"
                    "  Start with a short English question:\n\n"
                    "    What is the internet?\n    What is a keyboard?\n    What is a cat?\n\n"
                    "  F2 inspects tokens. F3 lists models and parameters.\n"
                    "  /update checks for model updates.\n\n"
                    "  1,000,000 tokens / 10 hours · roughly 5,000 messages.\n\n"
                    "  Small experimental model. Answers may be incorrect.")
        blocks = []
        for role, text in self.session.messages:
            label = "YOU" if role == "You" else "λ LAMBDA" if role == "Lambda" else "·"
            blocks.append(f"  {label}\n  " + text.replace("\n", "\n  "))
        if self.busy:
            blocks.append("  λ LAMBDA\n  " + (self.draft or "…").replace("\n", "\n  "))
        return "\n\n".join(blocks) + "\n"

    def refresh(self):
        try:
            if self.view == "model":
                text = self.session.model_text()
            elif self.view == "stats":
                text = self.session.stats_text()
            elif self.view == "tokens":
                value = self.input.text if not self.input.text.startswith("/") else ""
                text = self.session.tokens_text(value)
            elif self.view == "help":
                text = HELP
            elif self.view == 'intent':
                text = self.session.intent_text()
            else:
                text = self.chat_text()
        except ValueError as error:
            text = str(error)
        if text != self.body.text:
            position = len(text) if self.view == "chat" else 0
            self.body.buffer.set_document(Document(text, position), bypass_readonly=True)
        if hasattr(self, "app"):
            self.app.invalidate()

    def select(self, view):
        self.view = view
        self.refresh()

    def input_changed(self, buffer):
        if self.view == "tokens":
            self.refresh()

    def close(self):
        self.cancel.set()
        self.app.exit()

    def submit(self, buffer):
        text = buffer.text.strip()
        if self.view == "model" and text.isdigit():
            text = "/model " + text
        if not text:
            return False
        if self.busy and text not in ("/exit", "/quit"):
            self.notice = "An operation is running. Ctrl+C cancels it."
            return True
        try:
            if text.startswith("/"):
                view, notice = self.session.command(text)
                if view == "exit":
                    self.close()
                    return False
                if view == "update" or view.startswith(("use:", "install:")):
                    self.busy = True
                    self.job = "update"
                    self.cancel = Event()
                    self.notice = "Checking models…"
                    buffer.reset()
                    self.app.create_background_task(self.update_models(view))
                    self.refresh()
                    return False
                if view:
                    self.view = view
                if notice:
                    self.notice = notice
                buffer.reset()
                self.refresh()
            else:
                self.session.add_user(text)
                self.view = "chat"
                self.busy = True
                self.job = "generation"
                self.draft = ""
                self.live_count = 0
                self.cancel = Event()
                buffer.reset()
                self.refresh()
                self.app.create_background_task(self.answer(text))
        except (ValueError, OSError) as error:
            self.notice = str(error)
            self.app.invalidate()
            return True
        return False

    def progress(self, text, count):
        if self.app.is_running:
            self.draft = text
            self.live_count = count
            self.refresh()

    async def answer(self, question):
        loop = asyncio.get_running_loop()
        try:
            result = await asyncio.to_thread(
                self.session.generate, question,
                lambda text, count: loop.call_soon_threadsafe(self.progress, text, count), self.cancel,
            )
            self.session.complete(result)
            state = "Cancelled" if result.finish_reason == "cancelled" else "Done"
            if result.intent:
                state += ' · ' + result.intent.title()
            self.notice = (f"{state} · input {len(result.prompt_ids)} tok · output {len(result.generated)} tok"
                           f" · {result.seconds:.2f} s · {result.tokens_per_second:.0f} tok/s")
            if result.context_dropped:
                self.notice += f" · dropped {result.context_dropped} input tokens"
        except (ValueError, OSError) as error:
            self.notice = str(error)
        finally:
            self.busy = False
            self.refresh()

    async def update_models(self, action):
        loop = asyncio.get_running_loop()
        def progress(message):
            loop.call_soon_threadsafe(self.update_notice, message)
        try:
            self.notice = await asyncio.to_thread(self.session.model_action, action, progress, self.cancel)
            self.view = "model"
        except (ValueError, OSError) as error:
            self.notice = f"Update failed: {error}"
        finally:
            self.busy = False
            self.refresh()

    def update_notice(self, message):
        self.notice = message
        self.app.invalidate()

    def run(self):
        self.app.run()
