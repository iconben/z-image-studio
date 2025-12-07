import sqlite3

try:
    from .db import DB_PATH
except ImportError:
    from db import DB_PATH


def init_db():
    """Initialize the database and apply schema migrations."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create the main generations table
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

    # Create table for storing LoRA files metadata
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lora_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            display_name TEXT,
            trigger_word TEXT,
            hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Run schema migrations
    _migrate_add_precision_column(cursor)
    _migrate_add_lora_columns(cursor)
    _normalize_historical_data(cursor)
    
    conn.commit()
    conn.close()


def _migrate_add_precision_column(cursor: sqlite3.Cursor):
    """Add 'precision' column if it doesn't exist."""
    cursor.execute("PRAGMA table_info(generations)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if "precision" not in columns:
        cursor.execute("ALTER TABLE generations ADD COLUMN precision TEXT DEFAULT 'full'")


def _migrate_add_lora_columns(cursor: sqlite3.Cursor):
    """Add 'lora_file_id' and 'lora_strength' columns if they don't exist."""
    cursor.execute("PRAGMA table_info(generations)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if "lora_file_id" not in columns:
        cursor.execute("ALTER TABLE generations ADD COLUMN lora_file_id INTEGER REFERENCES lora_files(id) ON DELETE SET NULL")
    
    if "lora_strength" not in columns:
        cursor.execute("ALTER TABLE generations ADD COLUMN lora_strength REAL DEFAULT 0.0")


def _normalize_historical_data(cursor: sqlite3.Cursor):
    """Update NULL values in historical records with defaults."""
    cursor.execute("UPDATE generations SET precision = 'full' WHERE precision IS NULL")
    cursor.execute("UPDATE generations SET model = 'Tongyi-MAI/Z-Image-Turbo' WHERE model IS NULL")
