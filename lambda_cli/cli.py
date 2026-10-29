"""The lambda command: English terminal UI, model updates and local allowance."""
import argparse
import json
import sys
from . import __version__


def parser():
    p = argparse.ArgumentParser(prog="lambda", description="Lambda AI — local English chat in your terminal.")
    p.add_argument("--version", action="version", version=f"lambda {__version__}")
    p.add_argument("--model", help="Use a custom inference .npz file (also LAMBDA_MODEL)")
    p.add_argument("--plain", action="store_true", help="Plain text mode without a full-screen interface")
    sub = p.add_subparsers(dest="command")
    chat = sub.add_parser("chat", help="Open interactive chat")
    chat.add_argument("--plain", action="store_true", default=argparse.SUPPRESS)
    ask = sub.add_parser("ask", help="Ask one question")
    ask.add_argument("question")
    ask.add_argument("--json", action="store_true", help="Return text and actual token usage as JSON")
    for command in (chat, ask):
        command.add_argument("--temperature", type=float, default=argparse.SUPPRESS)
        command.add_argument("--max-tokens", type=int, default=argparse.SUPPRESS)
        command.add_argument("--top-k", type=int, default=argparse.SUPPRESS)
        command.add_argument("--seed", type=int, default=argparse.SUPPRESS)
    info = sub.add_parser("info", help="Show model parameters")
    info.add_argument("--json", action="store_true")
    tokens = sub.add_parser("tokens", help="Inspect BPE token IDs and pieces")
    tokens.add_argument("text", nargs="?")
    tokens.add_argument("--json", action="store_true")
    intent = sub.add_parser('intent', help='Inspect learned chat/calculation intent')
    intent.add_argument('text')
    intent.add_argument('--json', action='store_true')
    usage = sub.add_parser("usage", help="Show remaining tokens and the 10-hour reset")
    usage.add_argument("--json", action="store_true")
    sub.add_parser("update", help="Update the application, model catalog and installed models")
    model = sub.add_parser("model", help="List, install or select models")
    model.add_argument("action", choices=["list", "install", "use"], nargs="?", default="list")
    model.add_argument("identifier", nargs="?")
    return p


def plain_chat(session):
    from .session import HELP
    print(f"λ LAMBDA {__version__} · {session.engine.metadata['name']} · local English AI")
    print("Enter a question or /help. /exit ends the session.\n")
    while True:
        try:
            question = input("You › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not question:
            continue
        try:
            if question.startswith("/"):
                view, notice = session.command(question)
                if view == "exit":
                    return 0
                if view == "update" or view.startswith(("use:", "install:")):
                    print(session.model_action(view, progress=print))
                    if view != "update":
                        print(session.model_text())
                    continue
                content = {"help":lambda:HELP, "model":session.model_text,
                           "stats":session.stats_text, "tokens":session.tokens_text, "intent":session.intent_text,
                           "updates":session.updates_text, "chats":session.chats_text}
                if view in content:
                    print(content[view]())
                if notice:
                    print(notice)
                if view == 'chat' and question.startswith('/chat '):
                    print('\n'.join(f'{role} › {text}' for role,text in session.messages))
                continue
            session.add_user(question)
            result = session.generate(question)
            session.complete(result)
            print("λ ›", result.text or "[Empty response]")
            mode = f" · {result.intent.title()}" if result.intent else ""
            print(f"    {len(result.prompt_ids)} → {len(result.generated)} tok · "
                  f"{result.seconds:.2f} s · {session.quota.status()['remaining']:,} tokens left{mode}\n")
        except KeyboardInterrupt:
            print("\nCancelled.")
        except (ValueError, OSError) as error:
            print("Error:", error)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        import os
        from .engine import Engine, Settings
        from .models import ModelManager
        from .session import Session, token_table
        from .chats import ChatStore
        manager = ModelManager()
        engine = Engine(args.model or os.environ.get("LAMBDA_MODEL") or manager.resolve())
        settings = Settings(getattr(args,"temperature",0.4), getattr(args,"max_tokens",120),
                            getattr(args,"top_k",8), getattr(args,"seed",None))
        interactive = args.command in (None, 'chat')
        session = Session(engine, settings, manager=manager, store=ChatStore() if interactive else None,
                          resume=interactive and not bool(args.model or os.environ.get('LAMBDA_MODEL')))
        if interactive:
            for attribute in ('temperature','max_tokens','top_k','seed'):
                if hasattr(args, attribute):
                    setattr(session.settings, attribute, getattr(args, attribute))
            session.settings.validate()
            session.persist()
        if args.command == 'intent':
            if args.json:
                print(json.dumps(engine.classify(args.text), indent=2))
            else:
                session.inspected_text = args.text
                print(session.intent_text())
            return 0
        if args.command == "info":
            print(json.dumps(engine.info(),indent=2) if args.json else session.model_text())
            return 0
        if args.command == "usage":
            print(json.dumps(session.quota.status(),indent=2) if args.json else session.stats_text())
            return 0
        if args.command == "update":
            print(session.model_action("update",progress=print))
            return 1 if session.update_failed else 0
        if args.command == "model":
            if args.action != "list":
                if not args.identifier:
                    raise ValueError("Specify a model ID, for example lambda-1.0.")
                print(session.model_action(args.action+":"+args.identifier,progress=print))
            print(session.model_text())
            return 0
        if args.command == "tokens":
            text = args.text
            if text is None and not sys.stdin.isatty():
                text = sys.stdin.read()
            if text is None:
                from .tui import TerminalApp
                app = TerminalApp(session); app.select("tokens"); app.run()
                return 0
            ids = engine.tokenizer.encode(text)
            print(json.dumps({"count":len(ids),"tokens":[{"id":i,"text":engine.tokenizer.tokens[i]} for i in ids]},
                             ensure_ascii=False,indent=2) if args.json else
                  f"{len(text)} characters → {len(ids)} BPE tokens\n\n"+token_table(engine.tokenizer,ids))
            return 0
        if args.command == "ask":
            session.add_user(args.question)
            result = session.generate(args.question)
            print(json.dumps(result.to_dict(),ensure_ascii=False,indent=2) if args.json else result.text)
            return 0
        if args.plain or not (sys.stdin.isatty() and sys.stdout.isatty()):
            return plain_chat(session)
        from .tui import TerminalApp
        TerminalApp(session).run()
        return 0
    except KeyboardInterrupt:
        return 130
    except (ValueError, OSError) as error:
        print(f"lambda: {error}",file=sys.stderr)
        return 1
