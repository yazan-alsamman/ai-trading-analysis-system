"""Management commands.

python -m app.cli create-admin --email admin@example.com --password 'Secret123'
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.user import NormalizedEmail, Password
from app.services import user_service


async def create_admin(
    email: str, password: str, session_factory: async_sessionmaker[AsyncSession] | None = None
) -> int:
    try:
        email = TypeAdapter(NormalizedEmail).validate_python(email)
        password = TypeAdapter(Password).validate_python(password)
    except ValidationError as exc:
        print(f"Invalid input: {exc.errors()[0]['msg']}", file=sys.stderr)
        return 2
    if session_factory is None:
        from app.db.session import SessionLocal

        session_factory = SessionLocal
    async with session_factory() as session:
        user, created = await user_service.ensure_admin(session, email, password)
    if created:
        print(f"Created admin {user.email}")
    else:
        print(f"User {user.email} already exists; ensured role=admin (password unchanged)")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create-admin", help="Create an admin, or promote an existing user")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    args = parser.parse_args(argv)
    if args.command == "create-admin":
        return asyncio.run(create_admin(args.email, args.password))
    return 1


if __name__ == "__main__":
    sys.exit(main())
