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
from .model_browser import ModelBrowser
from .quota import duration

STYLE = Style.from_dict({
    "": "bg:#0c111b #dce5f2", "brand": "#80edc1 bold", "muted": "#8292a9",
    "tab": "bg:#141d2b #a6b5cb", "tab.active": "bg:#80edc1 #0c111b bold", "rule": "#253449",
    "frame.border": "#33455e", "frame.label": "#98b8ff bold", "input": "bg:#151f30 #f3f6fc",
    "sidebar": "#b3c1d6 bg:#101927", "status": "#b6c9e5 bg:#151f30",
    "quota.good": "#80edc1", "quota.low": "#f4c578", "quota.empty": "#ff8e9b",
    "quota.track": "#304057", "chat.user": "#96baff bold", "chat.ai": "#80edc1 bold",
    "chat.meta": "#8292a9", "menu.selected": "bg:#233d4d #80edc1 bold", "welcome": "#98b8ff bold",
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
            style = ('menu.selected' if stripped.startswith('›') else
                     'chat.user' if stripped.startswith('YOU  ·') else
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
        self.models = ModelBrowser(session.manager)
        self.chat_index = 0
        self.edit_turn = None
        self.notice = "Ready · enter a question or /help"
        self.cancel = Event()
        self.body = TextArea(read_only=True, focusable=False, scrollbar=True, wrap_lines=True, lexer=ConversationLexer())
        self.input = TextArea(
            height=2, prompt=" › ", multiline=False, wrap_lines=False, style="class:input",
            history=InMemoryHistory(), accept_handler=self.submit,
            completer=WordCompleter(["/chat", "/chats", "/rename", "/search", "/pin", "/edit", "/retry", "/tokens", "/model", "/stats", "/temperature",
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
            Window(FormattedTextControl(self.actions), height=1),
            Frame(self.input, title=self.input_title),
            Window(FormattedTextControl(self.status), height=1, style="class:status"),
            Window(FormattedTextControl(self.shortcuts),
                   height=1, style="class:muted"),
        ])
        bindings = KeyBindings()
        for key, view in (("f1", "chat"), ("f2", "tokens"), ("f3", "model"), ("f4", "stats"), ("f5", "updates"), ("f6", "chats")):
            bindings.add(key)(lambda event, selected=view: self.select(selected))

        menu = Condition(lambda: self.view in ('model','chats') and not self.input.text and not self.busy)
        @bindings.add('up', filter=menu)
        def menu_up(event):self.move_choice(-1)
        @bindings.add('down', filter=menu)
        def menu_down(event):self.move_choice(1)
        @bindings.add('enter', filter=menu)
        def menu_enter(event):self.activate_choice()
        @bindings.add('right', filter=menu)
        def menu_right(event):self.activate_choice()
        @bindings.add('left', filter=menu)
        @bindings.add('backspace', filter=menu)
        def menu_back(event):
            if self.view=='model' and self.models.back():self.refresh()
            else:self.select('chat')
        @bindings.add('escape', filter=Condition(lambda: self.edit_turn is not None or (self.view in ('model','chats') and not self.input.text)))
        def escape(event):
            if self.edit_turn is not None:self.cancel_edit()
            elif self.view=='model' and self.models.back():self.refresh()
            else:self.select('chat')
        @bindings.add('c-p', filter=Condition(lambda: self.view=='chats' and not self.input.text and not self.busy))
        def pin(event):self.pin_selected()
        @bindings.add('c-r', filter=Condition(lambda: self.view=='chat' and not self.busy))
        def retry(event):self.retry()
        @bindings.add('c-e', filter=Condition(lambda: self.view=='chat' and not self.busy))
        def edit(event):self.begin_edit()
        @bindings.add('c-n')
        def new(event):
            if not self.busy:
                self.session.command('/new');self.edit_turn=None;self.input.buffer.reset();self.select('chat')

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
                self.input.buffer.reset();self.edit_turn=None
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

    def input_title(self):
        if self.edit_turn is None:
            if self.view=="model":return "Models / arrows or a row number"
            if self.view=="chats":return "Chats / search words or a row number"
        return (f"Edit question {self.edit_turn} · Enter resend · Esc cancel" if self.edit_turn else
                "Message  /  type / for commands")

    def actions(self):
        if self.view in ('model','chats'):
            return [('class:muted',' ↑/↓ select · Enter open · ←/Esc back' + (' · Ctrl+P pin · /search words' if self.view=='chats' else ''))]
        if self.view!='chat':return [('class:muted',' F1 Chat · /help commands')]
        def action(fn):
            def clicked(event):
                if event.event_type==MouseEventType.MOUSE_UP and not self.busy:fn()
            return clicked
        def new():
            self.session.command('/new');self.edit_turn=None;self.input.buffer.reset();self.select('chat')
        return [('class:tab',' New chat ',action(new)),('', '  '),
                ('class:tab',' Regenerate ',action(self.retry)),('', '  '),
                ('class:tab',' Edit question ',action(self.begin_edit))]

    def chat_rows(self):
        rows=self.session.store.list(self.session.chat_query) if self.session.store else []
        self.chat_index=max(0,min(self.chat_index,len(rows)-1)) if rows else 0
        return rows

    def move_choice(self,delta):
        if self.view=='model':self.models.move(delta)
        else:
            rows=self.chat_rows();self.chat_index=max(0,min(len(rows)-1,self.chat_index+delta)) if rows else 0
        self.refresh()

    def activate_choice(self,index=None):
        if self.busy:return
        try:
            if self.view=='model':
                action=self.models.choose(index)
                if action:self.start_model_action(action)
                else:self.refresh()
            else:
                choices=self.session.chat_choices;i=self.chat_index if index is None else index
                if not 0<=i<len(choices):raise ValueError('No matching chat. Use /search to clear the filter.')
                self.session.open_chat(choices[i]);self.edit_turn=None;self.input.buffer.reset();self.select('chat')
        except (ValueError,OSError) as error:self.notice=str(error);self.app.invalidate()

    def pin_selected(self):
        try:
            choices=self.session.chat_choices
            if not 0<=self.chat_index<len(choices):return
            identifier=choices[self.chat_index];pinned=self.session.pin_chat(identifier)
            updated=self.session.store.list(self.session.chat_query)
            self.chat_index=next((i for i,row in enumerate(updated) if row['id']==identifier),0)
            self.notice='Chat pinned.' if pinned else 'Chat unpinned.';self.refresh()
        except (ValueError,OSError) as error:self.notice=str(error);self.app.invalidate()

    def begin_edit(self,number=None):
        if self.busy:return
        if self.input.text and self.edit_turn is None:
            self.notice='Send or clear your draft before editing a previous question.';self.app.invalidate();return
        number=number or len(self.session.turns)
        if not 1<=number<=len(self.session.turns):
            self.notice='There is no question to edit yet.';self.app.invalidate();return
        self.edit_turn=number;question=self.session.turns[number-1]['question']
        self.input.buffer.set_document(Document(question,len(question)))
        self.notice='Edit the question. Resending creates a new chat branch.';self.select('chat')

    def cancel_edit(self):
        self.edit_turn=None;self.input.buffer.reset();self.notice='Edit cancelled.';self.refresh()

    def retry(self):
        if self.busy:return
        if self.input.text:
            self.notice='Send or clear your draft before regenerating.';self.app.invalidate();return
        try:self.start_answer(None,number=len(self.session.turns),kind='retry')
        except (ValueError,OSError) as error:self.notice=str(error);self.app.invalidate()

    def start_answer(self,question,number=None,kind='edit'):
        if number is not None:question=self.session.prepare_revision(number,question,kind)
        self.session.add_user(question)
        self.view='chat';self.follow_output=True;self.busy=True;self.job='generation'
        self.draft='';self.live_count=0;self.cancel=Event();self.edit_turn=None
        self.input.buffer.reset();self.refresh()
        self.app.create_background_task(self.answer(question))

    def start_model_action(self,action):
        self.busy=True;self.job='update';self.cancel=Event();self.notice='Checking models…'
        self.input.buffer.reset();self.app.create_background_task(self.update_models(action));self.refresh()

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
        if self.view in ("model","chats"):return " ↑/↓ select · Enter open · ←/Esc back · /help · Ctrl+D exit"
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
        for index,(role,text) in enumerate(self.session.messages):
            numbered=(role=="You" and reply<len(self.session.turns) and self.session.turns[reply]["question"]==text
                      and index+1<len(self.session.messages) and self.session.messages[index+1][0]=="Lambda")
            user_label=f"YOU  ·  message {reply+1}" if numbered else "YOU  ·  message"
            label = (user_label if role == "You" else
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
                details=self.session.model_text()
                details=details[details.index('CURRENT MODEL /'):]
                text=self.models.text(self.session.engine.metadata.get('model_id'))+'\n\n'+details
            elif self.view == "stats":
                text = self.session.stats_text()
            elif self.view == "tokens":
                value = self.input.text if not self.input.text.startswith("/") else ""
                text = self.session.tokens_text(value)
            elif self.view == "updates":
                text = self.session.updates_text()
            elif self.view == "chats":
                rows=self.chat_rows()
                selected=rows[self.chat_index]['id'] if rows else None
                text = self.session.chats_text(selected)
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
            if self.view in ('model','chats'):
                selected_line=next((i for i,line in enumerate(text.splitlines()) if line.strip().startswith('›')),None)
                if selected_line is not None:position=sum(len(line)+1 for line in text.splitlines()[:selected_line])
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
        text=buffer.text.strip()
        if not text:return False
        if self.busy and text not in ('/exit','/quit'):
            self.notice='An operation is running. Ctrl+C cancels it.';return True
        try:
            if self.edit_turn is not None and not text.startswith('/'):
                self.start_answer(text,number=self.edit_turn);return False
            if self.view=='model' and text.isdigit():
                self.activate_choice(int(text)-1);buffer.reset();return False
            if self.view=='chats' and not text.startswith('/'):
                if text.isdigit():self.activate_choice(int(text)-1)
                else:self.session.command('/search '+text);self.chat_index=0;self.refresh()
                buffer.reset();return False
            if text.startswith('/'):
                view,notice=self.session.command(text)
                if view=='exit':self.close();return False
                if view=='edit':
                    buffer.reset();self.begin_edit(int(notice));return True
                if view=='retry':
                    buffer.reset();self.retry();return False
                if view.startswith('revise:'):
                    self.start_answer(notice,number=int(view.split(':')[1]));return False
                if view=='update' or view.startswith(('use:','install:')):
                    if view=='update':self.view='updates';self.follow_output=True
                    self.start_model_action(view);return False
                if view:
                    self.view=view
                    if view=='chat':self.follow_output=True;self.edit_turn=None
                    if view=='chats':self.chat_index=0
                if notice:self.notice=notice
                buffer.reset();self.refresh()
            else:self.start_answer(text)
        except (ValueError,OSError) as error:
            self.notice=str(error);self.app.invalidate();return True
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
