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
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.mouse_events import MouseEventType
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea

from . import __version__
from .session import HELP
from .quota import duration

STYLE = Style.from_dict({
    "": "bg:#0c111b #dce5f2", "brand": "#80edc1 bold", "muted": "#8292a9",
    "tab": "bg:#141d2b #a6b5cb", "tab.active": "bg:#80edc1 #0c111b bold", "rule": "#253449",
    "frame.border": "#33455e", "frame.label": "#98b8ff bold", "input": "bg:#151f30 #f3f6fc",
    "sidebar": "#b3c1d6 bg:#101927", "status": "#b6c9e5 bg:#151f30",
    "quota.good": "#80edc1", "quota.low": "#f4c578", "quota.empty": "#ff8e9b",
    "quota.track": "#304057", "chat.user": "#96baff bold", "chat.ai": "#80edc1 bold",
    "chat.meta": "#8292a9", "welcome": "#98b8ff bold",
    "completion-menu.completion": "bg:#1e2d43 #dce5f2",
    "completion-menu.completion.current": "bg:#80edc1 #0c111b",
    "scrollbar.background": "bg:#151f30", "scrollbar.button": "bg:#435b7d",
})


def allowance_meter(remaining, allowance, width=24):
    """Remaining allowance, not usage. Clamp reservations and zero denominators."""
    ratio = max(0., min(1., remaining / allowance)) if allowance > 0 else 0.
    filled = round(ratio * width)
    style = 'quota.good' if ratio > .25 else 'quota.low' if ratio > .10 else 'quota.empty'
    return ratio, filled, style


class ConversationLexer(Lexer):
    def lex_document(self, document):
        def line(index):
            text = document.lines[index]
            stripped = text.strip()
            style = ('chat.user' if stripped.startswith('YOU  ·') else
                     'chat.ai' if stripped.startswith('LAMBDA  ·') else
                     'chat.meta' if stripped.startswith(('↳ ', '──', 'SYSTEM')) else
                     'welcome' if stripped == 'YOUR LOCAL WORKSPACE' else '')
            return [('class:'+style if style else '', text)]
        return line


class TerminalApp:
    def __init__(self, session):
        self.session = session
        self.view = "chat"
        self.busy = False
        self.job = "generation"
        self.draft = ""
        self.live_count = 0
        self.follow_output = True
        self.close_requested = False
        self.notice = "Ready · enter a question or /help"
        self.cancel = Event()
        self.body = TextArea(read_only=True, focusable=False, scrollbar=True, wrap_lines=True, lexer=ConversationLexer())
        self.input = TextArea(
            height=2, prompt=" › ", multiline=False, wrap_lines=False, style="class:input",
            history=InMemoryHistory(), accept_handler=self.submit,
            completer=WordCompleter(["/chat", "/chats", "/rename", "/tokens", "/model", "/stats", "/temperature",
                                     "/limit", "/topk", "/new", "/memory", "/save", "/update", "/updates", "/intent", "/help", "/exit"]),
            complete_while_typing=True,
        )
        self.input.buffer.on_text_changed += self.input_changed
        header = Window(FormattedTextControl(self.header), height=3)
        allowance = Window(FormattedTextControl(self.allowance), height=2)
        tabs = Window(FormattedTextControl(self.tabs), height=1)
        sidebar = ConditionalContainer(
            Window(FormattedTextControl(self.sidebar), width=30, style="class:sidebar"),
            filter=Condition(lambda: get_app().output.get_size().columns >= 110 and get_app().output.get_size().rows >= 28),
        )
        root = HSplit([
            header, allowance, Window(height=1), tabs, Window(height=1, char="─", style="class:rule"),
            VSplit([self.body, sidebar], padding=1),
            Window(height=1, char="─", style="class:rule"),
            Frame(self.input, title="Message  /  type / for commands"),
            Window(FormattedTextControl(self.status), height=1, style="class:status"),
            Window(FormattedTextControl(self.shortcuts),
                   height=1, style="class:muted"),
        ])
        bindings = KeyBindings()
        for key, view in (("f1", "chat"), ("f2", "tokens"), ("f3", "model"), ("f4", "stats"), ("f5", "updates"), ("f6", "chats")):
            bindings.add(key)(lambda event, selected=view: self.select(selected))

        @bindings.add("c-d")
        def close(event):
            self.close()

        @bindings.add("c-c")
        def interrupt(event):
            if self.session.updater.installing:
                self.notice = "App installation is finishing. Please wait."
            elif self.busy:
                self.cancel.set()
                self.notice = "Stopping…"
            else:
                self.input.buffer.reset()
                self.notice = "Input cleared. Ctrl+D exits."
            self.app.invalidate()

        @bindings.add("pageup")
        def page_up(event):
            self.follow_output = False
            self.body.buffer.cursor_up(count=max(1, self.app.output.get_size().rows-12))

        @bindings.add("pagedown")
        def page_down(event):
            self.body.buffer.cursor_down(count=max(1, self.app.output.get_size().rows-12))
            self.follow_output = self.body.buffer.document.is_cursor_at_the_end

        @bindings.add("c-end")
        def follow(event):
            self.follow_output = True
            self.body.buffer.cursor_position = len(self.body.text)

        self.app = Application(layout=Layout(root, focused_element=self.input),
                               key_bindings=bindings, style=STYLE, full_screen=True,
                               mouse_support=True, refresh_interval=1.0,
                               min_redraw_interval=0.03)
        self.refresh()

    def header(self):
        model = self.session.engine.metadata.get('name', 'Local model')
        state = 'WORKING' if self.busy else 'READY'
        return [("class:brand", "\n  λ  LAMBDA"),
                ("class:muted", f"   /   {model}   ·   app {__version__}\n"),
                ("class:quota.good", f"  ● {state}"),
                ("class:muted", "   "+self.session.chat_title[:max(12, get_app().output.get_size().columns-16)])]

    def allowance(self):
        q = self.session.quota.status()
        width = 24 if get_app().output.get_size().columns >= 80 else 12
        ratio, filled, style = allowance_meter(q['remaining'], q['allowance'], width)
        reset = duration(q['resets_in_seconds']) if q['resets_in_seconds'] is not None else 'after first message'
        return [("class:muted", "  ALLOWANCE  "), ("class:"+style, '━'*filled),
                ("class:quota.track", '━'*(width-filled)), ("class:"+style, f"  {ratio:.1%} left\n"),
                ("class:muted", f"  {q['remaining']:,} / {q['allowance']:,} tokens · reset {reset}")]

    def shortcuts(self):
        return (" Enter send · /help · Ctrl+D exit" if get_app().output.get_size().columns < 75 else
                " Enter send  ·  /help  ·  PgUp history  ·  Ctrl+End latest  ·  Ctrl+D exit")

    def tabs(self):
        tabs = []
        compact = get_app().output.get_size().columns < 75
        for shortcut, name, view in (("F1", "Chat", "chat"), ("F2", "Tokens", "tokens"),
                                     ("F3", "Models", "model"), ("F4", "Usage", "stats"),
                                     ("F5", "Updates", "updates"), ("F6", "Chats", "chats")):
            def click(event, selected=view):
                if event.event_type == MouseEventType.MOUSE_UP:
                    self.select(selected)
            label = f" {name} " if compact else f" {shortcut} {name} "
            tabs.append(("class:tab.active" if self.view == view else "class:tab", label, click))
            tabs.append(("", " "))
        return tabs

    def sidebar(self):
        engine = self.session.engine
        totals = self.session.totals()
        result = self.session.last_result
        used = result.context_used if result else 0
        blocks = min(18, round(used / engine.context * 18))
        return [("class:brand", "\n  MODEL\n"),
                ("", f"  {engine.metadata.get('name', 'Local model')}\n"
                     f"  {engine.parameter_count/1e6:.2f}M parameters\n"
                     f"  {len(engine.tokenizer.tokens):,} vocabulary tokens\n\n"),
                ("class:brand", "  CONTEXT\n"),
                ("class:quota.good", f"  {'━'*blocks}"),
                ("class:quota.track", f"{'━'*(18-blocks)}\n"),
                ("", f"  {used:,} / {engine.context:,} tokens\n\n"),
                ("class:brand", "  SESSION\n"),
                ("", f"  {totals['turns']} replies\n"
                     f"  {totals['output']:,} output tokens\n"
                     f"  {totals['speed']:.1f} tokens / second\n\n"),
                ("class:muted", "  F3  Model details\n  F4  Token usage\n  F5  App & model updates\n  F6  Saved local chats")]

    def status(self):
        if self.busy:
            return (f" ● Generating…  {self.live_count} tokens  ·  Ctrl+C cancel" if self.job == "generation"
                    else " ● " + self.notice + ("" if self.session.updater.installing else " · Ctrl+C cancel"))
        q = self.session.quota.status()
        return f" {self.notice}  ·  {q['remaining']:,} tokens left"

    def chat_text(self):
        if not self.session.messages:
            return ("\n  YOUR LOCAL WORKSPACE\n\n"
                    "  Start a conversation in English.\n"
                    "  Your model runs on this computer.\n\n"
                    "  EXPLORE\n"
                    "  /model     Choose a model and inspect parameters\n"
                    "  /tokens    See how your message becomes tokens\n"
                    "  /stats     Check allowance and session usage\n"
                    "  /update    Update the app and installed models\n\n"
                    "  /chats     Open a saved local conversation\n"
                    "  /new starts another saved conversation.\n"
                    "  Experimental model · answers can be incorrect.")
        blocks = []
        reply = 0
        for role, text in self.session.messages:
            label = ("YOU  ·  message" if role == "You" else
                     f"LAMBDA  ·  {self.session.turns[reply].get('model') or 'local model'}"
                     if role == "Lambda" and reply < len(self.session.turns) else
                     "LAMBDA  ·  response" if role == "Lambda" else "SYSTEM")
            block = f"  {label}\n\n  " + text.replace("\n", "\n  ")
            if role == 'Lambda' and reply < len(self.session.turns):
                turn = self.session.turns[reply]
                block += f"\n\n  ↳ {turn['generated_tokens']} tokens · {turn['seconds']:.2f}s"
                reply += 1
            blocks.append(block)
        if self.busy and self.job == 'generation':
            blocks.append("  LAMBDA  ·  generating\n\n  " + (self.draft or "Thinking…").replace("\n", "\n  "))
        return "\n\n  ────────────────────────\n\n".join(blocks) + "\n"

    def refresh(self):
        try:
            if self.view == "model":
                text = self.session.model_text()
            elif self.view == "stats":
                text = self.session.stats_text()
            elif self.view == "tokens":
                value = self.input.text if not self.input.text.startswith("/") else ""
                text = self.session.tokens_text(value)
            elif self.view == "updates":
                text = self.session.updates_text()
            elif self.view == "chats":
                text = self.session.chats_text()
            elif self.view == "help":
                text = HELP
            elif self.view == 'intent':
                text = self.session.intent_text()
            else:
                text = self.chat_text()
        except ValueError as error:
            text = str(error)
        if text != self.body.text:
            position = (len(text) if self.follow_output else min(self.body.buffer.cursor_position, len(text))) if self.view == "chat" else 0
            if self.view == "chat" and not self.session.messages:
                position = 0
            if self.view == "updates" and self.busy and self.follow_output:
                position = len(text)
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
        if self.session.updater.installing:
            self.notice = "App installation is finishing. Please wait before exiting."
            self.app.invalidate()
            return
        if self.busy:
            self.close_requested = True
            self.cancel.set()
            self.notice = "Stopping and saving before exit…"
            self.app.invalidate()
            return
        self.cancel.set()
        self.app.exit()

    def submit(self, buffer):
        text = buffer.text.strip()
        if self.view == "model" and text.isdigit():
            text = "/model " + text
        if self.view == "chats" and text.isdigit():
            text = "/chat " + text
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
                    self.notice = "Checking updates…"
                    if view == "update":
                        self.view = "updates"
                        self.follow_output = True
                    buffer.reset()
                    self.app.create_background_task(self.update_models(view))
                    self.refresh()
                    return False
                if view:
                    self.view = view
                    if view == 'chat':
                        self.follow_output = True
                if notice:
                    self.notice = notice
                buffer.reset()
                self.refresh()
            else:
                self.session.add_user(text)
                self.view = "chat"
                self.follow_output = True
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
            if self.session.persistence_notice:
                self.notice += ' · ' + self.session.persistence_notice
            if result.context_dropped:
                self.notice += f" · dropped {result.context_dropped} input tokens"
        except (ValueError, OSError) as error:
            self.notice = str(error)
        finally:
            self.busy = False
            self.refresh()
            if self.close_requested:
                self.app.exit()

    async def update_models(self, action):
        loop = asyncio.get_running_loop()
        def progress(message):
            loop.call_soon_threadsafe(self.update_notice, message)
        try:
            result = await asyncio.to_thread(self.session.model_action, action, progress, self.cancel)
            self.view = "updates" if action == "update" else "model"
            self.notice = (("Update finished with errors · see activity above" if self.session.update_failed else
                            "Update check finished · see activity above") if action == "update" else result)
        except (ValueError, OSError) as error:
            self.notice = f"Update failed: {error}"
        finally:
            self.busy = False
            self.refresh()
            if self.close_requested:
                self.app.exit()

    def update_notice(self, message):
        self.notice = message
        if self.view == "updates":
            self.refresh()
        else:
            self.app.invalidate()

    def run(self):
        self.app.run()
