"""Structured memory write contract tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.memory_write import (
    ExtractionMethod,
    MemorySubject,
    MemoryWriteExpectation,
    MemoryWriteMode,
    StructuredMemoryRecord,
)


def test_memory_write_enums_define_subject_mode_and_extraction() -> None:
    assert MemorySubject.USER.value == "user"
    assert MemorySubject.ORG.value == "org"
    assert MemoryWriteMode.STRUCTURED.value == "structured"
    assert MemoryWriteMode.INFERRED.value == "inferred"
    assert ExtractionMethod.SLOT_FILL_V1.value == "slot_fill_v1"
    assert ExtractionMethod.STORE_PROFILE.value == "store_profile"
    assert ExtractionMethod.LANGMEM_INFER.value == "langmem_infer"


def test_structured_memory_record_serializes_to_trace_dict() -> None:
    record = StructuredMemoryRecord(
        subject=MemorySubject.USER,
        attribute="name",
        value="张三",
        raw_utterance="我叫张三",
        confidence=0.94,
        source_turn_id="thread-1:turn-3",
        extraction_method=ExtractionMethod.SLOT_FILL_V1.value,
    )

    payload = record.to_trace_dict()

    assert payload == {
        "subject": "user",
        "attribute": "name",
        "value": "张三",
        "raw_utterance": "我叫张三",
        "confidence": 0.94,
        "source_turn_id": "thread-1:turn-3",
        "extraction_method": "slot_fill_v1",
    }


def test_structured_memory_record_rejects_blank_fields() -> None:
    with pytest.raises(ValidationError):
        StructuredMemoryRecord(
            subject=MemorySubject.USER,
            attribute="name",
            value="",
            raw_utterance="我叫张三",
            confidence=0.94,
            source_turn_id="thread-1:turn-3",
        )


def test_structured_memory_record_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValidationError):
        StructuredMemoryRecord(
            subject=MemorySubject.USER,
            attribute="name",
            value="张三",
            raw_utterance="我叫张三",
            confidence=1.5,
            source_turn_id="thread-1:turn-3",
        )


def test_memory_write_expectation_supports_structured_target_state() -> None:
    record = StructuredMemoryRecord(
        subject=MemorySubject.ORG,
        attribute="company.address",
        value="天翔街188号",
        raw_utterance="我公司在天翔街188号",
        confidence=0.94,
        source_turn_id="thread-1:turn-3",
    )
    expectation = MemoryWriteExpectation(
        mode=MemoryWriteMode.STRUCTURED,
        infer=False,
        expected_record=record,
        expected_final_status="stored",
    )

    assert expectation.mode == MemoryWriteMode.STRUCTURED
    assert expectation.infer is False
    assert expectation.expected_record is record
    assert expectation.forbidden_final_status == ()


def test_memory_write_expectation_supports_regression_forbidden_status() -> None:
    expectation = MemoryWriteExpectation(
        mode=MemoryWriteMode.STRUCTURED,
        infer=False,
        forbidden_final_status=("stored_empty",),
    )

    assert "stored_empty" in expectation.forbidden_final_status
