"""Tests for TranslationCache, specifically purge_empty() (cache-poisoning repair).

Mock seam: none — uses a real SQLite file under tmp_path (fast, no I/O contention
with the app's real cache).
"""

from __future__ import annotations

import pytest

from app.backend.services.translation_cache import TranslationCache


@pytest.fixture
def cache(tmp_path):
    return TranslationCache(db_path=tmp_path / "test_translations.db")


def test_purge_empty_deletes_only_blank_translations(cache):
    cache.put("hello", "Vietnamese", "en", "panjit/gpt-oss:120b", "")
    cache.put("world", "Vietnamese", "en", "panjit/gpt-oss:120b", "the gian")

    deleted = cache.purge_empty()

    assert deleted == 1
    remaining = cache.get_batch(["hello", "world"], "Vietnamese", "en", "panjit/gpt-oss:120b")
    assert "hello" not in remaining
    assert remaining["world"] == "the gian"


def test_purge_empty_treats_whitespace_only_as_blank(cache):
    cache.put("hello", "Vietnamese", "en", "panjit/gpt-oss:120b", "   ")

    deleted = cache.purge_empty()

    assert deleted == 1


def test_purge_empty_scoped_to_model(cache):
    cache.put("hello", "Vietnamese", "en", "panjit/gpt-oss:120b", "")
    cache.put("hello", "Vietnamese", "en", "ollama/qwen3.5:9b", "")

    deleted = cache.purge_empty(model="panjit/gpt-oss:120b")

    assert deleted == 1
    remaining = cache.get_batch(["hello"], "Vietnamese", "en", "ollama/qwen3.5:9b")
    assert remaining["hello"] == ""


def test_purge_empty_noop_when_no_blank_entries(cache):
    cache.put("hello", "Vietnamese", "en", "panjit/gpt-oss:120b", "xin chao")

    deleted = cache.purge_empty()

    assert deleted == 0
    remaining = cache.get_batch(["hello"], "Vietnamese", "en", "panjit/gpt-oss:120b")
    assert remaining["hello"] == "xin chao"


def test_purged_entry_is_retranslated_on_next_get_batch_miss(cache):
    """Directly demonstrates the bug this fixes: an empty INSERT OR IGNORE
    entry blocks a later good translation from ever being stored, until
    purge_empty() clears it out and makes room for a real cache write."""
    cache.put("hello", "Vietnamese", "en", "panjit/gpt-oss:120b", "")

    # Simulate a later run attempting to write the correct translation —
    # INSERT OR IGNORE means this silently does nothing while the empty
    # entry still exists.
    cache.put("hello", "Vietnamese", "en", "panjit/gpt-oss:120b", "xin chao")
    still_blank = cache.get_batch(["hello"], "Vietnamese", "en", "panjit/gpt-oss:120b")
    assert still_blank["hello"] == "", "INSERT OR IGNORE must not overwrite the poisoned entry"

    cache.purge_empty()
    miss = cache.get_batch(["hello"], "Vietnamese", "en", "panjit/gpt-oss:120b")
    assert "hello" not in miss, "purge_empty() must make the key a cache miss again"

    cache.put("hello", "Vietnamese", "en", "panjit/gpt-oss:120b", "xin chao")
    fixed = cache.get_batch(["hello"], "Vietnamese", "en", "panjit/gpt-oss:120b")
    assert fixed["hello"] == "xin chao"
