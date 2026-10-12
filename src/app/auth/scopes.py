"""Delegated Graph scopes for the signed-in Outlook.com account.

MSAL adds offline_access, openid, and profile itself. Passing those reserved
scopes to the library raises an error, so they stay out of this list.
"""

SCOPES = [
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/Files.ReadWrite",
]
