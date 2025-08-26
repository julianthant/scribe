"""
azure package - Azure Services Integration

This package provides Azure Active Directory and Microsoft Graph API integration services.
It contains separate service classes for different Azure functionalities:

- AzureAuthService: Azure AD OAuth authentication and token management
- AzureGraphService: Base Microsoft Graph API operations  
- AzureMailService: Email and mailbox operations via Graph API

All services are built on top of the Microsoft Authentication Library (MSAL) and
provide secure, scalable access to Azure and Office 365 services.
"""