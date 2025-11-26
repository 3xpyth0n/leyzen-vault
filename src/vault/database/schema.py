"""SQLAlchemy database schema for Leyzen Vault."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
        # If it's already a string, return as-is
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
                # If value doesn't match any enum value, try to find by value
                for member in SSOProviderType:
                    if member.value == value:
                        return member
                # If still not found, return the string (shouldn't happen in normal operation)
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
    # Note: unique constraint on jti is created via partial index in migration
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
        # Note: jti index is created separately via migration to handle cases where column doesn't exist yet
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
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "action": self.action,
            "file_id": self.file_id,
            "user_ip": self.user_ip,
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
    # Note: token has unique=True which creates an index automatically,
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


def init_db(app) -> None:
    """Initialize database with Flask app.

    Creates all tables and indexes using SQLAlchemy. Handles cases where objects
    already exist gracefully (e.g., when database was previously initialized).

    This function will not raise exceptions for duplicate index/table errors,
    as these are expected when the database schema already exists.
    """
    db.init_app(app)
    with app.app_context():
        import logging

        logger = logging.getLogger(__name__)
        # Also try to use app logger if available (for consistency with app.py logs)
        app_logger = None
        try:
            app_logger = app.config.get("LOGGER")
        except Exception:
            pass

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
            import sys

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
                logger.warning(f"Failed to clean orphaned indexes: {cleanup_error}")
            import sys
            import traceback

            print(
                f"[WARNING] Failed to clean orphaned indexes: {cleanup_error}\n{traceback.format_exc()}",
                file=sys.stderr,
                flush=True,
            )

        # Create all tables and indexes using SQLAlchemy
        # If objects already exist, that's fine - database is already initialized
        try:
            # Log using app logger if available, otherwise use standard logger
            # Also print to stderr for visibility in Docker logs
            log_msg = "[INIT] Creating database tables..."
            if app_logger:
                app_logger.log(log_msg)
            else:
                logger.info(log_msg)
            import sys

            print(log_msg, file=sys.stderr, flush=True)

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
                        # Try to get the model from required_tables (if it's already loaded)
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
                        from sqlalchemy.schema import CreateTable

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
                                            print(log_msg, file=sys.stderr, flush=True)
                                # Index exists or was created
                        except Exception as idx_error:
                            # Index creation failed - log but continue
                            log_msg = f"[WARNING] Failed to create indexes for {table_name}: {idx_error}"
                            print(log_msg, file=sys.stderr, flush=True)

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
                        print(log_msg, file=sys.stderr, flush=True)

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

                except Exception as drop_err:
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
                    print(log_msg, file=sys.stderr, flush=True)
                    raise

            # Wait a moment to ensure all tables are fully created and visible
            import time

            time.sleep(0.5)

            # Validate api_keys.key_prefix column can store full prefixes (e.g., "leyz_<base64>")
            from sqlalchemy import inspect as sql_inspect
            from sqlalchemy.sql import text as sql_text

            try:
                desired_prefix_length = 64
                inspector = sql_inspect(db.engine)

                # Ensure the api_keys table exists before validating column length
                # Handles both fresh installs and upgrades
                if "api_keys" not in inspector.get_table_names():
                    try:
                        ApiKey.__table__.create(bind=db.engine, checkfirst=True)
                    except Exception:
                        # Continue to column verification below
                        pass

                    # Refresh inspector to pick up the newly created table if creation succeeded
                    inspector = sql_inspect(db.engine)

                if "api_keys" in inspector.get_table_names():
                    columns = inspector.get_columns("api_keys")
                    key_prefix_column = next(
                        (col for col in columns if col.get("name") == "key_prefix"),
                        None,
                    )

                    if key_prefix_column:
                        column_type = key_prefix_column.get("type")
                        current_length = (
                            column_type.length
                            if hasattr(column_type, "length")
                            else None
                        )

                        if (
                            current_length is not None
                            and current_length < desired_prefix_length
                        ):
                            db.session.execute(
                                sql_text(
                                    f"ALTER TABLE api_keys ALTER COLUMN key_prefix TYPE VARCHAR({desired_prefix_length})"
                                )
                            )
                            db.session.commit()

                            log_msg = (
                                "[INIT] api_keys.key_prefix length increased "
                                f"from {current_length} to {desired_prefix_length}"
                            )
                            if app_logger:
                                app_logger.log(log_msg)
                            else:
                                logger.info(log_msg)
                            print(log_msg, file=sys.stderr, flush=True)
                else:
                    log_msg = "[WARNING] api_keys table missing; could not verify key_prefix length"
                    if app_logger:
                        app_logger.log(log_msg)
                    else:
                        logger.warning(log_msg)
                    print(log_msg, file=sys.stderr, flush=True)
            except Exception as api_key_prefix_error:
                log_msg = (
                    "[WARNING] Failed to ensure api_keys.key_prefix length: "
                    f"{api_key_prefix_error}"
                )
                if app_logger:
                    app_logger.log(log_msg)
                else:
                    logger.warning(log_msg)
                print(log_msg, file=sys.stderr, flush=True)

            # CRITICAL: Always ensure jti column exists after db.create_all()
            # SQLAlchemy may not create nullable columns correctly in some cases
            # We must explicitly create it if missing
            try:
                from sqlalchemy import inspect as sql_inspect
                from sqlalchemy.sql import text as sql_text

                inspector = sql_inspect(db.engine)
                if "jwt_blacklist" in inspector.get_table_names():
                    # Check if jti column exists
                    columns = [
                        col["name"] for col in inspector.get_columns("jwt_blacklist")
                    ]

                    if "jti" not in columns:
                        # Creating jti column
                        db.session.execute(
                            sql_text(
                                "ALTER TABLE jwt_blacklist ADD COLUMN jti VARCHAR(255)"
                            )
                        )
                        db.session.execute(
                            sql_text(
                                "CREATE UNIQUE INDEX IF NOT EXISTS ix_jwt_blacklist_jti ON jwt_blacklist(jti) WHERE jti IS NOT NULL"
                            )
                        )
                        db.session.commit()
                        # jti column created
                        # Clear cache
                        try:
                            from vault.services.auth_service import (
                                reset_jti_column_cache,
                            )

                            reset_jti_column_cache()
                        except Exception:
                            pass
            except Exception as pre_check_error:
                log_msg = (
                    f"[WARNING] Pre-check for jti column failed: {pre_check_error}"
                )
                if app_logger:
                    app_logger.log(log_msg)
                else:
                    logger.warning(log_msg)
                # Continue - the migration logic below will handle it

            # Migrate jwt_blacklist table to add jti column if missing
            # SECURITY: In production, jti column is mandatory for JWT replay protection
            try:
                from sqlalchemy import inspect as sql_inspect
                from sqlalchemy.sql import text as sql_text
                from sqlalchemy.exc import ProgrammingError, InternalError

                # Check if jwt_blacklist table exists first
                # Retry logic handles transient database visibility issues
                inspector = sql_inspect(db.engine)
                table_exists = False
                max_table_retries = 5
                table_retry_delay = 0.3

                for table_attempt in range(max_table_retries):
                    table_names = inspector.get_table_names()
                    if "jwt_blacklist" in table_names:
                        table_exists = True
                        break
                    if table_attempt < max_table_retries - 1:
                        logger.debug(
                            f"jwt_blacklist table not found yet, retrying ({table_attempt + 1}/{max_table_retries})..."
                        )
                        time.sleep(table_retry_delay)
                        # Refresh inspector
                        inspector = sql_inspect(db.engine)

                if not table_exists:
                    error_msg = (
                        "[ERROR] jwt_blacklist table does not exist after db.create_all(). "
                        "This may indicate a schema issue."
                    )
                    if app_logger:
                        app_logger.log(error_msg)
                    else:
                        logger.warning(error_msg)
                else:
                    # Retry logic for checking columns (handles transient database issues)
                    columns = None
                    max_retries = 5
                    retry_delay = 0.3

                    for attempt in range(max_retries):
                        try:
                            columns = [
                                col["name"]
                                for col in inspector.get_columns("jwt_blacklist")
                            ]
                            break
                        except Exception as e:
                            if attempt < max_retries - 1:
                                logger.debug(
                                    f"Retry {attempt + 1}/{max_retries} for checking jti column: {e}"
                                )
                                time.sleep(retry_delay)
                                # Refresh inspector
                                inspector = sql_inspect(db.engine)
                            else:
                                logger.warning(
                                    f"Failed to check jti column after {max_retries} attempts: {e}"
                                )
                                raise

                    if columns is not None:
                        log_msg = (
                            f"[INIT] jwt_blacklist columns found: {', '.join(columns)}"
                        )
                        if app_logger:
                            app_logger.log(log_msg)
                        else:
                            logger.info(log_msg)

                        # CRITICAL: Always verify and ensure jti column exists
                        # Even if db.create_all() should have created it, we must verify
                        # and create it explicitly if missing
                        # This is necessary because SQLAlchemy may not create nullable columns with constraints correctly
                        if "jti" not in columns:
                            log_msg = (
                                "[INIT] CRITICAL: jti column missing after db.create_all()! "
                                "This should not happen. Creating it now..."
                            )
                            if app_logger:
                                app_logger.log(log_msg)
                            else:
                                logger.error(log_msg)
                            log_msg = "[INIT] jti column missing, adding to jwt_blacklist table..."
                            if app_logger:
                                app_logger.log(log_msg)
                            else:
                                logger.info(log_msg)
                            try:
                                db.session.execute(
                                    sql_text(
                                        "ALTER TABLE jwt_blacklist ADD COLUMN jti VARCHAR(255)"
                                    )
                                )
                                # Add unique constraint separately if needed
                                db.session.execute(
                                    sql_text(
                                        "CREATE UNIQUE INDEX IF NOT EXISTS ix_jwt_blacklist_jti ON jwt_blacklist(jti) WHERE jti IS NOT NULL"
                                    )
                                )
                                db.session.commit()
                                log_msg = "[INIT] jti column added successfully to jwt_blacklist table"
                                if app_logger:
                                    app_logger.log(log_msg)
                                else:
                                    logger.info(log_msg)

                                # Verify the column was actually created
                                time.sleep(0.2)  # Brief wait for commit to propagate
                                inspector = sql_inspect(db.engine)
                                verify_columns = [
                                    col["name"]
                                    for col in inspector.get_columns("jwt_blacklist")
                                ]
                                if "jti" in verify_columns:
                                    log_msg = "[INIT] jti column verified successfully after creation"
                                    if app_logger:
                                        app_logger.log(log_msg)
                                    else:
                                        logger.info(log_msg)
                                else:
                                    error_msg = "[ERROR] CRITICAL: jti column was not found after creation attempt!"
                                    if app_logger:
                                        app_logger.log(error_msg)
                                    else:
                                        logger.error(error_msg)
                                    raise RuntimeError(
                                        "Failed to verify jti column creation. "
                                        "The column may not have been added correctly."
                                    )

                                # Clear the cache in auth_service if it exists
                                try:
                                    from vault.services.auth_service import (
                                        reset_jti_column_cache,
                                    )

                                    reset_jti_column_cache()
                                except Exception:
                                    pass  # Cache reset is optional
                            except (ProgrammingError, InternalError) as db_error:
                                error_msg = str(db_error).lower()
                                if (
                                    "already exists" in error_msg
                                    or "duplicate" in error_msg
                                ):
                                    logger.debug(
                                        "jti column already exists in jwt_blacklist table"
                                    )
                                    # Verify it actually exists
                                    time.sleep(0.2)
                                    inspector = sql_inspect(db.engine)
                                    verify_columns = [
                                        col["name"]
                                        for col in inspector.get_columns(
                                            "jwt_blacklist"
                                        )
                                    ]
                                    if "jti" not in verify_columns:
                                        logger.error(
                                            "CRITICAL: Database reported jti column exists, but verification failed!"
                                        )
                                        raise RuntimeError(
                                            "jti column verification failed after database reported it exists."
                                        )
                                else:
                                    logger.error(
                                        f"Failed to add jti column to jwt_blacklist table: {db_error}"
                                    )
                                    db.session.rollback()
                                    # In production, this is critical - raise exception
                                    try:
                                        from flask import current_app

                                        is_production = current_app.config.get(
                                            "IS_PRODUCTION", True
                                        )
                                        if is_production:
                                            raise RuntimeError(
                                                "CRITICAL: Failed to add jti column to jwt_blacklist table. "
                                                "JWT replay protection is required in production. "
                                                "Please check database permissions and retry."
                                            )
                                    except RuntimeError:
                                        raise
                                    except Exception:
                                        # If we can't check production mode, log error but continue
                                        pass
                        else:
                            # jti column exists in columns list - verify it's actually usable
                            if "jti" in columns:
                                log_msg = "[INIT] jti column already exists in jwt_blacklist table"
                                if app_logger:
                                    app_logger.log(log_msg)
                                else:
                                    logger.info(log_msg)
                                # Clear cache to ensure it's recognized
                                try:
                                    from vault.services.auth_service import (
                                        reset_jti_column_cache,
                                    )

                                    reset_jti_column_cache()
                                    log_msg = "[INIT] jti column cache cleared"
                                    if app_logger:
                                        app_logger.log(log_msg)
                                    else:
                                        logger.info(log_msg)
                                except Exception as cache_err:
                                    log_msg = f"[WARNING] Failed to clear jti cache: {cache_err}"
                                    if app_logger:
                                        app_logger.log(log_msg)
                                    else:
                                        logger.warning(log_msg)
                            else:
                                logger.error(
                                    f"CRITICAL: jti column not found in jwt_blacklist table. "
                                    f"Found columns: {', '.join(columns)}"
                                )
                                # Even though columns were retrieved, jti is missing - try to add it
                                logger.info(
                                    "Attempting to add jti column to jwt_blacklist table..."
                                )
                                try:
                                    db.session.execute(
                                        sql_text(
                                            "ALTER TABLE jwt_blacklist ADD COLUMN jti VARCHAR(255)"
                                        )
                                    )
                                    db.session.execute(
                                        sql_text(
                                            "CREATE UNIQUE INDEX IF NOT EXISTS ix_jwt_blacklist_jti ON jwt_blacklist(jti) WHERE jti IS NOT NULL"
                                        )
                                    )
                                    db.session.commit()
                                    logger.info("jti column added successfully")

                                    # Verify
                                    time.sleep(0.2)
                                    inspector = sql_inspect(db.engine)
                                    verify_columns = [
                                        col["name"]
                                        for col in inspector.get_columns(
                                            "jwt_blacklist"
                                        )
                                    ]
                                    if "jti" not in verify_columns:
                                        raise RuntimeError(
                                            "jti column verification failed after creation"
                                        )

                                    # Clear cache
                                    try:
                                        from vault.services.auth_service import (
                                            reset_jti_column_cache,
                                        )

                                        reset_jti_column_cache()
                                    except Exception:
                                        pass
                                except Exception as add_error:
                                    logger.error(
                                        f"CRITICAL: Failed to add jti column: {add_error}"
                                    )
                                    db.session.rollback()
                                    raise
            except Exception as migration_error:
                # Check if we're in production - if so, this is critical
                try:
                    from flask import current_app

                    is_production = current_app.config.get("IS_PRODUCTION", True)
                    if is_production:
                        logger.error(
                            f"CRITICAL: Error during jti column migration check in production: {migration_error}"
                        )
                        raise RuntimeError(
                            "CRITICAL: JWT replay protection (jti column) migration failed in production. "
                            "This is a security requirement. Please check database connectivity and permissions."
                        ) from migration_error
                    else:
                        logger.warning(
                            f"Error during jti column migration check: {migration_error}"
                        )
                except RuntimeError:
                    raise
                except Exception:
                    # If we can't check production mode, log warning but continue
                    logger.warning(
                        f"Error during jti column migration check: {migration_error}"
                    )

            # Final verification: ensure jti column exists and is usable
            # This is critical for production security
            try:
                from sqlalchemy import inspect as sql_inspect
                from sqlalchemy.sql import text as sql_text

                inspector = sql_inspect(db.engine)
                if "jwt_blacklist" in inspector.get_table_names():
                    columns = [
                        col["name"] for col in inspector.get_columns("jwt_blacklist")
                    ]
                    if "jti" not in columns:
                        # Column still missing - create it now
                        log_msg = "[INIT] CRITICAL: jti column still missing after migration! Creating now..."
                        if app_logger:
                            app_logger.log(log_msg)
                        else:
                            logger.error(log_msg)
                        try:
                            db.session.execute(
                                sql_text(
                                    "ALTER TABLE jwt_blacklist ADD COLUMN jti VARCHAR(255)"
                                )
                            )
                            db.session.execute(
                                sql_text(
                                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_jwt_blacklist_jti ON jwt_blacklist(jti) WHERE jti IS NOT NULL"
                                )
                            )
                            db.session.commit()
                            log_msg = "[INIT] jti column created successfully in final verification"
                            if app_logger:
                                app_logger.log(log_msg)
                            else:
                                logger.info(log_msg)
                            # Clear cache
                            try:
                                from vault.services.auth_service import (
                                    reset_jti_column_cache,
                                )

                                reset_jti_column_cache()
                            except Exception:
                                pass
                        except Exception as final_error:
                            log_msg = f"[ERROR] Failed to create jti column in final verification: {final_error}"
                            if app_logger:
                                app_logger.log(log_msg)
                            else:
                                logger.error(log_msg)
                            raise
                    else:
                        log_msg = "[INIT] jti column verified in final check"
                        if app_logger:
                            app_logger.log(log_msg)
                        else:
                            logger.info(log_msg)
            except Exception as final_check_error:
                log_msg = (
                    f"[WARNING] Final jti column check failed: {final_check_error}"
                )
                if app_logger:
                    app_logger.log(log_msg)
                else:
                    logger.warning(log_msg)

            log_msg = "Database initialization completed successfully"
            if app_logger:
                app_logger.log(log_msg)
            else:
                logger.info(log_msg)
        except Exception as e:
            import sys
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
                print(f"[INFO] {log_msg}", file=sys.stderr, flush=True)
                # Database is already initialized, continue with verification
                # Verify all required tables exist, not just jwt_blacklist
                try:
                    from sqlalchemy import inspect as sql_inspect
                    from sqlalchemy.sql import text as sql_text
                    import time

                    # Verify all required tables exist
                    # Some tables may be missing even if db.create_all() raised a duplicate error
                    log_msg = "[INIT] Verifying all required tables exist..."
                    if app_logger:
                        app_logger.log(log_msg)
                    else:
                        logger.info(log_msg)
                    print(log_msg, file=sys.stderr, flush=True)

                    inspector = sql_inspect(db.engine)
                    existing_tables = set(inspector.get_table_names())

                    # Get all model tables that should exist
                    # Note: We're already in schema.py, so we can reference classes directly
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
                        print(log_msg, file=sys.stderr, flush=True)

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
                                                        print(
                                                            log_msg,
                                                            file=sys.stderr,
                                                            flush=True,
                                                        )
                                    except Exception as cleanup_error:
                                        # Ignore cleanup errors - continue with table creation
                                        pass

                                except Exception as pre_check_error:
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
                                            log_msg = f"[INIT] Found orphaned indexes for {table_name}: {', '.join(orphaned_indexes)}. Cleaning them up..."
                                            if app_logger:
                                                app_logger.log(log_msg)
                                            else:
                                                logger.warning(log_msg)
                                            print(log_msg, file=sys.stderr, flush=True)

                                            # Drop orphaned indexes
                                            for idx_name in orphaned_indexes:
                                                try:
                                                    db.session.execute(
                                                        sql_text(
                                                            f'DROP INDEX IF EXISTS "{idx_name}"'
                                                        )
                                                    )
                                                    db.session.commit()
                                                    log_msg = f"[INIT] Dropped orphaned index: {idx_name}"
                                                    if app_logger:
                                                        app_logger.log(log_msg)
                                                    else:
                                                        logger.info(log_msg)
                                                    print(
                                                        log_msg,
                                                        file=sys.stderr,
                                                        flush=True,
                                                    )
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
                                                        print(
                                                            log_msg,
                                                            file=sys.stderr,
                                                            flush=True,
                                                        )
                                    except Exception as cleanup_error:
                                        # Ignore cleanup errors - continue with table creation
                                        pass

                                    # Try creating with SQLAlchemy first
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
                                            log_msg = f"[INIT] Table {table_name} created using raw SQL"
                                            if app_logger:
                                                app_logger.log(log_msg)
                                            else:
                                                logger.info(log_msg)
                                            print(log_msg, file=sys.stderr, flush=True)
                                        except Exception as sql_error:
                                            # SQL fallback failed - log but continue with normal flow
                                            log_msg = f"[DEBUG] Raw SQL creation failed for {table_name}: {sql_error}"
                                            if app_logger:
                                                app_logger.log(log_msg)
                                            else:
                                                logger.debug(log_msg)
                                            print(log_msg, file=sys.stderr, flush=True)
                                    # Verify table was actually created
                                    time.sleep(
                                        0.5
                                    )  # Wait for table creation to propagate
                                    inspector = sql_inspect(db.engine)
                                    existing_tables_after = inspector.get_table_names()

                                    if table_name in existing_tables_after:
                                        log_msg = f"[INIT] Created missing table: {table_name} (verified)"
                                        if app_logger:
                                            app_logger.log(log_msg)
                                        else:
                                            logger.info(log_msg)
                                        print(log_msg, file=sys.stderr, flush=True)
                                        table_created = True
                                        break
                                    else:
                                        if create_attempt < max_create_attempts:
                                            log_msg = f"[WARNING] Table {table_name} creation attempt {create_attempt} did not create table. Retrying..."
                                            if app_logger:
                                                app_logger.log(log_msg)
                                            else:
                                                logger.warning(log_msg)
                                            print(log_msg, file=sys.stderr, flush=True)
                                        else:
                                            log_msg = f"[ERROR] Table {table_name} was not created after {max_create_attempts} attempts"
                                            if app_logger:
                                                app_logger.log(log_msg)
                                            else:
                                                logger.error(log_msg)
                                            print(log_msg, file=sys.stderr, flush=True)
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
                                            print(log_msg, file=sys.stderr, flush=True)
                                            time.sleep(1.0)  # Wait before retry
                                        else:
                                            log_msg = f"[ERROR] Failed to create table {table_name} after {max_create_attempts} attempts: {table_error}"
                                            if app_logger:
                                                app_logger.log(log_msg)
                                            else:
                                                logger.error(log_msg)
                                            print(log_msg, file=sys.stderr, flush=True)
                            if not table_created:
                                import traceback

                                error_msg = f"[ERROR] CRITICAL: Failed to create table {table_name} after all attempts.\n{traceback.format_exc()}"
                                if app_logger:
                                    app_logger.log(error_msg)
                                else:
                                    logger.error(error_msg)
                                print(error_msg, file=sys.stderr, flush=True)
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
                            print(log_msg, file=sys.stderr, flush=True)
                    # Now verify and create jti column if missing

                    # RADICAL SOLUTION: Use direct SQL to ensure table and column exist
                    # Don't rely on inspector which may not see tables immediately
                    # Try to create table if it doesn't exist, then add jti column
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
                        print(
                            "[INIT] jwt_blacklist table ensured to exist",
                            file=sys.stderr,
                            flush=True,
                        )
                    except Exception as create_table_error:
                        # Table might already exist, that's OK
                        db.session.rollback()
                        print(
                            f"[INIT] Table creation attempt: {create_table_error}",
                            file=sys.stderr,
                            flush=True,
                        )

                    # Now ensure jti column exists - use IF NOT EXISTS equivalent
                    try:
                        # Check if column exists by trying to add it (will fail if exists, that's OK)
                        db.session.execute(
                            sql_text(
                                "ALTER TABLE jwt_blacklist ADD COLUMN jti VARCHAR(255)"
                            )
                        )
                        db.session.commit()
                        print(
                            "[INIT] jti column added successfully",
                            file=sys.stderr,
                            flush=True,
                        )
                    except Exception as add_col_error:
                        error_str = str(add_col_error).lower()
                        if "already exists" in error_str or "duplicate" in error_str:
                            # Column already exists - that's what we want!
                            db.session.rollback()
                            print(
                                "[INIT] jti column already exists (good!)",
                                file=sys.stderr,
                                flush=True,
                            )
                        else:
                            # Different error - log but continue
                            db.session.rollback()
                            print(
                                f"[INIT] Error adding jti column: {add_col_error}",
                                file=sys.stderr,
                                flush=True,
                            )

                    # Ensure index exists
                    try:
                        db.session.execute(
                            sql_text(
                                "CREATE UNIQUE INDEX IF NOT EXISTS ix_jwt_blacklist_jti ON jwt_blacklist(jti) WHERE jti IS NOT NULL"
                            )
                        )
                        db.session.commit()
                        print("[INIT] jti index ensured", file=sys.stderr, flush=True)
                    except Exception as index_error:
                        db.session.rollback()
                        print(
                            f"[INIT] Index creation: {index_error}",
                            file=sys.stderr,
                            flush=True,
                        )

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
                        print(
                            "[INIT] jti column verified - can be queried",
                            file=sys.stderr,
                            flush=True,
                        )
                    except Exception as verify_error:
                        # This is bad - column doesn't exist or can't be queried
                        error_str = str(verify_error).lower()
                        if "column" in error_str and "jti" in error_str:
                            print(
                                f"[ERROR] CRITICAL: jti column verification failed: {verify_error}",
                                file=sys.stderr,
                                flush=True,
                            )
                            # Try one more time to add it
                            try:
                                db.session.execute(
                                    sql_text(
                                        "ALTER TABLE jwt_blacklist ADD COLUMN IF NOT EXISTS jti VARCHAR(255)"
                                    )
                                )
                                db.session.commit()
                                print(
                                    "[INIT] jti column added via IF NOT EXISTS",
                                    file=sys.stderr,
                                    flush=True,
                                )
                            except Exception:
                                # PostgreSQL doesn't support IF NOT EXISTS for ALTER TABLE ADD COLUMN
                                # So we'll just log the error
                                pass
                        else:
                            print(
                                f"[WARNING] jti verification query failed: {verify_error}",
                                file=sys.stderr,
                                flush=True,
                            )
                except Exception as jti_check_error:
                    import traceback

                    log_msg = f"[ERROR] Failed to verify jti column after duplicate error: {jti_check_error}"
                    if app_logger:
                        app_logger.log(
                            log_msg, context={"traceback": traceback.format_exc()}
                        )
                    else:
                        logger.error(log_msg, exc_info=True)
                    print(log_msg, file=sys.stderr, flush=True)
                    print(traceback.format_exc(), file=sys.stderr, flush=True)
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
