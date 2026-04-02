from __future__ import annotations


def text_message(body: str) -> dict[str, str]:
    """Generate simple text message template.

    Args:
        body: Message text content.

    Returns:
        Dictionary with 'body' key for Wappi API.
    """
    return {"body": body}


def file_message(file_url: str, caption: str = "") -> dict[str, str]:
    """Generate file message template (PDF, document, etc.).

    Args:
        file_url: URL of file to attach (PDF, doc, etc.).
        caption: Optional caption for the file.

    Returns:
        Dictionary with 'body' (caption) and 'media_url' for Wappi API.
    """
    return {
        "body": caption,
        "media_url": file_url,
    }


def media_message(media_url: str, caption: str = "") -> dict[str, str]:
    """Generate media message template (image, video, audio).

    Args:
        media_url: URL of media file (image, video, audio).
        caption: Optional caption for the media.

    Returns:
        Dictionary with 'body' (caption) and 'media_url' for Wappi API.
    """
    return {
        "body": caption,
        "media_url": media_url,
    }
