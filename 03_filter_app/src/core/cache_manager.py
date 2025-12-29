"""
Cache manager for AI responses using SQLite.

Stores AI responses based on a hash of the input content to avoid
re-processing the same news articles, saving time and API costs.
"""

import sqlite3
import hashlib
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ResponseCache:
    """
    Manages caching of AI responses using SQLite.
    
    The cache key is a hash of the input content (title + text).
    If the same content is processed again, the cached response is returned.
    """
    
    def __init__(self, db_path: str = "ai_cache.sqlite"):
        """
        Initialize the cache manager.
        
        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = Path(db_path)
        self._init_db()
    
    def _init_db(self):
        """Initialize the database schema if it doesn't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS responses (
                        hash TEXT PRIMARY KEY,
                        response TEXT,
                        model TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Error initializing cache db: {e}")
    
    def _generate_hash(self, content: str) -> str:
        """Generate SHA-256 hash of the content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def get(self, content: str, model: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a cached response for the given content and model.
        
        Args:
            content: The input text content to look up.
            model: The model identifier used (to avoid returning responses from different models).
            
        Returns:
            Dictionary with the response if found, None otherwise.
        """
        content_hash = self._generate_hash(content + model)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT response FROM responses WHERE hash = ?", 
                    (content_hash,)
                )
                row = cursor.fetchone()
                
                if row:
                    try:
                        return json.loads(row[0])
                    except json.JSONDecodeError:
                        return None
                return None
        except Exception as e:
            logger.warning(f"Error reading from cache: {e}")
            return None
    
    def set(self, content: str, model: str, response: Dict[str, Any]):
        """
        Save a response to the cache.
        
        Args:
            content: The input text content.
            model: The model identifier used.
            response: The result dictionary to cache.
        """
        content_hash = self._generate_hash(content + model)
        response_json = json.dumps(response, ensure_ascii=False)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO responses (hash, response, model)
                    VALUES (?, ?, ?)
                    """,
                    (content_hash, response_json, model)
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Error writing to cache: {e}")
            
    def clear(self):
        """Clear the entire cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM responses")
                conn.commit()
            logger.info("Cache cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*), COUNT(DISTINCT model) FROM responses")
                count, models = cursor.fetchone()
                
                # Get size of file
                size_mb = self.db_path.stat().st_size / (1024 * 1024) if self.db_path.exists() else 0
                
                return {
                    "entries": count,
                    "models": models,
                    "size_mb": round(size_mb, 2)
                }
        except Exception:
            return {"entries": 0, "models": 0, "size_mb": 0}
