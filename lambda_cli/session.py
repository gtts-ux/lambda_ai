"""Shared chat state, commands, persistent allowance and model selection."""
from dataclasses import asdict
from datetime import datetime
import json
import math
from pathlib import Path

from .engine import Engine, Settings, prompt_for
from .models import ModelManager
from .app_updates import AppUpdater
from .chats import ChatConflict
from .quota import Quota, duration

HELP = """KEYBOARD

F1             Chat
F2             Input and generated token inspector
F3             Models, parameters and model selection
F4             Allowance and session statistics
F5             Application and model updates
F6             Saved local chats
Enter          Send a question or run a command
Ctrl+C         Cancel generation / clear the input
Ctrl+D         Exit
PgUp / PgDn    Scroll

COMMANDS

/chat                     Return to chat
/chats                    List saved local conversations
/chat <number or id>      Open a saved conversation
/rename <title>           Rename the current conversation
/tokens [text]            Inspect BPE tokens
/intent [text]            Inspect learned chat/math routing
/model                    List models and show parameters
/model use lambda-1.0     Switch models (install if needed)
/model install <id>       Download a listed model
/update                   Update the application and installed models
/updates                  Show update progress and the last result
/stats                    Allowance, reset time and session usage
/temperature 0.4          Set temperature: 0.05–2
/limit 120                Set output limit: 1–2048 tokens
/topk 8                   Set top-k; 0 uses all tokens
/new                      Start a new saved chat
/memory                   Show whether this model uses conversation context
/save [filename.json]     Export this conversation
/help                     Show this help
/exit                     Exit

Allowance: 1,000,000 input + generated tokens per OS user every 10 hours,
starting with the first message. This is roughly 5,000 messages at 200 tokens
per exchange. Input is charged only for the context actually used.
Transformer models use recent completed exchanges within their context window.
Older MLP models process each question separately. /memory shows the current mode.
"""


def token_table(tokenizer, ids):
    rows = ["  #      ID   PIECE", "  ──     ──   ──────────────────────────────────"]
    for number, idx in enumerate(ids[:512], 1):
        rows.append(f"  {number:<5} {idx:<5} {json.dumps(tokenizer.tokens[idx], ensure_ascii=False)}")
    if len(ids) > 512:
        rows.append(f"  … {len(ids)-512} more tokens; showing the first 512.")
    return "\n".join(rows)


class Session:
    def __init__(self, engine, settings=None, quota=None, manager=None, updater=None, store=None, resume=False):
        self.engine = engine
        self.settings = settings or Settings()
        self.settings.validate()
        self.quota = quota or Quota()
        self.manager = manager or ModelManager()
        self.updater = updater or AppUpdater()
        self.update_log = []
        self.update_failed = False
        self.messages, self.turns = [], []
        self.last_question = self.inspected_text = ""
        self.last_result = None
        self.memory_start = 0
        self.store = store
        self.chat_id = None
        self.chat_revision = 0
        self.chat_title = 'New chat'
        self.persistence_notice = ''
        self.chat_choices = []
        if store is not None:
            if resume and store.active():
                self.open_chat(store.active())
            else:
                self.persist()

    def snapshot(self):
        try:
            managed = self.engine.path == self.manager.resolve(self.engine.metadata.get('model_id')).resolve()
        except (ValueError, OSError):
            managed = False
        return {'schema': 1, 'model_id': self.engine.metadata.get('model_id'),
                'model_name': self.engine.metadata.get('name'), 'model_path': str(self.engine.path),
                'custom_model': not managed,
                'settings': asdict(self.settings), 'messages': self.messages, 'turns': self.turns,
                'memory_start': self.memory_start, 'last_question': self.last_question}

    def persist(self):
        if self.store is None:
            return
        payload = self.snapshot()
        if self.chat_id is None:
            row = self.store.create(payload, self.chat_title)
            self.chat_id, self.chat_revision = row['id'], row['revision']
            return
        try:
            self.chat_revision = self.store.save(self.chat_id, self.chat_revision, self.chat_title, payload)
        except ChatConflict:
            # Preserve both windows' work instead of overwriting a newer snapshot.
            self.chat_title += ' (copy)'
            row = self.store.create(payload, self.chat_title)
            self.chat_id, self.chat_revision = row['id'], row['revision']
            self.persistence_notice = 'Another window changed this chat; your work was saved as a separate copy.'

    def open_chat(self, reference):
        if self.store is None:
            raise ValueError('Saved chats are available in interactive mode: run lambda.')
        if reference.isdigit() and len(reference) < 8:
            choices = self.chat_choices or [row['id'] for row in self.store.list()]
            index = int(reference)-1
            if not 0 <= index < len(choices):
                raise ValueError('Choose a chat number from /chats.')
            reference = choices[index]
        row = self.store.get(reference)
        if row['id'] == self.chat_id:
            return
        p = row['payload']
        try:
            if p['schema'] != 1 or not isinstance(p['messages'], list) or not isinstance(p['turns'], list):
                raise ValueError('Unsupported chat data.')
            for message in p['messages']:
                if len(message) != 2 or message[0] not in ('You','Lambda','System') or not isinstance(message[1],str):
                    raise ValueError('Invalid chat message.')
            for turn in p['turns']:
                if not isinstance(turn['question'],str) or not isinstance(turn['text'],str):
                    raise ValueError('Invalid conversation turn.')
                if not math.isfinite(turn['seconds']) or turn['seconds'] < 0:
                    raise ValueError('Invalid conversation timing.')
                if any(type(turn[k]) is not int or turn[k] < 0 for k in ('prompt_tokens','generated_tokens')):
                    raise ValueError('Invalid conversation token count.')
            settings = Settings(**p['settings'])
            settings.validate()
            if type(p['memory_start']) is not int or not 0 <= p['memory_start'] <= len(p['turns']):
                raise ValueError('Invalid conversation context boundary.')
            if not isinstance(p['last_question'],str):
                raise ValueError('Invalid last question.')
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f'Cannot open this chat: {error}. Its saved data was kept.') from error
        identifier = p.get('model_id')
        try:
            engine = Engine(p['model_path']) if p.get('custom_model') or not identifier else Engine(self.manager.resolve(identifier))
        except (ValueError, OSError) as error:
            if p.get('custom_model') or not identifier:
                raise ValueError(f"This chat needs its saved model file: {p.get('model_path')}. Restore that file to reopen the chat.") from error
            raise ValueError(f"This chat needs {p.get('model_name', 'its saved model')}. Install it with /model install {identifier}, then open the chat again.") from error
        if self.chat_id is not None:
            self.persist()
        if identifier and not p.get('custom_model'):
            engine = self.manager.activate(identifier)
        self.engine, self.settings = engine, settings
        self.messages = [tuple(message) for message in p['messages']]
        self.turns = p['turns']
        self.memory_start = p['memory_start']
        self.last_question, self.inspected_text = p['last_question'], ''
        # Old token IDs are never decoded using a potentially updated tokenizer.
        self.last_result = None
        self.chat_id, self.chat_revision, self.chat_title = row['id'], row['revision'], row['title']
        self.persistence_notice = ''
        self.store.set_active(self.chat_id)

    def chats_text(self):
        if self.store is None:
            return 'LOCAL CHATS\n\n  Run lambda to save and resume conversations.'
        lines = ['LOCAL CHATS', '', '  Enter a number to open a chat, or use /chat <id>.',
                 '  /new starts another conversation. /rename changes its title.', '']
        rows = self.store.list()
        self.chat_choices = [row['id'] for row in rows]
        for i, row in enumerate(rows, 1):
            selected = ' [current]' if row['id'] == self.chat_id else ''
            updated = datetime.fromtimestamp(row['updated']).strftime('%b %d, %H:%M')
            lines += [f"  {i}. {row['title']}{selected}",
                      f"     {row['model_name']} · {row['turns']} replies · {updated}",
                      f"     /chat {row['id'][:8]}", '']
        return '\n'.join(lines)

    def add_user(self, question):
        if len(question) > 20000:
            raise ValueError("A question may contain at most 20,000 characters.")
        prompt = self.build_prompt(question)
        ids = prompt if isinstance(prompt, list) else self.engine.tokenizer.encode(prompt)
        status = self.quota.status()
        if status["remaining"] <= min(len(ids), self.engine.context):
            from .quota import QuotaExceeded
            raise QuotaExceeded("Token allowance exhausted. Resets in " + duration(status["resets_in_seconds"] or 0) + ".")
        self.last_question = question
        self.messages.append(("You", question))
        if self.chat_title == 'New chat':
            self.chat_title = ''.join(c for c in ' '.join(question.split()) if c.isprintable())[:72] or 'New chat'
        self.persist()

    def generate(self, question, on_text=None, cancel=None):
        prompt = self.build_prompt(question)
        ids = prompt if isinstance(prompt, list) else self.engine.tokenizer.encode(prompt)
        input_tokens = min(len(ids), self.engine.context)
        reservation = self.quota.reserve(input_tokens, self.settings.max_tokens)
        settings = Settings(**asdict(self.settings))
        settings.max_tokens = reservation.max_output
        sampled = 0
        def progress(text, count):
            nonlocal sampled
            sampled = count
            if on_text:
                on_text(text, count)
        try:
            result = self.engine.generate(prompt, settings, progress, cancel)
            result.charged_tokens = result.context_used + len(result.generated) if result.generated else 0
            self.quota.complete(reservation, result.charged_tokens)
            return result
        except BaseException:
            self.quota.complete(reservation, input_tokens + sampled if sampled else 0)
            raise

    def complete(self, result):
        self.last_result = result
        self.turns.append({"question": self.last_question, "model": self.engine.metadata.get("model_id"), **result.to_dict()})
        self.messages.append(("Lambda", result.text or "[Empty response]"))
        self.persist()

    def build_prompt(self, question):
        if getattr(self.engine, "supports_memory", False):
            from .byte_tokenizer import conversation_prompt
            turns = [(t["question"], t["text"]) for t in self.turns[self.memory_start:]
                     if t.get("finish_reason") != "cancelled" and t.get("text")]
            return conversation_prompt(self.engine.tokenizer, turns, question, self.engine.context)
        return prompt_for(question)

    def memory_text(self):
        if not getattr(self.engine, "supports_memory", False):
            return "This MLP model processes each question separately. Select a trained Transformer for conversation context."
        return (f"CONVERSATION CONTEXT / {self.engine.context} TOKENS\n\n"
                "  Recent completed questions and answers are included with each message.\n"
                "  Old exchanges are dropped when the context window is full.\n"
                "  Interactive chats are saved locally and can be reopened with /chats.\n"
                "  /new starts another chat. The context window still limits each reply.\n"
                "  /save exports it to a file; it does not create permanent model memory.\n"
                "  Included history uses the existing token allowance. Weights never change during chat.")

    def totals(self):
        seconds = sum(t["seconds"] for t in self.turns)
        output = sum(t["generated_tokens"] for t in self.turns)
        return {"turns": len(self.turns), "input": sum(t["prompt_tokens"] for t in self.turns),
                "output": output, "seconds": seconds, "speed": output/seconds if seconds else 0}

    def reload_model(self, identifier=None):
        self.engine = Engine(self.manager.resolve(identifier))
        self.memory_start = len(self.turns)
        # A new model can have a different vocabulary. Do not decode old IDs with it.
        self.last_result = None
        self.inspected_text = ""
        self.persist()

    def model_action(self, action, progress=None, cancel=None):
        if action == "update":
            self.update_log = []
            self.update_failed = False
            def report(message):
                if message.startswith('Downloading ') and self.update_log and self.update_log[-1].startswith('Downloading '):
                    self.update_log[-1] = message
                else:
                    self.update_log.append(message)
                if progress:
                    progress(message)
            results = []
            before = self.manager.state()
            model_id = self.engine.metadata.get('model_id') if not self.snapshot()['custom_model'] else None
            for name, operation in [('Models', self.manager.update), ('Application', self.updater.update)]:
                if cancel is not None and cancel.is_set():
                    report('Update cancelled before the next stage.')
                    break
                try:
                    message = operation(report, cancel)
                except (ValueError, OSError) as error:
                    self.update_failed = True
                    message = f'{name} update failed: {error}'
                results.append(message)
                report(message)
                if name == 'Models':
                    after = self.manager.state()
                    if model_id and before['installed'].get(model_id) != after['installed'].get(model_id):
                        self.reload_model(model_id)
            return '\n'.join(results) or 'Update cancelled.'
        verb, identifier = action.split(":", 1)
        self.manager.install(identifier, progress, cancel)
        if verb == "use":
            engine = self.manager.activate(identifier)
            changed = engine.path != self.engine.path
            self.engine = engine
            if changed:
                self.memory_start = len(self.turns)
                self.last_result = None
                self.inspected_text = ''
            self.persist()
            return f"Using {self.engine.metadata.get('name', identifier)}."
        return f"Installed {identifier}. Use /model use {identifier} to switch."

    def updates_text(self):
        from . import __version__
        lines = ['APPLICATION & MODEL UPDATES', '', f'  Running app   {__version__}',
                 f"  Active model  {self.engine.metadata.get('name', 'Unknown')}", '',
                 '  /update checks the app, the model list and installed model revisions.',
                 '  App downloads are verified before installation.',
                 '  Restart Lambda after an app upgrade. Your models and allowance stay.', '',
                 'UPDATE ACTIVITY', '']
        lines.extend('  '+line for line in self.update_log)
        if not self.update_log:
            lines.append('  No update check in this session. Enter /update to begin.')
        return '\n'.join(lines)

    def model_text(self):
        info = self.engine.info()
        custom = self.snapshot()['custom_model']
        lines = ["MODELS / AVAILABLE CHOICES", ""]
        for number, item in enumerate(self.manager.entries(), 1):
            state = "active" if not custom and item['id'] == info.get('model_id') else "installed" if item["installed_revision"] else "available to download"
            if item["update_available"]:
                state += " · update available"
            lines.append(f"  {number}. {item['name']}  [{state}]  /model use {item['id']}")
        lines += ["", "  /update refreshes this list. New models appear when the maintainer publishes them.",
                  "  Type a choice number here or use /model use <id>.", "", f"CURRENT MODEL / {info['name']}", "",
                  f"  Architecture         {info['architecture']}", f"  Parameters           {info['parameters']:,}",
                  f"  Vocabulary           {info['vocabulary']:,} BPE tokens", f"  Context              {info['context']} tokens",
                  f"  Embedding            {info['embedding']}",
                  (f"  Transformer blocks   {info['layers']} × width {info['hidden']}" if info.get('conversation_memory')
                   else f"  Hidden layers        {info['hidden']} → {info['hidden']}"),
                  f"  Precision            {info['dtype']}", f"  Weights in RAM       {info['weight_bytes']/1048576:.2f} MiB",
                  f"  Model file           {info['file_bytes']/1048576:.2f} MiB", f"  Checkpoint step      {info['training_step']:,}",
                  "", "  MATRICES", ""]
        for name, weights in self.engine.all_weights.items():
            shape = " × ".join(str(n) for n in weights.shape)
            lines.append(f"  {name:<5} {shape:<22} {weights.size:>10,} parameters")
        lines += ["", "  Experimental English model. Responses can be incorrect.", "  Chat never changes model weights."]
        if info['intent_routing']:
            lines += [f"  Intent classifier: {info['router_parameters']:,} learned parameters.",
                      "  Routing probability describes intent, not answer correctness."]
        if info['question_features']:
            lines += ['  Chat topic features use the last 64 question tokens; no conversation memory.']
        if info.get('conversation_memory'):
            lines += [f"  Conversation context: up to {self.engine.context} tokens, current session only."]
        return "\n".join(lines)

    def stats_text(self):
        totals, q = self.totals(), self.quota.status()
        reset = duration(q["resets_in_seconds"]) if q["resets_in_seconds"] is not None else "10h after your first message"
        lines = ["ALLOWANCE / 10-HOUR WINDOW", "", f"  Remaining             {q['remaining']:,} / {q['allowance']:,} tokens",
                 f"  Available             {100*q['remaining']/q['allowance']:.1f}%",
                 f"  Used or reserved      {q['used']:,} tokens", f"  Resets in             {reset}",
                 "  Rough estimate        ~5,000 messages at 200 tokens per exchange", "",
                 "  A shared local ledger enforces the limit across app restarts and models.",
                 "  The next message is blocked when the allowance is exhausted.", "", "THIS SESSION", "",
                 f"  Responses             {totals['turns']}", f"  Prompt tokens         {totals['input']:,}",
                 f"  Generated tokens      {totals['output']:,}", f"  Generation time       {totals['seconds']:.3f} s",
                 f"  Average speed         {totals['speed']:.1f} tok/s"]
        if self.last_result:
            r = self.last_result
            lines += ["", "LAST RESPONSE", "", f"  Prompt tokens         {len(r.prompt_ids)} (includes role labels and any used history)",
                      f"  Used context          {r.context_used}/{self.engine.context}", f"  Dropped from start    {r.context_dropped}",
                      f"  Generated tokens      {len(r.generated)}", f"  Charged to allowance  {r.charged_tokens}",
                      f"  Speed                 {r.tokens_per_second:.1f} tok/s", f"  Finish reason         {r.finish_reason}"]
            if r.intent:
                lines += [f"  Detected intent       {r.intent}",
                          f"  Math intent score     {r.intent_math_probability:.1%}"]
        lines += ["", "  Charged tokens = used input context + actual generated tokens, including stop tokens.",
                  "  Padding and discarded input are not charged. /new does not reset the allowance."]
        return "\n".join(lines)

    def tokens_text(self, live_text=""):
        text = live_text or self.inspected_text or self.last_question
        if not text:
            return "TOKENS / BPE\n\n  Start typing below or use /tokens Your text."
        ids = self.engine.tokenizer.encode(text)
        lines = ["TOKENS / BPE", "", "  Text: " + json.dumps(text, ensure_ascii=False),
                 f"  {len(ids)} tokens · {len(text)} characters", "", token_table(self.engine.tokenizer, ids)]
        if self.last_result:
            lines += ["", "LAST RESPONSE / ACTUALLY SAMPLED TOKENS", "",
                      token_table(self.engine.tokenizer, [t.id for t in self.last_result.generated]),
                      "", "  Includes the tokens that ended the response."]
        return "\n".join(lines)

    def intent_text(self):
        text = self.inspected_text or self.last_question
        if not text:
            return 'Use /intent Your question to inspect its purpose.'
        result = self.engine.classify(text)
        if result['intent'] is None:
            return 'This model has no explicit intent classifier. Select lambda 1.6 to use one.'
        return (f"INTENT / {result['intent'].upper()}\n\n  Question: {text}\n"
                f"  Math probability: {result['math_probability']:.1%}\n\n"
                '  A calculation asks for a result. A chat question can contain numbers.\n'
                '  This score does not measure whether the answer is correct.')

    def command(self, text):
        command, _, value = text.partition(" ")
        command, value = command.lower(), value.strip()
        command = {"/quit":"/exit", "/clear":"/new", "/usage":"/stats"}.get(command, command)
        if command == "/update":
            return "update", ""
        if command == '/chat' and value:
            self.open_chat(value)
            return 'chat', f'Opened {self.chat_title}.'
        if command == '/rename':
            if not value or len(value) > 100 or any(not c.isprintable() for c in value):
                raise ValueError('Use /rename followed by a title of 1–100 printable characters.')
            self.chat_title = value
            self.persist()
            return 'chat', f'Renamed chat to {value}.'
        if command == "/model" and value:
            if value.isdigit():
                choices = self.manager.entries()
                index = int(value)-1
                if not 0 <= index < len(choices):
                    raise ValueError("Choose a model number from the list.")
                return "use:" + choices[index]["id"], ""
            verb, _, identifier = value.partition(" ")
            if verb not in ("use", "install") or not identifier:
                raise ValueError("Use /model use <id> or /model install <id>.")
            return verb + ":" + identifier.strip(), ""
        if command in ("/chat", "/chats", "/model", "/stats", "/help", "/updates"):
            return command[1:], ""
        if command == "/tokens":
            self.inspected_text = value or self.last_question
            return "tokens", ""
        if command == '/intent':
            self.inspected_text = value or self.last_question
            return 'intent', ''
        if command == "/exit":
            return "exit", ""
        if command == "/memory":
            return "", self.memory_text()
        if command == "/new":
            self.persist()
            self.messages.clear(); self.turns.clear()
            self.memory_start = 0
            self.last_result = None
            self.last_question = self.inspected_text = ""
            self.chat_id, self.chat_revision, self.chat_title = None, 0, 'New chat'
            self.persistence_notice = ''
            self.persist()
            return "chat", "New chat. Find previous conversations in /chats."
        if command in ("/temperature", "/limit", "/topk"):
            updated = Settings(**asdict(self.settings))
            if command == "/temperature":
                updated.temperature = float(value)
            elif command == "/limit":
                updated.max_tokens = int(value)
            else:
                updated.top_k = int(value)
            updated.validate()
            self.settings = updated
            self.persist()
            return "", f"Set {command[1:]} to {value}."
        if command == "/save":
            path = Path(value or datetime.now().strftime("conversation-%Y%m%d-%H%M%S.json")).expanduser()
            payload = {"application":"lambda-ai-terminal", "model":self.engine.metadata.get("name"),
                       "settings":asdict(self.settings), "turns":self.turns,
                       "messages":[{"role":role,"text":content} for role,content in self.messages]}
            with path.open("x", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
                file.write("\n")
            return "", f"Saved to {path.resolve()}"
        raise ValueError(f"Unknown command {command}. Type /help.")
