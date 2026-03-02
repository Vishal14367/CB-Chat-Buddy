import os
import logging
import pandas as pd
import re
from typing import Dict, List
from collections import defaultdict

from app.config.course_catalog import get_chapter_override

logger = logging.getLogger(__name__)


def _normalize_ch_key(title: str) -> str:
    """Normalize chapter title for matching: lowercase, collapse whitespace,
    and replace common Unicode variants with ASCII equivalents."""
    key = re.sub(r'\s+', ' ', title.lower().strip())
    # Curly single quotes → straight
    key = key.replace('\u2018', "'").replace('\u2019', "'")
    # Curly double quotes → straight
    key = key.replace('\u201c', '"').replace('\u201d', '"')
    # En/em dash → hyphen
    key = key.replace('\u2013', '-').replace('\u2014', '-')
    # Handle Windows-1252 artifacts that survived as latin-1 bytes
    key = key.replace('\x92', "'").replace('\x93', '"').replace('\x94', '"')
    key = key.replace('\x96', '-').replace('\x97', '-')
    return key

def normalize_vtt_transcript(transcript: str) -> str:
    """
    Remove VTT formatting: WEBVTT header, timestamps, cue numbers.
    Keep only readable text and normalize whitespace.
    """
    if not transcript or pd.isna(transcript):
        return ""
    
    # Remove WEBVTT header
    text = re.sub(r'^WEBVTT\s*', '', transcript, flags=re.MULTILINE)
    
    # Remove cue identifiers (standalone numbers or UUIDs)
    text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[a-f0-9\-]+\s*$', '', text, flags=re.MULTILINE)
    
    # Remove timestamps (00:00:00.000 --> 00:00:00.000 format)
    text = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}', '', text)
    
    # Remove cue settings (position, align, etc.)
    text = re.sub(r'\b(position|align|line|size):[^\n]*', '', text)
    
    # Normalize whitespace: collapse multiple spaces, remove extra newlines
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Max 2 newlines
    text = re.sub(r'[ \t]+', ' ', text)  # Collapse spaces
    text = text.strip()
    
    return text


def generate_lecture_id(row: pd.Series) -> str:
    """Generate stable lecture ID from row data."""
    # Use existing id if available
    if 'id' in row and not pd.isna(row['id']):
        return str(int(row['id']))
    
    # Fallback: create slug from titles
    course = str(row.get('course_title', '')).lower().replace(' ', '-')
    chapter = str(row.get('chapter_title', '')).lower().replace(' ', '-')
    lecture = str(row.get('lecture_title', '')).lower().replace(' ', '-')
    return f"{course}_{chapter}_{lecture}"


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug (lowercase, alphanumeric + hyphens only)."""
    slug = text.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)  # remove non-alphanumeric (keep spaces/hyphens)
    slug = re.sub(r'[\s-]+', '-', slug)         # collapse whitespace/hyphens
    slug = slug.strip('-')
    return slug


class CSVDataSource:
    """Loads and parses CSV file containing lecture data."""

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.df = None
        self.lectures_by_id: Dict[str, Dict] = {}
        self.course_structure: Dict[str, Dict] = {}
        self._load_and_parse()
    
    def _load_and_parse(self):
        """Load CSV and build data structures.

        In RAG mode the CSV file may not be present inside the Docker image.
        Rather than crashing on startup, log a warning and leave the data
        structures empty — the RAG pipeline (Qdrant) will serve all requests.
        """
        if not os.path.exists(self.csv_path):
            logger.warning(
                f"CSV file not found at '{self.csv_path}' — "
                "running without CSV data source (expected in RAG mode)."
            )
            return

        # Read CSV
        try:
            self.df = pd.read_csv(self.csv_path, encoding='utf-8-sig')
        except Exception as exc:
            logger.warning(f"Failed to read CSV from '{self.csv_path}': {exc} — continuing without CSV data.")
            return

        # Build lecture lookup and course structure
        # Use a normalized (lowercased) chapter key to merge case-variant duplicates
        courses = defaultdict(dict)  # course -> {ch_key -> [lectures]}

        # Track per-course sequential ordering (0-based)
        course_counters = defaultdict(int)

        # Track the earliest row/module_id per chapter for correct chapter ordering
        chapter_first_key = defaultdict(lambda: defaultdict(lambda: float('inf')))

        # Map normalized chapter key -> first-seen display title
        chapter_display_title: Dict[str, Dict[str, str]] = defaultdict(dict)

        # Track seen lectures per course by (title, duration) to catch cross-chapter duplicates
        # that share the same content but have different DB IDs
        seen_lectures: Dict[str, set] = defaultdict(set)

        for idx, row in self.df.iterrows():
            # Generate lecture ID
            lecture_id = generate_lecture_id(row)

            # Normalize transcript
            raw_transcript = row.get('transcript', '')
            normalized_transcript = normalize_vtt_transcript(raw_transcript)

            course_title = row.get('course_title', 'Unknown Course')
            chapter_title = str(row.get('chapter_title', 'Unknown Chapter')).strip()

            # Normalize chapter key for case/whitespace/unicode-insensitive merge
            ch_key = _normalize_ch_key(chapter_title)

            # Track chapter ordering using CSV row index (which preserves the
            # intended teaching sequence). module_id is an internal DB key and
            # does not reliably reflect chapter order.
            if idx < chapter_first_key[course_title][ch_key]:
                chapter_first_key[course_title][ch_key] = idx

            # Keep first-seen casing as display title
            if ch_key not in chapter_display_title[course_title]:
                chapter_display_title[course_title][ch_key] = chapter_title

            # Deduplicate: skip if a lecture with the same title+duration already
            # exists in this course (catches content re-added under different chapter
            # names or IDs, e.g. Python "JSON & APIs" vs "JSON, Generators" + "APIs")
            lecture_title_val = str(row.get('lecture_title', ''))
            duration_val = row['duration'] if 'duration' in row and not pd.isna(row.get('duration')) else None
            dedup_key = f"{lecture_title_val}|{duration_val}"
            if dedup_key in seen_lectures[course_title]:
                continue
            seen_lectures[course_title].add(dedup_key)

            # Per-course sequential order
            per_course_order = course_counters[course_title]
            course_counters[course_title] += 1

            # Store lecture data (use display title for the chapter)
            display_ch = chapter_display_title[course_title][ch_key]
            lecture_data = {
                'lecture_id': lecture_id,
                'lecture_title': row.get('lecture_title', ''),
                'course_title': course_title,
                'chapter_title': display_ch,
                'transcript': normalized_transcript,
                'thumbnail_url': row.get('player_embed_url', ''),
                'duration': int(row['duration']) if 'duration' in row and not pd.isna(row['duration']) else None,
                'lecture_order': per_course_order
            }

            self.lectures_by_id[lecture_id] = lecture_data

            if ch_key not in courses[course_title]:
                courses[course_title][ch_key] = []

            courses[course_title][ch_key].append({
                'lecture_id': lecture_id,
                'lecture_title': row.get('lecture_title', ''),
                'thumbnail_url': row.get('player_embed_url', ''),
                'duration': lecture_data['duration'],
                'lecture_order': per_course_order
            })

        # Convert to final structure with chapters sorted correctly
        self.course_structure = {}
        for course_title, chapters in courses.items():
            course_id = slugify(course_title)

            # Check for chapter override (fixes bundled/mis-ordered content)
            chapter_override = get_chapter_override(course_title)

            if chapter_override:
                # Use override: only include listed chapters, in specified order
                override_keys = [_normalize_ch_key(ch) for ch in chapter_override]
                sorted_ch_keys = [
                    ch_key for ch_key in override_keys
                    if ch_key in chapters and len(chapters[ch_key]) > 0
                ]
            else:
                # Default: sort by earliest row index
                sorted_ch_keys = sorted(
                    [ch for ch in chapters.keys() if len(chapters[ch]) > 0],
                    key=lambda ch: chapter_first_key[course_title][ch]
                )

            # Re-number lecture_order sequentially after filtering
            if chapter_override:
                new_order = 0
                for ch_key in sorted_ch_keys:
                    for lec in sorted(chapters[ch_key], key=lambda x: x['lecture_order']):
                        lec['lecture_order'] = new_order
                        # Also update the global lectures_by_id
                        if lec['lecture_id'] in self.lectures_by_id:
                            self.lectures_by_id[lec['lecture_id']]['lecture_order'] = new_order
                        new_order += 1
                # Remove lectures from excluded chapters from lectures_by_id
                included_ids = set()
                for ch_key in sorted_ch_keys:
                    for lec in chapters[ch_key]:
                        included_ids.add(lec['lecture_id'])
                excluded_ch_keys = set(chapters.keys()) - set(sorted_ch_keys)
                for ch_key in excluded_ch_keys:
                    for lec in chapters[ch_key]:
                        self.lectures_by_id.pop(lec['lecture_id'], None)

            self.course_structure[course_id] = {
                'course_id': course_id,
                'course_title': course_title,
                'chapters': [
                    {
                        'chapter_title': chapter_display_title[course_title][ch_key],
                        'lectures': sorted(chapters[ch_key], key=lambda x: x['lecture_order'])
                    }
                    for ch_key in sorted_ch_keys
                ]
            }
    
    def get_all_courses(self) -> List[Dict]:
        """Return list of all courses with chapter and lecture counts."""
        return [
            {
                'course_id': course_id,
                'course_title': data['course_title'],
                'chapter_count': len(data['chapters']),
                'lecture_count': sum(len(ch['lectures']) for ch in data['chapters'])
            }
            for course_id, data in self.course_structure.items()
        ]
    
    def get_course_detail(self, course_id: str) -> Dict:
        """Return course with chapters and lectures."""
        return self.course_structure.get(course_id)
    
    def get_lecture_detail(self, lecture_id: str) -> Dict:
        """Return lecture metadata + transcript."""
        return self.lectures_by_id.get(lecture_id)
