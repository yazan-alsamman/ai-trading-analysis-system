"""Load-test accounts and tokens. Runs INSIDE the backend container of a local stack:

    docker compose exec -T backend python - 200 < infra/loadtest/make_users.py > tokens.json

Creates (or reuses) analyst accounts ``load-NNN@example.com`` (analyst tier: 300 requests a
minute each, so the test measures the server, not the rate limiter), issues an access token for
each without the login endpoint (Argon2 x 200 and the login lockouts are not what is measured)
and prints JSON for k6: the tokens, the user ids and the instruments that have candles.

Remove the accounts afterwards with ``python -m app.cli purge-demo --prefix load- --yes``.
"""

import asyncio
import json
import sys
import uuid

from sqlalchemy import select, text

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole

PREFIX = "load-"


async def main(count: int) -> None:
    hashed = hash_password(uuid.uuid4().hex)  # nobody logs in with these accounts
    async with SessionLocal() as session:
        emails = [f"{PREFIX}{i:03d}@example.com" for i in range(count)]
        existing = {
            u.email: u for u in (await session.scalars(select(User).where(User.email.in_(emails))))
        }
        users = []
        for i, email in enumerate(emails):
            user = existing.get(email)
            if user is None:
                user = User(
                    id=uuid.uuid4(),
                    email=email,
                    hashed_password=hashed,
                    full_name=f"Load {i:03d}",
                    role=UserRole.analyst,
                )
                session.add(user)
            users.append(user)
        await session.commit()
        rows = await session.execute(
            text(
                "SELECT i.id, i.symbol FROM instruments i WHERE EXISTS "
                "(SELECT 1 FROM candles_1m c WHERE c.instrument_id = i.id) ORDER BY i.symbol"
            )
        )
        instruments = [{"id": str(r.id), "symbol": r.symbol} for r in rows]
    out = {
        "users": [{"id": str(u.id), "token": create_access_token(u)} for u in users],
        "instruments": instruments,
    }
    print(json.dumps(out))
    print(f"{len(users)} accounts ({len(users) - len(existing)} new)", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 200))
