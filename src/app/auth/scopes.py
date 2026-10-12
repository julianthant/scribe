"""OAuth scopes for the Gmail account that receives forwarded voicemail.

gmail.modify reads messages and applies the scribe/processed label.
spreadsheets reads and appends the transcript sheet.
"""

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/spreadsheets",
]
