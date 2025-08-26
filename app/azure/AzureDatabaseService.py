"""
AzureDatabaseService.py - Azure-specific Database Operations

Handles Azure AD authentication and Azure SQL Server specific configurations
for the Scribe application database layer.

This service provides:
- Azure AD access token management for database connections
- Azure SQL Server specific connection configurations
- Token refresh and error handling
- Integration with Azure Identity libraries

The service follows the existing Azure service pattern in the codebase.
"""

import logging
import struct
from typing import Optional, Dict, Any

from app.core.config import settings
from app.core.Exceptions import DatabaseError

logger = logging.getLogger(__name__)

# Connection option for Azure access tokens
SQL_COPT_SS_ACCESS_TOKEN = 1256


class AzureDatabaseService:
    """Service for Azure-specific database operations and authentication."""
    
    def __init__(self):
        self._credential = None
        self._current_token = None
    
    def _get_azure_credential(self):
        """Get Azure credential instance, creating if needed."""
        if self._credential is None:
            try:
                from azure.identity import DefaultAzureCredential
                self._credential = DefaultAzureCredential()
                logger.info("Azure credential initialized successfully")
            except ImportError:
                logger.error("Azure Identity library not available")
                raise DatabaseError(
                    "Azure Identity library not available",
                    error_code="AZURE_IDENTITY_MISSING"
                )
            except Exception as e:
                logger.error(f"Failed to initialize Azure credential: {e}")
                raise DatabaseError(
                    "Failed to initialize Azure credential",
                    error_code="AZURE_CREDENTIAL_ERROR",
                    details={"error": str(e)}
                )
        
        return self._credential
    
    def get_access_token(self) -> str:
        """Get Azure AD access token for database access."""
        if not settings.azure_database_use_access_token:
            return ""
        
        try:
            credential = self._get_azure_credential()
            token_result = credential.get_token("https://database.windows.net/.default")
            self._current_token = token_result.token
            
            logger.debug("Azure AD database access token acquired successfully")
            return self._current_token
            
        except Exception as e:
            logger.error(f"Failed to acquire Azure AD access token: {e}")
            raise DatabaseError(
                "Failed to acquire Azure AD access token",
                error_code="AZURE_TOKEN_ERROR",
                details={"error": str(e)}
            )
    
    def get_token_struct(self) -> bytes:
        """Get token as struct format for ODBC connection."""
        token = self.get_access_token()
        if not token:
            return b""
        
        try:
            # Convert token to UTF-16-LE bytes for SQL Server
            token_bytes = token.encode("UTF-16-LE")
            # Create struct with length prefix
            token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)
            
            logger.debug("Azure AD token struct created successfully")
            return token_struct
            
        except Exception as e:
            logger.error(f"Failed to create token struct: {e}")
            raise DatabaseError(
                "Failed to create token struct",
                error_code="TOKEN_STRUCT_ERROR",
                details={"error": str(e)}
            )
    
    def get_connection_attrs(self) -> Dict[int, Any]:
        """Get connection attributes for Azure AD authentication."""
        if not settings.azure_database_use_access_token:
            return {}
        
        try:
            token_struct = self.get_token_struct()
            if token_struct:
                return {SQL_COPT_SS_ACCESS_TOKEN: token_struct}
            return {}
            
        except Exception as e:
            logger.error(f"Failed to get connection attributes: {e}")
            # Return empty dict to allow connection without token
            return {}
    
    def is_token_authentication_enabled(self) -> bool:
        """Check if Azure AD token authentication is enabled."""
        return bool(settings.azure_database_use_access_token)
    
    def validate_azure_configuration(self) -> Dict[str, Any]:
        """Validate Azure database configuration."""
        errors_list: list[str] = []
        validation_result = {
            "azure_authentication_enabled": self.is_token_authentication_enabled(),
            "azure_identity_available": False,
            "credential_initialized": False,
            "token_acquired": False,
            "errors": errors_list
        }
        
        # Check if Azure Identity is available
        try:
            import azure.identity
            validation_result["azure_identity_available"] = True
        except ImportError:
            errors_list.append("Azure Identity library not installed")
            return validation_result
        
        if not self.is_token_authentication_enabled():
            return validation_result
        
        # Try to initialize credential
        try:
            self._get_azure_credential()
            validation_result["credential_initialized"] = True
        except Exception as e:
            errors_list.append(f"Failed to initialize credential: {str(e)}")
            return validation_result
        
        # Try to acquire token
        try:
            token = self.get_access_token()
            validation_result["token_acquired"] = bool(token)
        except Exception as e:
            errors_list.append(f"Failed to acquire token: {str(e)}")
        
        return validation_result
    
    def refresh_token(self) -> bool:
        """Refresh the current access token."""
        try:
            old_token = self._current_token
            new_token = self.get_access_token()
            
            if new_token and new_token != old_token:
                logger.info("Azure AD access token refreshed successfully")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to refresh access token: {e}")
            return False
    
    def clear_cached_token(self) -> None:
        """Clear cached token to force refresh on next request."""
        self._current_token = None
        logger.debug("Cached Azure AD token cleared")


# Global service instance
azure_database_service = AzureDatabaseService()