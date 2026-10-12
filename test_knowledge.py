from __future__ import annotations

import pytest

from app.errors import ValidationAppError
from app.schemas import SearchHit
from app.services.knowledge import (
    _frontmatter,
    _plain_text,
    _validate_public_url,
    _has_query_overlap,
    query_anchors,
    relevant_excerpt,
    citations_for,
    context_for,
    split_chunks,
    answer_uses_supported_quotes,
    validate_answer_citations,
)


def test_split_chunks_overlap_without_losing_coverage() -> None:
    chunks = split_chunks("one two three four five six", words_per_chunk=4, overlap=1)

    assert chunks == ["one two three four", "four five six"]


def test_context_for_keeps_relevant_text_after_citation_preview_and_honors_limit() -> None:
    hit = SearchHit(
        chunk_id="chunk-1",
        doc_id="doc-1",
        title="Transcript",
        url="https://example.org/transcript",
        source="lenny-podcast",
        score=1.0,
        content=f"{'x' * 550}The target-market mismatch is the red flag.",
    )

    context = context_for([hit], max_chars=700)

    assert "The target-market mismatch is the red flag." in context
    assert len(context) <= 700
    assert "The target-market mismatch is the red flag." in citations_for([hit])[0].snippet


def test_transcript_frontmatter_is_removed_and_preserved_for_source_metadata() -> None:
    metadata, body = _frontmatter(
        "---\ntitle: Finding product-market fit\nguest: Casey Smith\n"
        "youtube_url: https://youtube.com/watch?v=abc\npublish_date: 2024-01-05\n---\n"
        "Casey explains how teams test demand. (00:12:34)"
    )

    assert metadata == {
        "title": "Finding product-market fit",
        "guest": "Casey Smith",
        "youtube_url": "https://youtube.com/watch?v=abc",
        "publish_date": "2024-01-05",
    }
    assert "title:" not in _plain_text(body)
    assert "Casey explains how teams test demand." in _plain_text(body)


def test_answer_citations_keep_only_used_sources_and_remove_invalid_references() -> None:
    hits = [
        SearchHit(
            chunk_id=f"chunk-{index}",
            doc_id="doc-1",
            title=f"Episode {index}",
            url="https://example.org/transcript",
            source="lenny-podcast",
            score=0.9,
            content=f"Evidence {index}",
        )
        for index in (1, 2, 3)
    ]

    answer, citations, invalid = validate_answer_citations(
        "This is supported [1]. A second claim is unsupported [9].",
        citations_for(hits),
    )

    assert [citation.index for citation in citations] == [1]
    assert invalid == [9]
    answer_body, citation_note = answer.split("\n\nCitation note:", maxsplit=1)
    assert "[9]" not in answer_body
    assert "Removed unsupported citation reference(s) [9]" in citation_note


def test_answer_claims_must_quote_their_cited_transcript_excerpt() -> None:
    hit = SearchHit(
        chunk_id="chunk-1",
        doc_id="doc-1",
        title="Finding product-market fit",
        url="https://example.org/transcript",
        source="lenny-podcast",
        score=0.9,
        content="The TAM and product-market fit are not using the same definition.",
    )
    citations = citations_for([hit])

    assert answer_uses_supported_quotes(
        "Direct answer:\n> The TAM and product-market fit are not using the same definition. [1]",
        citations,
    )
    assert not answer_uses_supported_quotes(
        "Direct answer:\n> Track retention and referrals to measure product-market fit. [1]",
        citations,
    )


def test_query_relevance_filter_rejects_off_topic_chunks() -> None:
    assert _has_query_overlap(
        "What do the guests say about finding product-market fit?",
        "The TAM and product market fit are not using the same definition.",
    )
    assert not _has_query_overlap(
        "What do the guests say about finding product-market fit?",
        "Podcasting existed for a long time and now feels scalable as an emerging channel.",
    )
    assert query_anchors("Can you make that more concrete?") == {"concrete"}
    excerpt = relevant_excerpt(
        "What do the guests say about finding product-market fit?",
        "Emerging channels include things that have existed for a long time. "
        "The TAM and product-market fit are not using the same definition. "
        "This is a red flag for companies.",
    )
    assert excerpt == (
        "Emerging channels include things that have existed for a long time. "
        "The TAM and product-market fit are not using the same definition. "
        "This is a red flag for companies."
    )


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1/data", "http://10.1.2.3/", "file:///etc/passwd", "http://user:pass@example.com"],
)
def test_transcript_url_rejects_private_and_non_http_targets(url: str) -> None:
    with pytest.raises(ValidationAppError):
        _validate_public_url(url)
