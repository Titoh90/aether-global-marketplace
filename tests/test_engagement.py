#!/usr/bin/env python3
"""
test_engagement.py — Tests for core/engagement/

Coverage:
- Schemas: frozen dataclasses, INTENT_TYPES, immutability
- Comment listener: normalization, validation, batch processing
- Intent classifier: dispatch classification, local fallback, spam detection
- Response generator: dispatch generation, template fallback, empty/spam handling
- Tone guard: price check, sentence count, robotic language, affiliate reference, URLs
- Engagement executor: full pipeline, error resilience, batch processing
- Memory logger: persist calls, revenue signals
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_IMPERIO_ROOT = Path(__file__).parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))


# ═══════════════════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class TestSchemas:
    def test_comment_event_frozen(self):
        from core.engagement.schemas import CommentEvent
        event = CommentEvent(
            post_id="p1", comment_text="hello", platform="instagram",
            username="@user", timestamp="2026-05-27T00:00:00Z",
        )
        with pytest.raises((AttributeError, TypeError)):
            event.comment_text = "mutated"

    def test_intent_result_frozen(self):
        from core.engagement.schemas import IntentResult
        result = IntentResult(intent="curiosity", confidence=0.8, reasoning="test")
        with pytest.raises((AttributeError, TypeError)):
            result.intent = "spam"

    def test_response_result_frozen(self):
        from core.engagement.schemas import ResponseResult
        result = ResponseResult(response_text="hola", passed_tone_check=True)
        with pytest.raises((AttributeError, TypeError)):
            result.passed_tone_check = False

    def test_engagement_record_frozen(self):
        from core.engagement.schemas import CommentEvent, IntentResult, ResponseResult, EngagementRecord
        event = CommentEvent(post_id="p1", comment_text="hola", platform="ig", username="@u", timestamp="ts")
        intent = IntentResult(intent="curiosity", confidence=0.5, reasoning="r")
        resp = ResponseResult(response_text="hey", passed_tone_check=True)
        record = EngagementRecord(comment=event, intent=intent, response=resp, posted_at="ts")
        with pytest.raises((AttributeError, TypeError)):
            record.comment = event

    def test_intent_types_frozenset(self):
        from core.engagement.schemas import INTENT_TYPES
        assert isinstance(INTENT_TYPES, frozenset)

    def test_intent_types_contains_all_expected(self):
        from core.engagement.schemas import INTENT_TYPES
        expected = {"price_inquiry", "purchase_intent", "curiosity", "comparison_request",
                     "complaint", "spam", "support_request"}
        assert INTENT_TYPES == expected

    def test_engagement_record_to_dict(self):
        from core.engagement.schemas import CommentEvent, IntentResult, ResponseResult, EngagementRecord
        event = CommentEvent(post_id="p1", comment_text="hola", platform="instagram", username="@u", timestamp="ts")
        intent = IntentResult(intent="curiosity", confidence=0.8, reasoning="why")
        resp = ResponseResult(response_text="hey", passed_tone_check=True)
        record = EngagementRecord(comment=event, intent=intent, response=resp, posted_at="now", post_id=event.post_id, platform=event.platform)
        d = record.to_dict()
        assert isinstance(d, dict)
        assert d["post_id"] == "p1"
        assert d["platform"] == "instagram"
        assert d["comment"]["post_id"] == "p1"  # also nested in comment


# ═══════════════════════════════════════════════════════════════════════════════
# Comment Listener
# ═══════════════════════════════════════════════════════════════════════════════

class TestCommentListener:
    def test_listen_valid_comment(self):
        from core.engagement.comment_listener import listen
        from core.engagement.schemas import CommentEvent
        event = listen({
            "post_id": "post-123",
            "comment_text": "¿Cuánto cuesta?",
            "platform": "Instagram",
            "username": "@buyer",
        })
        assert isinstance(event, CommentEvent)
        assert event.post_id == "post-123"
        assert event.comment_text == "¿Cuánto cuesta?"
        assert event.platform == "instagram"  # normalized
        assert event.username == "@buyer"
        assert event.comment_id != ""  # auto-generated

    def test_listen_missing_fields_returns_empty_event(self):
        from core.engagement.comment_listener import listen
        event = listen({"platform": "tiktok"})  # missing post_id, comment_text
        assert event.comment_text == ""
        assert event.post_id == ""

    def test_listen_empty_comment_text_returns_empty(self):
        from core.engagement.comment_listener import listen
        event = listen({"post_id": "p1", "comment_text": "   ", "platform": "instagram"})
        assert event.comment_text == ""
        assert event.post_id == ""

    def test_listen_platform_normalization(self):
        from core.engagement.comment_listener import listen
        # Test various platform aliases
        for raw, expected in [
            ("ig", "instagram"),
            ("IG", "instagram"),
            ("tiktok", "tiktok"),
            ("TK", "tiktok"),
            ("twitter", "twitter"),
            ("x", "twitter"),
            ("pin", "pinterest"),
            ("pinterest", "pinterest"),
            ("youtube", "youtube"),
            ("fb", "facebook"),
        ]:
            event = listen({"post_id": "p", "comment_text": "hi", "platform": raw})
            assert event.platform == expected, f"{raw} → {event.platform} (expected {expected})"

    def test_listen_unknown_platform_passthrough(self):
        from core.engagement.comment_listener import listen
        event = listen({"post_id": "p", "comment_text": "hi", "platform": "snapchat"})
        assert event.platform == "snapchat"

    def test_listen_has_affiliate_link(self):
        from core.engagement.comment_listener import listen
        event = listen({
            "post_id": "p", "comment_text": "hi", "platform": "instagram",
            "has_affiliate_link": True,
        })
        assert event.has_affiliate_link is True

    def test_batch_listen(self):
        from core.engagement.comment_listener import batch_listen
        comments = [
            {"post_id": "p1", "comment_text": "a", "platform": "ig"},
            {"post_id": "p2", "comment_text": "b", "platform": "tiktok"},
            {"post_id": "p3", "comment_text": "c", "platform": "twitter"},
        ]
        events = batch_listen(comments)
        assert len(events) == 3
        assert events[0].post_id == "p1"
        assert events[2].platform == "twitter"

    def test_comment_id_is_deterministic(self):
        from core.engagement.comment_listener import listen
        c1 = listen({"post_id": "p1", "comment_text": "hi", "platform": "ig", "username": "@a"})
        c2 = listen({"post_id": "p1", "comment_text": "hi", "platform": "ig", "username": "@a"})
        assert c1.comment_id == c2.comment_id


# ═══════════════════════════════════════════════════════════════════════════════
# Intent Classifier
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntentClassifier:
    def test_empty_comment_is_spam(self):
        from core.engagement.intent_classifier import classify_intent
        from core.engagement.schemas import CommentEvent
        event = CommentEvent(post_id="p", comment_text="", platform="ig", username="@u", timestamp="ts")
        result = classify_intent(event)
        assert result.intent == "spam"
        assert result.is_actionable is False

    def test_local_classify_spam_keywords(self):
        from core.engagement.intent_classifier import classify_intent
        from core.engagement.schemas import CommentEvent
        event = CommentEvent(post_id="p", comment_text="Sígueme para más contenido 🎁", platform="ig", username="@u", timestamp="ts")
        with patch("core.engagement.intent_classifier._dispatch_classify", side_effect=Exception("fail")):
            result = classify_intent(event)
        assert result.intent == "spam"
        assert result.is_actionable is False

    def test_local_classify_price_inquiry(self):
        from core.engagement.intent_classifier import classify_intent
        from core.engagement.schemas import CommentEvent
        event = CommentEvent(post_id="p", comment_text="Cuánto cuesta este producto?", platform="ig", username="@u", timestamp="ts")
        with patch("core.engagement.intent_classifier._dispatch_classify", side_effect=Exception("fail")):
            result = classify_intent(event)
        assert result.intent == "price_inquiry"

    def test_local_classify_purchase_intent(self):
        from core.engagement.intent_classifier import classify_intent
        from core.engagement.schemas import CommentEvent
        event = CommentEvent(post_id="p", comment_text="Quiero comprarlo ya mismo", platform="tiktok", username="@u", timestamp="ts")
        with patch("core.engagement.intent_classifier._dispatch_classify", side_effect=Exception("fail")):
            result = classify_intent(event)
        assert result.intent == "purchase_intent"

    def test_local_classify_complaint(self):
        from core.engagement.intent_classifier import classify_intent
        from core.engagement.schemas import CommentEvent
        event = CommentEvent(post_id="p", comment_text="Esto es una estafa, no funciona", platform="ig", username="@u", timestamp="ts")
        with patch("core.engagement.intent_classifier._dispatch_classify", side_effect=Exception("fail")):
            result = classify_intent(event)
        assert result.intent == "complaint"

    def test_local_classify_curiosity_default(self):
        from core.engagement.intent_classifier import classify_intent
        from core.engagement.schemas import CommentEvent
        event = CommentEvent(post_id="p", comment_text="ok interesante...", platform="ig", username="@u", timestamp="ts")
        with patch("core.engagement.intent_classifier._dispatch_classify", side_effect=Exception("fail")):
            result = classify_intent(event)
        assert result.intent in ("curiosity",)  # weak signal → defaults to curiosity

    def test_never_raises(self):
        from core.engagement.intent_classifier import classify_intent
        from core.engagement.schemas import CommentEvent
        event = CommentEvent(post_id="p", comment_text="test", platform="ig", username="@u", timestamp="ts")
        with patch("core.engagement.intent_classifier._dispatch_classify", side_effect=RuntimeError("boom")):
            result = classify_intent(event)
        assert result is not None
        assert result.intent in ("curiosity",)


# ═══════════════════════════════════════════════════════════════════════════════
# Response Generator
# ═══════════════════════════════════════════════════════════════════════════════

class TestResponseGenerator:
    def test_spam_intent_returns_empty_response(self):
        from core.engagement.response_generator import generate_response
        from core.engagement.schemas import CommentEvent, IntentResult
        event = CommentEvent(post_id="p", comment_text="sígueme", platform="ig", username="@u", timestamp="ts")
        intent = IntentResult(intent="spam", confidence=1.0, reasoning="spam", is_actionable=False)
        result = generate_response(event, intent)
        assert result.response_text == ""
        assert result.was_generated is False

    def test_empty_comment_returns_empty(self):
        from core.engagement.response_generator import generate_response
        from core.engagement.schemas import CommentEvent, IntentResult
        event = CommentEvent(post_id="p", comment_text="a", platform="ig", username="@u", timestamp="ts")
        intent = IntentResult(intent="curiosity", confidence=0.5, reasoning="test")
        result = generate_response(event, intent)
        # very short comment (< 2 chars after strip) → empty
        assert result.response_text == ""
        assert result.was_generated is False

    def test_fallback_template_price_inquiry(self):
        from core.engagement.response_generator import generate_response
        from core.engagement.schemas import CommentEvent, IntentResult
        event = CommentEvent(post_id="p", comment_text="cuánto cuesta?", platform="ig", username="@u", timestamp="ts")
        intent = IntentResult(intent="price_inquiry", confidence=0.9, reasoning="test")
        with patch("core.engagement.response_generator._dispatch_generate", side_effect=Exception("fail")):
            result = generate_response(event, intent)
        assert len(result.response_text) > 5
        assert "precio" in result.response_text.lower() or "link" in result.response_text.lower()

    def test_fallback_template_purchase_intent(self):
        from core.engagement.response_generator import generate_response
        from core.engagement.schemas import CommentEvent, IntentResult
        event = CommentEvent(post_id="p", comment_text="lo quiero comprar", platform="ig", username="@u", timestamp="ts")
        intent = IntentResult(intent="purchase_intent", confidence=0.9, reasoning="test")
        with patch("core.engagement.response_generator._dispatch_generate", side_effect=Exception("fail")):
            result = generate_response(event, intent)
        assert len(result.response_text) > 5

    def test_fallback_template_complaint(self):
        from core.engagement.response_generator import generate_response
        from core.engagement.schemas import CommentEvent, IntentResult
        event = CommentEvent(post_id="p", comment_text="mal producto", platform="ig", username="@u", timestamp="ts")
        intent = IntentResult(intent="complaint", confidence=0.9, reasoning="test")
        with patch("core.engagement.response_generator._dispatch_generate", side_effect=Exception("fail")):
            result = generate_response(event, intent)
        assert len(result.response_text) > 5

    def test_never_raises(self):
        from core.engagement.response_generator import generate_response
        from core.engagement.schemas import CommentEvent, IntentResult
        event = CommentEvent(post_id="p", comment_text="test", platform="ig", username="@u", timestamp="ts")
        intent = IntentResult(intent="reasoning", confidence=0.5, reasoning="test")
        with patch("core.engagement.response_generator._dispatch_generate", side_effect=RuntimeError("boom")):
            result = generate_response(event, intent)
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Tone Guard
# ═══════════════════════════════════════════════════════════════════════════════

class TestToneGuard:
    def test_empty_response_passes(self):
        from core.engagement.tone_guard import validate
        result = validate("", "curiosity")
        assert result.passed_tone_check is True

    def test_good_response_passes(self):
        from core.engagement.tone_guard import validate
        result = validate("¡Me alegra que te guste! Es un gran producto 🙌", "curiosity")
        assert result.passed_tone_check is True
        assert len(result.tone_issues) == 0

    def test_robotic_phrase_blocked(self):
        from core.engagement.tone_guard import validate
        result = validate("Certainly! I would be happy to help you with that.", "curiosity")
        assert result.passed_tone_check is False
        assert len(result.tone_issues) > 0

    def test_price_invention_blocked(self):
        from core.engagement.tone_guard import validate
        result = validate("Cuesta $29.99 en Amazon", "price_inquiry")
        assert result.passed_tone_check is False
        assert any("price" in issue.lower() for issue in result.tone_issues)

    def test_direct_url_blocked(self):
        from core.engagement.tone_guard import validate
        result = validate("Cómpralo aquí: https://amazon.com/dp/B00TEST", "purchase_intent")
        assert result.passed_tone_check is False
        assert any("url" in issue.lower() or "link" in issue.lower() for issue in result.tone_issues)

    def test_too_many_sentences_blocked(self):
        from core.engagement.tone_guard import validate
        result = validate(
            "Hola. Es un gran producto. Te va a encantar. Tiene muchas funciones. Cómpralo ya. Es perfecto.",
            "curiosity"
        )
        assert result.passed_tone_check is False

    def test_missing_affiliate_reference_for_purchase(self):
        from core.engagement.tone_guard import validate
        result = validate(
            "¡Qué bueno que te interesa!",
            "purchase_intent",
            has_affiliate_link=True,
        )
        assert result.passed_tone_check is False
        assert any("affiliate" in issue.lower() for issue in result.tone_issues)

    def test_affiliate_reference_present_passes(self):
        from core.engagement.tone_guard import validate
        result = validate(
            "¡Qué bueno que te gusta! Lo encuentras en el link de la descripción 👆",
            "purchase_intent",
            has_affiliate_link=True,
        )
        assert result.passed_tone_check is True

    def test_affiliate_not_required_for_curiosity(self):
        from core.engagement.tone_guard import validate
        result = validate(
            "Es un producto genial, la verdad",
            "curiosity",
            has_affiliate_link=True,
        )
        # curiosity doesn't require affiliate reference
        assert result.passed_tone_check is True

    def test_sanitize_strips_quotes(self):
        from core.engagement.tone_guard import sanitize
        assert sanitize('  "hola"  ') == "hola"

    def test_sanitize_collapses_whitespace(self):
        from core.engagement.tone_guard import sanitize
        result = sanitize("hola    mundo   !")
        assert result == "hola mundo !"

    def test_needs_affiliate_flag_set(self):
        from core.engagement.tone_guard import validate
        result = validate(
            "Está en el link de la descripción 👆",
            "purchase_intent",
            has_affiliate_link=True,
        )
        assert result.needs_affiliate is True


# ═══════════════════════════════════════════════════════════════════════════════
# Engagement Executor (integration)
# ═══════════════════════════════════════════════════════════════════════════════

class TestEngagementExecutor:
    def test_process_comment_full_pipeline_integration(self):
        """End-to-end: valid comment → intent → response → tone → record."""
        from core.engagement.engagement_executor import process_comment
        record = process_comment({
            "post_id": "post-xyz",
            "comment_text": "Cuánto cuesta este producto? Se ve increíble",
            "platform": "Instagram",
            "username": "@comprador",
        })
        # Should produce a valid record
        assert record.post_id == "post-xyz"
        assert record.platform == "instagram"
        assert record.comment.comment_text != ""
        assert record.intent.intent != ""
        assert record.response is not None

    def test_process_comment_with_affiliate_link(self):
        from core.engagement.engagement_executor import process_comment
        record = process_comment({
            "post_id": "p1",
            "comment_text": "Lo quiero comprar ahora mismo!",
            "platform": "tiktok",
            "username": "@buyer",
        }, has_affiliate_link=True)
        assert record.comment.has_affiliate_link is True

    def test_process_invalid_comment_returns_record(self):
        from core.engagement.engagement_executor import process_comment
        record = process_comment({"platform": "ig"})  # missing required fields
        assert record is not None
        assert record.comment.comment_text == ""

    def test_process_spam_comment_returns_no_response(self):
        from core.engagement.engagement_executor import process_comment
        record = process_comment({
            "post_id": "p1",
            "comment_text": "Sígueme para más 🎁",
            "platform": "instagram",
            "username": "@spammer",
        })
        assert record.intent.intent in ("spam",) or record.response.response_text == ""

    def test_never_raises(self):
        from core.engagement.engagement_executor import process_comment
        record = process_comment({
            "post_id": "p",
            "comment_text": "test",
            "platform": "weird_platform_xyz",
            "username": "@test",
        })
        assert record is not None

    def test_process_batch(self):
        from core.engagement.engagement_executor import process_batch
        comments = [
            {"post_id": "p1", "comment_text": "cuánto cuesta", "platform": "ig", "username": "@a"},
            {"post_id": "p2", "comment_text": "me encanta!", "platform": "tiktok", "username": "@b"},
            {"post_id": "p3", "comment_text": "sígueme 🎁", "platform": "twitter", "username": "@c"},
        ]
        records = process_batch(comments)
        assert len(records) == 3
        for rec in records:
            assert rec is not None

    def test_process_batch_with_auto_log_false(self):
        from core.engagement.engagement_executor import process_batch
        comments = [
            {"post_id": "p1", "comment_text": "hola", "platform": "ig", "username": "@a"},
        ]
        records = process_batch(comments, auto_log=False)
        assert len(records) == 1

    def test_string_response_in_response_text(self):
        """Response text should always be a string."""
        from core.engagement.engagement_executor import process_comment
        record = process_comment({
            "post_id": "p1",
            "comment_text": "cuánto cuesta?",
            "platform": "instagram",
            "username": "@test",
        })
        assert isinstance(record.response.response_text, str)


# ═══════════════════════════════════════════════════════════════════════════════
# Memory Logger
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryLogger:
    def test_log_engagement_calls_persist(self):
        from core.engagement.memory_logger import log_engagement
        from core.engagement.schemas import CommentEvent, IntentResult, ResponseResult, EngagementRecord
        event = CommentEvent(post_id="p1", comment_text="hola", platform="ig", username="@u", timestamp="ts")
        intent = IntentResult(intent="curiosity", confidence=0.8, reasoning="r")
        resp = ResponseResult(response_text="hey!", passed_tone_check=True)
        record = EngagementRecord(comment=event, intent=intent, response=resp, posted_at="now")

        with patch("core.engagement.memory_logger.persist_learning") as mock_persist:
            log_engagement(record)
            assert mock_persist.called

    def test_log_purchase_intent_triggers_revenue_signal(self):
        from core.engagement.memory_logger import log_engagement
        from core.engagement.schemas import CommentEvent, IntentResult, ResponseResult, EngagementRecord
        event = CommentEvent(post_id="p1", comment_text="lo quiero!", platform="ig", username="@u", timestamp="ts")
        intent = IntentResult(intent="purchase_intent", confidence=0.9, reasoning="r")
        resp = ResponseResult(response_text="link en descripción", passed_tone_check=True)
        record = EngagementRecord(comment=event, intent=intent, response=resp, posted_at="now")

        with patch("core.engagement.memory_logger.persist_learning") as mock_persist:
            log_engagement(record)
            # Should be called twice: once for engagement, once for revenue
            assert mock_persist.call_count >= 2
            revenue_calls = [
                call for call in mock_persist.call_args_list
                if call.kwargs.get("memory_type") == "revenue" or
                   (len(call.args) >= 2 and call.args[1] == "revenue")
            ]
            # Check revenue signal was triggered
            assert len(revenue_calls) >= 1

    def test_log_complaint_no_revenue_signal(self):
        from core.engagement.memory_logger import log_engagement
        from core.engagement.schemas import CommentEvent, IntentResult, ResponseResult, EngagementRecord
        event = CommentEvent(post_id="p1", comment_text="mal producto", platform="ig", username="@u", timestamp="ts")
        intent = IntentResult(intent="complaint", confidence=0.9, reasoning="r")
        resp = ResponseResult(response_text="lo siento, cuéntame más", passed_tone_check=True)
        record = EngagementRecord(comment=event, intent=intent, response=resp, posted_at="now")

        with patch("core.engagement.memory_logger.persist_learning") as mock_persist:
            log_engagement(record)
            revenue_calls = [
                call for call in mock_persist.call_args_list
                if call.kwargs.get("memory_type") == "revenue" or
                   (len(call.args) >= 2 and call.args[1] == "revenue")
            ]
            # complaint should NOT trigger revenue signal
            assert len(revenue_calls) == 0

    def test_log_never_raises(self):
        from core.engagement.memory_logger import log_engagement
        from core.engagement.schemas import CommentEvent, IntentResult, ResponseResult, EngagementRecord
        event = CommentEvent(post_id="p1", comment_text="test", platform="ig", username="@u", timestamp="ts")
        intent = IntentResult(intent="curiosity", confidence=0.5, reasoning="r")
        resp = ResponseResult(response_text="ok", passed_tone_check=True)
        record = EngagementRecord(comment=event, intent=intent, response=resp, posted_at="now")

        with patch("core.engagement.memory_logger.persist_learning", side_effect=RuntimeError("boom")):
            # Should not raise
            try:
                log_engagement(record)
            except RuntimeError:
                pytest.fail("log_engagement raised when it should be non-blocking")

    def test_log_batch(self):
        from core.engagement.memory_logger import log_batch
        from core.engagement.schemas import CommentEvent, IntentResult, ResponseResult, EngagementRecord
        event = CommentEvent(post_id="p1", comment_text="test", platform="ig", username="@u", timestamp="ts")
        intent = IntentResult(intent="curiosity", confidence=0.5, reasoning="r")
        resp = ResponseResult(response_text="ok", passed_tone_check=True)
        records = [
            EngagementRecord(comment=event, intent=intent, response=resp, posted_at="t1"),
            EngagementRecord(comment=event, intent=intent, response=resp, posted_at="t2"),
        ]
        with patch("core.engagement.memory_logger.persist_learning") as mock_persist:
            log_batch(records)
            assert mock_persist.call_count >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: No cross-layer contamination
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsolation:
    def test_engagement_never_imports_flow_operator(self):
        import inspect
        from core.engagement import engagement_executor as ee
        src = inspect.getsource(ee)
        assert "flow_operator" not in src.lower()
        assert "master_pipeline" not in src.lower()

    def test_engagement_never_imports_truth_layer(self):
        import inspect
        from core.engagement import engagement_executor as ee
        src = inspect.getsource(ee)
        assert "visual_truth" not in src.lower()
        assert "truth_layer" not in src.lower()

    def test_engagement_never_imports_dispatch_gate(self):
        import inspect
        from core.engagement import engagement_executor as ee
        src = inspect.getsource(ee)
        assert "dispatch_gate" not in src

    def test_engagement_never_calls_providers_directly(self):
        import inspect
        from core.engagement import engagement_executor as ee
        src = inspect.getsource(ee)
        # Should not contain direct provider calls
        for banned in ["anthropic.", "gemini.", "groq.", "openai."]:
            assert banned not in src, f"Found direct provider call: {banned}"
