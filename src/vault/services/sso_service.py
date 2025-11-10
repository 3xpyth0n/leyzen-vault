"""SSO service for SAML, OAuth2, and OpenID Connect authentication."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode, urlparse, parse_qs

from flask import current_app, redirect, request, session, url_for
from sqlalchemy.orm import Session

from vault.database.schema import SSOProvider, SSOProviderType, User, db
from vault.services.auth_service import AuthService


class SSOService:
    """Service for SSO authentication (SAML, OAuth2, OIDC)."""

    def __init__(self, auth_service: AuthService | None = None):
        """Initialize SSO service.

        Args:
            auth_service: Optional AuthService instance
        """
        self.auth_service = auth_service
        if self.auth_service is None:
            secret_key = current_app.config.get("SECRET_KEY", "")
            self.auth_service = AuthService(secret_key)

    def get_provider(self, provider_id: str) -> SSOProvider | None:
        """Get SSO provider by ID.

        Args:
            provider_id: Provider ID

        Returns:
            SSOProvider object or None
        """
        return (
            db.session.query(SSOProvider)
            .filter_by(id=provider_id, is_active=True)
            .first()
        )

    def list_providers(self) -> list[SSOProvider]:
        """Get all active SSO providers.

        Returns:
            List of SSOProvider objects
        """
        return db.session.query(SSOProvider).filter_by(is_active=True).all()

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
            config = json.loads(provider.config)
            saml_settings = {
                "sp": {
                    "entityId": config.get("sp_entity_id", "leyzen-vault"),
                    "assertionConsumerService": {
                        "url": config.get(
                            "acs_url",
                            f"{request.host_url}api/sso/callback/{provider_id}",
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

            config = json.loads(provider.config)
            saml_settings = {
                "sp": {
                    "entityId": config.get("sp_entity_id", "leyzen-vault"),
                    "assertionConsumerService": {
                        "url": config.get(
                            "acs_url",
                            f"{request.host_url}api/sso/callback/{provider_id}",
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

                # Find or create user
                user = db.session.query(User).filter_by(email=email).first()
                if not user:
                    # Auto-create user from SSO (optional, can be disabled)
                    if config.get("auto_create_users", False):
                        user = self.auth_service.create_user(
                            email=email,
                            password="",  # SSO users don't have passwords
                            global_role=config.get("default_role", "user"),
                        )
                    else:
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

            config = json.loads(provider.config)
            client_id = config.get("client_id")
            authorization_url = config.get("authorization_url")
            redirect_uri = config.get(
                "redirect_uri", f"{request.host_url}api/sso/callback/{provider_id}"
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

            config = json.loads(provider.config)
            client_id = config.get("client_id")
            client_secret = config.get("client_secret")
            token_url = config.get("token_url")
            userinfo_url = config.get("userinfo_url")
            redirect_uri = config.get(
                "redirect_uri", f"{request.host_url}api/sso/callback/{provider_id}"
            )

            # Exchange code for token
            token_data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            }

            token_response = requests.post(token_url, data=token_data)
            token_response.raise_for_status()
            token_json = token_response.json()
            access_token = token_json.get("access_token")

            if not access_token:
                return None

            # Get user info
            headers = {"Authorization": f"Bearer {access_token}"}
            userinfo_response = requests.get(userinfo_url, headers=headers)
            userinfo_response.raise_for_status()
            userinfo = userinfo_response.json()

            email = userinfo.get("email") or userinfo.get("sub")
            if not email:
                return None

            # Find or create user
            user = db.session.query(User).filter_by(email=email).first()
            if not user:
                if config.get("auto_create_users", False):
                    user = self.auth_service.create_user(
                        email=email,
                        password="",  # SSO users don't have passwords
                        global_role=config.get("default_role", "user"),
                    )
                else:
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

            config = json.loads(provider.config)
            issuer_url = config.get("issuer_url")

            # Discover OIDC endpoints
            discovery_url = f"{issuer_url}/.well-known/openid-configuration"
            discovery_response = requests.get(discovery_url)
            discovery_response.raise_for_status()
            discovery = discovery_response.json()

            authorization_url = discovery.get("authorization_endpoint")
            client_id = config.get("client_id")
            redirect_uri = config.get(
                "redirect_uri", f"{request.host_url}api/sso/callback/{provider_id}"
            )
            scopes = config.get("scopes", "openid email profile")

            # Store state and return_url in session
            import secrets

            state = secrets.token_urlsafe(32)
            session["sso_provider_id"] = provider_id
            session["sso_state"] = state
            session["sso_return_url"] = return_url
            session["sso_discovery"] = discovery  # Store for callback

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

            config = json.loads(provider.config)
            discovery = session.get("sso_discovery", {})
            token_url = discovery.get("token_endpoint") or config.get("token_url")
            userinfo_url = discovery.get("userinfo_endpoint") or config.get(
                "userinfo_url"
            )

            client_id = config.get("client_id")
            client_secret = config.get("client_secret")
            redirect_uri = config.get(
                "redirect_uri", f"{request.host_url}api/sso/callback/{provider_id}"
            )

            # Exchange code for token
            token_data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            }

            token_response = requests.post(token_url, data=token_data)
            token_response.raise_for_status()
            token_json = token_response.json()
            access_token = token_json.get("access_token")
            id_token = token_json.get("id_token")

            if not access_token:
                return None

            # Get user info from userinfo endpoint or ID token
            if userinfo_url:
                headers = {"Authorization": f"Bearer {access_token}"}
                userinfo_response = requests.get(userinfo_url, headers=headers)
                userinfo_response.raise_for_status()
                userinfo = userinfo_response.json()
            else:
                # Decode ID token (simplified - in production use proper JWT verification)
                import base64

                parts = id_token.split(".")
                if len(parts) >= 2:
                    payload = base64.urlsafe_b64decode(parts[1] + "==")
                    userinfo = json.loads(payload)
                else:
                    return None

            email = userinfo.get("email") or userinfo.get("sub")
            if not email:
                return None

            # Find or create user
            user = db.session.query(User).filter_by(email=email).first()
            if not user:
                if config.get("auto_create_users", False):
                    user = self.auth_service.create_user(
                        email=email,
                        password="",
                        global_role=config.get("default_role", "user"),
                    )
                else:
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
        """
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
        """
        provider = self.get_provider(provider_id)
        if not provider:
            return None

        if name is not None:
            provider.name = name
        if config is not None:
            provider.config = json.dumps(config)
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
