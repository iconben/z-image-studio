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
    _migrate_create_generation_loras_table(cursor)
    _normalize_historical_data(cursor)
    
    conn.commit()
    conn.close()


def _migrate_add_precision_column(cursor: sqlite3.Cursor):
    """Add 'precision' column if it doesn't exist."""
    cursor.execute("PRAGMA table_info(generations)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if "precision" not in columns:
        cursor.execute("ALTER TABLE generations ADD COLUMN precision TEXT DEFAULT 'full'")

def _migrate_create_generation_loras_table(cursor: sqlite3.Cursor):
    """Create table for many-to-many relationship between generations and LoRAs."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS generation_loras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generation_id INTEGER NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
            lora_file_id INTEGER NOT NULL REFERENCES lora_files(id) ON DELETE CASCADE,
            strength REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')


def _normalize_historical_data(cursor: sqlite3.Cursor):
    """Update NULL values in historical records with defaults."""
    cursor.execute("UPDATE generations SET precision = 'full' WHERE precision IS NULL")
    cursor.execute("UPDATE generations SET model = 'Tongyi-MAI/Z-Image-Turbo' WHERE model IS NULL")
