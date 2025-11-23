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
        String(255), nullable=True, unique=True
    )  # JWT ID for replay protection (nullable for backward compatibility)
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
        String(20), nullable=False
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
                ]
                if any(indicator in msg_lower for indicator in duplicate_indicators):
                    return True

            return False

        # Create all tables and indexes using SQLAlchemy
        # If objects already exist, that's fine - database is already initialized
        try:
            db.create_all()

            # Migrate jwt_blacklist table to add jti column if missing
            # This handles cases where the table was created before jti column was added
            # SECURITY: In production, jti column is mandatory for JWT replay protection
            try:
                from sqlalchemy import inspect as sql_inspect
                from sqlalchemy.sql import text as sql_text
                from sqlalchemy.exc import ProgrammingError, InternalError
                import time

                # Check if jwt_blacklist table exists first
                inspector = sql_inspect(db.engine)
                if "jwt_blacklist" not in inspector.get_table_names():
                    logger.debug(
                        "jwt_blacklist table does not exist yet, skipping jti migration"
                    )
                else:
                    # Retry logic for checking columns (handles transient database issues)
                    columns = None
                    max_retries = 3
                    retry_delay = 0.5

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
                            else:
                                logger.warning(
                                    f"Failed to check jti column after {max_retries} attempts: {e}"
                                )
                                raise

                    if columns is not None and "jti" not in columns:
                        logger.info("Adding jti column to jwt_blacklist table...")
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
                            logger.info(
                                "jti column added successfully to jwt_blacklist table"
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
                    elif columns is not None:
                        logger.debug("jti column already exists in jwt_blacklist table")
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

            logger.info("Database initialization completed successfully")
        except Exception as e:
            # Check if it's a duplicate/already exists error
            # These are expected when database schema already exists
            if is_duplicate_error(e):
                # Database objects already exist - this is expected and OK
                logger.info(
                    "Database objects already exist (database was previously initialized). "
                    "This is normal and expected. Continuing with initialization."
                )
                # Don't raise - database is already properly initialized
                # The schema exists, so we can continue
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
