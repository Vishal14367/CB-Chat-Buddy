"""
WEBVTT transcript parser with timestamp-preserving chunking.
Parses VTT format into structured cues, then groups them into
45-60 second chunks for vector embedding.
"""

import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class WebVTTCue:
    """A single subtitle cue with timing and text."""
    start_seconds: float
    end_seconds: float
    text: str


@dataclass
class TranscriptChunk:
    """A chunk of transcript text spanning ~45-60 seconds."""
    text: str
    timestamp_start: str      # "00:02:15"
    timestamp_end: str        # "00:03:02"
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    chunk_index: int


def parse_timestamp(ts: str) -> float:
    """Convert VTT timestamp to seconds.

    Handles both "HH:MM:SS.mmm" and "MM:SS.mmm" formats.
    """
    parts = ts.strip().split(':')
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return 0.0


def format_timestamp(seconds: float) -> str:
    """Convert seconds to "HH:MM:SS" format."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_webvtt(raw_text: str) -> List[WebVTTCue]:
    """Parse WEBVTT text into a list of cues with timing info.

    Handles standard VTT format:
        WEBVTT

        1
        00:00:00.400 --> 00:00:03.700
        You might be wondering what kind of career benefit

        2
        00:00:03.700 --> 00:00:06.400
        you can get by learning Excel
    """
    if not raw_text or not raw_text.strip():
        return []

    cues = []

    # Match timestamp lines and capture the text that follows
    # Pattern: start --> end (with optional cue settings after the end timestamp)
    pattern = re.compile(
        r'(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})[^\n]*\n((?:(?!\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}\s*-->).+\n?)*)',
        re.MULTILINE
    )

    for match in pattern.finditer(raw_text):
        start_ts = match.group(1).replace(',', '.')
        end_ts = match.group(2).replace(',', '.')
        text_block = match.group(3).strip()

        # Clean up the text: remove HTML tags, collapse whitespace
        text_block = re.sub(r'<[^>]+>', '', text_block)
        text_block = re.sub(r'\s+', ' ', text_block).strip()

        if text_block:
            cues.append(WebVTTCue(
                start_seconds=parse_timestamp(start_ts),
                end_seconds=parse_timestamp(end_ts),
                text=text_block
            ))

    return cues


def _is_sentence_boundary(text: str) -> bool:
    """Check if text ends at a sentence boundary."""
    text = text.rstrip()
    return bool(text) and text[-1] in '.!?'


def chunk_cues_by_time(
    cues: List[WebVTTCue],
    window_seconds: int = 50
) -> List[TranscriptChunk]:
    """Group consecutive cues into ~45-60 second chunks.

    The window targets `window_seconds` (default 50, midpoint of 45-60)
    but extends to the nearest sentence boundary to avoid cutting mid-thought.
    Maximum extension is 15 seconds beyond the window to prevent overly long chunks.

    Args:
        cues: List of parsed VTT cues
        window_seconds: Target chunk duration in seconds (default 50)

    Returns:
        List of TranscriptChunk objects with timing metadata
    """
    if not cues:
        return []

    chunks = []
    chunk_index = 0
    i = 0

    while i < len(cues):
        # Start a new chunk
        chunk_start = cues[i].start_seconds
        chunk_texts = []
        chunk_end = chunk_start

        # Collect cues within the time window
        while i < len(cues):
            cue = cues[i]
            elapsed = cue.end_seconds - chunk_start

            # If we're within the window, always include
            if elapsed <= window_seconds:
                chunk_texts.append(cue.text)
                chunk_end = cue.end_seconds
                i += 1
                continue

            # We've exceeded the window. Check if last cue ended at sentence boundary.
            if chunk_texts and _is_sentence_boundary(chunk_texts[-1]):
                break

            # Not at sentence boundary — extend up to 15 seconds max
            if elapsed <= window_seconds + 15:
                chunk_texts.append(cue.text)
                chunk_end = cue.end_seconds
                i += 1

                # Check if this cue ends at a sentence boundary
                if _is_sentence_boundary(cue.text):
                    break
                continue

            # Hard cap reached, stop here regardless
            break

        # Build the chunk if we collected any text
        if chunk_texts:
            combined_text = ' '.join(chunk_texts)
            chunks.append(TranscriptChunk(
                text=combined_text,
                timestamp_start=format_timestamp(chunk_start),
                timestamp_end=format_timestamp(chunk_end),
                start_seconds=chunk_start,
                end_seconds=chunk_end,
                duration_seconds=round(chunk_end - chunk_start, 1),
                chunk_index=chunk_index
            ))
            chunk_index += 1

    return chunks


def parse_and_chunk_transcript(
    raw_vtt: str,
    window_seconds: int = 50
) -> List[TranscriptChunk]:
    """Convenience function: parse VTT and chunk in one call."""
    cues = parse_webvtt(raw_vtt)
    return chunk_cues_by_time(cues, window_seconds)
