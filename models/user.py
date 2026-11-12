from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from enums.role import RoleId
from enums.user import UserStatus
from models.role import Role


class User(Base):
    __tablename__ = "kh_user"

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(start=1001),
        primary_key=True,
    )

    username: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    avatar_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )

    role_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("kh_role.id", ondelete="RESTRICT"),
        nullable=False,
        default=RoleId.USER,
        server_default=text(str(RoleId.USER.value)),
    )

    role: Mapped[Role] = relationship(back_populates="users", lazy="selectin")

    status: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=UserStatus.PENDING_VERIFICATION,
        server_default=text(
            str(UserStatus.PENDING_VERIFICATION.value),
        ),
    )

    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    token_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    __table_args__ = (
        Index(
            "uq_kh_user_username_active",
            func.lower(username),
            unique=True,
            postgresql_where=deleted.is_(False),
        ),
        Index(
            "uq_kh_user_email_active",
            func.lower(email),
            unique=True,
            postgresql_where=deleted.is_(False),
        ),
    )
