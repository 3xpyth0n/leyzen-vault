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
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

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


class SSOProvider(db.Model):
    """SSO provider configuration."""

    __tablename__ = "sso_providers"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_type: Mapped[SSOProviderType] = mapped_column(
        Enum(SSOProviderType), nullable=False
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
        import json

        return {
            "id": self.id,
            "name": self.name,
            "provider_type": self.provider_type.value,
            "is_active": self.is_active,
            "config": json.loads(self.config) if self.config else {},
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<SSOProvider {self.name} ({self.provider_type.value})>"


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
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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
            "is_active": self.is_active,
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


class FileVersion(db.Model):
    """File version with branch support (advanced versioning)."""

    __tablename__ = "file_versions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid()
    )
    file_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    branch_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="main"
    )
    encrypted_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    change_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_version_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("file_versions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    file: Mapped["File"] = relationship("File")
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by])
    parent_version: Mapped["FileVersion | None"] = relationship(
        "FileVersion", remote_side=[id], foreign_keys=[parent_version_id]
    )

    __table_args__ = (
        Index(
            "ix_file_versions_file_branch", "file_id", "branch_name", "version_number"
        ),
        Index("ix_file_versions_created_by", "created_by"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "file_id": self.file_id,
            "version_number": self.version_number,
            "branch_name": self.branch_name,
            "encrypted_hash": self.encrypted_hash,
            "storage_ref": self.storage_ref,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "change_description": self.change_description,
            "parent_version_id": self.parent_version_id,
        }


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
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_download: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_preview: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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
            "is_active": self.is_active,
            "allow_download": self.allow_download,
            "allow_preview": self.allow_preview,
            "permission_type": self.permission_type,
            "created_at": self.created_at.isoformat(),
            "last_accessed_at": (
                self.last_accessed_at.isoformat() if self.last_accessed_at else None
            ),
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
            self.is_active
            and not self.is_expired()
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
        import json

        return {
            "id": self.id,
            "action": self.action,
            "file_id": self.file_id,
            "user_ip": self.user_ip,
            "timestamp": self.timestamp.isoformat(),
            "details": json.loads(self.details) if self.details else {},
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
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    file: Mapped["File"] = relationship("File", foreign_keys=[file_id])

    # Indexes for efficient queries
    __table_args__ = (
        Index("ix_share_links_file_id", "file_id"),
        Index("ix_share_links_expires_at", "expires_at"),
        Index("ix_share_links_is_active", "is_active"),
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
            "is_active": self.is_active,
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

        if not self.is_active:
            return True
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


class SSODomainRule(db.Model):
    """SSO domain rule model for domain-based SSO configuration."""

    __tablename__ = "sso_domain_rules"

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
        return f"<SSODomainRule domain={self.domain_pattern}>"


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


def init_db(app) -> None:
    """Initialize database with Flask app.

    Creates all tables and indexes. Handles cases where objects already exist
    gracefully (e.g., when database was previously initialized).

    This function will not raise exceptions for duplicate index/table errors,
    as these are expected when the database schema already exists.
    """
    db.init_app(app)
    with app.app_context():
        import logging
        from sqlalchemy.exc import ProgrammingError, OperationalError, StatementError
        from sqlalchemy import inspect, text

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

        # First, run cleanup migrations to remove duplicate indexes
        # This should be done before create_all() to avoid conflicts
        try:
            _migrate_remove_duplicate_indexes()
        except Exception as migration_error:
            # Log but don't fail - cleanup migrations are non-critical
            logger.debug(
                f"Index cleanup migration error (non-fatal): {migration_error}"
            )

        # Try to create all tables and indexes
        # If objects already exist, that's fine - database is already initialized
        try:
            db.create_all()
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

        # Run other migrations for existing databases (these handle existence checks internally)
        try:
            _migrate_add_icon_name_column()
            _migrate_extend_rate_limit_ip_address()
        except Exception as migration_error:
            # Log migration errors but don't fail initialization
            # Migrations should handle their own existence checks
            logger.warning(
                f"Migration error (non-fatal): {migration_error}",
                exc_info=True,
            )


def _migrate_remove_duplicate_indexes() -> None:
    """Remove duplicate indexes that may have been created in previous versions.

    This migration removes indexes that are now created automatically by constraints
    (e.g., unique constraints automatically create indexes).

    Specifically, removes ix_user_invitations_token if it exists, since the token
    column has unique=True which creates an index automatically.
    """
    from sqlalchemy import text, inspect
    import logging

    logger = logging.getLogger(__name__)

    try:
        inspector = inspect(db.engine)

        # Check if user_invitations table exists
        if "user_invitations" not in inspector.get_table_names():
            return

        # List of duplicate indexes to remove
        # These indexes are now redundant because they're created automatically by constraints
        # or were removed from the model definition
        duplicate_indexes_to_remove = [
            "ix_user_invitations_token",  # Created automatically by unique=True on token column
            # Note: If email had index=True and also an explicit index, we would list it here too
            # But currently email only has the explicit index, so no duplication
        ]

        # Get existing indexes on user_invitations table
        indexes = inspector.get_indexes("user_invitations")
        existing_index_names = {idx["name"] for idx in indexes}

        # Remove duplicate indexes if they exist
        for index_name in duplicate_indexes_to_remove:
            # Validate index name to prevent SQL injection (alphanumeric and underscores only)
            if not index_name.replace("_", "").isalnum():
                logger.warning(
                    f"Skipping invalid index name (potential security risk): {index_name}"
                )
                continue

            if index_name in existing_index_names:
                try:
                    with db.engine.begin() as conn:
                        # Use IF EXISTS to avoid errors if index was already removed
                        # Use SQLAlchemy's identifier quoting for safety
                        from sqlalchemy import quoted_name
                        from sqlalchemy.sql import Identifier

                        # Index name is validated above (alphanumeric + underscores only)
                        # Use quoted_name to safely quote the identifier
                        quoted_index_name = quoted_name(index_name, True)
                        # PostgreSQL doesn't support parameterized identifiers in DROP INDEX
                        # So we validate strictly above and use quoted_name for safe quoting
                        # The validation ensures only safe characters (alphanumeric + underscore)
                        conn.execute(text(f"DROP INDEX IF EXISTS {quoted_index_name}"))
                    logger.info(f"Removed duplicate index: {index_name}")
                except Exception as e:
                    # Log but don't fail - index might have been removed already
                    logger.debug(
                        f"Could not remove index {index_name} (may not exist): {e}"
                    )

    except Exception as e:
        # Log but don't fail - this is a cleanup migration
        # Errors here are non-critical
        logger.debug(f"Error during index cleanup migration (non-fatal): {e}")


def _migrate_add_icon_name_column() -> None:
    """Add icon_name column to vaultspaces table if it doesn't exist.

    This migration adds the icon_name column to support custom VaultSpace icons.
    """
    from sqlalchemy import text
    import logging

    try:
        # Check if table exists using parameterized query
        table_result = db.session.execute(
            text(
                """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name = :table_name
            """
            ).bindparams(table_name="vaultspaces")
        )
        table_exists = table_result.fetchone() is not None

        if not table_exists:
            # Table doesn't exist yet, db.create_all() will create it with the column
            return

        # Check if column exists using parameterized query
        column_result = db.session.execute(
            text(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = :table_name AND column_name = :column_name
            """
            ).bindparams(table_name="vaultspaces", column_name="icon_name")
        )
        column_exists = column_result.fetchone() is not None

        if not column_exists:
            # Add the column - table and column names are hardcoded, safe to use text()
            # But we still use parameterized queries for consistency
            db.session.execute(
                text(
                    """
                    ALTER TABLE vaultspaces 
                    ADD COLUMN icon_name VARCHAR(50) NULL
                """
                )
            )
            db.session.commit()
            logging.info("Successfully added icon_name column to vaultspaces table")
    except Exception as e:
        # If migration fails, rollback and log error
        db.session.rollback()
        # Don't raise exception - allow app to start even if migration fails
        # The column will be added on next startup if it still doesn't exist
        logging.warning(f"Failed to add icon_name column to vaultspaces table: {e}")


def _migrate_extend_rate_limit_ip_address() -> None:
    """Extend ip_address column in rate_limit_tracking table to support IPv6 + action_name suffix.

    This migration extends the ip_address column from VARCHAR(45) to VARCHAR(100) to support
    IPv6 addresses (up to 39 characters) combined with action name suffixes (e.g., :auth_login).
    """
    from sqlalchemy import text
    import logging

    logger = logging.getLogger(__name__)

    try:
        # Check if table exists using parameterized query
        table_result = db.session.execute(
            text(
                """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name = :table_name
            """
            ).bindparams(table_name="rate_limit_tracking")
        )
        table_exists = table_result.fetchone() is not None

        if not table_exists:
            # Table doesn't exist yet, db.create_all() will create it with the correct size
            return

        # Check current column definition using parameterized query
        column_result = db.session.execute(
            text(
                """
                SELECT character_maximum_length
                FROM information_schema.columns
                WHERE table_name = :table_name 
                AND column_name = :column_name
            """
            ).bindparams(table_name="rate_limit_tracking", column_name="ip_address")
        )
        column_info = column_result.fetchone()

        if column_info is None:
            # Column doesn't exist (shouldn't happen, but handle gracefully)
            logger.warning("ip_address column not found in rate_limit_tracking table")
            return

        current_max_length = column_info[0]

        # Only migrate if current size is less than 100
        if current_max_length is None or current_max_length < 100:
            # Extend the column to VARCHAR(100) - table/column names are hardcoded, safe
            db.session.execute(
                text(
                    """
                    ALTER TABLE rate_limit_tracking 
                    ALTER COLUMN ip_address TYPE VARCHAR(100)
                """
                )
            )
            db.session.commit()
            logger.info(
                f"Successfully extended ip_address column in rate_limit_tracking table "
                f"from {current_max_length} to 100 characters"
            )
        else:
            # Column is already large enough
            logger.debug(
                f"ip_address column in rate_limit_tracking table already has size {current_max_length}, "
                f"no migration needed"
            )
    except Exception as e:
        # If migration fails, rollback and log error
        db.session.rollback()
        # Don't raise exception - allow app to start even if migration fails
        # The migration will be retried on next startup if it still needs to be applied
        logger.warning(
            f"Failed to extend ip_address column in rate_limit_tracking table: {e}"
        )
