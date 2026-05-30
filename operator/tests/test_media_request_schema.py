from __future__ import annotations

import pytest

from mediafactory.media_request_schema import MediaRequest, normalize_media_request


def test_normalize_media_request_from_dict_with_defaults() -> None:
    result = normalize_media_request(
        {
            "intent": "create_video",
            "topic": "AI tool that saves time",
        }
    )

    assert result == MediaRequest(
        intent="create_video",
        topic="AI tool that saves time",
        platform="tiktok",
        format="short",
        goal="awareness",
        budget_mode="free",
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Tik Tok", "tiktok"),
        ("reels", "instagram"),
        ("YouTube Shorts", "youtube"),
    ],
)
def test_normalize_media_request_normalizes_platform_aliases(
    value: str, expected: str
) -> None:
    result = normalize_media_request(
        {
            "intent": "create_video",
            "topic": "office gadget",
            "platform": value,
        }
    )

    assert result.platform == expected


def test_normalize_media_request_rejects_blank_topic() -> None:
    with pytest.raises(ValueError, match="topic"):
        normalize_media_request(
            {
                "intent": "create_video",
                "topic": "   ",
            }
        )
