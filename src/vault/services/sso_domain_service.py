"""SSO domain rule service for managing domain-based SSO configuration."""

from __future__ import annotations

from typing import Any

from vault.database.schema import SSODomainRule, SSOProvider, db


class SSODomainService:
    """Service for managing SSO domain rules."""

    def create_rule(
        self,
        domain_pattern: str,
        sso_provider_id: str | None = None,
        is_active: bool = True,
    ) -> SSODomainRule:
        """Create a new SSO domain rule.

        Args:
            domain_pattern: Domain pattern (e.g., "example.com" or "*.example.com")
            sso_provider_id: Optional SSO provider ID
            is_active: Whether rule is active

        Returns:
            SSODomainRule object

        Raises:
            ValueError: If domain pattern is invalid or already exists
        """
        # Validate domain pattern
        if not domain_pattern or "@" in domain_pattern:
            raise ValueError("Invalid domain pattern")

        # Check if rule already exists
        existing = (
            db.session.query(SSODomainRule)
            .filter_by(domain_pattern=domain_pattern)
            .first()
        )
        if existing:
            raise ValueError(f"Rule for domain {domain_pattern} already exists")

        # Validate SSO provider if provided
        if sso_provider_id:
            provider = (
                db.session.query(SSOProvider)
                .filter_by(id=sso_provider_id, is_active=True)
                .first()
            )
            if not provider:
                raise ValueError(f"SSO provider {sso_provider_id} not found")

        # Create rule
        rule = SSODomainRule(
            domain_pattern=domain_pattern,
            sso_provider_id=sso_provider_id,
            is_active=is_active,
        )
        db.session.add(rule)
        db.session.commit()

        return rule

    def update_rule(
        self,
        rule_id: str,
        domain_pattern: str | None = None,
        sso_provider_id: str | None = None,
        is_active: bool | None = None,
    ) -> SSODomainRule | None:
        """Update an SSO domain rule.

        Args:
            rule_id: Rule ID
            domain_pattern: New domain pattern (optional)
            sso_provider_id: New SSO provider ID (optional)
            is_active: New active status (optional)

        Returns:
            Updated SSODomainRule object or None if not found

        Raises:
            ValueError: If domain pattern is invalid
        """
        rule = db.session.query(SSODomainRule).filter_by(id=rule_id).first()
        if not rule:
            return None

        if domain_pattern is not None:
            if not domain_pattern or "@" in domain_pattern:
                raise ValueError("Invalid domain pattern")

            # Check if another rule with this pattern exists
            existing = (
                db.session.query(SSODomainRule)
                .filter_by(domain_pattern=domain_pattern)
                .filter(SSODomainRule.id != rule_id)
                .first()
            )
            if existing:
                raise ValueError(f"Rule for domain {domain_pattern} already exists")

            rule.domain_pattern = domain_pattern

        if sso_provider_id is not None:
            if sso_provider_id:
                provider = (
                    db.session.query(SSOProvider)
                    .filter_by(id=sso_provider_id, is_active=True)
                    .first()
                )
                if not provider:
                    raise ValueError(f"SSO provider {sso_provider_id} not found")
            rule.sso_provider_id = sso_provider_id

        if is_active is not None:
            rule.is_active = is_active

        db.session.commit()
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        """Delete an SSO domain rule.

        Args:
            rule_id: Rule ID

        Returns:
            True if deleted, False if not found
        """
        rule = db.session.query(SSODomainRule).filter_by(id=rule_id).first()
        if not rule:
            return False

        db.session.delete(rule)
        db.session.commit()
        return True

    def get_rule(self, rule_id: str) -> SSODomainRule | None:
        """Get an SSO domain rule by ID.

        Args:
            rule_id: Rule ID

        Returns:
            SSODomainRule object or None if not found
        """
        return db.session.query(SSODomainRule).filter_by(id=rule_id).first()

    def list_rules(
        self,
        is_active: bool | None = None,
        sso_provider_id: str | None = None,
    ) -> list[SSODomainRule]:
        """List SSO domain rules with filters.

        Args:
            is_active: Filter by active status
            sso_provider_id: Filter by SSO provider ID

        Returns:
            List of SSODomainRule objects
        """
        query = db.session.query(SSODomainRule)

        if is_active is not None:
            query = query.filter_by(is_active=is_active)

        if sso_provider_id is not None:
            query = query.filter_by(sso_provider_id=sso_provider_id)

        return query.order_by(SSODomainRule.domain_pattern).all()

    def find_matching_rule(self, email: str) -> SSODomainRule | None:
        """Find SSO domain rule matching email domain.

        Args:
            email: Email address to check

        Returns:
            SSODomainRule object if match found, None otherwise
        """
        if "@" not in email:
            return None

        # Get all active rules
        rules = self.list_rules(is_active=True)

        # Check each rule
        for rule in rules:
            if rule.matches_domain(email):
                return rule

        return None

    def validate_email_domain(self, email: str) -> tuple[bool, str | None]:
        """Validate email domain against SSO rules.

        Args:
            email: Email address to validate

        Returns:
            Tuple of (is_allowed, error_message)
            - is_allowed: True if domain is allowed or no rules exist
            - error_message: Error message if domain is not allowed
        """
        # If no rules exist, allow all domains
        rules = self.list_rules(is_active=True)
        if not rules:
            return True, None

        # Check if domain matches any rule
        matching_rule = self.find_matching_rule(email)
        if matching_rule:
            # Domain matches a rule - check if it requires SSO
            if matching_rule.sso_provider_id:
                # This domain requires SSO authentication
                return (
                    False,
                    f"This domain ({matching_rule.domain_pattern}) requires SSO authentication",
                )
            # Rule exists but no SSO provider - domain is allowed
            return True, None

        # No matching rule - domain is not allowed
        return False, "This email domain is not allowed for registration"
