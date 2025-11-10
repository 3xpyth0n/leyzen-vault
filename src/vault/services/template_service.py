"""VaultSpace templates service for workspace templates."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from vault.database.schema import (
    File,
    VaultSpace,
    VaultSpaceTemplate,
    VaultSpaceType,
    db,
)


class TemplateService:
    """Service for VaultSpace templates."""

    def create_template(
        self,
        user_id: str,
        name: str,
        template_config: dict[str, Any],
        description: str | None = None,
        is_public: bool = False,
    ) -> VaultSpaceTemplate:
        """Create a VaultSpace template.

        Args:
            user_id: User ID creating template
            name: Template name
            template_config: Template configuration (structure, folders, etc.)
            description: Optional description
            is_public: Whether template is public

        Returns:
            VaultSpaceTemplate object
        """
        template = VaultSpaceTemplate(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            template_config=json.dumps(template_config),
            is_public=is_public,
            created_by=user_id,
        )
        db.session.add(template)
        db.session.commit()

        return template

    def create_from_template(
        self,
        template_id: str,
        user_id: str,
        vaultspace_name: str,
    ) -> VaultSpace:
        """Create a VaultSpace from a template.

        Args:
            template_id: Template ID
            user_id: User ID creating VaultSpace
            vaultspace_name: Name for new VaultSpace

        Returns:
            Created VaultSpace object
        """
        template = (
            db.session.query(VaultSpaceTemplate).filter_by(id=template_id).first()
        )
        if not template:
            raise ValueError(f"Template {template_id} not found")

        # Check if template is accessible
        if not template.is_public and template.created_by != user_id:
            raise ValueError("Template not accessible")

        template_config = json.loads(template.template_config)

        # Create VaultSpace
        vaultspace = VaultSpace(
            id=str(uuid.uuid4()),
            name=vaultspace_name,
            type=VaultSpaceType.PERSONAL,
            owner_user_id=user_id,
            owner_org_id=None,
        )
        db.session.add(vaultspace)

        # Apply template structure (create folders, etc.)
        if "folders" in template_config:
            for folder_config in template_config["folders"]:
                # Create folder structure
                # This would create File entries representing folders
                pass

        template.usage_count += 1
        db.session.commit()

        return vaultspace

    def list_templates(
        self,
        user_id: str | None = None,
        public_only: bool = False,
    ) -> list[VaultSpaceTemplate]:
        """List available templates.

        Args:
            user_id: Optional user ID filter
            public_only: Only return public templates

        Returns:
            List of VaultSpaceTemplate objects
        """
        query = db.session.query(VaultSpaceTemplate)

        if public_only:
            query = query.filter_by(is_public=True)
        elif user_id:
            # Return user's templates and public templates
            query = query.filter(
                (VaultSpaceTemplate.created_by == user_id)
                | (VaultSpaceTemplate.is_public == True)
            )
        else:
            query = query.filter_by(is_public=True)

        return query.order_by(VaultSpaceTemplate.usage_count.desc()).all()
