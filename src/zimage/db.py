import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from .paths import get_db_path
except ImportError:
    from paths import get_db_path

DB_PATH = get_db_path()

def _get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    conn.execute("PRAGMA foreign_keys = ON") # Enable foreign key enforcement
    return conn

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
    conn = _get_db_connection()
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

def get_history(
    limit: int = 50,
    offset: int = 0,
    q: str = None,
    start_date: str = None,
    end_date: str = None
) -> tuple[List[Dict[str, Any]], int]:
    """Get generations with keyword search and date filtering.

    Always returns results ordered by created_at DESC.
    Preserves existing pagination and response format.

    Args:
        limit: Number of items to return
        offset: Number of items to skip
        q: Keyword search (matches prompt/negative_prompt only)
        start_date: Start date in YYYY-MM-DD format (inclusive)
        end_date: End date in YYYY-MM-DD format (inclusive, auto-extended to 23:59:59)

    Returns:
        Tuple of (list of generation items, total count)
    """
    conn = _get_db_connection()
    cursor = conn.cursor()

    # Validate search query length
    if q and len(q) > 100:
        conn.close()
        raise ValueError("Search query too long (max 100 chars)")

    # Validate date range
    if start_date and end_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)
            if (end_dt - start_dt).days > 365:
                conn.close()
                raise ValueError("Date range cannot exceed 365 days")
        except ValueError:
            conn.close()
            raise ValueError("Invalid date format. Use YYYY-MM-DD")

    # Build WHERE clauses
    where_clauses = ["status = 'succeeded'"]
    params = []

    # Keyword search (prompt and negative_prompt only, LIKE queries)
    if q:
        search_term = f"%{q}%"
        where_clauses.append("(prompt LIKE ? OR negative_prompt LIKE ?)")
        params.extend([search_term, search_term])

    # Date range (normalize end_date to 23:59:59 for inclusive search)
    if start_date or end_date:
        date_clauses = []
        if start_date:
            date_clauses.append("created_at >= ?")
            params.append(start_date)
        if end_date:
            date_clauses.append("created_at <= ?")
            params.append(f"{end_date} 23:59:59")
        where_clauses.append(f"({' AND '.join(date_clauses)})")

    # Build final WHERE clause
    where_clause_sql = " AND ".join(where_clauses)

    # Count query (respects all filters)
    count_query = f"SELECT COUNT(*) FROM generations WHERE {where_clause_sql}"
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()[0]

    # Use JSON aggregation to get LoRAs.
    # We left join generation_loras and lora_files.
    # Note: This requires SQLite 3.38.0+ (bundled with Python 3.10+ usually).
    # If json_group_array is not available, this will fail.
    # Let's try robust query.
    try:
        cursor.execute(f"""
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
            WHERE {where_clause_sql}
            GROUP BY g.id
            ORDER BY g.created_at DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])

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

            result.append(d)

    except sqlite3.OperationalError:
        # Fallback for older SQLite without JSON support
        cursor.execute(f"""
            SELECT * FROM generations
            WHERE {where_clause_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]

    conn.close()
    return result, total_count

    # Build final WHERE clause
    where_clause_sql = " AND ".join(where_clauses)

    # Count query (respects all filters)
    count_query = f"SELECT COUNT(*) FROM generations WHERE {where_clause_sql}"
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()[0]

    # Use JSON aggregation to get LoRAs.
    # We left join generation_loras and lora_files.
    # Note: This requires SQLite 3.38.0+ (bundled with Python 3.10+ usually).
    # If json_group_array is not available, this will fail.
    # Let's try robust query.
    try:
        cursor.execute(f"""
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
            WHERE {where_clause_sql}
            GROUP BY g.id
            ORDER BY g.created_at DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])

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

            result.append(d)

    except sqlite3.OperationalError:
        # Fallback for older SQLite without JSON support
        cursor.execute(f"""
            SELECT * FROM generations
            WHERE {where_clause_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]

    conn.close()
    return result, total_count

def delete_generation(item_id: int):
    """Delete a generation record by its ID."""
    conn = _get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM generations WHERE id = ?', (item_id,))
    
    conn.commit()
    conn.close()

def add_lora(filename: str, display_name: str = None, trigger_word: str = None, hash_val: str = None) -> int:
    """Register a new LoRA file."""
    if display_name is None:
        display_name = filename
    
    conn = _get_db_connection()
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

def get_lora_by_hash(hash_val: str) -> Optional[Dict[str, Any]]:
    """Get LoRA details by its hash."""
    conn = _get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM lora_files WHERE hash = ?", (hash_val,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def list_loras() -> List[Dict[str, Any]]:
    """List all available LoRAs."""
    conn = _get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM lora_files ORDER BY display_name ASC")
    rows = cursor.fetchall()
    result = [dict(row) for row in rows]
    conn.close()
    return result

def get_lora_by_filename(filename: str) -> Optional[Dict[str, Any]]:
    conn = _get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM lora_files WHERE filename = ?", (filename,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_lora(lora_id: int):
    """Delete a LoRA record."""
    conn = _get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lora_files WHERE id = ?", (lora_id,))
    conn.commit()
    conn.close()