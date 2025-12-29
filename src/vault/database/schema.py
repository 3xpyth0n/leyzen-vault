"""SQLAlchemy database schema for Leyzen Vault."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from vault.utils.safe_json import safe_json_loads

db = SQLAlchemy()


class GlobalRole(str, enum.Enum):
    """Global user role."""

    USER = "user"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class VaultSpaceType(str, enum.Enum):
    """VaultSpace type."""

    PERSONAL = "personal"


class SSOProviderType(str, enum.Enum):
    """SSO provider type."""

    SAML = "saml"
    OAUTH2 = "oauth2"
    OIDC = "oidc"
    EMAIL_MAGIC_LINK = "email-magic-link"


class SSOProviderTypeEnum(TypeDecorator):
    """Custom type decorator to store enum values as strings.

    This avoids issues with PostgreSQL enum types that may have been created
    with member names instead of values. We store the enum value as a string.
    """

    impl = String(50)  # Store as string instead of native enum
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convert enum member to its value for database storage."""
        if value is None:
            return None
        if isinstance(value, SSOProviderType):
            return value.value

        return value

    def process_result_value(self, value, dialect):
        """Convert database value back to enum member."""
        if value is None:
            return None
        if isinstance(value, SSOProviderType):
            return value
        # Convert string value to enum member
        if isinstance(value, str):
            try:
                return SSOProviderType(value)
            except ValueError:

                for member in SSOProviderType:
                    if member.value == value:
                        return member

                return value
        return value


class SSOProvider(db.Model):
    """SSO provider configuration."""

    __tablename__ = "sso_providers"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_type: Mapped[SSOProviderType] = mapped_column(
        SSOProviderTypeEnum(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Configuration stored as JSON (encrypted in production)
    config: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    # SAML: metadata_url, entity_id, x509_cert
    # OAuth2/OIDC: client_id, client_secret, authorization_url, token_url, userinfo_url, scopes
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        # Handle both enum member and string (for backward compatibility)
        provider_type_value = (
            self.provider_type.value
            if isinstance(self.provider_type, SSOProviderType)
            else str(self.provider_type)
        )

        return {
            "id": self.id,
            "name": self.name,
            "provider_type": provider_type_value,
            "is_active": self.is_active,
            "config": (
                safe_json_loads(
                    self.config,
                    max_size=10 * 1024,  # 10KB for SSO config
                    max_depth=20,
                    context="SSO provider config",
                )
                if self.config
                else {}
            ),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self) -> str:
        provider_type_str = (
            self.provider_type.value
            if isinstance(self.provider_type, SSOProviderType)
            else str(self.provider_type)
        )
        return f"<SSOProvider {self.name} ({provider_type_str})>"


class User(db.Model):
    """User model."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    global_role: Mapped[GlobalRole] = mapped_column(
        Enum(GlobalRole), nullable=False, default=GlobalRole.USER
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    master_key_salt: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Base64-encoded salt for master key derivation (16 bytes)
    session_key_salt: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Base64-encoded salt for session key derivation (32 bytes)
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )  # Email verification status (always required)
    invited_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )  # ID of admin who invited this user

    # Two-Factor Authentication (2FA/TOTP) fields
    totp_secret: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # Encrypted TOTP secret (base32)
    totp_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )  # Whether 2FA is enabled for this user
    totp_backup_codes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Encrypted JSON array of backup recovery codes
    totp_enabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # Timestamp when 2FA was enabled

    # Relationships
    owned_vaultspaces: Mapped[list["VaultSpace"]] = relationship(
        "VaultSpace",
        foreign_keys="VaultSpace.owner_user_id",
        back_populates="owner_user",
    )
    vaultspace_keys: Mapped[list["VaultSpaceKey"]] = relationship(
        "VaultSpaceKey", back_populates="user", cascade="all, delete-orphan"
    )
    owned_files: Mapped[list["File"]] = relationship(
        "File", foreign_keys="File.owner_user_id", back_populates="owner_user"
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(
        "ApiKey", back_populates="user", cascade="all, delete-orphan"
    )

    def to_dict(self, include_salt: bool = False) -> dict[str, Any]:
        """Convert to dictionary.

        Args:
            include_salt: If True, include master_key_salt in the response.
                          Should only be True during login/signup for security.
        """
        result = {
            "id": self.id,
            "email": self.email,
            "global_role": self.global_role.value,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "email_verified": self.email_verified,
            "invited_by": self.invited_by,
        }
        if include_salt:
            result["master_key_salt"] = self.master_key_salt
        return result

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class VaultSpace(db.Model):
    """VaultSpace model."""

    __tablename__ = "vaultspaces"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    type: Mapped[VaultSpaceType] = mapped_column(
        Enum(VaultSpaceType), nullable=False, default=VaultSpaceType.PERSONAL
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    icon_name: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default=None
    )
    owner_user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    encrypted_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_refs: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON string: {"64x64": "storage_ref", "128x128": "storage_ref", "256x256": "storage_ref"}
    has_thumbnail: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    owner_user: Mapped["User | None"] = relationship(
        "User", foreign_keys=[owner_user_id], back_populates="owned_vaultspaces"
    )
    vaultspace_keys: Mapped[list["VaultSpaceKey"]] = relationship(
        "VaultSpaceKey", back_populates="vaultspace", cascade="all, delete-orphan"
    )
    files: Mapped[list["File"]] = relationship(
        "File", back_populates="vaultspace", cascade="all, delete-orphan"
    )

    # Constraints: VaultSpace must have owner_user_id
    # Check constraint enforced at application level
    __table_args__ = (
        Index("ix_vaultspaces_owner_user", "owner_user_id"),
        Index("ix_vaultspaces_type", "type"),
        Index("ix_vaultspaces_owner_user_type", "owner_user_id", "type"),
    )

    def validate_ownership(self) -> bool:
        """Validate that ownership is correct.

        Returns:
            True if ownership is valid (has user_id)
        """
        return self.owner_user_id is not None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "icon_name": self.icon_name,
            "owner_user_id": self.owner_user_id,
            "encrypted_metadata": self.encrypted_metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<VaultSpace {self.name} ({self.type.value})>"


class VaultSpaceKey(db.Model):
    """VaultSpace key encrypted for a user."""

    __tablename__ = "vaultspace_keys"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    vaultspace_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("vaultspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    vaultspace: Mapped["VaultSpace"] = relationship(
        "VaultSpace", back_populates="vaultspace_keys"
    )
    user: Mapped["User"] = relationship("User", back_populates="vaultspace_keys")

    # Unique constraint: one encrypted key per user per vaultspace
    __table_args__ = (
        Index(
            "ix_vaultspace_keys_user_vaultspace",
            "user_id",
            "vaultspace_id",
            unique=True,
        ),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "vaultspace_id": self.vaultspace_id,
            "user_id": self.user_id,
            "encrypted_key": self.encrypted_key,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<VaultSpaceKey vaultspace={self.vaultspace_id} user={self.user_id}>"


class UserPinnedVaultSpace(db.Model):
    """User pinned VaultSpace for quick access."""

    __tablename__ = "user_pinned_vaultspaces"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    vaultspace_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("vaultspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    pinned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=True, default=0, server_default="0"
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    vaultspace: Mapped["VaultSpace"] = relationship("VaultSpace")

    # Unique constraint: one pin per user per vaultspace
    __table_args__ = (
        Index(
            "ix_user_pinned_vaultspaces_user_vaultspace",
            "user_id",
            "vaultspace_id",
            unique=True,
        ),
        Index("ix_user_pinned_vaultspaces_user", "user_id"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "vaultspace_id": self.vaultspace_id,
            "pinned_at": self.pinned_at.isoformat(),
            "display_order": self.display_order,
        }

    def __repr__(self) -> str:
        return f"<UserPinnedVaultSpace user={self.user_id} vaultspace={self.vaultspace_id}>"


class File(db.Model):
    """File model."""

    __tablename__ = "files"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    vaultspace_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("vaultspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    owner_user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    encrypted_size: Mapped[int] = mapped_column(Integer, nullable=False)
    encrypted_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_refs: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON string: {"64x64": "storage_ref", "128x128": "storage_ref", "256x256": "storage_ref"}
    has_thumbnail: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    storage_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    is_starred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    vaultspace: Mapped["VaultSpace"] = relationship(
        "VaultSpace", back_populates="files"
    )
    parent: Mapped["File | None"] = relationship(
        "File", remote_side=[id], backref="children", foreign_keys=[parent_id]
    )
    owner_user: Mapped["User"] = relationship(
        "User", foreign_keys=[owner_user_id], back_populates="owned_files"
    )
    file_keys: Mapped[list["FileKey"]] = relationship(
        "FileKey", back_populates="file", cascade="all, delete-orphan"
    )

    # Indexes for efficient queries
    __table_args__ = (
        Index("ix_files_vaultspace", "vaultspace_id"),
        Index("ix_files_parent", "parent_id"),
        Index("ix_files_owner_user", "owner_user_id"),
        Index("ix_files_vaultspace_parent", "vaultspace_id", "parent_id"),
        Index("ix_files_created_at", "created_at"),
        Index("ix_files_updated_at", "updated_at"),
        Index("ix_files_original_name", "original_name"),
        Index("ix_files_mime_type", "mime_type"),
        Index("ix_files_size", "size"),
        Index("ix_files_deleted_at", "deleted_at"),
        Index("ix_files_is_starred", "is_starred"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "vaultspace_id": self.vaultspace_id,
            "parent_id": self.parent_id,
            "owner_user_id": self.owner_user_id,
            "original_name": self.original_name,
            "size": self.size,
            "encrypted_size": self.encrypted_size,
            "encrypted_hash": self.encrypted_hash,
            "encrypted_metadata": self.encrypted_metadata,
            "thumbnail_refs": self.thumbnail_refs,
            "has_thumbnail": self.has_thumbnail,
            "storage_ref": self.storage_ref,
            "mime_type": self.mime_type,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "is_starred": self.is_starred,
        }

    def __repr__(self) -> str:
        return f"<File {self.original_name}>"


class FileKey(db.Model):
    """File key encrypted with VaultSpace key."""

    __tablename__ = "file_keys"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    file_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    vaultspace_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("vaultspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    file: Mapped["File"] = relationship("File", back_populates="file_keys")
    vaultspace: Mapped["VaultSpace"] = relationship("VaultSpace")

    # Unique constraint: one encrypted key per file per vaultspace
    __table_args__ = (
        Index("ix_file_keys_file_vaultspace", "file_id", "vaultspace_id", unique=True),
        Index("ix_file_keys_file", "file_id"),
        Index("ix_file_keys_vaultspace", "vaultspace_id"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "file_id": self.file_id,
            "vaultspace_id": self.vaultspace_id,
            "encrypted_key": self.encrypted_key,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<FileKey file={self.file_id} vaultspace={self.vaultspace_id}>"


class Webhook(db.Model):
    """Webhook for external integrations."""

    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret: Mapped[str] = mapped_column(String(255), nullable=False)  # HMAC secret
    events: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # JSON array of event types
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "url": self.url,
            "events": self.events,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "last_triggered_at": (
                self.last_triggered_at.isoformat() if self.last_triggered_at else None
            ),
            "failure_count": self.failure_count,
        }


class Device(db.Model):
    """User device for multi-device management."""

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    device_name: Mapped[str] = mapped_column(String(255), nullable=False)
    device_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # desktop, mobile, tablet, etc.
    device_fingerprint: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_trusted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "device_fingerprint": self.device_fingerprint,
            "last_seen_at": self.last_seen_at.isoformat(),
            "is_trusted": self.is_trusted,
            "location": self.location,
            "ip_address": self.ip_address,
        }


class Quota(db.Model):
    """Storage quota for users."""

    __tablename__ = "quotas"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    max_storage_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    used_storage_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_files: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (Index("ix_quotas_user", "user_id"),)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "max_storage_bytes": self.max_storage_bytes,
            "used_storage_bytes": self.used_storage_bytes,
            "max_files": self.max_files,
            "used_files": self.used_files,
            "updated_at": self.updated_at.isoformat(),
        }


class Workflow(db.Model):
    """Workflow definition for automation."""

    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_conditions: Mapped[str] = mapped_column(Text, nullable=False)
    actions: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    execution_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "trigger_event": self.trigger_event,
            "trigger_conditions": self.trigger_conditions,
            "actions": self.actions,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "last_triggered_at": (
                self.last_triggered_at.isoformat() if self.last_triggered_at else None
            ),
            "execution_count": self.execution_count,
        }


class WorkflowExecution(db.Model):
    """Workflow execution log."""

    __tablename__ = "workflow_executions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    workflow_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False)
    trigger_data: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "trigger_event": self.trigger_event,
            "trigger_data": self.trigger_data,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "error_message": self.error_message,
        }


class BehaviorAnalytics(db.Model):
    """Behavioral analytics data."""

    __tablename__ = "behavior_analytics"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    device_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_behavior_user_timestamp", "user_id", "timestamp"),
        Index("ix_behavior_event_type", "event_type"),
    )


class VaultSpaceTemplate(db.Model):
    """VaultSpace template for quick workspace creation."""

    __tablename__ = "vaultspace_templates"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_config: Mapped[str] = mapped_column(Text, nullable=False)  # JSON structure
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "template_config": self.template_config,
            "is_public": self.is_public,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "usage_count": self.usage_count,
        }


class BackupJob(db.Model):
    """Backup job record."""

    __tablename__ = "backup_jobs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    vaultspace_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("vaultspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    backup_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # full, incremental
    status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # pending, running, completed, failed
    storage_location: Mapped[str] = mapped_column(String(500), nullable=False)
    backup_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "vaultspace_id": self.vaultspace_id,
            "backup_type": self.backup_type,
            "status": self.status,
            "storage_location": self.storage_location,
            "backup_hash": self.backup_hash,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "file_count": self.file_count,
            "total_size_bytes": self.total_size_bytes,
        }


class DatabaseBackup(db.Model):
    """Database backup record."""

    __tablename__ = "database_backups"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    backup_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # manual, scheduled
    status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # pending, running, completed, failed
    storage_location: Mapped[str] = mapped_column(String(500), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    backup_metadata: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON metadata

    __table_args__ = (Index("ix_database_backups_created_at", "created_at"),)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        metadata_dict = None
        if self.backup_metadata:
            try:
                metadata_dict = safe_json_loads(
                    self.backup_metadata,
                    max_size=10240,
                    max_depth=10,
                    context="backup metadata",
                )
            except Exception:
                metadata_dict = None

        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "backup_type": self.backup_type,
            "status": self.status,
            "storage_location": self.storage_location,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "metadata": metadata_dict,
        }

    def __repr__(self) -> str:
        return f"<DatabaseBackup {self.id} ({self.backup_type}, {self.status})>"


class ReplicationTarget(db.Model):
    """Replication target configuration."""

    __tablename__ = "replication_targets"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    vaultspace_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("vaultspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # s3, azure, gcs, local
    target_config: Mapped[str] = mapped_column(Text, nullable=False)  # JSON config
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sync_frequency_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=24
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "vaultspace_id": self.vaultspace_id,
            "target_type": self.target_type,
            "target_config": self.target_config,
            "is_active": self.is_active,
            "last_sync_at": (
                self.last_sync_at.isoformat() if self.last_sync_at else None
            ),
            "sync_frequency_hours": self.sync_frequency_hours,
            "created_at": self.created_at.isoformat(),
        }


class PublicShareLink(db.Model):
    """Public share link for files and folders."""

    __tablename__ = "public_share_links"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    resource_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    resource_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'file' or 'vaultspace'
    created_by: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # Optional password protection
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    max_downloads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    download_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_access_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    allow_download: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    permission_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="read"
    )  # read, write, admin
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    note: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )  # Optional note for the share link

    # Relationships
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("ix_public_share_links_resource", "resource_id", "resource_type"),
        Index("ix_public_share_links_created_by", "created_by"),
        Index("ix_public_share_links_expires_at", "expires_at"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "created_by": self.created_by,
            "token": self.token,
            "has_password": self.password_hash is not None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "max_downloads": self.max_downloads,
            "download_count": self.download_count,
            "max_access_count": self.max_access_count,
            "access_count": self.access_count,
            "allow_download": self.allow_download,
            "permission_type": self.permission_type,
            "created_at": self.created_at.isoformat(),
            "last_accessed_at": (
                self.last_accessed_at.isoformat() if self.last_accessed_at else None
            ),
            "note": self.note,
            "is_expired": self.is_expired(),
            "is_download_limit_reached": self.is_download_limit_reached(),
            "is_access_limit_reached": self.is_access_limit_reached(),
            "is_available": self.can_access(),
        }

    def is_expired(self) -> bool:
        """Check if link is expired."""
        if not self.expires_at:
            return False
        from datetime import timezone

        return datetime.now(timezone.utc) > self.expires_at

    def is_download_limit_reached(self) -> bool:
        """Check if download limit is reached."""
        if not self.max_downloads:
            return False
        return self.download_count >= self.max_downloads

    def is_access_limit_reached(self) -> bool:
        """Check if access limit is reached."""
        if not self.max_access_count:
            return False
        return self.access_count >= self.max_access_count

    def can_access(self) -> bool:
        """Check if link can be accessed."""
        return (
            not self.is_expired()
            and not self.is_download_limit_reached()
            and not self.is_access_limit_reached()
        )


class RateLimitTracking(db.Model):
    """Rate limit tracking for IP addresses."""

    __tablename__ = "rate_limit_tracking"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    ip_address: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # Support IPv6 + action_name suffix
    last_request_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_rate_limit_ip_window", "ip_address", "window_start"),
        Index("ix_rate_limit_window_start", "window_start"),
    )


class CaptchaEntry(db.Model):
    """CAPTCHA entry stored in database for multi-worker synchronization."""

    __tablename__ = "captcha_entries"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    nonce: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    text: Mapped[str] = mapped_column(String(50), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_captcha_entries_session_expires", "session_id", "expires_at"),
    )


class JWTBlacklist(db.Model):
    """JWT token blacklist for logout functionality."""

    __tablename__ = "jwt_blacklist"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    token: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    jti: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # JWT ID for replay protection (nullable for backward compatibility)

    # (CREATE UNIQUE INDEX ... WHERE jti IS NOT NULL) to handle nullable column
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_jwt_blacklist_token", "token"),
        Index("ix_jwt_blacklist_expires_at", "expires_at"),
    )


class AuditLogEntry(db.Model):
    """Audit log entry for security and compliance tracking."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    file_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    user_ip: Mapped[str] = mapped_column(String(45), nullable=False)  # IPv6 max length
    ipv4: Mapped[str | None] = mapped_column(String(15), nullable=True)  # IPv4 address
    ip_location: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON string with location data
    user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    details: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_timestamp", "timestamp"),
        Index("ix_audit_logs_file_id", "file_id"),
        Index("ix_audit_logs_user_ip", "user_ip"),
        Index("ix_audit_logs_success", "success"),
        Index("ix_audit_logs_user_id", "user_id"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "action": self.action,
            "file_id": self.file_id,
            "user_ip": self.user_ip,
            "ipv4": self.ipv4,
            "ip_location": (
                safe_json_loads(
                    self.ip_location,
                    max_size=5 * 1024,  # 5KB for location data
                    max_depth=10,
                    context="audit log ip_location",
                )
                if self.ip_location
                else None
            ),
            "user_id": self.user_id,
            "user_email": None,  # Email is retrieved via join in AuditService.get_logs()
            "timestamp": self.timestamp.isoformat(),
            "details": (
                safe_json_loads(
                    self.details,
                    max_size=10 * 1024,  # 10KB for audit details
                    max_depth=20,
                    context="audit log details",
                )
                if self.details
                else {}
            ),
            "success": self.success,
        }


class ShareLink(db.Model):
    """Share link for files with expiration and download limits."""

    __tablename__ = "share_links"

    link_id: Mapped[str] = mapped_column(
        String(255), primary_key=True
    )  # Token from secrets.token_urlsafe(32)
    file_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    max_downloads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    download_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    file: Mapped["File"] = relationship("File", foreign_keys=[file_id])

    # Indexes for efficient queries
    __table_args__ = (
        Index("ix_share_links_file_id", "file_id"),
        Index("ix_share_links_expires_at", "expires_at"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "link_id": self.link_id,
            "file_id": self.file_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "max_downloads": self.max_downloads,
            "download_count": self.download_count,
        }

    def is_expired(self, tolerance_seconds: int = 60) -> bool:
        """Check if the link has expired.

        Uses UTC for comparison to ensure consistency.
        Adds a tolerance window to account for clock drift and network delays.

        Args:
            tolerance_seconds: Tolerance in seconds (default: 60)

        Returns:
            True if expired, False otherwise
        """
        from datetime import timezone, timedelta

        if self.expires_at:
            now_utc = datetime.now(timezone.utc)
            expires_utc = self.expires_at.astimezone(timezone.utc)
            expires_with_tolerance = expires_utc + timedelta(seconds=tolerance_seconds)
            return now_utc > expires_with_tolerance
        return False

    def has_reached_limit(self) -> bool:
        """Check if the download limit has been reached."""
        if self.max_downloads is None:
            return False
        return self.download_count >= self.max_downloads


class EmailVerificationToken(db.Model):
    """Email verification token model."""

    __tablename__ = "email_verification_tokens"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    code: Mapped[str] = mapped_column(
        String(6), nullable=False
    )  # 6-digit verification code
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("ix_email_verification_tokens_user_id", "user_id"),
        Index("ix_email_verification_tokens_expires_at", "expires_at"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "expires_at": self.expires_at.isoformat(),
            "used_at": self.used_at.isoformat() if self.used_at else None,
            "created_at": self.created_at.isoformat(),
        }

    def is_expired(self) -> bool:
        """Check if token is expired."""
        from datetime import timezone

        now_utc = datetime.now(timezone.utc)
        expires_utc = self.expires_at.astimezone(timezone.utc)
        return now_utc > expires_utc

    def is_used(self) -> bool:
        """Check if token has been used."""
        return self.used_at is not None

    def __repr__(self) -> str:
        return f"<EmailVerificationToken user={self.user_id}>"


class MagicLinkToken(db.Model):
    """Magic link token for SSO email authentication."""

    __tablename__ = "magic_link_tokens"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sso_providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    token: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    provider: Mapped["SSOProvider"] = relationship("SSOProvider")

    __table_args__ = (
        Index("ix_magic_link_tokens_email", "email"),
        Index("ix_magic_link_tokens_provider_id", "provider_id"),
        Index("ix_magic_link_tokens_expires_at", "expires_at"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "email": self.email,
            "provider_id": self.provider_id,
            "expires_at": self.expires_at.isoformat(),
            "used_at": self.used_at.isoformat() if self.used_at else None,
            "created_at": self.created_at.isoformat(),
        }

    def is_expired(self) -> bool:
        """Check if token is expired."""
        from datetime import timezone

        now_utc = datetime.now(timezone.utc)
        expires_utc = self.expires_at.astimezone(timezone.utc)
        return now_utc > expires_utc

    def is_used(self) -> bool:
        """Check if token has been used."""
        return self.used_at is not None

    def __repr__(self) -> str:
        return f"<MagicLinkToken {self.token[:8]}...>"


class UserInvitation(db.Model):
    """User invitation model."""

    __tablename__ = "user_invitations"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    invited_by: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    inviter: Mapped["User"] = relationship("User", foreign_keys=[invited_by])

    # Indexes for efficient queries

    # so we don't need to define it again here
    __table_args__ = (
        Index("ix_user_invitations_email", "email"),
        Index("ix_user_invitations_invited_by", "invited_by"),
        Index("ix_user_invitations_expires_at", "expires_at"),
        # Token index is created automatically by unique=True constraint
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "email": self.email,
            "invited_by": self.invited_by,
            "expires_at": self.expires_at.isoformat(),
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "created_at": self.created_at.isoformat(),
        }

    def is_expired(self) -> bool:
        """Check if invitation is expired."""
        from datetime import timezone

        now_utc = datetime.now(timezone.utc)
        expires_utc = self.expires_at.astimezone(timezone.utc)
        return now_utc > expires_utc

    def is_accepted(self) -> bool:
        """Check if invitation has been accepted."""
        return self.accepted_at is not None

    def __repr__(self) -> str:
        return f"<UserInvitation email={self.email} invited_by={self.invited_by}>"


class DomainRule(db.Model):
    """Domain rule model for domain-based access configuration."""

    __tablename__ = "domain_rules"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    domain_pattern: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )  # e.g., "example.com" or "*.example.com"
    sso_provider_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sso_providers.id", ondelete="SET NULL"),
        nullable=True,
    )  # Optional SSO provider association
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    sso_provider: Mapped["SSOProvider | None"] = relationship(
        "SSOProvider", foreign_keys=[sso_provider_id]
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "domain_pattern": self.domain_pattern,
            "sso_provider_id": self.sso_provider_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def matches_domain(self, email: str) -> bool:
        """Check if email domain matches this rule.

        Args:
            email: Email address to check

        Returns:
            True if domain matches, False otherwise
        """
        if "@" not in email:
            return False

        domain = email.split("@")[1].lower()
        pattern = self.domain_pattern.lower()

        # Exact match
        if pattern == domain:
            return True

        # Wildcard match (e.g., "*.example.com" matches "sub.example.com")
        if pattern.startswith("*."):
            base_domain = pattern[2:]  # Remove "*."
            if domain == base_domain or domain.endswith("." + base_domain):
                return True

        return False

    def __repr__(self) -> str:
        return f"<DomainRule domain={self.domain_pattern}>"


class SystemSettings(db.Model):
    """System settings model for storing configuration."""

    __tablename__ = "system_settings"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    key: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<SystemSettings key={self.key}>"


class SystemSecrets(db.Model):
    """System secrets model for storing encrypted system-level secrets.

    This table stores secrets that are generated at runtime and need to be
    shared across all instances (e.g., internal API token).
    Secrets are encrypted using SECRET_KEY before storage.
    """

    __tablename__ = "system_secrets"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    key: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )  # Secret key name, e.g., "internal_api_token"
    encrypted_value: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # Encrypted secret value
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (Index("ix_system_secrets_key", "key", unique=True),)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (without decrypted value for security)."""
        return {
            "id": self.id,
            "key": self.key,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<SystemSecrets key={self.key}>"


class SchemaMigration(db.Model):
    """Schema migration tracking for database migrations."""

    __tablename__ = "schema_migrations"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    migration_name: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_schema_migrations_name", "migration_name"),)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "migration_name": self.migration_name,
            "version": self.version,
            "applied_at": self.applied_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<SchemaMigration {self.migration_name} v{self.version}>"


class ApiKey(db.Model):
    """API key model for automation and external integrations."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    key_prefix: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # Prefix for display, e.g., "leyz_..."
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])

    # Indexes for efficient queries
    __table_args__ = (
        Index("ix_api_keys_user_id", "user_id"),
        Index("ix_api_keys_key_hash", "key_hash"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "key_prefix": self.key_prefix,
            "last_used_at": (
                self.last_used_at.isoformat() if self.last_used_at else None
            ),
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<ApiKey {self.name} (user={self.user_id})>"


class ExternalStorageMetadata(db.Model):
    """External storage metadata model for tracking S3 file synchronization."""

    __tablename__ = "external_storage_metadata"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    file_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sync_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )  # 'synced', 'pending', 'failed', 'restored'
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    file: Mapped["File"] = relationship("File", foreign_keys=[file_id])

    # Indexes for efficient queries
    __table_args__ = (
        Index("ix_external_storage_metadata_file_id", "file_id"),
        Index("ix_external_storage_metadata_s3_key", "s3_key"),
        Index("ix_external_storage_metadata_sync_status", "sync_status"),
        Index("ix_external_storage_metadata_last_synced_at", "last_synced_at"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "file_id": self.file_id,
            "s3_key": self.s3_key,
            "last_synced_at": (
                self.last_synced_at.isoformat() if self.last_synced_at else None
            ),
            "sync_status": self.sync_status,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<ExternalStorageMetadata file_id={self.file_id} status={self.sync_status}>"


class UploadSession(db.Model):
    """Upload session model for chunked file uploads."""

    __tablename__ = "upload_sessions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    vaultspace_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("vaultspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_id: Mapped[str] = mapped_column(
        String(500), nullable=False
    )  # Generated upfront for the file being uploaded (storage_ref format)
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    total_size: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )  # 'pending', 'uploading', 'completed', 'failed', 'expired'
    encrypted_file_key: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    encrypted_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    vaultspace: Mapped["VaultSpace"] = relationship(
        "VaultSpace", foreign_keys=[vaultspace_id]
    )
    parent: Mapped["File | None"] = relationship(
        "File", foreign_keys=[parent_id], remote_side="File.id"
    )

    # Indexes for efficient queries
    __table_args__ = (
        Index("ix_upload_sessions_user_id", "user_id"),
        Index("ix_upload_sessions_file_id", "file_id"),
        Index("ix_upload_sessions_status", "status"),
        Index("ix_upload_sessions_expires_at", "expires_at"),
        Index("ix_upload_sessions_vaultspace_id", "vaultspace_id"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "vaultspace_id": self.vaultspace_id,
            "file_id": self.file_id,
            "original_name": self.original_name,
            "total_size": self.total_size,
            "uploaded_size": self.uploaded_size,
            "chunk_size": self.chunk_size,
            "total_chunks": self.total_chunks,
            "uploaded_chunks": self.uploaded_chunks,
            "status": self.status,
            "parent_id": self.parent_id,
            "mime_type": self.mime_type,
            "expires_at": self.expires_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def is_expired(self) -> bool:
        """Check if session is expired."""
        from datetime import timezone

        now_utc = datetime.now(timezone.utc)
        expires_utc = self.expires_at.astimezone(timezone.utc)
        return now_utc > expires_utc

    def __repr__(self) -> str:
        return f"<UploadSession {self.id} ({self.status})>"


def init_db_roles(app: Any, secret_key: str) -> None:
    """Initialize PostgreSQL roles with proper privileges.

    Creates four roles with limited privileges:
    - leyzen_app: SELECT/INSERT/UPDATE/DELETE on application tables (no SystemSecrets, no schema changes)
    - leyzen_migrator: CREATE/ALTER/DROP on schema (no data access)
    - leyzen_secrets: Full access to SystemSecrets only
    - leyzen_orchestrator: SELECT only on SystemSecrets

    Args:
        app: Flask app instance
        secret_key: SECRET_KEY for encrypting passwords in SystemSecrets
    """
    from sqlalchemy import create_engine, text
    from common.env import load_env_with_override
    import os
    from vault.services.db_password_service import DBPasswordService

    env_values = load_env_with_override()
    env_values.update(dict(os.environ))

    postgres_host = env_values.get("POSTGRES_HOST", "postgres")
    postgres_port = env_values.get("POSTGRES_PORT", "5432")
    postgres_db = env_values.get("POSTGRES_DB", "leyzen_vault")
    postgres_user = env_values.get("POSTGRES_USER", "leyzen")
    postgres_password = env_values.get("POSTGRES_PASSWORD", "")

    if not postgres_password:
        raise RuntimeError("POSTGRES_PASSWORD is required for role initialization")

    # Connect as main user to create roles
    postgres_url = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"
    engine = create_engine(postgres_url, pool_pre_ping=True)

    app_logger = None
    try:
        app_logger = app.config.get("LOGGER")
    except Exception:
        # Logger may not be available during initialization - expected
        pass

    import logging

    logger = logging.getLogger(__name__)

    # Use advisory lock to ensure only one worker initializes roles
    # Lock ID: Use two 32-bit integers (high, low) for "LEYZENROLES"
    ADVISORY_LOCK_HIGH = 0x4C45595A  # "LEYZ"
    ADVISORY_LOCK_LOW = 0x524F4C45  # "ROLE" (different from init_db lock)

    # Store passwords_to_store outside try block so it's accessible in finally
    passwords_to_store = {}

    lock_acquired = False
    try:
        with engine.begin() as lock_conn:
            result = lock_conn.execute(
                text("SELECT pg_try_advisory_lock(:lock_high, :lock_low)"),
                {"lock_high": ADVISORY_LOCK_HIGH, "lock_low": ADVISORY_LOCK_LOW},
            )
            lock_acquired = result.scalar() is True
    except Exception:

        lock_acquired = False

    if not lock_acquired:

        import time

        time.sleep(1)
        engine.dispose()
        return

    try:
        # Use engine.begin() for automatic transaction management
        # This ensures all operations are committed correctly in SQLAlchemy 2.0
        with engine.begin() as conn:
            # Check if roles already exist
            role_check = conn.execute(
                text(
                    """
                    SELECT rolname FROM pg_roles
                    WHERE rolname IN ('leyzen_app', 'leyzen_migrator', 'leyzen_secrets', 'leyzen_orchestrator')
                    """
                )
            )
            existing_roles = {row[0] for row in role_check.fetchall()}

            # Check which passwords already exist in SystemSecrets (direct SQL check)
            # This is more reliable than using get_password which might fail
            try:
                secrets_check = conn.execute(
                    text(
                        """
                        SELECT key FROM system_secrets
                        WHERE key IN (:key1, :key2, :key3, :key4)
                        """
                    ),
                    {
                        "key1": DBPasswordService.SECRET_KEY_APP,
                        "key2": DBPasswordService.SECRET_KEY_MIGRATOR,
                        "key3": DBPasswordService.SECRET_KEY_SECRETS,
                        "key4": DBPasswordService.SECRET_KEY_ORCHESTRATOR,
                    },
                )
                existing_secret_keys = {row[0] for row in secrets_check.fetchall()}

            except Exception:

                existing_secret_keys = set()

            # Generate passwords for roles that don't exist or passwords not in SystemSecrets
            # (passwords_to_store is already initialized outside the try block)

            # Create or update leyzen_app role
            if DBPasswordService.ROLE_APP not in existing_roles:
                app_password = DBPasswordService.generate_password()
                conn.execute(
                    text(
                        f'CREATE ROLE "{DBPasswordService.ROLE_APP}" WITH LOGIN PASSWORD :password'
                    ),
                    {"password": app_password},
                )
                passwords_to_store[DBPasswordService.SECRET_KEY_APP] = app_password

            elif DBPasswordService.SECRET_KEY_APP not in existing_secret_keys:
                # Role exists but password not in SystemSecrets - generate and store it
                app_password = DBPasswordService.generate_password()
                passwords_to_store[DBPasswordService.SECRET_KEY_APP] = app_password
                conn.execute(
                    text(
                        f'ALTER ROLE "{DBPasswordService.ROLE_APP}" WITH PASSWORD :password'
                    ),
                    {"password": app_password},
                )

            # Create or update leyzen_migrator role
            if DBPasswordService.ROLE_MIGRATOR not in existing_roles:
                migrator_password = DBPasswordService.generate_password()
                conn.execute(
                    text(
                        f'CREATE ROLE "{DBPasswordService.ROLE_MIGRATOR}" WITH LOGIN PASSWORD :password'
                    ),
                    {"password": migrator_password},
                )
                passwords_to_store[DBPasswordService.SECRET_KEY_MIGRATOR] = (
                    migrator_password
                )

            elif DBPasswordService.SECRET_KEY_MIGRATOR not in existing_secret_keys:
                # Role exists but password not in SystemSecrets - generate and store it
                migrator_password = DBPasswordService.generate_password()
                passwords_to_store[DBPasswordService.SECRET_KEY_MIGRATOR] = (
                    migrator_password
                )
                conn.execute(
                    text(
                        f'ALTER ROLE "{DBPasswordService.ROLE_MIGRATOR}" WITH LOGIN PASSWORD :password'
                    ),
                    {"password": migrator_password},
                )

            # Create or update leyzen_secrets role
            if DBPasswordService.ROLE_SECRETS not in existing_roles:
                secrets_password = DBPasswordService.generate_password()
                conn.execute(
                    text(
                        f'CREATE ROLE "{DBPasswordService.ROLE_SECRETS}" WITH LOGIN PASSWORD :password'
                    ),
                    {"password": secrets_password},
                )
                passwords_to_store[DBPasswordService.SECRET_KEY_SECRETS] = (
                    secrets_password
                )

            elif DBPasswordService.SECRET_KEY_SECRETS not in existing_secret_keys:
                # Role exists but password not in SystemSecrets - generate and store it
                secrets_password = DBPasswordService.generate_password()
                passwords_to_store[DBPasswordService.SECRET_KEY_SECRETS] = (
                    secrets_password
                )
                conn.execute(
                    text(
                        f'ALTER ROLE "{DBPasswordService.ROLE_SECRETS}" WITH LOGIN PASSWORD :password'
                    ),
                    {"password": secrets_password},
                )

            # Create or update leyzen_orchestrator role
            if DBPasswordService.ROLE_ORCHESTRATOR not in existing_roles:
                orchestrator_password = DBPasswordService.generate_password()
                conn.execute(
                    text(
                        f'CREATE ROLE "{DBPasswordService.ROLE_ORCHESTRATOR}" WITH LOGIN PASSWORD :password'
                    ),
                    {"password": orchestrator_password},
                )
                passwords_to_store[DBPasswordService.SECRET_KEY_ORCHESTRATOR] = (
                    orchestrator_password
                )

            elif DBPasswordService.SECRET_KEY_ORCHESTRATOR not in existing_secret_keys:
                # Role exists but password not in SystemSecrets - generate and store it
                orchestrator_password = DBPasswordService.generate_password()
                passwords_to_store[DBPasswordService.SECRET_KEY_ORCHESTRATOR] = (
                    orchestrator_password
                )
                conn.execute(
                    text(
                        f'ALTER ROLE "{DBPasswordService.ROLE_ORCHESTRATOR}" WITH LOGIN PASSWORD :password'
                    ),
                    {"password": orchestrator_password},
                )

        # Configure privileges in a separate phase
        # This ensures roles are created and committed before we try to grant privileges to them
        # Grant USAGE on schema public to all roles
        # Handle "tuple concurrently updated" and transaction errors gracefully (multiple workers)
        def safe_grant(statement: str, description: str = ""):
            """Execute GRANT statement in a separate transaction, handling errors gracefully."""
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    # Use a separate transaction for each GRANT to avoid transaction conflicts
                    with engine.begin() as grant_conn:
                        grant_conn.execute(text(statement))
                    # Success - break out of retry loop
                    break
                except Exception as grant_error:
                    error_str = str(grant_error).lower()
                    # Check for transaction errors that require rollback
                    is_transaction_error = (
                        "infailedsqltransaction" in error_str
                        or "current transaction is aborted" in error_str
                    )
                    is_concurrent_error = (
                        "tuple concurrently updated" in error_str
                        or "internalerror" in error_str
                    )

                    if is_concurrent_error:
                        # Another worker already granted this - that's fine
                        break
                    elif is_transaction_error and attempt < max_retries - 1:
                        # Transaction was aborted - retry in a new transaction
                        import time

                        time.sleep(0.1 * (attempt + 1))  # Small delay before retry
                        continue
                    else:
                        # Different error or max retries reached - log but continue
                        if app_logger:
                            app_logger.log(
                                f"[WARNING] Failed to {description}: {grant_error}"
                            )
                        else:
                            logger.warning(f"Failed to {description}: {grant_error}")
                        break

        safe_grant(
            'GRANT USAGE ON SCHEMA public TO "leyzen_app"',
            "grant USAGE to leyzen_app",
        )
        safe_grant(
            'GRANT USAGE ON SCHEMA public TO "leyzen_migrator"',
            "grant USAGE to leyzen_migrator",
        )
        safe_grant(
            'GRANT USAGE ON SCHEMA public TO "leyzen_secrets"',
            "grant USAGE to leyzen_secrets",
        )
        safe_grant(
            'GRANT USAGE ON SCHEMA public TO "leyzen_orchestrator"',
            "grant USAGE to leyzen_orchestrator",
        )

        # Get list of all application tables (exclude system_secrets)
        # We need a new connection for this since the previous transaction is closed
        with engine.connect() as conn:
            tables_result = conn.execute(
                text(
                    """
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = 'public'
                    AND tablename != 'system_secrets'
                    ORDER BY tablename
                    """
                )
            )
            app_tables = [row[0] for row in tables_result.fetchall()]

        # Grant privileges to leyzen_app on application tables
        for table in app_tables:
            safe_grant(
                f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "{table}" TO "leyzen_app"',
                f"grant privileges on {table} to leyzen_app",
            )

        # Grant CREATE privilege to leyzen_migrator on schema
        # This allows leyzen_migrator to create, alter, and drop tables in the schema
        # No need to grant ALTER/DROP on individual tables - CREATE on schema is sufficient
        safe_grant(
            'GRANT CREATE ON SCHEMA public TO "leyzen_migrator"',
            "grant CREATE to leyzen_migrator",
        )

        # Grant privileges to leyzen_secrets on system_secrets only
        safe_grant(
            'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "system_secrets" TO "leyzen_secrets"',
            "grant privileges on system_secrets to leyzen_secrets",
        )

        # Grant SELECT only to leyzen_orchestrator on system_secrets
        safe_grant(
            'GRANT SELECT ON TABLE "system_secrets" TO "leyzen_orchestrator"',
            "grant SELECT on system_secrets to leyzen_orchestrator",
        )

        # Revoke all privileges from leyzen_app on system_secrets
        safe_grant(
            'REVOKE ALL ON TABLE "system_secrets" FROM "leyzen_app"',
            "revoke privileges from leyzen_app on system_secrets",
        )

        # Set default privileges for future tables
        # Future tables created by leyzen_migrator will grant SELECT/INSERT/UPDATE/DELETE to leyzen_app
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        'ALTER DEFAULT PRIVILEGES FOR ROLE "leyzen_migrator" IN SCHEMA public '
                        'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "leyzen_app"'
                    )
                )
        except Exception as default_priv_error:
            # Log but don't fail - default privileges might not be critical
            error_msg = (
                f"[WARNING] Failed to set default privileges: {default_priv_error}"
            )
            if app_logger:
                app_logger.log(error_msg)
            else:
                logger.warning(error_msg)

            # Transaction commits here automatically with engine.begin()

    except Exception as transaction_error:
        # Log the error but continue to store passwords
        # Passwords were already set in PostgreSQL before the error occurred
        error_msg = f"[WARNING] Transaction error during role initialization: {transaction_error}"
        if app_logger:
            app_logger.log(error_msg)
        else:
            logger.warning(error_msg)

    finally:
        # Store passwords in SystemSecrets AFTER the transaction (or even if it failed)
        # This ensures passwords are stored even if privilege configuration has issues
        # (We're using a new admin connection, so use_admin_connection=True)
        # IMPORTANT: Store passwords even if transaction failed - passwords were already set in PostgreSQL
        if passwords_to_store:
            storage_errors = []
            for password_key, password_value in passwords_to_store.items():
                try:
                    DBPasswordService.store_password(
                        secret_key,
                        password_key,
                        password_value,
                        app,
                        use_admin_connection=True,
                    )

                except Exception as store_error:
                    # Collect errors but continue to try storing all passwords
                    error_msg = f"[ERROR] Failed to store password for {password_key} in SystemSecrets: {store_error}"
                    import traceback

                    error_msg += f"\n{traceback.format_exc()}"
                    storage_errors.append((password_key, store_error))
                    if app_logger:
                        app_logger.log(error_msg)
                    else:
                        logger.error(error_msg)

            if storage_errors:
                error_details = "; ".join(
                    [f"{key}: {str(err)}" for key, err in storage_errors]
                )
                raise RuntimeError(
                    f"Failed to store {len(storage_errors)} password(s) in SystemSecrets: {error_details}"
                )

        # Always release the advisory lock
        try:
            with engine.begin() as unlock_conn:
                unlock_conn.execute(
                    text("SELECT pg_advisory_unlock(:lock_high, :lock_low)"),
                    {"lock_high": ADVISORY_LOCK_HIGH, "lock_low": ADVISORY_LOCK_LOW},
                )
        except Exception:
            # Ignore errors when releasing lock
            pass

        engine.dispose()


def get_migrator_connection(app: Any, secret_key: str) -> Any:
    """Get a database connection using the leyzen_migrator role.

    Args:
        app: Flask app instance
        secret_key: SECRET_KEY for decrypting the migrator password

    Returns:
        SQLAlchemy engine with migrator role
    """
    from sqlalchemy import create_engine
    from common.env import load_env_with_override
    import os
    from vault.services.db_password_service import DBPasswordService

    env_values = load_env_with_override()
    env_values.update(dict(os.environ))

    postgres_host = env_values.get("POSTGRES_HOST", "postgres")
    postgres_port = env_values.get("POSTGRES_PORT", "5432")
    postgres_db = env_values.get("POSTGRES_DB", "leyzen_vault")

    migrator_password = DBPasswordService.get_password(
        secret_key, DBPasswordService.SECRET_KEY_MIGRATOR, app
    )

    if not migrator_password:
        raise RuntimeError(
            "leyzen_migrator password not found in SystemSecrets. "
            "Run init_db_roles() first."
        )

    postgres_url = f"postgresql://{DBPasswordService.ROLE_MIGRATOR}:{migrator_password}@{postgres_host}:{postgres_port}/{postgres_db}"
    return create_engine(postgres_url, pool_pre_ping=True)


def get_secrets_connection(app: Any, secret_key: str) -> Any:
    """Get a database connection using the leyzen_secrets role.

    Args:
        app: Flask app instance
        secret_key: SECRET_KEY for decrypting the secrets password

    Returns:
        SQLAlchemy engine with secrets role
    """
    from sqlalchemy import create_engine
    from common.env import load_env_with_override
    import os
    from vault.services.db_password_service import DBPasswordService

    env_values = load_env_with_override()
    env_values.update(dict(os.environ))

    postgres_host = env_values.get("POSTGRES_HOST", "postgres")
    postgres_port = env_values.get("POSTGRES_PORT", "5432")
    postgres_db = env_values.get("POSTGRES_DB", "leyzen_vault")

    secrets_password = DBPasswordService.get_password(
        secret_key, DBPasswordService.SECRET_KEY_SECRETS, app
    )

    if not secrets_password:
        raise RuntimeError(
            "leyzen_secrets password not found in SystemSecrets. "
            "Run init_db_roles() first."
        )

    postgres_url = f"postgresql://{DBPasswordService.ROLE_SECRETS}:{secrets_password}@{postgres_host}:{postgres_port}/{postgres_db}"
    return create_engine(postgres_url, pool_pre_ping=True)


def init_db(app) -> bool:
    """Initialize database with Flask app.

    Creates all tables and indexes using SQLAlchemy. Handles cases where objects
    already exist gracefully (e.g., when database was previously initialized).

    This function will not raise exceptions for duplicate index/table errors,
    as these are expected when the database schema already exists.

    Uses PostgreSQL advisory locks to ensure only one worker performs initialization
    when multiple workers start simultaneously.

    Returns:
        bool: True if this worker actually performed the initialization,
              False if another worker did it or database was already initialized.
    """
    db.init_app(app)
    with app.app_context():
        from sqlalchemy import text as sql_text

        # Get logger early to ensure logs are written
        import logging

        logger = logging.getLogger(__name__)
        app_logger = None
        try:
            app_logger = app.config.get("LOGGER")
        except Exception:
            pass

        # Use advisory lock to ensure only one worker initializes the database
        # Lock ID: Use two 32-bit integers (high, low) for "LEYZENVAULT"
        # Split the hex value 0x4C45595A454E5641554C54 into two parts
        # High 32 bits: 0x4C45595A, Low 32 bits: 0x454E5641 (truncated, but unique enough)
        ADVISORY_LOCK_HIGH = 0x4C45595A  # "LEYZ"
        ADVISORY_LOCK_LOW = 0x5641554C  # "VAUL" (using part of the remaining)

        # Check if database is already initialized before acquiring lock
        inspector = None
        try:
            from sqlalchemy import inspect as sql_inspect

            inspector = sql_inspect(db.engine)
            existing_tables = set(inspector.get_table_names())
            # Consider database initialized if system_secrets table exists
            db_already_initialized = "system_secrets" in existing_tables
        except Exception:

            db_already_initialized = False

        if db_already_initialized:
            # Check if another worker already logged this by checking system_settings
            already_logged = False
            try:
                SystemSettings = globals()["SystemSettings"]
                existing_log = (
                    db.session.query(SystemSettings)
                    .filter_by(key="init_status_logged")
                    .first()
                )
                if existing_log and existing_log.value == "true":
                    already_logged = True
            except Exception:
                pass

            if not already_logged:

                lock_acquired = False
                try:
                    result = db.session.execute(
                        sql_text("SELECT pg_try_advisory_lock(:lock_high, :lock_low)"),
                        {
                            "lock_high": ADVISORY_LOCK_HIGH,
                            "lock_low": ADVISORY_LOCK_LOW,
                        },
                    )
                    lock_acquired = result.scalar() is True
                    db.session.commit()

                    if lock_acquired:
                        # Double-check after acquiring lock (another worker might have set it)
                        try:
                            SystemSettings = globals()["SystemSettings"]
                            existing_log = (
                                db.session.query(SystemSettings)
                                .filter_by(key="init_status_logged")
                                .first()
                            )
                            if existing_log and existing_log.value == "true":
                                already_logged = True
                            else:
                                # Set flag and log
                                if existing_log:
                                    existing_log.value = "true"
                                else:
                                    from uuid import uuid4

                                    log_flag = SystemSettings(
                                        id=str(uuid4()),
                                        key="init_status_logged",
                                        value="true",
                                    )
                                    db.session.add(log_flag)
                                db.session.commit()

                                if app_logger:
                                    app_logger.log(
                                        "[INIT] Database already initialized, skipping initialization"
                                    )
                                    app_logger.flush()
                                else:
                                    logger.info(
                                        "[INIT] Database already initialized, skipping initialization"
                                    )
                        except Exception:

                            if app_logger:
                                app_logger.log(
                                    "[INIT] Database already initialized, skipping initialization"
                                )
                                app_logger.flush()
                            else:
                                logger.info(
                                    "[INIT] Database already initialized, skipping initialization"
                                )

                        # Release lock
                        try:
                            db.session.execute(
                                sql_text(
                                    "SELECT pg_advisory_unlock(:lock_high, :lock_low)"
                                ),
                                {
                                    "lock_high": ADVISORY_LOCK_HIGH,
                                    "lock_low": ADVISORY_LOCK_LOW,
                                },
                            )
                            db.session.commit()
                        except Exception:
                            db.session.rollback()
                except Exception:
                    db.session.rollback()

            # Always run migrations even if database is already initialized
            # Migrations are idempotent and safe to run multiple times
            try:
                from vault.database.migrations.registry import run_migrations

                run_migrations(app_logger)
            except Exception as migration_error:
                log_msg = (
                    f"[MIGRATIONS] ERROR: Migration system failed: {migration_error}"
                )
                if app_logger:
                    app_logger.log(log_msg)
                else:
                    logger.error(log_msg)
                # Don't re-raise - other workers might succeed

            return False

        # Use a small random delay to avoid all workers trying at exactly the same time
        import time
        import random

        lock_acquired = False
        max_retries = 10
        base_delay = 0.1 + random.uniform(
            0, 0.2
        )  # Random delay between 0.1 and 0.3 seconds

        for attempt in range(max_retries):
            try:
                # Always use non-blocking lock with retries (two-integer version)
                result = db.session.execute(
                    sql_text("SELECT pg_try_advisory_lock(:lock_high, :lock_low)"),
                    {"lock_high": ADVISORY_LOCK_HIGH, "lock_low": ADVISORY_LOCK_LOW},
                )
                lock_acquired = result.scalar() is True
                db.session.commit()

                if lock_acquired:
                    # Lock successfully acquired - only log if we're actually going to initialize
                    # (not if database is already initialized)
                    break
                else:
                    pass

            except Exception as lock_error:
                db.session.rollback()
                lock_acquired = False
                if app_logger:
                    app_logger.log(
                        f"[INIT] Lock acquisition attempt {attempt + 1} failed: {lock_error}"
                    )
                    app_logger.flush()

            if attempt < max_retries - 1 and not lock_acquired:
                # Exponential backoff with jitter
                delay = base_delay * (2**attempt) + random.uniform(0, 0.1)
                time.sleep(delay)

        if not lock_acquired:

            time.sleep(2)
            # Even if we don't have the lock, we should still run migrations
            # Migrations are idempotent and safe to run multiple times
            try:
                from vault.database.migrations.registry import run_migrations

                run_migrations(app_logger)
            except Exception as migration_error:
                log_msg = (
                    f"[MIGRATIONS] ERROR: Migration system failed: {migration_error}"
                )
                if app_logger:
                    app_logger.log(log_msg)
                else:
                    logger.error(log_msg)
                # Don't re-raise here - other worker might succeed
            return False

        # This worker has the lock - proceed with initialization
        initialization_performed = False

        # Double-check if database is initialized NOW (after acquiring lock)
        # Another worker might have finished initialization while we were waiting
        try:
            from sqlalchemy import inspect as sql_inspect

            inspector = sql_inspect(db.engine)
            existing_tables = set(inspector.get_table_names())
            if "system_secrets" in existing_tables:
                db_already_initialized = True
        except Exception:
            pass

        if db_already_initialized:
            initialization_performed = False
            if app_logger:
                app_logger.log(
                    "[INIT] Database already initialized, skipping table creation"
                )
                app_logger.flush()
            else:
                logger.info(
                    "[INIT] Database already initialized, skipping table creation"
                )

            # Still run migrations even if database is already initialized
            # New migrations may have been added since last initialization
            try:
                from vault.database.migrations.registry import run_migrations

                run_migrations(app_logger)
            except Exception as migration_error:
                log_msg = (
                    f"[MIGRATIONS] ERROR: Migration system failed: {migration_error}"
                )
                if app_logger:
                    app_logger.log(log_msg)
                else:
                    logger.error(log_msg)
                # Re-raise to prevent startup with incomplete migrations
                raise

            try:
                db.session.execute(
                    sql_text("SELECT pg_advisory_unlock(:lock_high, :lock_low)"),
                    {"lock_high": ADVISORY_LOCK_HIGH, "lock_low": ADVISORY_LOCK_LOW},
                )
                db.session.commit()
            except Exception:
                db.session.rollback()
            return False
        else:
            initialization_performed = True
            if app_logger:
                app_logger.log("[INIT] Starting database initialization...")
                app_logger.flush()
            else:
                logger.info("[INIT] Starting database initialization...")

        # to ensure system_secrets table exists before storing passwords

        # Helper function to check if error is a duplicate/already exists error
        def is_duplicate_error(error: Exception) -> bool:
            """Check if error is about duplicate objects (expected for existing databases)."""
            # Check error message
            error_msg = str(error)
            if hasattr(error, "orig") and error.orig:
                error_msg = str(error.orig)

            # Also check the exception's args
            error_parts = [error_msg]
            if hasattr(error, "args") and error.args:
                error_parts.extend(str(arg) for arg in error.args)

            # Check all error messages
            for msg in error_parts:
                msg_lower = msg.lower()
                duplicate_indicators = [
                    "duplicatetable",
                    "already exists",
                    "duplicate key",
                    "relation.*already exists",
                    "duplicate",
                    "duplicate index",
                    "duplicate constraint",
                    "pg_type_typname_nsp_index",  # PostgreSQL type already exists
                    "uniqueviolation",
                ]
                # Also check for specific PostgreSQL error codes and patterns
                if any(indicator in msg_lower for indicator in duplicate_indicators):
                    return True
                # Check for PostgreSQL error codes:
                # - 42P07 (duplicate_table)
                # - 42710 (duplicate_object)
                # - 23505 (unique_violation) - for ENUM types and other unique constraints
                if hasattr(error, "orig") and hasattr(error.orig, "pgcode"):
                    if error.orig.pgcode in ("42P07", "42710", "23505"):
                        return True

            return False

        # Clean up indexes that may conflict with table creation
        # Drop indexes before db.create_all() to prevent duplicate index errors
        try:
            from sqlalchemy.sql import text as sql_text

            # Clean up indexes before creating tables
            all_problematic_indexes = [
                "ix_system_secrets_key",
                "ix_magic_link_tokens_expires_at",
                "ix_magic_link_tokens_email",
            ]

            for idx_name in all_problematic_indexes:
                try:
                    db.session.execute(
                        sql_text(f'DROP INDEX IF EXISTS "{idx_name}" CASCADE')
                    )
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    pass

            # Get list of all existing tables first
            from sqlalchemy import inspect as sql_inspect

            inspector = sql_inspect(db.engine)
            existing_tables_set = set(inspector.get_table_names())

            # Get all indexes from pg_indexes
            all_indexes_query = db.session.execute(
                sql_text(
                    """
                    SELECT indexname, tablename
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                    ORDER BY tablename, indexname
                """
                )
            )
            all_indexes = [(row[0], row[1]) for row in all_indexes_query.fetchall()]

            # Find orphaned indexes (indexes whose tables don't exist)
            orphaned_indexes = []
            for idx_name, table_name in all_indexes:
                if table_name not in existing_tables_set:
                    orphaned_indexes.append((idx_name, table_name))

            # Drop known indexes that may conflict
            # SQLAlchemy will recreate them properly during db.create_all()
            known_problematic_indexes = [
                "ix_system_secrets_key",
                "ix_magic_link_tokens_expires_at",
                "ix_magic_link_tokens_email",
            ]

            for idx_name in known_problematic_indexes:
                try:
                    db.session.execute(
                        sql_text(f'DROP INDEX IF EXISTS "{idx_name}" CASCADE')
                    )
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    pass

            for idx_name, table_name in orphaned_indexes:
                try:
                    db.session.execute(
                        sql_text(f'DROP INDEX IF EXISTS "{idx_name}" CASCADE')
                    )
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    pass
        except Exception as cleanup_error:
            # Log the error but continue - we'll try to handle it in the create_all error handler
            if app_logger:
                app_logger.log(
                    f"[WARNING] Failed to clean orphaned indexes: {cleanup_error}"
                )
            else:
                logger.warning(
                    f"Failed to clean orphaned indexes: {cleanup_error}",
                    exc_info=True,
                )

        # Create all tables and indexes using SQLAlchemy

        try:
            # Log using app logger if available, otherwise use standard logger

            # Create specific tables manually with SQL before db.create_all()
            # Prevents db.create_all() from trying to create indexes for non-existent tables
            from sqlalchemy.sql import text as sql_text
            from sqlalchemy import inspect as sql_inspect

            problematic_tables = ["system_secrets", "magic_link_tokens"]

            for table_name in problematic_tables:
                try:
                    inspector = sql_inspect(db.engine)
                    if table_name in inspector.get_table_names():
                        continue  # Table already exists

                    # Create table manually if needed

                    # Get the model class
                    model_class = None
                    try:

                        # Otherwise try to import it
                        if table_name == "system_secrets":
                            from vault.database.schema import SystemSecrets

                            model_class = SystemSecrets
                        elif table_name == "magic_link_tokens":
                            from vault.database.schema import MagicLinkToken

                            model_class = MagicLinkToken
                    except ImportError:
                        # Models might not be imported yet
                        pass

                    if model_class:
                        # Clean up orphaned indexes for this table first
                        try:
                            index_check = db.session.execute(
                                sql_text(
                                    """
                                    SELECT indexname FROM pg_indexes
                                    WHERE tablename = :table_name
                                    AND schemaname = 'public'
                                """
                                ),
                                {"table_name": table_name},
                            )
                            orphaned_indexes = [
                                row[0] for row in index_check.fetchall()
                            ]
                            for idx_name in orphaned_indexes:
                                try:
                                    db.session.execute(
                                        sql_text(
                                            f'DROP INDEX IF EXISTS "{idx_name}" CASCADE'
                                        )
                                    )
                                    db.session.commit()
                                except Exception:
                                    db.session.rollback()
                        except Exception:
                            pass

                        # Create table manually without indexes
                        table_def = model_class.__table__
                        columns = []
                        from sqlalchemy.dialects import postgresql

                        # Use SQLAlchemy's dialect to get correct PostgreSQL types
                        for col in table_def.columns:
                            # Get the PostgreSQL-specific type using the dialect compiler
                            col_type_obj = col.type
                            # Convert DATETIME to TIMESTAMP for PostgreSQL
                            if isinstance(col_type_obj, DateTime):
                                if col_type_obj.timezone:
                                    col_type = "TIMESTAMP WITH TIME ZONE"
                                else:
                                    col_type = "TIMESTAMP"
                            else:
                                # Use the dialect to compile the type
                                col_type = str(
                                    col_type_obj.compile(dialect=postgresql.dialect())
                                )

                            nullable = "NULL" if col.nullable else "NOT NULL"
                            default = ""
                            if col.server_default is not None:
                                if hasattr(col.server_default, "arg"):
                                    default_value = str(col.server_default.arg)
                                    default = f" DEFAULT {default_value}"
                                else:
                                    default_value = str(col.server_default)
                                    # Handle func.now() and similar
                                    if (
                                        "now()" in default_value.lower()
                                        or "gen_random_uuid()" in default_value.lower()
                                    ):
                                        default = f" DEFAULT {default_value}"
                                    else:
                                        default = f" DEFAULT {default_value}"
                            elif col.default is not None:
                                if hasattr(col.default, "arg"):
                                    default_value = str(col.default.arg)
                                    default = f" DEFAULT {default_value}"
                            columns.append(
                                f'"{col.name}" {col_type} {nullable}{default}'
                            )

                        create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(columns)})'
                        db.session.execute(sql_text(create_sql))
                        db.session.commit()

                        # Now create indexes manually to prevent SQLAlchemy from trying to create them
                        # and failing because they already exist as orphaned indexes
                        try:
                            # Get index definitions from table
                            for idx in table_def.indexes:
                                idx_name = idx.name
                                # Check if index already exists
                                idx_check = db.session.execute(
                                    sql_text(
                                        """
                                        SELECT EXISTS (
                                            SELECT 1 FROM pg_indexes
                                            WHERE indexname = :idx_name
                                            AND schemaname = 'public'
                                        )
                                    """
                                    ),
                                    {"idx_name": idx_name},
                                )
                                idx_exists = idx_check.fetchone()[0]

                                if not idx_exists:
                                    # Create index
                                    columns_str = ", ".join(
                                        f'"{col.name}"' for col in idx.columns
                                    )
                                    unique_str = "UNIQUE " if idx.unique else ""
                                    create_idx_sql = f'CREATE {unique_str}INDEX IF NOT EXISTS "{idx_name}" ON "{table_name}" ({columns_str})'

                                    try:
                                        db.session.execute(sql_text(create_idx_sql))
                                        db.session.commit()
                                    except Exception as idx_error:
                                        db.session.rollback()
                                        if is_duplicate_error(idx_error):
                                            # Index already exists - that's fine
                                            pass
                                        else:
                                            log_msg = f"[WARNING] Failed to create index {idx_name}: {idx_error}"
                                            if app_logger:
                                                app_logger.log(log_msg)
                                            else:
                                                logger.warning(log_msg)
                                # Index exists or was created
                        except Exception as idx_error:
                            # Index creation failed - log but continue
                            log_msg = f"[WARNING] Failed to create indexes for {table_name}: {idx_error}"
                            if app_logger:
                                app_logger.log(log_msg)
                            else:
                                logger.warning(log_msg)

                        # Table created successfully
                except Exception as manual_create_error:
                    db.session.rollback()
                    # Only log non-duplicate errors (duplicate errors are expected)
                    if not is_duplicate_error(manual_create_error):
                        log_msg = f"[WARNING] Failed to manually create table {table_name}: {manual_create_error}"
                        if app_logger:
                            app_logger.log(log_msg)
                        else:
                            logger.warning(log_msg)

            # Drop indexes again right before db.create_all()
            # Ensures indexes are removed before SQLAlchemy attempts to create them
            import time

            for idx_name in [
                "ix_system_secrets_key",
                "ix_magic_link_tokens_expires_at",
                "ix_magic_link_tokens_email",
            ]:
                try:
                    # Drop with CASCADE and verify it's gone
                    db.session.execute(
                        sql_text(f'DROP INDEX IF EXISTS "{idx_name}" CASCADE')
                    )
                    db.session.commit()

                    # Verify the index is actually gone
                    check_idx = db.session.execute(
                        sql_text(
                            """
                            SELECT EXISTS (
                                SELECT 1 FROM pg_indexes
                                WHERE indexname = :idx_name
                                AND schemaname = 'public'
                            )
                        """
                        ),
                        {"idx_name": idx_name},
                    )
                    still_exists = check_idx.fetchone()[0]
                    if still_exists:
                        # Force drop without IF EXISTS
                        db.session.execute(sql_text(f'DROP INDEX "{idx_name}" CASCADE'))
                        db.session.commit()

                except Exception:
                    db.session.rollback()
                    # Ignore errors - index may not exist or already dropped
                    pass

            # Small delay to ensure indexes are fully dropped
            time.sleep(0.1)

            # Wrap db.create_all() in try/except to handle duplicate index errors
            # SQLAlchemy may try to create indexes that already exist

            try:
                db.create_all()
            except Exception as create_all_error:
                # Check if this is a duplicate index error - if so, ignore it
                # Tables are still created even if some indexes fail
                if is_duplicate_error(create_all_error):
                    # Ignore duplicate errors when database is already initialized
                    pass
                else:
                    # Re-raise unexpected errors
                    log_msg = f"[ERROR] db.create_all() failed with unexpected error: {create_all_error}"
                    if app_logger:
                        app_logger.log(log_msg)
                    else:
                        logger.error(log_msg)
                    raise

            # Initialize PostgreSQL roles AFTER tables are created
            # This ensures system_secrets table exists before storing passwords
            try:
                secret_key = app.config.get("SECRET_KEY")

                if secret_key:
                    init_db_roles(app, secret_key)

                else:
                    log_msg = "[WARNING] SECRET_KEY not available, skipping role initialization"
                    if app_logger:
                        app_logger.log(log_msg)
                    else:
                        logger.warning(log_msg)
            except RuntimeError as roles_error:
                # RuntimeError indicates a critical failure (e.g., password storage failed)
                # Don't silently ignore - this is a security issue
                error_msg = f"[ERROR] Critical failure initializing PostgreSQL roles: {roles_error}"
                if app_logger:
                    app_logger.log(error_msg)
                else:
                    logger.error(error_msg)
                raise  # Re-raise to prevent startup with incomplete security setup
            except Exception as roles_error:
                # Other exceptions might be non-critical (e.g., roles already exist)
                log_msg = (
                    f"[WARNING] Failed to initialize PostgreSQL roles: {roles_error}"
                )
                if app_logger:
                    app_logger.log(log_msg)
                else:
                    logger.warning(log_msg)
                # Continue anyway - roles might already exist

            import time

            time.sleep(0.5)

            # Run database migrations using the uniform migration system

            try:
                from vault.database.migrations.registry import run_migrations

                run_migrations(app_logger)
            except Exception as migration_error:
                log_msg = (
                    f"[MIGRATIONS] ERROR: Migration system failed: {migration_error}"
                )
                if app_logger:
                    app_logger.log(log_msg)
                else:
                    logger.error(log_msg)
                # Re-raise to prevent startup with incomplete migrations
                raise

            # Update privileges on newly created tables
            if secret_key:
                try:
                    from sqlalchemy import create_engine, text
                    from common.env import load_env_with_override
                    import os

                    env_values = load_env_with_override()
                    env_values.update(dict(os.environ))

                    postgres_host = env_values.get("POSTGRES_HOST", "postgres")
                    postgres_port = env_values.get("POSTGRES_PORT", "5432")
                    postgres_db = env_values.get("POSTGRES_DB", "leyzen_vault")
                    postgres_user = env_values.get("POSTGRES_USER", "leyzen")
                    postgres_password = env_values.get("POSTGRES_PASSWORD", "")

                    if postgres_password:
                        postgres_url = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"
                        admin_engine = create_engine(postgres_url, pool_pre_ping=True)

                        try:
                            # Use engine.begin() for automatic transaction management
                            with admin_engine.begin() as conn:
                                # Get all tables
                                tables_result = conn.execute(
                                    text(
                                        """
                                        SELECT tablename FROM pg_tables
                                        WHERE schemaname = 'public'
                                        AND tablename != 'system_secrets'
                                        ORDER BY tablename
                                        """
                                    )
                                )
                                app_tables = [
                                    row[0] for row in tables_result.fetchall()
                                ]

                                # Grant privileges to leyzen_app on all application tables
                                for table in app_tables:
                                    conn.execute(
                                        text(
                                            f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "{table}" TO "leyzen_app"'
                                        )
                                    )

                                # Ensure system_secrets privileges are correct
                                conn.execute(
                                    text(
                                        'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE "system_secrets" TO "leyzen_secrets"'
                                    )
                                )
                                conn.execute(
                                    text(
                                        'GRANT SELECT ON TABLE "system_secrets" TO "leyzen_orchestrator"'
                                    )
                                )
                                conn.execute(
                                    text(
                                        'REVOKE ALL ON TABLE "system_secrets" FROM "leyzen_app"'
                                    )
                                )
                        finally:
                            admin_engine.dispose()
                except Exception as priv_error:
                    log_msg = f"[WARNING] Failed to update privileges: {priv_error}"
                    if app_logger:
                        app_logger.log(log_msg)
                    else:
                        logger.warning(log_msg)

            log_msg = "Database initialization completed successfully"
            if app_logger:
                app_logger.log(log_msg)
                app_logger.flush()
            else:
                logger.info(log_msg)

            # This worker performed initialization
            initialization_performed = True
        except Exception as e:
            import traceback

            # Check if it's a duplicate/already exists error
            # These are expected when database schema already exists
            if is_duplicate_error(e):
                # Database objects already exist - this is expected and OK
                log_msg = (
                    "Database objects already exist (database was previously initialized). "
                    "This is normal and expected. Continuing with initialization."
                )
                logger.info(log_msg)
                # Database is already initialized, continue with verification
                # Verify all required tables exist, not just jwt_blacklist
                try:
                    from sqlalchemy import inspect as sql_inspect
                    from sqlalchemy.sql import text as sql_text
                    import time

                    # Verify all required tables exist
                    # Some tables may be missing even if db.create_all() raised a duplicate error

                    inspector = sql_inspect(db.engine)
                    existing_tables = set(inspector.get_table_names())

                    # Get all model tables that should exist

                    # Use globals() to access classes defined in this module
                    User = globals()["User"]
                    VaultSpace = globals()["VaultSpace"]
                    File = globals()["File"]
                    JWTBlacklist = globals()["JWTBlacklist"]
                    SystemSecrets = globals()["SystemSecrets"]
                    UserInvitation = globals()["UserInvitation"]
                    EmailVerificationToken = globals()["EmailVerificationToken"]
                    AuditLogEntry = globals()["AuditLogEntry"]
                    UploadSession = globals()["UploadSession"]
                    SSOProvider = globals()["SSOProvider"]
                    VaultSpaceKey = globals()["VaultSpaceKey"]
                    FileKey = globals()["FileKey"]
                    Webhook = globals()["Webhook"]
                    Device = globals()["Device"]
                    Quota = globals()["Quota"]
                    Workflow = globals()["Workflow"]
                    WorkflowExecution = globals()["WorkflowExecution"]
                    BehaviorAnalytics = globals()["BehaviorAnalytics"]
                    VaultSpaceTemplate = globals()["VaultSpaceTemplate"]
                    BackupJob = globals()["BackupJob"]
                    ReplicationTarget = globals()["ReplicationTarget"]
                    PublicShareLink = globals()["PublicShareLink"]
                    RateLimitTracking = globals()["RateLimitTracking"]
                    ShareLink = globals()["ShareLink"]
                    MagicLinkToken = globals()["MagicLinkToken"]
                    DomainRule = globals()["DomainRule"]
                    SystemSettings = globals()["SystemSettings"]
                    ApiKey = globals()["ApiKey"]
                    ExternalStorageMetadata = globals()["ExternalStorageMetadata"]
                    DatabaseBackup = globals()["DatabaseBackup"]

                    # Map table names to their model classes
                    required_tables = {
                        "users": User,
                        "vaultspaces": VaultSpace,
                        "files": File,
                        "jwt_blacklist": JWTBlacklist,
                        "system_secrets": SystemSecrets,
                        "user_invitations": UserInvitation,
                        "email_verification_tokens": EmailVerificationToken,
                        "audit_logs": AuditLogEntry,
                        "upload_sessions": UploadSession,
                        "sso_providers": SSOProvider,
                        "vaultspace_keys": VaultSpaceKey,
                        "file_keys": FileKey,
                        "webhooks": Webhook,
                        "devices": Device,
                        "quotas": Quota,
                        "workflows": Workflow,
                        "workflow_executions": WorkflowExecution,
                        "behavior_analytics": BehaviorAnalytics,
                        "vaultspace_templates": VaultSpaceTemplate,
                        "backup_jobs": BackupJob,
                        "replication_targets": ReplicationTarget,
                        "public_share_links": PublicShareLink,
                        "rate_limit_tracking": RateLimitTracking,
                        "share_links": ShareLink,
                        "magic_link_tokens": MagicLinkToken,
                        "domain_rules": DomainRule,
                        "system_settings": SystemSettings,
                        "api_keys": ApiKey,
                        "external_storage_metadata": ExternalStorageMetadata,
                        "database_backups": DatabaseBackup,
                    }

                    missing_tables = [
                        tbl
                        for tbl in required_tables.keys()
                        if tbl not in existing_tables
                    ]

                    if missing_tables:
                        log_msg = (
                            f"[INIT] CRITICAL: Some required tables are missing: {', '.join(missing_tables)}. "
                            "Creating them now..."
                        )
                        if app_logger:
                            app_logger.log(log_msg)
                        else:
                            logger.error(log_msg)

                        # Create missing tables one by one, ignoring duplicate errors
                        for table_name in missing_tables:
                            model_class = required_tables[table_name]
                            table_created = False
                            max_create_attempts = 3

                            for create_attempt in range(1, max_create_attempts + 1):
                                # First, check if table exists (it might exist but not be detected)
                                try:
                                    from sqlalchemy import inspect as sql_inspect
                                    from sqlalchemy.sql import text as sql_text

                                    inspector = sql_inspect(db.engine)
                                    existing_tables_check = inspector.get_table_names()
                                    if table_name in existing_tables_check:
                                        table_created = True
                                        break

                                    # Clean up orphaned indexes that might prevent table creation
                                    # Get all indexes for this table
                                    try:
                                        # Query for orphaned indexes
                                        index_check = db.session.execute(
                                            sql_text(
                                                """
                                                SELECT indexname FROM pg_indexes
                                                WHERE tablename = :table_name
                                                AND schemaname = 'public'
                                            """
                                            ),
                                            {"table_name": table_name},
                                        )
                                        orphaned_indexes = [
                                            row[0] for row in index_check.fetchall()
                                        ]
                                        if orphaned_indexes:
                                            # Drop orphaned indexes
                                            for idx_name in orphaned_indexes:
                                                try:
                                                    db.session.execute(
                                                        sql_text(
                                                            f'DROP INDEX IF EXISTS "{idx_name}"'
                                                        )
                                                    )
                                                    db.session.commit()
                                                except Exception as drop_error:
                                                    # Ignore errors when dropping indexes
                                                    db.session.rollback()
                                                    if (
                                                        is_duplicate_error(drop_error)
                                                        or "does not exist"
                                                        in str(drop_error).lower()
                                                    ):
                                                        pass  # Expected
                                                    else:
                                                        log_msg = f"[WARNING] Failed to drop orphaned index {idx_name}: {drop_error}"
                                                        if app_logger:
                                                            app_logger.log(log_msg)
                                                        else:
                                                            logger.warning(log_msg)
                                    except Exception:
                                        # Ignore cleanup errors - continue with table creation
                                        pass

                                except Exception:
                                    # Continue with table creation even if pre-check fails
                                    pass

                                try:
                                    # Clean up orphaned indexes before creating table
                                    try:
                                        from sqlalchemy.sql import text as sql_text

                                        # Check for orphaned indexes (indexes without their table)
                                        index_check = db.session.execute(
                                            sql_text(
                                                """
                                                SELECT indexname FROM pg_indexes
                                                WHERE tablename = :table_name
                                                AND schemaname = 'public'
                                            """
                                            ),
                                            {"table_name": table_name},
                                        )
                                        orphaned_indexes = [
                                            row[0] for row in index_check.fetchall()
                                        ]

                                        if orphaned_indexes:
                                            pass

                                            # Drop orphaned indexes
                                            for idx_name in orphaned_indexes:
                                                try:
                                                    db.session.execute(
                                                        sql_text(
                                                            f'DROP INDEX IF EXISTS "{idx_name}"'
                                                        )
                                                    )
                                                    db.session.commit()

                                                except Exception as drop_error:
                                                    # Ignore errors when dropping indexes
                                                    db.session.rollback()
                                                    if (
                                                        is_duplicate_error(drop_error)
                                                        or "does not exist"
                                                        in str(drop_error).lower()
                                                    ):
                                                        pass  # Expected
                                                    else:
                                                        log_msg = f"[WARNING] Failed to drop orphaned index {idx_name}: {drop_error}"
                                                        if app_logger:
                                                            app_logger.log(log_msg)
                                                        else:
                                                            logger.warning(log_msg)
                                    except Exception:
                                        # Ignore cleanup errors - continue with table creation
                                        pass

                                    model_class.__table__.create(
                                        db.engine, checkfirst=True
                                    )
                                    # Also try using raw SQL as fallback for critical tables
                                    if table_name in (
                                        "system_secrets",
                                        "magic_link_tokens",
                                    ):
                                        try:
                                            from sqlalchemy.sql import text as sql_text

                                            # Get table definition from model
                                            table_def = model_class.__table__
                                            columns = []
                                            for col in table_def.columns:
                                                col_type = str(col.type)
                                                nullable = (
                                                    "NULL"
                                                    if col.nullable
                                                    else "NOT NULL"
                                                )
                                                default = ""
                                                if col.server_default is not None:
                                                    default = f" DEFAULT {str(col.server_default.arg)}"
                                                elif col.default is not None:
                                                    if hasattr(col.default, "arg"):
                                                        default = f" DEFAULT {col.default.arg}"
                                                columns.append(
                                                    f"{col.name} {col_type} {nullable}{default}"
                                                )

                                            # Create table with IF NOT EXISTS
                                            create_sql = f"""
                                                CREATE TABLE IF NOT EXISTS {table_name} (
                                                    {', '.join(columns)}
                                                )
                                            """
                                            db.session.execute(sql_text(create_sql))
                                            db.session.commit()

                                        except Exception as sql_error:
                                            # SQL fallback failed - log but continue with normal flow
                                            log_msg = f"[DEBUG] Raw SQL creation failed for {table_name}: {sql_error}"
                                            if app_logger:
                                                app_logger.log(log_msg)
                                            else:
                                                logger.debug(log_msg)
                                    # Verify table was actually created
                                    time.sleep(0.5)
                                    inspector = sql_inspect(db.engine)
                                    existing_tables_after = inspector.get_table_names()

                                    if table_name in existing_tables_after:
                                        table_created = True
                                        break
                                    else:
                                        if create_attempt < max_create_attempts:
                                            log_msg = f"[WARNING] Table {table_name} creation attempt {create_attempt} did not create table. Retrying..."
                                            if app_logger:
                                                app_logger.log(log_msg)
                                            else:
                                                logger.warning(log_msg)
                                        else:
                                            log_msg = f"[ERROR] Table {table_name} was not created after {max_create_attempts} attempts"
                                            if app_logger:
                                                app_logger.log(log_msg)
                                            else:
                                                logger.error(log_msg)
                                except Exception as table_error:
                                    if is_duplicate_error(table_error):
                                        # Table might have been created by another process
                                        time.sleep(0.5)
                                        inspector = sql_inspect(db.engine)
                                        existing_tables_after = (
                                            inspector.get_table_names()
                                        )
                                        if table_name in existing_tables_after:
                                            table_created = True
                                            break
                                    else:
                                        if create_attempt < max_create_attempts:
                                            log_msg = f"[WARNING] Failed to create table {table_name} (attempt {create_attempt}/{max_create_attempts}): {table_error}. Retrying..."
                                            if app_logger:
                                                app_logger.log(log_msg)
                                            else:
                                                logger.warning(log_msg)
                                            time.sleep(1.0)
                                        else:
                                            log_msg = f"[ERROR] Failed to create table {table_name} after {max_create_attempts} attempts: {table_error}"
                                            if app_logger:
                                                app_logger.log(log_msg)
                                            else:
                                                logger.error(log_msg)
                            if not table_created:
                                import traceback

                                error_msg = f"[ERROR] CRITICAL: Failed to create table {table_name} after all attempts.\n{traceback.format_exc()}"
                                if app_logger:
                                    app_logger.log(error_msg)
                                else:
                                    logger.error(error_msg)
                        # Refresh inspector after creating tables
                        inspector = sql_inspect(db.engine)
                        existing_tables = set(inspector.get_table_names())
                        still_missing = [
                            tbl
                            for tbl in required_tables.keys()
                            if tbl not in existing_tables
                        ]
                        if still_missing:
                            log_msg = (
                                f"[WARNING] Some tables are still missing after creation attempt: "
                                f"{', '.join(still_missing)}"
                            )
                            if app_logger:
                                app_logger.log(log_msg)
                            else:
                                logger.warning(log_msg)
                    # Now verify and create jti column if missing

                    # RADICAL SOLUTION: Use direct SQL to ensure table and column exist
                    # Don't rely on inspector which may not see tables immediately

                    try:
                        # First, try to create the table if it doesn't exist (idempotent)
                        db.session.execute(
                            sql_text(
                                """
                                CREATE TABLE IF NOT EXISTS jwt_blacklist (
                                    id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
                                    token VARCHAR(512) NOT NULL UNIQUE,
                                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                                )
                            """
                            )
                        )
                        db.session.commit()

                    except Exception:
                        # Table might already exist, that's OK
                        db.session.rollback()

                    # Now ensure jti column exists - use IF NOT EXISTS equivalent
                    try:
                        # Check if column exists by trying to add it (will fail if exists, that's OK)
                        db.session.execute(
                            sql_text(
                                "ALTER TABLE jwt_blacklist ADD COLUMN jti VARCHAR(255)"
                            )
                        )
                        db.session.commit()

                    except Exception as add_col_error:
                        error_str = str(add_col_error).lower()
                        if "already exists" in error_str or "duplicate" in error_str:
                            # Column already exists - that's what we want!
                            db.session.rollback()

                        else:
                            # Different error - log but continue
                            db.session.rollback()

                    # Ensure index exists
                    try:
                        db.session.execute(
                            sql_text(
                                "CREATE UNIQUE INDEX IF NOT EXISTS ix_jwt_blacklist_jti ON jwt_blacklist(jti) WHERE jti IS NOT NULL"
                            )
                        )
                        db.session.commit()

                    except Exception:
                        db.session.rollback()

                    # Clear cache
                    try:
                        from vault.services.auth_service import reset_jti_column_cache

                        reset_jti_column_cache()
                    except Exception:
                        pass

                    # Final verification: try to query the column
                    try:
                        result = db.session.execute(
                            sql_text("SELECT jti FROM jwt_blacklist LIMIT 0")
                        )

                    except Exception as verify_error:
                        # This is bad - column doesn't exist or can't be queried
                        error_str = str(verify_error).lower()
                        if "column" in error_str and "jti" in error_str:
                            log_msg = f"[ERROR] CRITICAL: jti column verification failed: {verify_error}"
                            if app_logger:
                                app_logger.log(log_msg)
                            else:
                                logger.error(log_msg)

                            try:
                                db.session.execute(
                                    sql_text(
                                        "ALTER TABLE jwt_blacklist ADD COLUMN IF NOT EXISTS jti VARCHAR(255)"
                                    )
                                )
                                db.session.commit()

                            except Exception:
                                # PostgreSQL doesn't support IF NOT EXISTS for ALTER TABLE ADD COLUMN

                                pass
                        else:
                            log_msg = f"[WARNING] jti verification query failed: {verify_error}"
                            if app_logger:
                                app_logger.log(log_msg)
                            else:
                                logger.warning(log_msg)
                except Exception as jti_check_error:
                    import traceback

                    log_msg = f"[ERROR] Failed to verify jti column after duplicate error: {jti_check_error}"
                    if app_logger:
                        app_logger.log(
                            log_msg, context={"traceback": traceback.format_exc()}
                        )
                    else:
                        logger.error(log_msg, exc_info=True)
            else:
                # Different error - check if it's a database connection/configuration issue
                error_type = type(e).__name__
                error_module = type(e).__module__

                # Check if it's a SQLAlchemy database error
                if "sqlalchemy" in error_module or "psycopg2" in error_module:
                    # It's a database error, but not a duplicate error
                    # This could be a real problem (connection, permissions, etc.)
                    logger.error(
                        f"Database initialization error ({error_type}): {e}",
                        exc_info=True,
                    )
                    raise
                else:
                    # Unexpected error type - log and re-raise
                    logger.error(
                        f"Unexpected error during database initialization ({error_type}): {e}",
                        exc_info=True,
                    )
                    raise
        finally:
            # Always release the advisory lock
            try:
                db.session.execute(
                    sql_text("SELECT pg_advisory_unlock(:lock_high, :lock_low)"),
                    {"lock_high": ADVISORY_LOCK_HIGH, "lock_low": ADVISORY_LOCK_LOW},
                )
                db.session.commit()
            except Exception:
                db.session.rollback()
                # Ignore errors when releasing lock

        # Return True if this worker performed initialization, False otherwise
        return initialization_performed
