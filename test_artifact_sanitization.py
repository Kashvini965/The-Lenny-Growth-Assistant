from __future__ import annotations

from app.services.artifacts import sanitize_html


def test_preview_sanitizes_active_html_and_includes_strict_csp() -> None:
    preview = sanitize_html(
        '<h1 onclick="alert(1)">Hello</h1><script>alert(1)</script>'
        '<a href="javascript:alert(1)">bad link</a>'
        '<img src="https://example.com/pixel.png"><style>@import url(https://example.com/x);'
        "h1 { color: red; } @media screen and (max-width: 640px) { h1 { color: blue; } }</style>",
        "artifact-id",
        "Title",
    )

    assert "<h1>Hello</h1>" in preview.html
    assert "<script" not in preview.html.lower()
    assert "onclick" not in preview.html.lower()
    assert "javascript:" not in preview.html.lower()
    assert "https://example.com/pixel.png" not in preview.html
    assert "@import" not in preview.html.lower()
    assert "@media screen and (max-width: 640px)" in preview.html
    assert "style-src 'unsafe-inline'" in preview.csp
    assert preview.sandbox == ""
