"""``lucidnews-users``: manage accounts from the terminal.

With ``auth.allow_signup`` off nobody can register from the web app, so the accounts are made here,
by whoever can run commands on the server. The password is read without echo (or from stdin with
``--password-stdin``) and is never taken as an argument, which would leave it in the shell history.
"""

import argparse
import getpass
import sys
from pathlib import Path
from typing import List, Optional

from .._cli import add_data_dir_arguments
from .passwords import hash_password, password_problem
from .service import AuthService
from .store import AuthDB

PROBLEMS = {
    "too_short": "the password must have at least 8 characters",
    "too_long": "the password must have at most 128 characters",
    "required": "a password is required",
}


def _read_password(from_stdin: bool) -> Optional[str]:
    if from_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    first = getpass.getpass("Password: ")
    return first if first == getpass.getpass("Repeat the password: ") else None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="LucidNews accounts (web app sign-in)")
    add_data_dir_arguments(parser)
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="create an account")
    add.add_argument("email")
    add.add_argument("--name", default="")
    add.add_argument("--password-stdin", action="store_true", help="read the password from stdin (scripts)")
    commands.add_parser("list", help="list the accounts")
    remove = commands.add_parser("remove", help="delete an account and its sessions")
    remove.add_argument("email")
    passwd = commands.add_parser("passwd", help="set a new password (ends the account's sessions)")
    passwd.add_argument("email")
    passwd.add_argument("--password-stdin", action="store_true")
    args = parser.parse_args(argv)

    db = AuthDB(Path(args.data_dir) / "auth.sqlite3")
    if args.command == "list":
        for user in db.list_users():
            how = " + ".join(filter(None, ["password" if user.has_password else "", "google" if user.google_sub else ""]))
            print(f"{user.email}\t{user.name}\t{how}\t{user.created_at[:10]}")
        return 0

    email = AuthService._email(args.email)
    if email is None:
        print("error: not a valid e-mail address", file=sys.stderr)
        return 2
    found = db.by_email(email)
    if args.command == "remove":
        if found is None or not db.delete_user(found[0].id):
            print("error: no such account", file=sys.stderr)
            return 1
        print(f"removed {email}")
        return 0

    password = _read_password(args.password_stdin)
    if password is None:
        print("error: the two passwords differ", file=sys.stderr)
        return 2
    problem = password_problem(password)
    if problem:
        print(f"error: {PROBLEMS[problem]}", file=sys.stderr)
        return 2
    if args.command == "passwd":
        if found is None:
            print("error: no such account", file=sys.stderr)
            return 1
        db.set_password(found[0].id, hash_password(password))
        print(f"password changed for {email}; its sessions ended")
        return 0
    user = db.create_user(email, AuthService._name(args.name) or email.split("@")[0], password_hash=hash_password(password))
    if user is None:
        print("error: an account already uses this address", file=sys.stderr)
        return 1
    print(f"created {email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
