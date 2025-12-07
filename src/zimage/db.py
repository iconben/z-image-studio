import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

DB_PATH = Path("zimage.db")


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
    precision: str = "q8",
    lora_file_id: Optional[int] = None,
    lora_strength: float = 0.0
) -> int:
    """Insert a new generation record."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO generations (
            prompt, negative_prompt, steps, width, height, 
            cfg_scale, seed, model, status, filename, 
            error_message, generation_time, file_size_kb, created_at, precision,
            lora_file_id, lora_strength
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        prompt, negative_prompt, steps, width, height,
        cfg_scale, seed, model, status, filename,
        error_message, generation_time, file_size_kb, datetime.now(), precision,
        lora_file_id, lora_strength
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
        SELECT g.*, l.display_name as lora_name, l.filename as lora_filename
        FROM generations g
        LEFT JOIN lora_files l ON g.lora_file_id = l.id
        WHERE g.status = 'succeeded' 
        ORDER BY g.created_at DESC 
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

def add_lora(filename: str, display_name: str = None, trigger_word: str = None, hash_val: str = None) -> int:
    """Register a new LoRA file."""
    if display_name is None:
        display_name = filename
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO lora_files (filename, display_name, trigger_word, hash)
            VALUES (?, ?, ?, ?)
        ''', (filename, display_name, trigger_word, hash_val))
        new_id = cursor.lastrowid
        conn.commit()
        return new_id
    except sqlite3.IntegrityError:
        # If filename exists, return existing ID
        cursor.execute("SELECT id FROM lora_files WHERE filename = ?", (filename,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return row[0]
        raise
    finally:
        conn.close()

def list_loras() -> List[Dict[str, Any]]:
    """List all available LoRAs."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM lora_files ORDER BY display_name ASC")
    rows = cursor.fetchall()
    result = [dict(row) for row in rows]
    conn.close()
    return result

def get_lora_by_filename(filename: str) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM lora_files WHERE filename = ?", (filename,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_lora(lora_id: int):
    """Delete a LoRA record."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lora_files WHERE id = ?", (lora_id,))
    conn.commit()
    conn.close()
