from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings and configuration."""
    
    # Application settings
    app_name: str = "Scribe API"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # API settings
    api_v1_prefix: str = "/api/v1"
    
    # Security settings
    secret_key: str = Field(..., description="Secret key for JWT tokens")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Database settings
    database_url: Optional[str] = Field(None, description="Database connection URL")
    database_echo: bool = False
    
    # Redis settings
    redis_url: Optional[str] = Field(None, description="Redis connection URL")
    
    # CORS settings
    backend_cors_origins: list[str] = ["*"]
    
    # Logging settings
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds
    
    # Azure AD OAuth settings
    azure_client_id: Optional[str] = Field(None, description="Azure AD Client ID")
    azure_client_secret: Optional[str] = Field(None, description="Azure AD Client Secret")
    azure_tenant_id: Optional[str] = Field(None, description="Azure AD Tenant ID")
    azure_redirect_uri: str = Field("http://localhost:8000/api/v1/auth/callback", description="OAuth redirect URI")
    azure_authority: Optional[str] = Field(None, description="Azure AD Authority URL")
    azure_scopes: list[str] = Field(["User.Read"], description="Default OAuth scopes")
    
    @property
    def azure_authority_url(self) -> str:
        """Get the full Azure authority URL."""
        if self.azure_authority:
            return self.azure_authority
        if self.azure_tenant_id:
            return f"https://login.microsoftonline.com/{self.azure_tenant_id}"
        return "https://login.microsoftonline.com/common"
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "env_file_encoding": "utf-8"
    }


settings = Settings()