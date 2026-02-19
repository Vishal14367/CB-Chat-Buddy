import pandas as pd
import re
from typing import Dict, List
from collections import defaultdict

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


class CSVDataSource:
    """Loads and parses CSV file containing lecture data."""
    
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.df = None
        self.lectures_by_id: Dict[str, Dict] = {}
        self.course_structure: Dict[str, Dict] = {}
        self._load_and_parse()
    
    def _load_and_parse(self):
        """Load CSV and build data structures."""
        # Read CSV
        self.df = pd.read_csv(self.csv_path, encoding='utf-8-sig')

        # Build lecture lookup and course structure
        courses = defaultdict(lambda: defaultdict(list))

        # Track per-course sequential ordering (0-based)
        course_counters = defaultdict(int)

        for idx, row in self.df.iterrows():
            # Generate lecture ID
            lecture_id = generate_lecture_id(row)

            # Normalize transcript
            raw_transcript = row.get('transcript', '')
            normalized_transcript = normalize_vtt_transcript(raw_transcript)

            course_title = row.get('course_title', 'Unknown Course')
            chapter_title = row.get('chapter_title', 'Unknown Chapter')

            # Per-course sequential order
            per_course_order = course_counters[course_title]
            course_counters[course_title] += 1

            # Store lecture data
            lecture_data = {
                'lecture_id': lecture_id,
                'lecture_title': row.get('lecture_title', ''),
                'course_title': course_title,
                'chapter_title': chapter_title,
                'transcript': normalized_transcript,
                'thumbnail_url': row.get('player_embed_url', ''),
                'duration': int(row['duration']) if 'duration' in row and not pd.isna(row['duration']) else None,
                'lecture_order': per_course_order
            }

            self.lectures_by_id[lecture_id] = lecture_data

            courses[course_title][chapter_title].append({
                'lecture_id': lecture_id,
                'lecture_title': row.get('lecture_title', ''),
                'thumbnail_url': row.get('player_embed_url', ''),
                'duration': lecture_data['duration'],
                'lecture_order': per_course_order
            })
        
        # Convert to final structure
        self.course_structure = {}
        for course_title, chapters in courses.items():
            course_id = course_title.lower().replace(' ', '-')
            self.course_structure[course_id] = {
                'course_id': course_id,
                'course_title': course_title,
                'chapters': [
                    {
                        'chapter_title': chapter_title,
                        'lectures': sorted(lectures, key=lambda x: x['lecture_order'])
                    }
                    for chapter_title, lectures in chapters.items()
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
