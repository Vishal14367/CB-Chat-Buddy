import re
from typing import List, Tuple
from rank_bm25 import BM25Okapi

def chunk_text(text: str, chunk_size: int = 400) -> List[str]:
    """
    Split text into chunks of approximately chunk_size tokens.
    Uses simple word-based splitting.
    """
    words = text.split()
    chunks = []
    current_chunk = []
    current_size = 0
    
    for word in words:
        current_chunk.append(word)
        current_size += 1
        
        if current_size >= chunk_size:
            chunks.append(' '.join(current_chunk))
            current_chunk = []
            current_size = 0
    
    # Add remaining words
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks


def tokenize(text: str) -> List[str]:
    """Simple tokenizer for BM25."""
    # Lowercase and split on non-alphanumeric
    tokens = re.findall(r'\b\w+\b', text.lower())
    return tokens


class LectureRetriever:
    """
    Retrieves relevant chunks from a SINGLE lecture transcript.
    Uses BM25 scoring with a threshold for not-answerable detection.
    """
    
    def __init__(self, transcript: str, chunk_size: int = 400, threshold: float = 0.1):
        self.transcript = transcript
        self.chunk_size = chunk_size
        self.threshold = threshold
        
        # Chunk the transcript
        self.chunks = chunk_text(transcript, chunk_size)
        
        # Build BM25 index
        tokenized_chunks = [tokenize(chunk) for chunk in self.chunks]
        self.bm25 = BM25Okapi(tokenized_chunks) if self.chunks else None
    
    def retrieve(self, query: str, top_k: int = 3) -> Tuple[List[str], bool]:
        """
        Retrieve top-k relevant chunks.
        Returns: (list of chunks, is_answerable)
        """
        if not self.chunks or not self.bm25:
            return [], False
        
        # Tokenize query
        tokenized_query = tokenize(query)
        
        # Get BM25 scores
        scores = self.bm25.get_scores(tokenized_query)
        
        # Get top-k indices
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        
        # Check if best score exceeds threshold
        best_score = scores[top_indices[0]] if top_indices else 0
        is_answerable = best_score >= self.threshold
        
        # Return top chunks
        top_chunks = [self.chunks[i] for i in top_indices]
        
        return top_chunks, is_answerable
