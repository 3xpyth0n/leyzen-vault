"""Email service for sending verification, invitation, and notification emails."""

from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import current_app

from vault.config import SMTPConfig


class EmailService:
    """Service for sending emails via SMTP."""

    def __init__(self, smtp_config: SMTPConfig | None = None):
        """Initialize email service.

        Args:
            smtp_config: SMTP configuration. If None, will try to get from Flask config.
        """
        self.smtp_config = smtp_config

    def _get_smtp_config(self) -> SMTPConfig | None:
        """Get SMTP configuration from Flask config if not provided.

        Returns:
            SMTPConfig or None if not configured
        """
        if self.smtp_config:
            return self.smtp_config

        try:
            settings = current_app.config.get("VAULT_SETTINGS")
            if settings and hasattr(settings, "smtp_config"):
                return settings.smtp_config
        except Exception:
            pass

        return None

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
    ) -> bool:
        """Send an email.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body_html: HTML email body
            body_text: Plain text email body (optional, auto-generated from HTML if not provided)

        Returns:
            True if email sent successfully, False otherwise
        """
        smtp_config = self._get_smtp_config()
        if not smtp_config:
            current_app.logger.warning("SMTP not configured, cannot send email")
            return False

        email_sent = False
        server = None

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{smtp_config.from_name} <{smtp_config.from_email}>"
            msg["To"] = to_email

            # Add text and HTML parts
            if body_text:
                text_part = MIMEText(body_text, "plain")
                msg.attach(text_part)

            html_part = MIMEText(body_html, "html")
            msg.attach(html_part)

            # Send email
            if smtp_config.use_tls:
                server = smtplib.SMTP(smtp_config.host, smtp_config.port, timeout=30)
                server.starttls()
            else:
                server = smtplib.SMTP(smtp_config.host, smtp_config.port, timeout=30)

            server.login(smtp_config.user, smtp_config.password)
            server.send_message(msg)

            current_app.logger.info(f"Email sent to {to_email}: {subject}")
            email_sent = True

        except Exception as e:
            current_app.logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
        finally:
            # Always try to close the connection, even if there's an error
            if server:
                try:
                    server.quit()
                except Exception:
                    # If quit() fails, try close() as fallback
                    try:
                        server.close()
                    except Exception:
                        # Ignore errors during cleanup - email may have been sent successfully
                        pass

        return email_sent

    def send_verification_email(
        self,
        to_email: str,
        verification_url: str,
        expiry_minutes: int = 10,
    ) -> bool:
        """Send email verification email with link.

        Args:
            to_email: Recipient email address
            verification_url: Verification URL (required)
            expiry_minutes: Expiration time in minutes (default: 10)

        Returns:
            True if email sent successfully, False otherwise
        """
        smtp_config = self._get_smtp_config()
        if not smtp_config:
            return False

        if not verification_url:
            return False

        subject = "Verify your email address - Leyzen Vault"

        # HTML email body
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
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Verify your email address</h1>
                <p>Hello,</p>
                <p>Thank you for signing up for Leyzen Vault. To complete your registration,
                please click on the following link to verify your email address:</p>
                <p><a href="{verification_url}" class="button">Verify my email</a></p>
                <p>This link is valid for {expiry_minutes} minutes.</p>
                <p>If you did not create an account, you can ignore this email.</p>
                <p>Best regards,<br>The Leyzen Vault Team</p>
            </div>
        </body>
        </html>
        """

        # Plain text version
        body_text = f"""
Verify your email address

Hello,

Thank you for signing up for Leyzen Vault. To complete your registration,
please click on the following link to verify your email address:

{verification_url}

This link is valid for {expiry_minutes} minutes.

If you did not create an account, you can ignore this email.

Best regards,
The Leyzen Vault Team
        """

        return self.send_email(to_email, subject, body_html, body_text)

    def send_invitation_email(
        self,
        to_email: str,
        invitation_url: str,
        invited_by: str | None = None,
    ) -> bool:
        """Send invitation email.

        Args:
            to_email: Recipient email address
            invitation_url: URL to accept invitation and set password
            invited_by: Name or email of the admin who sent the invitation

        Returns:
            True if email sent successfully, False otherwise
        """
        smtp_config = self._get_smtp_config()
        if not smtp_config:
            return False

        subject = "Invitation to join Leyzen Vault"

        invited_by_text = f"by {invited_by}" if invited_by else "by an administrator"

        # HTML email body
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
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Invitation to join Leyzen Vault</h1>
                <p>Hello,</p>
                <p>You have been invited {invited_by_text} to join Leyzen Vault.</p>
                <p>To accept the invitation and create your account, click on the button below:</p>
                <p><a href="{invitation_url}" class="button">Accept invitation</a></p>
                <p>This link is valid for 7 days.</p>
                <p>If you did not request this invitation, you can ignore this email.</p>
                <p>Best regards,<br>The Leyzen Vault Team</p>
            </div>
        </body>
        </html>
        """

        # Plain text version
        body_text = f"""
Invitation to join Leyzen Vault

Hello,

You have been invited {invited_by_text} to join Leyzen Vault.

To accept the invitation and create your account, click on the following link:
{invitation_url}

This link is valid for 7 days.

If you did not request this invitation, you can ignore this email.

Best regards,
The Leyzen Vault Team
        """

        return self.send_email(to_email, subject, body_html, body_text)

    def send_password_reset_email(
        self,
        to_email: str,
        reset_url: str,
    ) -> bool:
        """Send password reset email.

        Args:
            to_email: Recipient email address
            reset_url: URL to reset password

        Returns:
            True if email sent successfully, False otherwise
        """
        smtp_config = self._get_smtp_config()
        if not smtp_config:
            return False

        subject = "Reset your password - Leyzen Vault"

        # HTML email body
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
                .warning {{ color: #dc3545; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Reset your password</h1>
                <p>Hello,</p>
                <p>You have requested to reset your password for your Leyzen Vault account.</p>
                <p>Click on the button below to reset your password:</p>
                <p><a href="{reset_url}" class="button">Reset my password</a></p>
                <p class="warning">This link is valid for 1 hour. If you did not request
                this password reset, ignore this email and your password will remain unchanged.</p>
                <p>Best regards,<br>The Leyzen Vault Team</p>
            </div>
        </body>
        </html>
        """

        # Plain text version
        body_text = f"""
Reset your password

Hello,

You have requested to reset your password for your Leyzen Vault account.

Click on the following link to reset your password:
{reset_url}

This link is valid for 1 hour. If you did not request this password reset,
ignore this email and your password will remain unchanged.

Best regards,
The Leyzen Vault Team
        """

        return self.send_email(to_email, subject, body_html, body_text)

    def send_notification_email(
        self,
        to_email: str,
        subject: str,
        message: str,
    ) -> bool:
        """Send a generic notification email.

        Args:
            to_email: Recipient email address
            subject: Email subject
            message: Message content (HTML)

        Returns:
            True if email sent successfully, False otherwise
        """
        body_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                {message}
                <p>Best regards,<br>The Leyzen Vault Team</p>
            </div>
        </body>
        </html>
        """

        return self.send_email(to_email, subject, body_html)

    def send_share_link_email(
        self,
        to_email: str,
        share_url: str,
        file_name: str,
        sender_name: str | None = None,
    ) -> bool:
        """Send share link email with styled template.

        Args:
            to_email: Recipient email address
            share_url: Full share URL including decryption key in fragment
            file_name: Name of the shared file
            sender_name: Name or email of the sender (optional)

        Returns:
            True if email sent successfully, False otherwise
        """
        smtp_config = self._get_smtp_config()
        if not smtp_config:
            return False

        if not share_url:
            return False

        subject = f"Shared file: {file_name} - Leyzen Vault"

        sender_text = f" by {sender_name}" if sender_name else ""

        # HTML email body
        body_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    margin: 0;
                    padding: 0;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #ffffff;
                }}
                .header {{
                    text-align: center;
                    padding: 30px 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border-radius: 8px 8px 0 0;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 24px;
                    font-weight: 600;
                }}
                .content {{
                    padding: 30px 20px;
                }}
                .file-info {{
                    background-color: #f8f9fa;
                    border-left: 4px solid #667eea;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                }}
                .file-name {{
                    font-weight: 600;
                    color: #333;
                    font-size: 16px;
                    margin: 0 0 5px 0;
                }}
                .button-container {{
                    text-align: center;
                    margin: 30px 0;
                }}
                .button {{
                    display: inline-block;
                    padding: 14px 28px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: 600;
                    font-size: 16px;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    transition: transform 0.2s ease;
                }}
                .button:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
                }}
                .security-note {{
                    background-color: #fff3cd;
                    border: 1px solid #ffc107;
                    border-radius: 4px;
                    padding: 15px;
                    margin: 20px 0;
                    color: #856404;
                    font-size: 14px;
                }}
                .security-note strong {{
                    display: block;
                    margin-bottom: 5px;
                }}
                .footer {{
                    text-align: center;
                    padding: 20px;
                    color: #6c757d;
                    font-size: 14px;
                    border-top: 1px solid #e9ecef;
                    margin-top: 30px;
                }}
                .url-fallback {{
                    background-color: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                    padding: 15px;
                    margin: 20px 0;
                    word-break: break-all;
                    font-family: monospace;
                    font-size: 12px;
                    color: #495057;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>File Shared with You</h1>
                </div>
                <div class="content">
                    <p>Hello,</p>
                    <p>A file has been shared with you{sender_text} via Leyzen Vault.</p>

                    <div class="file-info">
                        <div class="file-name">📄 {file_name}</div>
                    </div>

                    <div class="button-container">
                        <a href="{share_url}" class="button">Access Shared File</a>
                    </div>

                    <div class="url-fallback">
                        <strong>Or copy this link:</strong><br>
                        {share_url}
                    </div>

                    <div class="security-note">
                        <strong>🔒 Security Information:</strong>
                        This link contains the decryption key needed to access the file.
                        Keep this link secure and do not share it with unauthorized parties.
                        The link will remain valid according to the sharing settings.
                    </div>

                    <p>If you did not expect this email, you can safely ignore it.</p>
                </div>
                <div class="footer">
                    <p>Best regards,<br>The Leyzen Vault Team</p>
                    <p style="margin-top: 10px; font-size: 12px; color: #adb5bd;">
                        This is an automated message. Please do not reply to this email.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        # Plain text version
        body_text = f"""
File Shared with You

Hello,

A file has been shared with you{sender_text} via Leyzen Vault.

File: {file_name}

Access the shared file using this link:
{share_url}

Security Information:
This link contains the decryption key needed to access the file.
Keep this link secure and do not share it with unauthorized parties.
The link will remain valid according to the sharing settings.

If you did not expect this email, you can safely ignore it.

Best regards,
The Leyzen Vault Team

---
This is an automated message. Please do not reply to this email.
        """

        return self.send_email(to_email, subject, body_html, body_text)
