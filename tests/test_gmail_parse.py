from app.google.parse import decode_b64url, parse_gmail_message


def test_parse_walks_nested_audio_parts():
    payload = {
        "id": "18f4abc",
        "internalDate": "1760000000000",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "From", "value": "Caller <caller@example.com>"},
                {"name": "Subject", "value": "Voicemail"},
            ],
            "parts": [
                {"mimeType": "text/plain", "filename": "", "body": {"size": 4}},
                {
                    "mimeType": "multipart/mixed",
                    "parts": [
                        {
                            "filename": "clip.wav",
                            "mimeType": "audio/wav",
                            "body": {"attachmentId": "ANGjdJ", "size": 12},
                        }
                    ],
                },
            ],
        },
    }
    parsed = parse_gmail_message(payload)
    assert parsed["sender"] == "Caller <caller@example.com>"
    assert parsed["subject"] == "Voicemail"
    assert parsed["received_time"].startswith("2025-")
    assert parsed["attachments"] == [{"id": "ANGjdJ", "name": "clip.wav", "mime": "audio/wav"}]
    assert parsed["attachment_pending"] is False


def test_filename_without_bytes_is_pending():
    payload = {
        "id": "abc",
        "payload": {
            "filename": "clip.mp3",
            "mimeType": "audio/mpeg",
            "body": {"size": 10},
        },
    }
    parsed = parse_gmail_message(payload)
    assert parsed["attachments"] == []
    assert parsed["attachment_pending"] is True


def test_decode_b64url_pads():
    assert decode_b64url("YQ") == b"a"
