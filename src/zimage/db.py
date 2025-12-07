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
    loras: List[Dict[str, Any]] = None, # List of {id: int, strength: float}
) -> int:
    """Insert a new generation record."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Legacy support: store first LoRA in main table columns if exists
    legacy_lora_id = None
    legacy_lora_strength = 0.0
    if loras and len(loras) > 0:
        legacy_lora_id = loras[0].get('id')
        legacy_lora_strength = loras[0].get('strength', 1.0)

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
        legacy_lora_id, legacy_lora_strength
    ))
    
    new_id = cursor.lastrowid
    
    # Insert into junction table
    if loras:
        for lora in loras:
            if lora.get('id'):
                cursor.execute('''
                    INSERT INTO generation_loras (generation_id, lora_file_id, strength)
                    VALUES (?, ?, ?)
                ''', (new_id, lora['id'], lora.get('strength', 1.0)))

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

    # Use JSON aggregation to get LoRAs. 
    # We left join generation_loras and lora_files.
    # Note: This requires SQLite 3.38.0+ (bundled with Python 3.10+ usually).
    # If json_group_array is not available, this will fail. 
    # Fallback logic: Just simple query and python fetch if needed? 
    # Let's try the robust query.
    try:
        cursor.execute('''
            SELECT g.*, 
                   json_group_array(
                       json_object(
                           'filename', l.filename, 
                           'strength', gl.strength, 
                           'display_name', l.display_name
                       )
                   ) as loras_json
            FROM generations g
            LEFT JOIN generation_loras gl ON g.id = gl.generation_id
            LEFT JOIN lora_files l ON gl.lora_file_id = l.id
            WHERE g.status = 'succeeded' 
            GROUP BY g.id
            ORDER BY g.created_at DESC 
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        
        rows = cursor.fetchall()
        result = []
        import json
        for row in rows:
            d = dict(row)
            # Parse JSON string back to list
            if d.get('loras_json'):
                try:
                    loaded_loras = json.loads(d['loras_json'])
                    # Filter out nulls (from left join where no lora exists)
                    d['loras'] = [x for x in loaded_loras if x.get('filename') is not None]
                except json.JSONDecodeError:
                    d['loras'] = []
            else:
                d['loras'] = []
            
            # Fallback for legacy single-lora items if list is empty but legacy columns exist
            if not d['loras'] and d.get('lora_file_id'):
                 # We need to fetch the legacy lora info... or just rely on the left join above?
                 # The left join above covers the legacy table structure IF we migrated data.
                 # But we didn't migrate data from `generations.lora_file_id` to `generation_loras`.
                 # So for old items, we might want to shim it.
                 # Actually, the `lora_name` and `lora_filename` from previous query are gone.
                 pass
            
            result.append(d)
            
    except sqlite3.OperationalError:
        # Fallback for older SQLite without JSON support
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
