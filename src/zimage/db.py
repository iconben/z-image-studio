import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

DB_PATH = Path("zimage.db")

def init_db():
    """Initialize the database and create table if not exists."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt TEXT,
            negative_prompt TEXT,
            steps INTEGER,
            width INTEGER,
            height INTEGER,
            cfg_scale REAL,
            seed INTEGER,
            model TEXT,
            status TEXT, -- queued, running, succeeded, failed
            filename TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            generation_time REAL,
            file_size_kb REAL,
            precision TEXT
        )
    ''')
    
    # Migration: Add 'precision' column if it doesn't exist
    cursor.execute("PRAGMA table_info(generations)")
    columns = [info[1] for info in cursor.fetchall()]
    if "precision" not in columns:
        cursor.execute("ALTER TABLE generations ADD COLUMN precision TEXT DEFAULT 'full'")
    
    # Handle historical data normalization
    cursor.execute("UPDATE generations SET precision = 'full' WHERE precision IS NULL")
    cursor.execute("UPDATE generations SET model = 'Tongyi-MAI/Z-Image-Turbo' WHERE model IS NULL")
    
    conn.commit()
    conn.close()

def add_generation(
    prompt: str,
    steps: int,
    width: int,
    height: int,
    filename: str,
    generation_time: float,
    file_size_kb: float,
    model: str = "Tongyi-MAI/Z-Image-Turbo",
    status: str = "succeeded",
    negative_prompt: Optional[str] = None,
    cfg_scale: float = 0.0,
    seed: Optional[int] = None,
    error_message: Optional[str] = None,
    precision: str = "q8"
) -> int:
    """Insert a new generation record."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO generations (
            prompt, negative_prompt, steps, width, height, 
            cfg_scale, seed, model, status, filename, 
            error_message, generation_time, file_size_kb, created_at, precision
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        prompt, negative_prompt, steps, width, height,
        cfg_scale, seed, model, status, filename,
        error_message, generation_time, file_size_kb, datetime.now(), precision
    ))
    
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def get_history(limit: int = 50, offset: int = 0) -> tuple[List[Dict[str, Any]], int]:
    """Get recent generations with pagination."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    cursor = conn.cursor()
    
    # Get total count
    cursor.execute("SELECT COUNT(*) FROM generations WHERE status = 'succeeded'")
    total_count = cursor.fetchone()[0]

    cursor.execute('''
        SELECT * FROM generations 
        WHERE status = 'succeeded' 
        ORDER BY created_at DESC 
        LIMIT ? OFFSET ?
    ''', (limit, offset))
    
    rows = cursor.fetchall()
    result = [dict(row) for row in rows]
    conn.close()
    return result, total_count

def delete_generation(item_id: int):
    """Delete a generation record by its ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM generations WHERE id = ?', (item_id,))
    
    conn.commit()
    conn.close()
