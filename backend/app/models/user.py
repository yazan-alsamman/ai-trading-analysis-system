import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserRole(StrEnum):
    trader = "trader"
    analyst = "analyst"
    expert = "expert"
    admin = "admin"


class User(Base):
    """An account: login e-mail, Argon2 password hash and one of four roles (trader, analyst,
    expert, admin)."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
        CheckConstraint(
            "phone_e164 IS NULL OR phone_e164 ~ '^\\+[1-9][0-9]{6,14}$'",
            name="ck_users_phone_e164",
        ),
        UniqueConstraint("phone_e164", name="uq_users_phone_e164"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]),
        default=UserRole.trader,
        server_default=UserRole.trader.value,
    )
    # a WhatsApp number in E.164 (+963...), set only after its OTP was verified (docs/otp.md);
    # unique: one account per number, which can then sign in with a WhatsApp code
    phone_e164: Mapped[str | None] = mapped_column(String(16))
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    # every session ended at this time (password change, refresh reuse, deactivation): the
    # WebSockets of access tokens issued before it without a session id close (B12 part 2)
    sessions_revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
