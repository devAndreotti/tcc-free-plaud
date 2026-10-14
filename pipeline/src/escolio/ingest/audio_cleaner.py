"""Conservative, traceable cleaning; timestamps and raw words are immutable."""

import re

from escolio.providers.audio_models import TranscriptSegment

SPECIAL_TOKENS = re.compile(r"<\|[^<>]*\|>")
HESITATION = re.compile(r"(?i)(?<!\w)(?:uh+|uhm+|umm+|humm+)(?!\w)[,;]?")


def clean_segment(segment: TranscriptSegment) -> TranscriptSegment:
    text = segment.raw_text
    reasons: list[str] = []
    stripped = SPECIAL_TOKENS.sub("", text)
    if stripped != text:
        reasons.append("special_tokens")
    cleaned = HESITATION.sub("", stripped)
    if cleaned != stripped:
        reasons.append("isolated_hesitation")
    # Text alone is never evidence that real speech is a hallucination.
    if (
        segment.no_speech_probability is not None
        and segment.no_speech_probability >= 0.6
        and segment.average_log_probability is not None
        and segment.average_log_probability <= -1.0
    ):
        cleaned = ""
        reasons.append("low_confidence_non_speech")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    return segment.model_copy(update={"text": cleaned, "cleaning": reasons})
