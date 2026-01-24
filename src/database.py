import sqlite3
import os
import json
import secrets
import string
import hashlib
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from pathlib import Path
from config import DATABASE_URL

# Extract database path from SQLAlchemy URL
DB_PATH = DATABASE_URL.replace("sqlite:///", "")

def get_db_connection():
    """Get a database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    return conn

@contextmanager
def get_db_cursor():
    """Context manager for database operations"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def generate_access_key():
    """Generate access key in format XXXX-XXXX-XXXX using secure random"""
    chars = string.ascii_uppercase + string.digits
    parts = []
    for _ in range(3):
        part = ''.join(secrets.choice(chars) for _ in range(4))
        parts.append(part)
    return '-'.join(parts)

def get_cards_directory():
    """Get or create the cards directory using pathlib"""
    cards_dir = Path.cwd() / "cards"
    cards_dir.mkdir(exist_ok=True)
    return str(cards_dir)

def cleanup_old_temp_files(max_age_hours=24):
    """Clean up temporary card files older than specified hours"""
    import tempfile
    import glob
    import time
    
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    
    # Clean cards directory
    cards_dir = get_cards_directory()
    card_files = glob.glob(os.path.join(cards_dir, 'card_*.png'))
    card_files.extend(glob.glob(os.path.join(cards_dir, 'background_card_*.png')))
    card_files.extend(glob.glob(os.path.join(cards_dir, 'temp_bg_*.png')))
    card_files.extend(glob.glob(os.path.join(cards_dir, 'collection_card_*.png')))
    
    for card_file in card_files:
        try:
            file_age = current_time - os.path.getmtime(card_file)
            if file_age > max_age_seconds:
                os.remove(card_file)
                print(f"Removed old card file: {card_file}")
        except:
            pass
    
    # Clean temp directory (for any remaining temp files)
    temp_dir = tempfile.gettempdir()
    temp_files = glob.glob(os.path.join(temp_dir, 'card_*.png'))
    for temp_file in temp_files:
        try:
            file_age = current_time - os.path.getmtime(temp_file)
            if file_age > max_age_seconds:
                os.remove(temp_file)
                print(f"Removed old temp file: {temp_file}")
        except:
            pass

def init_db():
    """Initialize database tables with migration support"""
    with get_db_cursor() as cursor:
        # Create migration table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Get current migration version
        cursor.execute("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1")
        migration_row = cursor.fetchone()
        current_version = migration_row[0] if migration_row else "0.0.0"
        
        # Apply migrations based on version
        if current_version < "1.0.0":
            # Initial database setup
            migrate_to_v1_0_0(cursor)
        
        if current_version < "1.1.0":
            # Add collection links table
            migrate_to_v1_1_0(cursor)
        
        if current_version < "1.2.0":
            # Add access_key column to cards table
            migrate_to_v1_2_0(cursor)
        
        if current_version < "1.3.0":
            # Add reservation_status column to collections table
            migrate_to_v1_3_0(cursor)

        if current_version < "1.4.0":
            migrate_to_v1_4_0(cursor)
        
        if current_version < "1.5.0":
            # Add star_price column to cards table
            migrate_to_v1_5_0(cursor)
        
        if current_version < "1.6.0":
            # Add airdrops table
            migrate_to_v1_6_0(cursor)
        
        if current_version < "1.7.0":
            # Add cover_image column to airdrops table
            migrate_to_v1_7_0(cursor)
        
        # Update migration version
        cursor.execute("INSERT OR REPLACE INTO schema_migrations (version) VALUES ('1.7.0')")
        
        # Verify database integrity
        cursor.execute("PRAGMA integrity_check")
        integrity_result = cursor.fetchone()
        if integrity_result and integrity_result[0] != "ok":
            print(f"Database integrity check failed: {integrity_result[0]}")
        else:
            print("Database initialized successfully")

def migrate_to_v1_0_0(cursor):
    """Initial database schema migration"""
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            is_admin BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Collections table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            author_id INTEGER NOT NULL,
            star_price INTEGER DEFAULT 1,
            is_published BOOLEAN DEFAULT 0,
            link_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (author_id) REFERENCES users (id)
        )
    """)
    
    # Cards table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_number INTEGER NOT NULL,
            name TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            registration_date TEXT DEFAULT CURRENT_TIMESTAMP,
            expires TEXT DEFAULT 'Never',
            engraving_color TEXT DEFAULT 'white',
            has_background BOOLEAN DEFAULT 0,
            collection_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users (id),
            FOREIGN KEY (collection_id) REFERENCES collections (id)
        )
    """)
    
    # Trade links table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_id TEXT UNIQUE NOT NULL,
            card_id INTEGER NOT NULL,
            seller_id INTEGER NOT NULL,
            price INTEGER NOT NULL,
            is_gift BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (card_id) REFERENCES cards (id),
            FOREIGN KEY (seller_id) REFERENCES users (id)
        )
    """)

def migrate_to_v1_1_0(cursor):
    """Add collection links table migration"""
    # Collection links table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS collection_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_id TEXT UNIQUE NOT NULL,
            collection_id INTEGER NOT NULL,
            seller_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (collection_id) REFERENCES collections (id),
            FOREIGN KEY (seller_id) REFERENCES users (id)
        )
    """)
    
    # Add description column to collections if not exists
    cursor.execute("PRAGMA table_info(collections)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'description' not in columns:
        cursor.execute("ALTER TABLE collections ADD COLUMN description TEXT")
    if 'is_published' not in columns:
        cursor.execute("ALTER TABLE collections ADD COLUMN is_published BOOLEAN DEFAULT 0")

def migrate_to_v1_2_0(cursor):
    """Add access_key column to cards table migration"""
    # Add access_key column to cards table if not exists
    cursor.execute("PRAGMA table_info(cards)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'access_key' not in columns:
        cursor.execute("ALTER TABLE cards ADD COLUMN access_key TEXT")

def migrate_to_v1_3_0(cursor):
    """Add reservation_status column to collections table migration"""
    # Add reservation_status column to collections table if not exists
    cursor.execute("PRAGMA table_info(collections)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'reservation_status' not in columns:
        cursor.execute("ALTER TABLE collections ADD COLUMN reservation_status TEXT DEFAULT 'available'")
    if 'reserved_by' not in columns:
        cursor.execute("ALTER TABLE collections ADD COLUMN reserved_by INTEGER")
    if 'reserved_at' not in columns:
        cursor.execute("ALTER TABLE collections ADD COLUMN reserved_at TEXT")


def migrate_to_v1_4_0(cursor):
    cursor.execute("PRAGMA table_info(collections)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'link_id' not in columns:
        cursor.execute("ALTER TABLE collections ADD COLUMN link_id TEXT")

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_collections_link_id
        ON collections(link_id)
    """)

    cursor.execute("SELECT id FROM collections WHERE link_id IS NULL OR link_id = ''")
    collections_without_link = cursor.fetchall()
    for collection in collections_without_link:
        new_link_id = str(uuid.uuid4().hex)[:16]
        cursor.execute("UPDATE collections SET link_id = ? WHERE id = ?", (new_link_id, collection[0]))


def migrate_to_v1_6_0(cursor):
    """Add airdrops table migration"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS airdrops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            creator_id INTEGER NOT NULL,
            message_id INTEGER,
            chat_id INTEGER,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (creator_id) REFERENCES users (id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS airdrop_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            airdrop_id INTEGER NOT NULL,
            card_id INTEGER NOT NULL,
            is_reserved BOOLEAN DEFAULT 0,
            reserved_by INTEGER,
            reserved_at TEXT,
            FOREIGN KEY (airdrop_id) REFERENCES airdrops (id),
            FOREIGN KEY (card_id) REFERENCES cards (id),
            FOREIGN KEY (reserved_by) REFERENCES users (id)
        )
    """)

def migrate_to_v1_7_0(cursor):
    """Add cover_image column to airdrops table migration"""
    cursor.execute("PRAGMA table_info(airdrops)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'cover_image' not in columns:
        cursor.execute("ALTER TABLE airdrops ADD COLUMN cover_image TEXT")


def migrate_to_v1_5_0(cursor):
    """Add star_price column to cards table migration"""
    cursor.execute("PRAGMA table_info(cards)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'star_price' not in columns:
        cursor.execute("ALTER TABLE cards ADD COLUMN star_price INTEGER DEFAULT 1")
    
    # Set default star_price for existing cards
    cursor.execute("UPDATE cards SET star_price = 1 WHERE star_price IS NULL")

class User:
    def __init__(self, telegram_id: int, username: str = None, first_name: str = None, is_admin: bool = False):
        self.telegram_id = telegram_id
        self.username = username
        self.first_name = first_name
        self.is_admin = is_admin
        self.created_at = datetime.utcnow().isoformat()
        self.id = None
    
    def save(self):
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT OR REPLACE INTO users (telegram_id, username, first_name, is_admin, created_at)
                VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM users WHERE telegram_id = ?), ?))
            """, (self.telegram_id, self.username, self.first_name, self.is_admin, self.telegram_id, self.created_at))
            
            if self.id is None:
                self.id = cursor.lastrowid
            return self
    
    @classmethod
    def get_by_telegram_id(cls, telegram_id: int):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = cursor.fetchone()
            if row:
                user = cls(row['telegram_id'], row['username'], row['first_name'], bool(row['is_admin']))
                user.id = row['id']
                user.created_at = row['created_at']
                return user
            return None
    
    @classmethod
    def get_by_id(cls, user_id: int):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                user = cls(row['telegram_id'], row['username'], row['first_name'], bool(row['is_admin']))
                user.id = row['id']
                user.created_at = row['created_at']
                return user
            return None
    
    def get_cards(self):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM cards WHERE owner_id = ?", (self.telegram_id,))
            return [Card.from_row(row) for row in cursor.fetchall()]
    
    def get_collections(self):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM collections WHERE author_id = ?", (self.telegram_id,))
            return [Collection.from_row(row) for row in cursor.fetchall()]

class Card:
    def __init__(self, card_number: int, name: str, owner_id: int, expires: str = "Never", 
                 engraving_color: str = "white", has_background: bool = False, collection_id: int = None, registration_date: str = None, access_key: str = None, star_price: int = 1):
        self.card_number = card_number
        self.name = name
        self.owner_id = owner_id
        self.expires = expires
        self.engraving_color = engraving_color
        self.has_background = has_background
        self.collection_id = collection_id
        self.registration_date = registration_date or datetime.utcnow().strftime("%d.%m.%Y")
        self.access_key = access_key
        self.star_price = star_price
        self.created_at = datetime.utcnow().isoformat()
        self.id = None
    
    def save(self):
        with get_db_cursor() as cursor:
            if self.id is None:
                # Insert new card
                cursor.execute("""
                    INSERT INTO cards (card_number, name, owner_id, registration_date, expires, 
                                     engraving_color, has_background, collection_id, created_at, access_key, star_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (self.card_number, self.name, self.owner_id, self.registration_date, 
                      self.expires, self.engraving_color, self.has_background, self.collection_id, self.created_at, self.access_key, self.star_price))
                
                self.id = cursor.lastrowid
            else:
                # Update existing card
                cursor.execute("""
                    UPDATE cards 
                    SET name = ?, owner_id = ?, registration_date = ?, expires = ?,
                        engraving_color = ?, has_background = ?, collection_id = ?, access_key = ?, star_price = ?
                    WHERE id = ?
                """, (self.name, self.owner_id, self.registration_date, self.expires,
                      self.engraving_color, self.has_background, self.collection_id, self.access_key, self.star_price, self.id))
            return self
    
    @classmethod
    def from_row(cls, row):
        access_key = row['access_key'] if 'access_key' in row.keys() else None
        star_price = row['star_price'] if 'star_price' in row.keys() else 1
        card = cls(row['card_number'], row['name'], row['owner_id'], row['expires'], 
                  row['engraving_color'], bool(row['has_background']), row['collection_id'], 
                  row['registration_date'], access_key, star_price)
        card.id = row['id']
        card.created_at = row['created_at']
        card.registration_date = row['registration_date']
        return card
    
    @classmethod
    def get_by_id(cls, card_id: int):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
            row = cursor.fetchone()
            return cls.from_row(row) if row else None
    
    @classmethod
    def get_by_number(cls, card_number: int):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM cards WHERE card_number = ?", (card_number,))
            row = cursor.fetchone()
            return cls.from_row(row) if row else None
    
    @classmethod
    def get_by_access_key(cls, access_key: str):
        """Получает карту по access key"""
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM cards WHERE access_key = ?", (access_key,))
            row = cursor.fetchone()
            return cls.from_row(row) if row else None
    
    def get_owner(self):
        return User.get_by_telegram_id(self.owner_id)
    
    def get_collection(self):
        if self.collection_id:
            return Collection.get_by_id(self.collection_id)
        return None
    
    def delete(self):
        """Delete the card from database"""
        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM cards WHERE id = ?", (self.id,))

class Collection:
    def __init__(self, name: str, author_id: int, star_price: int = 1, description: str = None, link_id: str = None):
        self.name = name
        self.description = description or ""
        self.author_id = author_id
        self.star_price = star_price
        self.link_id = link_id or self._generate_link_id()
        self.is_published = False  # Always false now, collections are accessed via links
        self.created_at = datetime.utcnow().isoformat()
        self.id = None
    
    def _generate_link_id(self):
        """Генерирует уникальный link_id для коллекции"""
        return str(uuid.uuid4().hex)[:16]
    
    def save(self):
        with get_db_cursor() as cursor:
            # Check if description column exists, if not add it
            cursor.execute("PRAGMA table_info(collections)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'description' not in columns:
                cursor.execute("ALTER TABLE collections ADD COLUMN description TEXT")
            if 'is_published' not in columns:
                cursor.execute("ALTER TABLE collections ADD COLUMN is_published BOOLEAN DEFAULT 0")
            if 'link_id' not in columns:
                cursor.execute("ALTER TABLE collections ADD COLUMN link_id TEXT")
            
            cursor.execute("""
                INSERT INTO collections (name, description, author_id, star_price, is_published, created_at, link_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (self.name, self.description, self.author_id, self.star_price, self.is_published, self.created_at, self.link_id))
            
            self.id = cursor.lastrowid
            return self
    
    def update_price(self):
        """Simple price update - set to 0 when collections are disabled"""
        from config import ENABLE_COLLECTIONS
        if not ENABLE_COLLECTIONS:
            self.star_price = 0
            with get_db_cursor() as cursor:
                cursor.execute("UPDATE collections SET star_price = ? WHERE id = ?", (0, self.id))
            return 0
        
        # Original complex logic for enabled collections
        cards = self.get_cards()
        total_price = 0
        
        if not cards:
            self.star_price = 0
            with get_db_cursor() as cursor:
                cursor.execute("UPDATE collections SET star_price = ? WHERE id = ?", (0, self.id))
            return 0
        
        # Get active trade links for cards in this collection
        with get_db_cursor() as cursor:
            card_ids = [card.id for card in cards]
            if card_ids:
                placeholders = ','.join(['?'] * len(card_ids))
                cursor.execute(f"""
                    SELECT card_id, price FROM trade_links 
                    WHERE card_id IN ({placeholders}) AND is_active = 1 AND is_gift = 0
                    ORDER BY created_at DESC
                """, card_ids)
                
                # Get latest price for each card
                card_prices = {}
                for row in cursor.fetchall():
                    card_id = row[0]
                    if card_id not in card_prices:
                        card_prices[card_id] = row[1]
                
                total_price = sum(card_prices.values())
        
        self.star_price = total_price
        
        # Update in database
        with get_db_cursor() as cursor:
            cursor.execute("UPDATE collections SET star_price = ? WHERE id = ?", (total_price, self.id))
        
        return total_price
    
    @classmethod
    def from_row(cls, row):
        star_price = row['star_price'] if 'star_price' in row.keys() else 1
        description = row['description'] if 'description' in row.keys() else ''
        link_id = row['link_id'] if 'link_id' in row.keys() else None
        collection = cls(row['name'], row['author_id'], star_price, description, link_id)
        collection.id = row['id']
        collection.created_at = row['created_at']
        # Keep is_published for compatibility but don't use it
        if 'is_published' in row.keys():
            collection.is_published = row['is_published']
        return collection
    
    @classmethod
    def get_by_id(cls, collection_id: int):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM collections WHERE id = ?", (collection_id,))
            row = cursor.fetchone()
            return cls.from_row(row) if row else None
    
    @classmethod
    def get_by_access_key(cls, access_key: str):
        """Получает коллекцию по access key любой из её карт"""
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT c.* FROM collections c
                JOIN cards ca ON c.id = ca.collection_id
                WHERE ca.access_key = ?
            """, (access_key,))
            row = cursor.fetchone()
            return cls.from_row(row) if row else None
    
    @classmethod
    def get_by_link_id(cls, link_id: str):
        """Получает коллекцию по постоянной ссылке"""
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM collections WHERE link_id = ?", (link_id,))
            row = cursor.fetchone()
            return cls.from_row(row) if row else None
    
    def get_author(self):
        return User.get_by_id(self.author_id)
    
    def get_cards(self):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM cards WHERE collection_id = ?", (self.id,))
            return [Card.from_row(row) for row in cursor.fetchall()]
    

class TradeLink:
    def __init__(self, link_id: str, card_id: int, seller_id: int, price: int, is_gift: bool = False):
        self.link_id = link_id
        self.card_id = card_id
        self.seller_id = seller_id
        self.price = price
        self.is_gift = is_gift
        self.created_at = datetime.utcnow().isoformat()
        self.is_active = True
        self.id = None
    
    def save(self):
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO trade_links (link_id, card_id, seller_id, price, is_gift, created_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (self.link_id, self.card_id, self.seller_id, self.price, 
                  self.is_gift, self.created_at, self.is_active))
            
            self.id = cursor.lastrowid
            return self
    
    @classmethod
    def from_row(cls, row):
        link = cls(row['link_id'], row['card_id'], row['seller_id'], row['price'], bool(row['is_gift']))
        link.id = row['id']
        link.created_at = row['created_at']
        link.is_active = bool(row['is_active'])
        return link
    
    @classmethod
    def get_by_link_id(cls, link_id: str):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM trade_links WHERE link_id = ?", (link_id,))
            row = cursor.fetchone()
            return cls.from_row(row) if row else None
    
    @classmethod
    def get_active_links(cls):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM trade_links WHERE is_active = 1")
            return [cls.from_row(row) for row in cursor.fetchall()]
    
    def get_card(self):
        return Card.get_by_id(self.card_id)
    
    def get_seller(self):
        return User.get_by_id(self.seller_id)
    
    def deactivate(self):
        with get_db_cursor() as cursor:
            cursor.execute("UPDATE trade_links SET is_active = 0 WHERE id = ?", (self.id,))
            self.is_active = False

class CollectionLink:
    def __init__(self, link_id: str, collection_id: int, seller_id: int):
        self.link_id = link_id
        self.collection_id = collection_id
        self.seller_id = seller_id
        self.created_at = datetime.utcnow().isoformat()
        self.is_active = True
        self.id = None
    
    def save(self):
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO collection_links (link_id, collection_id, seller_id, created_at, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, (self.link_id, self.collection_id, self.seller_id, self.created_at, self.is_active))
            
            self.id = cursor.lastrowid
            return self
    
    @classmethod
    def from_row(cls, row):
        link = cls(row['link_id'], row['collection_id'], row['seller_id'])
        link.id = row['id']
        link.created_at = row['created_at']
        link.is_active = bool(row['is_active'])
        return link
    
    @classmethod
    def get_by_link_id(cls, link_id: str):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM collection_links WHERE link_id = ?", (link_id,))
            row = cursor.fetchone()
            return cls.from_row(row) if row else None
    
    @classmethod
    def get_active_links(cls):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM collection_links WHERE is_active = 1")
            return [cls.from_row(row) for row in cursor.fetchall()]
    
    def get_collection(self):
        return Collection.get_by_id(self.collection_id)
    
    def get_seller(self):
        return User.get_by_id(self.seller_id)
    
    def deactivate(self):
        with get_db_cursor() as cursor:
            cursor.execute("UPDATE collection_links SET is_active = 0 WHERE id = ?", (self.id,))
            self.is_active = False

class Airdrop:
    def __init__(self, name: str, creator_id: int, description: str = None):
        self.name = name
        self.description = description or ""
        self.creator_id = creator_id
        self.message_id = None
        self.chat_id = None
        self.is_active = True
        self.created_at = datetime.utcnow().isoformat()
        self.id = None

    def save(self):
        with get_db_cursor() as cursor:
            if self.id is None:
                cursor.execute("""
                    INSERT INTO airdrops (name, description, creator_id, message_id, chat_id, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (self.name, self.description, self.creator_id, self.message_id, self.chat_id, self.is_active, self.created_at))
                self.id = cursor.lastrowid
            else:
                cursor.execute("""
                    UPDATE airdrops 
                    SET name = ?, description = ?, message_id = ?, chat_id = ?, is_active = ?
                    WHERE id = ?
                """, (self.name, self.description, self.message_id, self.chat_id, self.is_active, self.id))
            return self
    
    @classmethod
    def from_row(cls, row):
        airdrop = cls(row['name'], row['creator_id'], row['description'])
        airdrop.id = row['id']
        airdrop.message_id = row['message_id']
        airdrop.chat_id = row['chat_id']
        airdrop.is_active = bool(row['is_active'])
        airdrop.created_at = row['created_at']
        return airdrop
    
    @classmethod
    def get_by_id(cls, airdrop_id: int):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM airdrops WHERE id = ?", (airdrop_id,))
            row = cursor.fetchone()
            return cls.from_row(row) if row else None
    
    @classmethod
    def get_active_airdrops(cls):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM airdrops WHERE is_active = 1 ORDER BY created_at DESC")
            return [cls.from_row(row) for row in cursor.fetchall()]
    
    def get_creator(self):
        return User.get_by_id(self.creator_id)
    
    def get_cards(self):
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT c.* FROM cards c
                JOIN airdrop_cards ac ON c.id = ac.card_id
                WHERE ac.airdrop_id = ? AND ac.is_reserved = 0
            """, (self.id,))
            return [Card.from_row(row) for row in cursor.fetchall()]
    
    def get_total_cards(self):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM airdrop_cards WHERE airdrop_id = ?", (self.id,))
            return cursor.fetchone()[0]
    
    def get_available_cards(self):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM airdrop_cards WHERE airdrop_id = ? AND is_reserved = 0", (self.id,))
            return cursor.fetchone()[0]
    
    def add_card(self, card_id: int):
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT OR IGNORE INTO airdrop_cards (airdrop_id, card_id)
                VALUES (?, ?)
            """, (self.id, card_id))
    
    def deactivate(self):
        self.is_active = False
        self.save()


class AirdropCard:
    def __init__(self, airdrop_id: int, card_id: int):
        self.airdrop_id = airdrop_id
        self.card_id = card_id
        self.is_reserved = False
        self.reserved_by = None
        self.reserved_at = None
        self.id = None
    
    def save(self):
        with get_db_cursor() as cursor:
            if self.id is None:
                cursor.execute("""
                    INSERT INTO airdrop_cards (airdrop_id, card_id, is_reserved, reserved_by, reserved_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (self.airdrop_id, self.card_id, self.is_reserved, self.reserved_by, self.reserved_at))
                self.id = cursor.lastrowid
            else:
                cursor.execute("""
                    UPDATE airdrop_cards 
                    SET is_reserved = ?, reserved_by = ?, reserved_at = ?
                    WHERE id = ?
                """, (self.is_reserved, self.reserved_by, self.reserved_at, self.id))
            return self
    
    @classmethod
    def from_row(cls, row):
        airdrop_card = cls(row['airdrop_id'], row['card_id'])
        airdrop_card.id = row['id']
        airdrop_card.is_reserved = bool(row['is_reserved'])
        airdrop_card.reserved_by = row['reserved_by']
        airdrop_card.reserved_at = row['reserved_at']
        return airdrop_card
    
    @classmethod
    def get_random_available_card(cls, airdrop_id: int):
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT ac.* FROM airdrop_cards ac
                WHERE ac.airdrop_id = ? AND ac.is_reserved = 0
                ORDER BY RANDOM() LIMIT 1
            """, (airdrop_id,))
            row = cursor.fetchone()
            return cls.from_row(row) if row else None
    
    def reserve_card(self, user_id: int):
        self.is_reserved = True
        self.reserved_by = user_id
        self.reserved_at = datetime.utcnow().isoformat()
        
        # Transfer card ownership
        card = Card.get_by_id(self.card_id)
        if card:
            card.owner_id = user_id
            card.save()
        
        self.save()
        return card
    
    def get_card(self):
        return Card.get_by_id(self.card_id)
    
    def get_reserved_user(self):
        if self.reserved_by:
            return User.get_by_id(self.reserved_by)
        return None
