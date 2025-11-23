"""SSO service for SAML, OAuth2, and OpenID Connect authentication."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode, urlparse, parse_qs

from flask import current_app, redirect, request, session, url_for
from sqlalchemy.orm import Session

import secrets
from datetime import timedelta

from vault.database.schema import (
    MagicLinkToken,
    SSOProvider,
    SSOProviderType,
    User,
    db,
)
from vault.services.auth_service import AuthService
from vault.services.email_service import EmailService
from vault.security.url_validator import SSRFProtection, SSRFProtectionError
from vault.utils.safe_json import safe_json_loads


class SSOService:
    """Service for SSO authentication (SAML, OAuth2, OIDC)."""

    @staticmethod
    def _detect_provider_preset(
        provider_type: SSOProviderType, config: dict[str, Any]
    ) -> str:
        """Detect provider preset from technical type and config.

        Args:
            provider_type: Technical provider type (oauth2, oidc, saml, email-magic-link)
            config: Provider configuration dictionary

        Returns:
            Preset name (google, slack, discord, etc.) or technical type as fallback
        """
        if provider_type.value == "email-magic-link":
            return "email-magic-link"
        elif provider_type.value == "saml":
            return "saml"
        elif provider_type.value == "oauth2":
            auth_url = config.get("authorization_url", "")
            if "google.com" in auth_url:
                return "google"
            elif "slack.com" in auth_url:
                return "slack"
            elif "discord.com" in auth_url:
                return "discord"
            elif "gitlab.com" in auth_url or config.get("instance_url"):
                return "gitlab"
            else:
                return "oauth2"  # Generic OAuth2
        elif provider_type.value == "oidc":
            issuer_url = config.get("issuer_url", "")
            if "microsoftonline.com" in issuer_url:
                return "microsoft"
            else:
                return "oidc"  # Generic OIDC
        else:
            return provider_type.value

    def __init__(self, auth_service: AuthService | None = None):
        """Initialize SSO service.

        Args:
            auth_service: Optional AuthService instance
        """
        self.auth_service = auth_service
        if self.auth_service is None:
            secret_key = current_app.config.get("SECRET_KEY", "")
            self.auth_service = AuthService(secret_key)

    def _validate_provider_config_urls(
        self, provider_type: SSOProviderType, config: dict[str, Any]
    ) -> None:
        """Validate all URLs in provider configuration to prevent SSRF attacks.

        Args:
            provider_type: Type of SSO provider
            config: Provider configuration dictionary

        Raises:
            ValueError: If any URL in config fails SSRF validation
        """
        ssrf_protection = SSRFProtection()
        urls_to_validate = []

        # Collect URLs based on provider type
        if provider_type == SSOProviderType.SAML:
            # SAML providers have sso_url
            if config.get("sso_url"):
                urls_to_validate.append(("sso_url", config["sso_url"]))
            # Note: acs_url is our own callback URL, no need to validate
        elif provider_type == SSOProviderType.OAUTH2:
            # OAuth2 providers have authorization_url, token_url, userinfo_url
            if config.get("authorization_url"):
                urls_to_validate.append(
                    ("authorization_url", config["authorization_url"])
                )
            if config.get("token_url"):
                urls_to_validate.append(("token_url", config["token_url"]))
            if config.get("userinfo_url"):
                urls_to_validate.append(("userinfo_url", config["userinfo_url"]))
        elif provider_type == SSOProviderType.OIDC:
            # OIDC providers have issuer_url (and optionally explicit endpoints)
            if config.get("issuer_url"):
                urls_to_validate.append(("issuer_url", config["issuer_url"]))
            if config.get("token_url"):
                urls_to_validate.append(("token_url", config["token_url"]))
            if config.get("userinfo_url"):
                urls_to_validate.append(("userinfo_url", config["userinfo_url"]))

        # Validate all collected URLs
        for url_name, url in urls_to_validate:
            try:
                ssrf_protection.validate_url(url)
            except SSRFProtectionError as e:
                current_app.logger.error(
                    f"SSRF protection blocked {url_name} in provider config: {e}"
                )
                raise ValueError(
                    f"Invalid {url_name}: {e}. "
                    "URLs must not point to private networks, localhost, or cloud metadata services."
                ) from e

    def _get_base_url(self) -> str:
        """Get base URL from VAULT_URL setting.

        Returns:
            Base URL string

        Raises:
            ValueError: If VAULT_URL is not configured (required for security)
        """
        # Try to get from VAULT_SETTINGS
        try:
            settings = current_app.config.get("VAULT_SETTINGS")
            if settings and hasattr(settings, "vault_url") and settings.vault_url:
                return settings.vault_url.rstrip("/")
        except Exception:
            pass

        # SECURITY: VAULT_URL is mandatory - no fallback to request.host_url
        # This prevents Host header injection attacks
        is_production = current_app.config.get("IS_PRODUCTION", True)
        if is_production:
            raise ValueError(
                "VAULT_URL must be configured in production. "
                "Set VAULT_URL environment variable to prevent Host header injection attacks."
            )

        # In development, log warning and raise error
        current_app.logger.warning(
            "VAULT_URL not configured. SSO flows may not work correctly. "
            "Set VAULT_URL environment variable."
        )
        raise ValueError(
            "VAULT_URL must be configured for SSO flows. "
            "Set VAULT_URL environment variable to generate SSO callback URLs."
        )

    def _is_signup_allowed(self) -> bool:
        """Check if public signup is allowed.

        Returns:
            True if signup is allowed, False otherwise
        """
        try:
            from vault.database.schema import SystemSettings

            setting = (
                db.session.query(SystemSettings).filter_by(key="allow_signup").first()
            )
            if setting:
                return setting.value.lower() == "true"
        except Exception:
            pass

        return True

    def get_provider(
        self, provider_id: str, active_only: bool = True
    ) -> SSOProvider | None:
        """Get SSO provider by ID.

        Args:
            provider_id: Provider ID
            active_only: If True, only return active providers. If False, return any provider.

        Returns:
            SSOProvider object or None
        """
        query = db.session.query(SSOProvider).filter_by(id=provider_id)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.first()

    def list_providers(self, active_only: bool = True) -> list[SSOProvider]:
        """Get SSO providers.

        Args:
            active_only: If True, return only active providers. If False, return all providers.

        Returns:
            List of SSOProvider objects
        """
        query = db.session.query(SSOProvider)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.all()

    def initiate_saml_login(
        self, provider_id: str, return_url: str | None = None
    ) -> str:
        """Initiate SAML login flow.

        Args:
            provider_id: SSO provider ID
            return_url: URL to return to after authentication

        Returns:
            Redirect URL to SAML IdP

        Raises:
            ValueError: If provider not found or not SAML type, or if SAML library not available
        """
        provider = self.get_provider(provider_id)
        if not provider:
            raise ValueError(f"SSO provider {provider_id} not found")
        if provider.provider_type != SSOProviderType.SAML:
            raise ValueError(f"Provider {provider_id} is not SAML type")

        try:
            from onelogin.saml2.auth import OneLogin_Saml2_Auth
        except ImportError:
            raise ValueError(
                "SAML support not available. Install python3-saml manually: "
                "pip install python3-saml"
            )

        try:
            config = safe_json_loads(
                provider.config,
                max_size=10 * 1024,  # 10KB for SSO config
                max_depth=20,
                context="SSO provider config",
            )
            saml_settings = {
                "sp": {
                    "entityId": config.get("sp_entity_id", "leyzen-vault"),
                    "assertionConsumerService": {
                        "url": config.get(
                            "acs_url",
                            f"{self._get_base_url()}/api/sso/callback/{provider_id}",
                        ),
                        "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                    },
                },
                "idp": {
                    "entityId": config.get("idp_entity_id"),
                    "singleSignOnService": {
                        "url": config.get("sso_url"),
                        "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
                    },
                    "x509cert": config.get("x509_cert"),
                },
            }

            req = {
                "https": "on" if request.is_secure else "off",
                "http_host": request.host,
                "script_name": request.path,
                "get_data": dict(request.args),
                "post_data": dict(request.form),
            }

            saml_auth = OneLogin_Saml2_Auth(req, saml_settings)
            login_url = saml_auth.login(return_to=return_url)

            # Store provider_id in session for callback
            session["sso_provider_id"] = provider_id
            session["sso_return_url"] = return_url

            return login_url
        except Exception as e:
            raise ValueError(f"SAML login initiation failed: {str(e)}")

    def handle_saml_callback(self, provider_id: str) -> tuple[User, str] | None:
        """Handle SAML authentication callback.

        Args:
            provider_id: SSO provider ID

        Returns:
            Tuple of (User, JWT token) if authentication succeeds, None otherwise
        """
        provider = self.get_provider(provider_id)
        if not provider or provider.provider_type != SSOProviderType.SAML:
            return None

        try:
            from onelogin.saml2.auth import OneLogin_Saml2_Auth
        except ImportError:
            # SAML library not available
            return None

        try:

            config = safe_json_loads(
                provider.config,
                max_size=10 * 1024,  # 10KB for SSO config
                max_depth=20,
                context="SSO provider config",
            )
            saml_settings = {
                "sp": {
                    "entityId": config.get("sp_entity_id", "leyzen-vault"),
                    "assertionConsumerService": {
                        "url": config.get(
                            "acs_url",
                            f"{self._get_base_url()}/api/sso/callback/{provider_id}",
                        ),
                        "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                    },
                },
                "idp": {
                    "entityId": config.get("idp_entity_id"),
                    "singleSignOnService": {
                        "url": config.get("sso_url"),
                        "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
                    },
                    "x509cert": config.get("x509_cert"),
                },
            }

            req = {
                "https": "on" if request.is_secure else "off",
                "http_host": request.host,
                "script_name": request.path,
                "get_data": dict(request.args),
                "post_data": dict(request.form),
            }

            saml_auth = OneLogin_Saml2_Auth(req, saml_settings)
            saml_auth.process_response()

            if saml_auth.is_authenticated():
                # Extract user attributes from SAML response
                attributes = saml_auth.get_attributes()
                email = (
                    attributes.get("email", [None])[0]
                    or attributes.get("mail", [None])[0]
                    or attributes.get(
                        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
                        [None],
                    )[0]
                )

                if not email:
                    return None

                # Find user (do not create automatically - users must register with password first)
                user = db.session.query(User).filter_by(email=email).first()
                if not user:
                    # User does not exist - they must register with a password first
                    # SSO can only be used to login to existing accounts
                    current_app.logger.warning(
                        f"SAML SSO login attempted for non-existent user: {email}"
                    )
                    return None

                # Generate JWT token
                token = self.auth_service._generate_token(user)
                return user, token

            return None
        except ImportError:
            return None
        except Exception:
            return None

    def initiate_oauth2_login(
        self, provider_id: str, return_url: str | None = None
    ) -> str:
        """Initiate OAuth2 login flow.

        Args:
            provider_id: SSO provider ID
            return_url: URL to return to after authentication

        Returns:
            Redirect URL to OAuth2 provider

        Raises:
            ValueError: If provider not found or not OAuth2 type
        """
        provider = self.get_provider(provider_id)
        if not provider:
            raise ValueError(f"SSO provider {provider_id} not found")
        if provider.provider_type != SSOProviderType.OAUTH2:
            raise ValueError(f"Provider {provider_id} is not OAuth2 type")

        try:
            from authlib.integrations.flask_client import OAuth

            config = safe_json_loads(
                provider.config,
                max_size=10 * 1024,  # 10KB for SSO config
                max_depth=20,
                context="SSO provider config",
            )
            client_id = config.get("client_id")
            authorization_url = config.get("authorization_url")
            redirect_uri = config.get(
                "redirect_uri", f"{self._get_base_url()}/api/sso/callback/{provider_id}"
            )
            scopes = config.get("scopes", "openid email profile")

            # Store state and return_url in session
            import secrets

            state = secrets.token_urlsafe(32)
            session["sso_provider_id"] = provider_id
            session["sso_state"] = state
            session["sso_return_url"] = return_url

            # Build authorization URL
            params = {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": scopes,
                "state": state,
            }

            auth_url = f"{authorization_url}?{urlencode(params)}"
            return auth_url
        except ImportError:
            raise ValueError("authlib not installed. Install with: pip install authlib")
        except Exception as e:
            raise ValueError(f"OAuth2 login initiation failed: {str(e)}")

    def handle_oauth2_callback(
        self, provider_id: str, code: str, state: str
    ) -> tuple[User, str] | None:
        """Handle OAuth2 authentication callback.

        Args:
            provider_id: SSO provider ID
            code: Authorization code
            state: State parameter (for CSRF protection)

        Returns:
            Tuple of (User, JWT token) if authentication succeeds, None otherwise
        """
        # Verify state
        if state != session.get("sso_state"):
            return None

        provider = self.get_provider(provider_id)
        if not provider or provider.provider_type != SSOProviderType.OAUTH2:
            return None

        try:
            import requests

            config = safe_json_loads(
                provider.config,
                max_size=10 * 1024,  # 10KB for SSO config
                max_depth=20,
                context="SSO provider config",
            )
            client_id = config.get("client_id")
            client_secret = config.get("client_secret")
            token_url = config.get("token_url")
            userinfo_url = config.get("userinfo_url")
            redirect_uri = config.get(
                "redirect_uri", f"{self._get_base_url()}/api/sso/callback/{provider_id}"
            )

            # Exchange code for token
            token_data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            }

            # SECURITY: Add timeout to prevent DoS attacks and validate URLs to prevent SSRF
            timeout = 10  # 10 seconds timeout
            ssrf_protection = SSRFProtection()

            # SECURITY: Validate token URL to prevent SSRF attacks
            try:
                ssrf_protection.validate_url(token_url)
            except SSRFProtectionError as e:
                current_app.logger.error(
                    f"SSRF protection blocked token URL for OAuth2 provider {provider_id}: {e}"
                )
                return None

            # SECURITY: Validate userinfo URL to prevent SSRF attacks
            try:
                ssrf_protection.validate_url(userinfo_url)
            except SSRFProtectionError as e:
                current_app.logger.error(
                    f"SSRF protection blocked userinfo URL for OAuth2 provider {provider_id}: {e}"
                )
                return None

            try:
                token_response = requests.post(
                    token_url, data=token_data, timeout=timeout, allow_redirects=False
                )
                token_response.raise_for_status()
                token_json = token_response.json()
                access_token = token_json.get("access_token")

                if not access_token:
                    return None

                # Get user info
                headers = {"Authorization": f"Bearer {access_token}"}
                userinfo_response = requests.get(
                    userinfo_url,
                    headers=headers,
                    timeout=timeout,
                    allow_redirects=False,
                )
                userinfo_response.raise_for_status()
                userinfo = userinfo_response.json()
            except requests.Timeout:
                current_app.logger.error(
                    f"Timeout while communicating with OAuth2 provider {provider_id}"
                )
                return None
            except requests.RequestException as e:
                current_app.logger.error(
                    f"Request error while communicating with OAuth2 provider {provider_id}: {e}"
                )
                return None

            email = userinfo.get("email") or userinfo.get("sub")
            if not email:
                return None

            # Find user (do not create automatically - users must register with password first)
            user = db.session.query(User).filter_by(email=email).first()
            if not user:
                # User does not exist - they must register with a password first
                # SSO can only be used to login to existing accounts
                current_app.logger.warning(
                    f"SSO login attempted for non-existent user: {email}"
                )
                return None

            # Generate JWT token
            from datetime import datetime, timedelta, timezone
            import jwt

            expiration = datetime.now(timezone.utc) + timedelta(hours=24)
            payload = {
                "user_id": user.id,
                "email": user.email,
                "global_role": user.global_role.value,
                "exp": expiration,
                "iat": datetime.now(timezone.utc),
            }
            secret_key = current_app.config.get("SECRET_KEY", "")
            token = jwt.encode(payload, secret_key, algorithm="HS256")
            return user, token
        except Exception:
            return None

    def initiate_oidc_login(
        self, provider_id: str, return_url: str | None = None
    ) -> str:
        """Initiate OpenID Connect login flow.

        Args:
            provider_id: SSO provider ID
            return_url: URL to return to after authentication

        Returns:
            Redirect URL to OIDC provider
        """
        # OIDC is similar to OAuth2, but uses OpenID Connect discovery
        provider = self.get_provider(provider_id)
        if not provider:
            raise ValueError(f"SSO provider {provider_id} not found")
        if provider.provider_type != SSOProviderType.OIDC:
            raise ValueError(f"Provider {provider_id} is not OIDC type")

        try:
            import requests

            config = safe_json_loads(
                provider.config,
                max_size=10 * 1024,  # 10KB for SSO config
                max_depth=20,
                context="SSO provider config",
            )
            issuer_url = config.get("issuer_url")

            # Discover OIDC endpoints
            # SECURITY: Add timeout to prevent DoS attacks and validate URL to prevent SSRF
            timeout = 10  # 10 seconds timeout
            discovery_url = f"{issuer_url}/.well-known/openid-configuration"

            # SECURITY: Validate discovery URL to prevent SSRF attacks
            ssrf_protection = SSRFProtection()
            try:
                ssrf_protection.validate_url(discovery_url)
            except SSRFProtectionError as e:
                current_app.logger.error(
                    f"SSRF protection blocked discovery URL for provider {provider_id}: {e}"
                )
                raise ValueError(f"Invalid discovery URL: {e}") from e

            try:
                discovery_response = requests.get(
                    discovery_url, timeout=timeout, allow_redirects=False
                )
                discovery_response.raise_for_status()
                discovery = discovery_response.json()
            except requests.Timeout:
                current_app.logger.error(
                    f"Timeout while discovering OIDC endpoints for provider {provider_id}"
                )
                raise ValueError("Timeout while discovering OIDC endpoints") from None
            except requests.RequestException as e:
                current_app.logger.error(
                    f"Request error while discovering OIDC endpoints for provider {provider_id}: {e}"
                )
                raise ValueError(f"Failed to discover OIDC endpoints: {e}") from e

            authorization_url = discovery.get("authorization_endpoint")
            client_id = config.get("client_id")
            redirect_uri = config.get(
                "redirect_uri", f"{self._get_base_url()}/api/sso/callback/{provider_id}"
            )
            scopes = config.get("scopes", "openid email profile")

            # Store state and return_url in session
            import secrets

            state = secrets.token_urlsafe(32)
            # SECURITY: Generate and store nonce for ID token validation
            nonce = secrets.token_urlsafe(32)
            session["sso_provider_id"] = provider_id
            session["sso_state"] = state
            session["sso_nonce"] = nonce  # Store nonce for ID token validation
            session["sso_return_url"] = return_url
            session["sso_discovery"] = discovery  # Store for callback

            # Build authorization URL
            params = {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": scopes,
                "state": state,
                "nonce": nonce,  # Include nonce in authorization request
            }

            auth_url = f"{authorization_url}?{urlencode(params)}"
            return auth_url
        except ImportError:
            raise ValueError(
                "requests not installed. Install with: pip install requests"
            )
        except Exception as e:
            raise ValueError(f"OIDC login initiation failed: {str(e)}")

    def handle_oidc_callback(
        self, provider_id: str, code: str, state: str
    ) -> tuple[User, str] | None:
        """Handle OpenID Connect authentication callback.

        Args:
            provider_id: SSO provider ID
            code: Authorization code
            state: State parameter

        Returns:
            Tuple of (User, JWT token) if authentication succeeds, None otherwise
        """
        # Verify state
        if state != session.get("sso_state"):
            return None

        provider = self.get_provider(provider_id)
        if not provider or provider.provider_type != SSOProviderType.OIDC:
            return None

        try:
            import requests

            config = safe_json_loads(
                provider.config,
                max_size=10 * 1024,  # 10KB for SSO config
                max_depth=20,
                context="SSO provider config",
            )
            discovery = session.get("sso_discovery", {})
            token_url = discovery.get("token_endpoint") or config.get("token_url")
            userinfo_url = discovery.get("userinfo_endpoint") or config.get(
                "userinfo_url"
            )

            client_id = config.get("client_id")
            client_secret = config.get("client_secret")
            redirect_uri = config.get(
                "redirect_uri", f"{self._get_base_url()}/api/sso/callback/{provider_id}"
            )

            # Exchange code for token
            token_data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            }

            # SECURITY: Add timeout to prevent DoS attacks and validate URLs to prevent SSRF
            timeout = 10  # 10 seconds timeout
            ssrf_protection = SSRFProtection()

            # SECURITY: Validate token URL to prevent SSRF attacks
            try:
                ssrf_protection.validate_url(token_url)
            except SSRFProtectionError as e:
                current_app.logger.error(
                    f"SSRF protection blocked token URL for provider {provider_id}: {e}"
                )
                return None

            try:
                token_response = requests.post(
                    token_url, data=token_data, timeout=timeout, allow_redirects=False
                )
                token_response.raise_for_status()
                token_json = token_response.json()
                access_token = token_json.get("access_token")
                id_token = token_json.get("id_token")

                if not access_token:
                    return None

                # Get user info from userinfo endpoint or ID token
                if userinfo_url:
                    # SECURITY: Validate userinfo URL to prevent SSRF attacks
                    try:
                        ssrf_protection.validate_url(userinfo_url)
                    except SSRFProtectionError as e:
                        current_app.logger.error(
                            f"SSRF protection blocked userinfo URL for provider {provider_id}: {e}"
                        )
                        return None

                    headers = {"Authorization": f"Bearer {access_token}"}
                    userinfo_response = requests.get(
                        userinfo_url,
                        headers=headers,
                        timeout=timeout,
                        allow_redirects=False,
                    )
                    userinfo_response.raise_for_status()
                    userinfo = userinfo_response.json()
                else:
                    # SECURITY: Validate ID token using authlib (signature, iss, aud, nonce, exp)
                    if not id_token:
                        current_app.logger.error(
                            f"ID token missing from OIDC provider {provider_id} response"
                        )
                        return None

                    try:
                        from authlib.jose import jwt, JoseError
                        from authlib.jose.rfc7517 import JsonWebKey

                        # Get stored nonce from session
                        expected_nonce = session.get("sso_nonce")
                        if not expected_nonce:
                            current_app.logger.error(
                                f"Nonce not found in session for OIDC provider {provider_id}"
                            )
                            return None

                        # Get issuer URL from config
                        issuer_url = config.get("issuer_url")
                        if not issuer_url:
                            current_app.logger.error(
                                f"Issuer URL not configured for OIDC provider {provider_id}"
                            )
                            return None

                        # Get JWKS URI from discovery or construct it
                        jwks_uri = discovery.get("jwks_uri")
                        if not jwks_uri:
                            jwks_uri = f"{issuer_url}/.well-known/jwks.json"

                        # Fetch JWKS (JSON Web Key Set) for signature verification
                        # SECURITY: Validate JWKS URL to prevent SSRF attacks
                        try:
                            ssrf_protection.validate_url(jwks_uri)
                        except SSRFProtectionError as e:
                            current_app.logger.error(
                                f"SSRF protection blocked JWKS URL for provider {provider_id}: {e}"
                            )
                            return None

                        try:
                            jwks_response = requests.get(
                                jwks_uri, timeout=timeout, allow_redirects=False
                            )
                            jwks_response.raise_for_status()
                            jwks = jwks_response.json()
                        except requests.RequestException as e:
                            current_app.logger.error(
                                f"Failed to fetch JWKS from {jwks_uri}: {e}"
                            )
                            return None

                        # Decode and verify ID token
                        try:
                            # Decode header to get key ID (kid)
                            import base64

                            header_part = id_token.split(".")[0]
                            header_data = base64.urlsafe_b64decode(header_part + "==")
                            header = safe_json_loads(
                                header_data.decode("utf-8"),
                                max_size=1024,  # 1KB for JWT header
                                max_depth=10,
                                context="JWT header",
                            )
                            kid = header.get("kid")

                            # Find the key in JWKS
                            key = None
                            for jwk in jwks.get("keys", []):
                                if jwk.get("kid") == kid:
                                    key = JsonWebKey.import_key(jwk)
                                    break

                            if not key:
                                current_app.logger.error(
                                    f"Key with kid={kid} not found in JWKS for OIDC provider {provider_id}"
                                )
                                return None

                            # Verify and decode ID token
                            claims = jwt.decode(
                                id_token,
                                key,
                                claims_options={
                                    "iss": {"essential": True, "value": issuer_url},
                                    "aud": {"essential": True, "value": client_id},
                                    "exp": {"essential": True},
                                    "iat": {"essential": True},
                                    "nonce": {
                                        "essential": True,
                                        "value": expected_nonce,
                                    },
                                },
                            )

                            # Validate claims
                            claims.validate()

                            # Extract user info from validated ID token
                            userinfo = {
                                "email": claims.get("email"),
                                "sub": claims.get("sub"),
                            }

                            # Clear nonce from session after successful validation
                            session.pop("sso_nonce", None)

                        except JoseError as e:
                            current_app.logger.error(
                                f"ID token validation failed for OIDC provider {provider_id}: {e}"
                            )
                            return None
                        except Exception as e:
                            current_app.logger.error(
                                f"Error validating ID token for OIDC provider {provider_id}: {e}"
                            )
                            return None
                    except ImportError:
                        # Fallback to simple decoding if authlib.jose is not available
                        current_app.logger.warning(
                            f"authlib.jose not available, using simplified ID token decoding "
                            f"for OIDC provider {provider_id}. This is insecure and should be fixed."
                        )
                        if not id_token:
                            return None
                        import base64

                        parts = id_token.split(".")
                        if len(parts) >= 2:
                            payload = base64.urlsafe_b64decode(parts[1] + "==")
                            userinfo = safe_json_loads(
                                payload.decode("utf-8"),
                                max_size=10 * 1024,  # 10KB for JWT payload
                                max_depth=20,
                                context="JWT payload",
                            )
                        else:
                            return None
            except requests.Timeout:
                current_app.logger.error(
                    f"Timeout while communicating with OIDC provider {provider_id}"
                )
                return None
            except requests.RequestException as e:
                current_app.logger.error(
                    f"Request error while communicating with OIDC provider {provider_id}: {e}"
                )
                return None

            email = userinfo.get("email") or userinfo.get("sub")
            if not email:
                return None

            # Find user (do not create automatically - users must register with password first)
            user = db.session.query(User).filter_by(email=email).first()
            if not user:
                # User does not exist - they must register with a password first
                # SSO can only be used to login to existing accounts
                current_app.logger.warning(
                    f"OIDC SSO login attempted for non-existent user: {email}"
                )
                return None

            # Generate JWT token
            from datetime import datetime, timedelta, timezone
            import jwt

            expiration = datetime.now(timezone.utc) + timedelta(hours=24)
            payload = {
                "user_id": user.id,
                "email": user.email,
                "global_role": user.global_role.value,
                "exp": expiration,
                "iat": datetime.now(timezone.utc),
            }
            secret_key = current_app.config.get("SECRET_KEY", "")
            token = jwt.encode(payload, secret_key, algorithm="HS256")
            return user, token
        except Exception:
            return None

    def initiate_magic_link_login(
        self, provider_id: str, email: str, return_url: str | None = None
    ) -> bool:
        """Initiate magic link login by sending email with magic link.

        Args:
            provider_id: SSO provider ID
            email: User email address
            return_url: Optional return URL after authentication

        Returns:
            True if email sent successfully, False otherwise
        """
        provider = self.get_provider(provider_id, active_only=True)
        if not provider:
            raise ValueError("SSO provider not found or inactive")

        if provider.provider_type != SSOProviderType.EMAIL_MAGIC_LINK:
            raise ValueError("Provider is not a magic link provider")

        config = (
            safe_json_loads(
                provider.config,
                max_size=10 * 1024,  # 10KB for SSO config
                max_depth=20,
                context="SSO provider config",
            )
            if isinstance(provider.config, str)
            else provider.config
        )
        expiry_minutes = config.get("expiry_minutes", 15)

        # Generate secure token
        token = secrets.token_urlsafe(32)

        # Calculate expiration
        from datetime import datetime, timezone

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)

        # Create magic link token
        magic_token = MagicLinkToken(
            email=email,
            provider_id=provider_id,
            token=token,
            expires_at=expires_at,
        )
        db.session.add(magic_token)
        db.session.commit()

        # Build callback URL
        base_url = self._get_base_url()
        callback_url = f"{base_url}/api/sso/callback/{provider_id}?token={token}"
        if return_url:
            callback_url += f"&return_url={return_url}"

        # Send email with magic link
        email_service = EmailService()
        subject = f"Sign in to {provider.name} - Leyzen Vault"
        body_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .button {{ display: inline-block; padding: 12px 24px; background: #007bff; 
                          color: white; text-decoration: none; border-radius: 5px; 
                          margin: 20px 0; }}
                .warning {{ color: #dc3545; font-size: 0.9em; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Sign in to Leyzen Vault</h1>
                <p>Hello,</p>
                <p>Click the button below to sign in to your account. No password required!</p>
                <p><a href="{callback_url}" class="button">Sign in</a></p>
                <p class="warning">This link is valid for {expiry_minutes} minutes. If you did not request this link, you can safely ignore this email.</p>
                <p>Best regards,<br>The Leyzen Vault Team</p>
            </div>
        </body>
        </html>
        """
        body_text = f"""
Sign in to Leyzen Vault

Hello,

Click the link below to sign in to your account. No password required!

{callback_url}

This link is valid for {expiry_minutes} minutes. If you did not request this link, you can safely ignore this email.

Best regards,
The Leyzen Vault Team
        """

        return email_service.send_email(email, subject, body_html, body_text)

    def handle_magic_link_callback(
        self, provider_id: str, token: str
    ) -> tuple[User, str] | None:
        """Handle magic link callback and authenticate user.

        Args:
            provider_id: SSO provider ID
            token: Magic link token

        Returns:
            Tuple of (User, JWT token) if successful, None otherwise
        """
        provider = self.get_provider(provider_id, active_only=True)
        if not provider:
            return None

        if provider.provider_type != SSOProviderType.EMAIL_MAGIC_LINK:
            return None

        # Find magic link token
        magic_token = (
            db.session.query(MagicLinkToken)
            .filter_by(provider_id=provider_id, token=token)
            .first()
        )

        if not magic_token:
            return None

        # Check if token is expired or used
        if magic_token.is_expired():
            return None

        if magic_token.is_used():
            return None

        # Mark token as used
        from datetime import datetime, timezone

        magic_token.used_at = datetime.now(timezone.utc)
        db.session.commit()

        # Find user (do not create automatically - users must register with password first)
        email = magic_token.email
        user = db.session.query(User).filter_by(email=email).first()

        if not user:
            # User does not exist - they must register with a password first
            # SSO can only be used to login to existing accounts
            current_app.logger.warning(
                f"Magic link SSO login attempted for non-existent user: {email}"
            )
            return None

        # Generate JWT token
        token = self.auth_service._generate_token(user)
        return user, token

    def create_provider(
        self,
        name: str,
        provider_type: SSOProviderType,
        config: dict[str, Any],
    ) -> SSOProvider:
        """Create a new SSO provider.

        Args:
            name: Provider name
            provider_type: Provider type (SAML, OAuth2, OIDC)
            config: Provider configuration dictionary

        Returns:
            Created SSOProvider object

        Raises:
            ValueError: If name already exists or if another provider of the same preset is active
                       or if configuration contains invalid URLs (SSRF protection)
        """
        # SECURITY: Validate all URLs in config to prevent SSRF attacks
        self._validate_provider_config_urls(provider_type, config)

        # Check if name already exists
        existing_by_name = db.session.query(SSOProvider).filter_by(name=name).first()
        if existing_by_name:
            raise ValueError(f"A provider with the name '{name}' already exists")

        # Get the preset from config (google, slack, discord, etc.)
        preset = config.get("provider_preset")
        if not preset:
            # If no preset, use the technical type as fallback
            preset = provider_type.value

        # Check if another provider with the same preset is active
        # We need to check all active providers and compare their presets
        from sqlalchemy import cast, String

        active_providers = (
            db.session.query(SSOProvider).filter(SSOProvider.is_active == True).all()
        )

        for active_provider in active_providers:
            active_config = (
                safe_json_loads(
                    active_provider.config,
                    max_size=10 * 1024,  # 10KB for SSO config
                    max_depth=20,
                    context="SSO provider config",
                )
                if active_provider.config
                else {}
            )
            active_preset = active_config.get("provider_preset")
            if not active_preset:
                # Fallback: detect preset from technical type and config
                active_preset = self._detect_provider_preset(
                    active_provider.provider_type, active_config
                )

            if active_preset == preset:
                raise ValueError(
                    f"Another {preset} provider ('{active_provider.name}') is already active. "
                    "Only one provider of each preset type can be active at a time."
                )

        provider = SSOProvider(
            name=name,
            provider_type=provider_type,
            config=json.dumps(config),
            is_active=True,
        )
        db.session.add(provider)
        db.session.commit()
        return provider

    def update_provider(
        self,
        provider_id: str,
        name: str | None = None,
        config: dict[str, Any] | None = None,
        is_active: bool | None = None,
    ) -> SSOProvider | None:
        """Update SSO provider.

        Args:
            provider_id: Provider ID
            name: New name (optional)
            config: New config (optional)
            is_active: New active status (optional)

        Returns:
            Updated SSOProvider object or None if not found

        Raises:
            ValueError: If name already exists (for another provider) or if activating would conflict
                       with another active provider of the same type or if configuration contains
                       invalid URLs (SSRF protection)
        """
        # When updating, we need to access the provider even if it's inactive
        provider = self.get_provider(provider_id, active_only=False)
        if not provider:
            return None

        # SECURITY: Validate all URLs in new config to prevent SSRF attacks
        if config is not None:
            self._validate_provider_config_urls(provider.provider_type, config)

        # Check if name already exists (for another provider)
        if name is not None:
            existing_by_name = (
                db.session.query(SSOProvider)
                .filter_by(name=name)
                .filter(SSOProvider.id != provider_id)
                .first()
            )
            if existing_by_name:
                raise ValueError(f"A provider with the name '{name}' already exists")

        # Check if activating would conflict with another active provider of the same preset
        if is_active is True:
            # Get the preset for the current provider
            provider_config = (
                safe_json_loads(
                    provider.config,
                    max_size=10 * 1024,  # 10KB for SSO config
                    max_depth=20,
                    context="SSO provider config",
                )
                if provider.config
                else {}
            )
            provider_preset = provider_config.get("provider_preset")
            if not provider_preset:
                provider_preset = self._detect_provider_preset(
                    provider.provider_type, provider_config
                )

            # Check all active providers for the same preset
            from sqlalchemy import cast, String

            active_providers = (
                db.session.query(SSOProvider)
                .filter(SSOProvider.is_active == True)
                .filter(SSOProvider.id != provider_id)
                .all()
            )

            for active_provider in active_providers:
                active_config = (
                    json.loads(active_provider.config) if active_provider.config else {}
                )
                active_preset = active_config.get("provider_preset")
                if not active_preset:
                    active_preset = self._detect_provider_preset(
                        active_provider.provider_type, active_config
                    )

                if active_preset == provider_preset:
                    raise ValueError(
                        f"Another {provider_preset} provider ('{active_provider.name}') is already active. "
                        "Only one provider of each preset type can be active at a time."
                    )

        if name is not None:
            provider.name = name
        if config is not None:
            # Ensure provider_preset is preserved or set in config
            config_dict = (
                config
                if isinstance(config, dict)
                else safe_json_loads(
                    config,
                    max_size=10 * 1024,  # 10KB for SSO config
                    max_depth=20,
                    context="SSO provider config",
                )
            )
            if "provider_preset" not in config_dict:
                # If preset not provided, detect it or preserve existing
                existing_config = (
                    safe_json_loads(
                        provider.config,
                        max_size=10 * 1024,  # 10KB for SSO config
                        max_depth=20,
                        context="SSO provider config",
                    )
                    if provider.config
                    else {}
                )
                existing_preset = existing_config.get("provider_preset")
                if not existing_preset:
                    existing_preset = self._detect_provider_preset(
                        provider.provider_type, existing_config
                    )
                config_dict["provider_preset"] = existing_preset
            provider.config = json.dumps(config_dict)
        if is_active is not None:
            provider.is_active = is_active

        db.session.commit()
        return provider

    def delete_provider(self, provider_id: str) -> bool:
        """Delete SSO provider.

        Args:
            provider_id: Provider ID

        Returns:
            True if deleted, False if not found
        """
        provider = self.get_provider(provider_id)
        if not provider:
            return False

        db.session.delete(provider)
        db.session.commit()
        return True
