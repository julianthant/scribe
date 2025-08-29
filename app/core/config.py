"""
config.py - Application Configuration Settings

Defines the global configuration settings for the Scribe application using Dynaconf.
This file manages:
- Application metadata (name, version, debug mode)
- API configuration (versioning, prefixes)
- Security settings (JWT tokens, secret keys)
- In-memory cache settings
- CORS policies
- Logging configuration
- Rate limiting parameters
- Azure AD OAuth authentication settings

Configuration follows Dynaconf best practices:
- Non-sensitive settings in settings.toml
- Sensitive settings in .secrets.toml (gitignored)
- Environment variables override file settings with SCRIBE_ prefix
- Environment-specific configuration sections [development], [production], [testing]
"""

from dynaconf import Dynaconf  # type: ignore[import-untyped]
from typing import List, Optional


# Initialize Dynaconf with proper TOML-based configuration
settings = Dynaconf(
    # Enable environment-specific configuration sections
    environments=True,
    
    # Load configuration files in order (later files override earlier ones)
    settings_files=["settings.toml", ".secrets.toml"],
    
    # Environment variable prefix for overrides
    envvar_prefix="SCRIBE",
    
    # Load .env file for environment switching
    load_dotenv=True,
    
    # Enable merging of nested dictionaries and lists
    merge_enabled=True,
    
    # Environment switcher variable (set ENV_FOR_DYNACONF=production to switch)
    env_switcher="ENV_FOR_DYNACONF",
    
    # Default environment if not specified
    env="development"
)

def get_azure_authority_url() -> str:
    """
    Get the full Azure authority URL for OAuth authentication.
    
    Returns:
        Azure AD authority URL
    """
    if settings.get("azure_authority"):
        return str(settings.azure_authority)
    if settings.get("azure_tenant_id"):
        return f"https://login.microsoftonline.com/{settings.azure_tenant_id}"
    return "https://login.microsoftonline.com/common"



def validate_required_settings() -> None:
    """
    Validate that all required settings are present.
    
    Raises:
        ValueError: If required settings are missing
    """
    required_settings = [
        ("secret_key", "Secret key for JWT token signing"),
        ("jwt_secret", "JWT secret for token generation"),
    ]
    
    missing_settings = []
    for setting, description in required_settings:
        if not settings.get(setting):
            missing_settings.append(f"{setting} ({description})")
    
    if missing_settings:
        raise ValueError(
            f"Missing required settings:\n" + 
            "\n".join(f"  - {setting}" for setting in missing_settings) +
            f"\n\nSet these via environment variables with SCRIBE_ prefix or in .secrets.toml file."
        )


# Add computed properties to settings object
settings.azure_authority_url_computed = get_azure_authority_url


# Environment-specific validation and setup
if settings.current_env == "production":
    # Additional production validations
    if not settings.get("azure_client_secret"):
        raise ValueError("azure_client_secret must be set in production environment")
    if settings.debug:
        raise ValueError("Debug mode should not be enabled in production")