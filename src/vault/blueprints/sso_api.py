"""SSO API routes for SAML, OAuth2, and OIDC authentication."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, redirect, request, session, url_for
from urllib.parse import parse_qs, urlparse, quote

from vault.database.schema import SSOProviderType
from vault.extensions import csrf
from vault.services.sso_service import SSOService

sso_api_bp = Blueprint("sso_api", __name__, url_prefix="/api/sso")


def _get_sso_service() -> SSOService:
    """Get SSOService instance."""
    return SSOService()


def _validate_host_header() -> None:
    """Validate that the Host header matches VAULT_URL to prevent Host header injection.

    Raises:
        ValueError: If Host header does not match VAULT_URL
    """
    try:
        settings = current_app.config.get("VAULT_SETTINGS")
        if not settings or not hasattr(settings, "vault_url") or not settings.vault_url:
            # If VAULT_URL is not configured, skip validation (will be caught by _get_base_url)
            return

        vault_url = settings.vault_url.rstrip("/")
        parsed_vault_url = urlparse(vault_url)
        vault_host = parsed_vault_url.netloc or parsed_vault_url.path.split("/")[0]

        # Get Host header from request
        request_host = request.host

        # Compare hosts (case-insensitive, without port if not specified in VAULT_URL)
        if vault_host and request_host:
            # Remove port from comparison if VAULT_URL doesn't specify one
            vault_host_no_port = vault_host.split(":")[0]
            request_host_no_port = request_host.split(":")[0]

            if vault_host_no_port.lower() != request_host_no_port.lower():
                current_app.logger.warning(
                    f"Host header mismatch: expected {vault_host}, got {request_host}"
                )
                raise ValueError(
                    "Host header does not match configured VAULT_URL. "
                    "This may indicate a Host header injection attack."
                )
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        # Log but don't fail if validation itself has an error
        current_app.logger.warning(f"Error validating Host header: {e}")


@sso_api_bp.route("/check-domain", methods=["POST"])
@csrf.exempt  # Public endpoint
def check_domain():
    """Check if an email domain requires domain-based authentication.

    Request body:
        {
            "email": "user@example.com"
        }

    Returns:
        JSON with domain info and required SSO provider if applicable
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400

        email = data.get("email", "").strip()
        if not email or "@" not in email:
            return jsonify({"error": "Invalid email address"}), 400

        from vault.services.domain_service import DomainService

        domain_service = DomainService()
        matching_rule = domain_service.find_matching_rule(email)

        if matching_rule and matching_rule.sso_provider_id:
            # Domain requires SSO
            sso_service = _get_sso_service()
            provider = sso_service.get_provider(matching_rule.sso_provider_id)
            if provider:
                return (
                    jsonify(
                        {
                            "requires_sso": True,
                            "domain_pattern": matching_rule.domain_pattern,
                            "provider": {
                                "id": provider.id,
                                "name": provider.name,
                                "provider_type": provider.provider_type.value,
                            },
                        }
                    ),
                    200,
                )

        return jsonify({"requires_sso": False}), 200
    except Exception as e:
        current_app.logger.error(f"Error checking domain: {e}")
        return jsonify({"error": "Failed to check domain"}), 500


@sso_api_bp.route("/providers", methods=["GET"])
@csrf.exempt  # Public endpoint
def list_providers():
    """List all active SSO providers (public endpoint).

    Returns:
        JSON with list of active SSO providers
    """
    try:
        sso_service = _get_sso_service()
        providers = sso_service.list_providers()

        # Return provider info without sensitive config data
        providers_data = []
        for provider in providers:
            provider_dict = provider.to_dict()
            # Remove sensitive information from config
            config = provider_dict.get("config", {})
            # Only expose non-sensitive config fields
            safe_config = {}
            if provider.provider_type == SSOProviderType.SAML:
                safe_config = {
                    "entity_id": config.get("entity_id"),
                    "sso_url": config.get("sso_url"),
                }
            elif provider.provider_type in (
                SSOProviderType.OAUTH2,
                SSOProviderType.OIDC,
            ):
                safe_config = {
                    "authorization_url": config.get("authorization_url"),
                }
                if provider.provider_type == SSOProviderType.OIDC:
                    safe_config["issuer_url"] = config.get("issuer_url")

            providers_data.append(
                {
                    "id": provider_dict["id"],
                    "name": provider_dict["name"],
                    "provider_type": provider_dict["provider_type"],
                    "is_active": provider_dict["is_active"],
                    "config": safe_config,
                }
            )

        return jsonify({"providers": providers_data}), 200
    except Exception as e:
        current_app.logger.error(f"Error listing SSO providers: {e}")
        return jsonify({"error": "Failed to list SSO providers"}), 500


@sso_api_bp.route("/login/<provider_id>", methods=["POST"])
@csrf.exempt  # Public endpoint, CSRF handled by state parameter
def initiate_login(provider_id: str):
    """Initiate SSO login flow.

    Args:
        provider_id: SSO provider ID

    Request body (optional):
        {
            "return_url": "https://example.com/dashboard" (optional)
        }

    Returns:
        Redirect to SSO provider or JSON with redirect URL
    """
    try:
        # SECURITY: Validate Host header to prevent Host header injection
        try:
            _validate_host_header()
        except ValueError as e:
            current_app.logger.error(f"Host header validation failed: {e}")
            return jsonify({"error": "Invalid request"}), 400

        data = request.get_json() or {}
        return_url = data.get("return_url")

        sso_service = _get_sso_service()
        provider = sso_service.get_provider(provider_id)

        if not provider:
            return jsonify({"error": "SSO provider not found"}), 404

        if not provider.is_active:
            return jsonify({"error": "SSO provider is not active"}), 400

        # Initiate login based on provider type
        try:
            if provider.provider_type == SSOProviderType.EMAIL_MAGIC_LINK:
                # Magic link requires email in request body
                email = data.get("email", "").strip()
                if not email:
                    return (
                        jsonify({"error": "Email is required for magic link login"}),
                        400,
                    )

                success = sso_service.initiate_magic_link_login(
                    provider_id, email, return_url
                )

                if success:
                    return (
                        jsonify(
                            {
                                "message": "Magic link sent to your email address",
                                "email": email,
                            }
                        ),
                        200,
                    )
                else:
                    return jsonify({"error": "Failed to send magic link email"}), 500
            elif provider.provider_type == SSOProviderType.SAML:
                redirect_url = sso_service.initiate_saml_login(provider_id, return_url)
            elif provider.provider_type == SSOProviderType.OAUTH2:
                redirect_url = sso_service.initiate_oauth2_login(
                    provider_id, return_url
                )
            elif provider.provider_type == SSOProviderType.OIDC:
                redirect_url = sso_service.initiate_oidc_login(provider_id, return_url)
            else:
                return jsonify({"error": "Unsupported provider type"}), 400

            # For AJAX requests, return JSON with redirect URL
            if request.headers.get("Content-Type") == "application/json":
                return jsonify({"redirect_url": redirect_url}), 200

            # For form submissions, redirect directly
            return redirect(redirect_url)

        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            current_app.logger.error(f"Error initiating SSO login: {e}")
            return jsonify({"error": "Failed to initiate SSO login"}), 500

    except Exception as e:
        current_app.logger.error(f"Error in initiate_login: {e}")
        return jsonify({"error": "An error occurred"}), 500


@sso_api_bp.route("/callback/<provider_id>", methods=["GET", "POST"])
@csrf.exempt  # Public endpoint, CSRF handled by state parameter
def handle_callback(provider_id: str):
    """Handle SSO authentication callback.

    Args:
        provider_id: SSO provider ID

    For OAuth2/OIDC: expects 'code' and 'state' query parameters
    For SAML: expects POST data with SAML response

    Returns:
        Redirect to frontend with token or error message
    """
    try:
        # SECURITY: Validate Host header to prevent Host header injection
        try:
            _validate_host_header()
        except ValueError as e:
            current_app.logger.error(f"Host header validation failed: {e}")
            error_msg = "Invalid request"
            frontend_url = f"/login?error={error_msg}"
            return redirect(frontend_url)

        sso_service = _get_sso_service()
        provider = sso_service.get_provider(provider_id)

        if not provider:
            return jsonify({"error": "SSO provider not found"}), 404

        # Get return URL from session
        return_url = session.get("sso_return_url")
        if not return_url:
            # Default to dashboard
            return_url = "/dashboard"

        # Handle callback based on provider type
        result = None
        if provider.provider_type == SSOProviderType.EMAIL_MAGIC_LINK:
            # Magic link uses GET with token parameter
            token = request.args.get("token")
            if not token:
                return jsonify({"error": "Missing token parameter"}), 400
            result = sso_service.handle_magic_link_callback(provider_id, token)
        elif provider.provider_type == SSOProviderType.SAML:
            # SAML uses POST with form data
            result = sso_service.handle_saml_callback(provider_id)
        elif provider.provider_type == SSOProviderType.OAUTH2:
            # OAuth2 uses GET with code and state
            code = request.args.get("code")
            state = request.args.get("state")
            if not code or not state:
                return jsonify({"error": "Missing code or state parameter"}), 400
            result = sso_service.handle_oauth2_callback(provider_id, code, state)
        elif provider.provider_type == SSOProviderType.OIDC:
            # OIDC uses GET with code and state
            code = request.args.get("code")
            state = request.args.get("state")
            if not code or not state:
                return jsonify({"error": "Missing code or state parameter"}), 400
            result = sso_service.handle_oidc_callback(provider_id, code, state)
        else:
            return jsonify({"error": "Unsupported provider type"}), 400

        if not result:
            # Authentication failed - user may not exist
            error_msg = "Account not found. Please register first."
            # Redirect to SSO callback page with error (which will show error and redirect to login)
            frontend_url = f"/sso/callback/{provider_id}?error={quote(error_msg)}"
            return redirect(frontend_url)

        user, token = result

        # Clear SSO session data
        session.pop("sso_provider_id", None)
        session.pop("sso_state", None)
        session.pop("sso_nonce", None)  # Clear nonce
        session.pop("sso_return_url", None)
        session.pop("sso_discovery", None)

        # For SSO users, we need to handle master key differently
        # Since they don't have a password, we'll need to handle this in the frontend
        # For now, redirect to frontend with token
        # The frontend will need to handle SSO users specially

        # Build redirect URL with token
        # Use VAULT_URL (mandatory, no fallback to request.host_url)
        from vault.services.share_link_service import ShareService

        share_service = ShareService()
        frontend_base = share_service._get_base_url()
        if not frontend_base:
            # If VAULT_URL is not configured, use relative URL
            current_app.logger.warning(
                "VAULT_URL not configured, using relative URL for SSO callback"
            )
            callback_url = (
                f"/sso/callback/{provider_id}?token={token}&user_id={user.id}"
            )
        else:
            callback_url = f"{frontend_base}/sso/callback/{provider_id}?token={token}&user_id={user.id}"

        return redirect(callback_url)

    except Exception as e:
        current_app.logger.error(f"Error in SSO callback: {e}")
        error_msg = "An error occurred during SSO authentication"
        frontend_url = f"/login?error={error_msg}"
        return redirect(frontend_url)
