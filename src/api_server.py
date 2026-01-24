import logging
import os
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from config import FLASK_HOST, FLASK_PORT, API_BASE_URL
from database import init_db, User, Card, Collection, Airdrop, AirdropCard

# Initialize Flask app
app = Flask(__name__)

# Configure CORS for websites
CORS(app, resources={
    r"/api/*": {
        "origins": ["*"],  # Allow all origins for websites
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

@app.route('/api/health', methods=['GET'])
def health_check():
    """Проверка работы API"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.1.0",
        "endpoints": [
            "GET /api/health",
            "POST /api/check-card",
            "POST /api/check-collection",
            "POST /api/check-airdrop",
            "GET /api/collections",
            "GET /api/collections/<id>",
            "GET /api/cards/<access_key>",
            "GET /api/user/<telegram_id>/cards",
            "GET /api/docs"
        ]
    })

@app.route('/api/check-card', methods=['POST'])
def check_card():
    """
    Проверяет наличие любой карты у пользователя
    
    Request body:
    {
        "telegram_id": 123456789
    }
    
    Response:
    {
        "has_card": true,
        "card_count": 5,
        "cards": [
            {
                "id": 1,
                "card_number": 1,
                "name": "Card Name",
                "access_key": "ABCD-EFGH-IJKL"
            }
        ]
    }
    """
    try:
        data = request.get_json()
        if not data or 'telegram_id' not in data:
            return jsonify({"error": "telegram_id is required"}), 400
        
        telegram_id = int(data['telegram_id'])
        
        # Получаем пользователя
        user = User.get_by_telegram_id(telegram_id)
        if not user:
            return jsonify({
                "has_card": False,
                "card_count": 0,
                "cards": [],
                "message": "User not found"
            })
        
        # Получаем все карты пользователя
        cards = user.get_cards()
        
        # Формируем ответ
        card_data = []
        for card in cards:
            card_data.append({
                "id": card.id,
                "card_number": card.card_number,
                "name": card.name,
                "access_key": card.access_key,
                "registration_date": card.registration_date,
                "collection_id": card.collection_id
            })
        
        return jsonify({
            "has_card": len(cards) > 0,
            "card_count": len(cards),
            "cards": card_data,
            "message": f"Found {len(cards)} cards"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/check-collection', methods=['POST'])
def check_collection():
    """
    Проверяет наличие карты из указанной коллекции у пользователя
    
    Request body:
    {
        "telegram_id": 123456789,
        "collection_access_key": "ABCD-EFGH-IJKL"
    }
    
    Response:
    {
        "has_collection_card": true,
        "collection": {
            "id": 1,
            "name": "Collection Name",
            "description": "Description"
        },
        "cards": [
            {
                "id": 1,
                "card_number": 1,
                "name": "Card Name",
                "access_key": "ABCD-EFGH-IJKL"
            }
        ]
    }
    """
    try:
        data = request.get_json()
        if not data or 'telegram_id' not in data or 'collection_access_key' not in data:
            return jsonify({"error": "telegram_id and collection_access_key are required"}), 400
        
        telegram_id = int(data['telegram_id'])
        collection_access_key = data['collection_access_key']
        
        # Получаем пользователя
        user = User.get_by_telegram_id(telegram_id)
        if not user:
            return jsonify({
                "has_collection_card": False,
                "collection": None,
                "cards": [],
                "message": "User not found"
            })
        
        # Ищем коллекцию по access key
        collection = Collection.get_by_access_key(collection_access_key)
        if not collection:
            return jsonify({
                "has_collection_card": False,
                "collection": None,
                "cards": [],
                "message": "Collection not found"
            })
        
        # Получаем все карты коллекции
        collection_cards = collection.get_cards()
        
        # Проверяем, есть ли у пользователя карты из этой коллекции
        user_cards_in_collection = []
        for card in collection_cards:
            if card.owner_id == user.id:
                user_cards_in_collection.append({
                    "id": card.id,
                    "card_number": card.card_number,
                    "name": card.name,
                    "access_key": card.access_key,
                    "registration_date": card.registration_date
                })
        
        # Формируем ответ
        collection_data = {
            "id": collection.id,
            "name": collection.name,
            "description": collection.description,
            "author_id": collection.author_id,
            "star_price": collection.star_price,
            "link_id": collection.link_id
        }
        
        return jsonify({
            "has_collection_card": len(user_cards_in_collection) > 0,
            "collection": collection_data,
            "cards": user_cards_in_collection,
            "message": f"Found {len(user_cards_in_collection)} cards from collection"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/collections', methods=['GET'])
def get_collections():
    """
    Получить список всех публичных коллекций
    
    Response:
    {
        "collections": [
            {
                "id": 1,
                "name": "Collection Name",
                "description": "Description",
                "star_price": 100,
                "link_id": "abc123",
                "card_count": 5
            }
        ]
    }
    """
    try:
        from database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT c.id, c.name, c.description, c.star_price, c.link_id,
                   COUNT(cards.id) as card_count
            FROM collections c
            LEFT JOIN cards ON c.id = cards.collection_id
            GROUP BY c.id, c.name, c.description, c.star_price, c.link_id
            ORDER BY c.created_at DESC
        """)
        
        collections = []
        for row in cursor.fetchall():
            collections.append({
                "id": row[0],
                "name": row[1],
                "description": row[2] or "",
                "star_price": row[3],
                "link_id": row[4],
                "card_count": row[5]
            })
        
        conn.close()
        
        return jsonify({
            "collections": collections,
            "count": len(collections)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/collections/<int:collection_id>', methods=['GET'])
def get_collection(collection_id):
    """
    Получить детальную информацию о коллекции
    
    Response:
    {
        "collection": {
            "id": 1,
            "name": "Collection Name",
            "description": "Description",
            "star_price": 100,
            "link_id": "abc123",
            "author_id": 123,
            "cards": [
                {
                    "id": 1,
                    "card_number": 1,
                    "name": "Card Name",
                    "access_key": "ABCD-EFGH-IJKL",
                    "registration_date": "01.01.2024"
                }
            ]
        }
    }
    """
    try:
        collection = Collection.get_by_id(collection_id)
        if not collection:
            return jsonify({"error": "Collection not found"}), 404
        
        cards = collection.get_cards()
        card_data = []
        
        for card in cards:
            card_data.append({
                "id": card.id,
                "card_number": card.card_number,
                "name": card.name,
                "access_key": card.access_key,
                "registration_date": card.registration_date
            })
        
        collection_data = {
            "id": collection.id,
            "name": collection.name,
            "description": collection.description or "",
            "star_price": collection.star_price,
            "link_id": collection.link_id,
            "author_id": collection.author_id,
            "cards": card_data
        }
        
        return jsonify({
            "collection": collection_data
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/cards/<access_key>', methods=['GET'])
def get_card_by_access_key(access_key):
    """
    Получить карту по access key
    
    Response:
    {
        "card": {
            "id": 1,
            "card_number": 1,
            "name": "Card Name",
            "access_key": "ABCD-EFGH-IJKL",
            "registration_date": "01.01.2024",
            "collection_id": 1,
            "owner_id": 123
        }
    }
    """
    try:
        from database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, card_number, name, access_key, registration_date, 
                   collection_id, owner_id
            FROM cards 
            WHERE access_key = ?
        """, (access_key,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({"error": "Card not found"}), 404
        
        card_data = {
            "id": row[0],
            "card_number": row[1],
            "name": row[2],
            "access_key": row[3],
            "registration_date": row[4],
            "collection_id": row[5],
            "owner_id": row[6]
        }
        
        return jsonify({
            "card": card_data
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/user/<int:telegram_id>/cards', methods=['GET'])
def get_user_cards(telegram_id):
    """
    Получить все карты пользователя по telegram_id
    
    Response:
    {
        "user": {
            "telegram_id": 123456789,
            "card_count": 5
        },
        "cards": [
            {
                "id": 1,
                "card_number": 1,
                "name": "Card Name",
                "access_key": "ABCD-EFGH-IJKL",
                "registration_date": "01.01.2024",
                "collection_id": 1
            }
        ]
    }
    """
    try:
        user = User.get_by_telegram_id(telegram_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        cards = user.get_cards()
        card_data = []
        
        for card in cards:
            card_data.append({
                "id": card.id,
                "card_number": card.card_number,
                "name": card.name,
                "access_key": card.access_key,
                "registration_date": card.registration_date,
                "collection_id": card.collection_id
            })
        
        return jsonify({
            "user": {
                "telegram_id": telegram_id,
                "card_count": len(cards)
            },
            "cards": card_data
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/check-airdrop', methods=['POST'])
def check_airdrop():
    """
    Проверяет наличие карт из указанного аирдропа у пользователя
    
    Request body:
    {
        "telegram_id": 123456789,
        "airdrop_id": 1
    }
    
    Response:
    {
        "has_airdrop_card": true,
        "can_claim_more": false,
        "airdrop": {
            "id": 1,
            "name": "Airdrop Name",
            "description": "Description",
            "creator_id": 123,
            "total_cards": 10,
            "available_cards": 5,
            "is_active": true
        },
        "user_cards": [
            {
                "id": 1,
                "card_number": 1,
                "name": "Card Name",
                "access_key": "ABCD-EFGH-IJKL",
                "registration_date": "01.01.2024"
            }
        ],
        "claimed_cards": 2
    }
    """
    try:
        data = request.get_json()
        if not data or 'telegram_id' not in data or 'airdrop_id' not in data:
            return jsonify({"error": "telegram_id and airdrop_id are required"}), 400
        
        telegram_id = int(data['telegram_id'])
        airdrop_id = int(data['airdrop_id'])
        
        # Получаем пользователя
        user = User.get_by_telegram_id(telegram_id)
        if not user:
            return jsonify({
                "has_airdrop_card": False,
                "airdrop": None,
                "user_cards": [],
                "claimed_cards": 0,
                "message": "User not found"
            })
        
        # Получаем аирдроп
        airdrop = Airdrop.get_by_id(airdrop_id)
        if not airdrop:
            return jsonify({
                "has_airdrop_card": False,
                "airdrop": None,
                "user_cards": [],
                "claimed_cards": 0,
                "message": "Airdrop not found"
            })
        
        # Получаем все карты пользователя
        user_cards = user.get_cards()
        
        # Получаем все карты из аирдропа
        from database import get_db_cursor
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT c.* FROM cards c
                JOIN airdrop_cards ac ON c.id = ac.card_id
                WHERE ac.airdrop_id = ?
            """, (airdrop_id,))
            airdrop_card_rows = cursor.fetchall()
            airdrop_cards = [Card.from_row(row) for row in airdrop_card_rows]
        
        # Находим карты пользователя из этого аирдропа
        user_airdrop_cards = []
        for card in user_cards:
            if any(card.id == acard.id for acard in airdrop_cards):
                user_airdrop_cards.append({
                    "id": card.id,
                    "card_number": card.card_number,
                    "name": card.name,
                    "access_key": card.access_key,
                    "registration_date": card.registration_date,
                    "collection_id": card.collection_id
                })
        
        # Получаем количество забранных карт
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) FROM airdrop_cards 
                WHERE airdrop_id = ? AND is_reserved = 1
            """, (airdrop_id,))
            claimed_cards = cursor.fetchone()[0]
        
        # Формируем информацию об аирдропе
        airdrop_info = {
            "id": airdrop.id,
            "name": airdrop.name,
            "description": airdrop.description or "",
            "creator_id": airdrop.creator_id,
            "total_cards": airdrop.get_total_cards(),
            "available_cards": airdrop.get_available_cards(),
            "is_active": airdrop.is_active,
            "created_at": airdrop.created_at
        }
        
        return jsonify({
            "has_airdrop_card": len(user_airdrop_cards) > 0,
            "can_claim_more": len(user_airdrop_cards) == 0 and airdrop.is_active,
            "airdrop": airdrop_info,
            "user_cards": user_airdrop_cards,
            "claimed_cards": claimed_cards,
            "message": f"Found {len(user_airdrop_cards)} cards from airdrop {airdrop_id}"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/docs', methods=['GET'])
def api_docs():
    """
    API документация
    
    Response:
    {
        "title": "AURA Cards API",
        "version": "1.1.0",
        "description": "API для интеграции с AURA Cards",
        "endpoints": [...]
    }
    """
    return jsonify({
        "title": "AURA Cards API",
        "version": "1.1.0",
        "description": "API для интеграции с AURA Cards - системой генерации ID карт",
        "base_url": API_BASE_URL,
        "endpoints": [
            {
                "path": "/api/health",
                "method": "GET",
                "description": "Проверка работоспособности API",
                "parameters": [],
                "example": f"{API_BASE_URL}/api/health"
            },
            {
                "path": "/api/check-card",
                "method": "POST",
                "description": "Проверить наличие карт у пользователя",
                "parameters": [
                    {"name": "telegram_id", "type": "integer", "required": True}
                ],
                "example": {
                    "url": f"{API_BASE_URL}/api/check-card",
                    "body": {"telegram_id": 123456789}
                }
            },
            {
                "path": "/api/check-collection",
                "method": "POST", 
                "description": "Проверить наличие карт из коллекции у пользователя",
                "parameters": [
                    {"name": "telegram_id", "type": "integer", "required": True},
                    {"name": "collection_access_key", "type": "string", "required": True}
                ],
                "example": {
                    "url": f"{API_BASE_URL}/api/check-collection",
                    "body": {
                        "telegram_id": 123456789,
                        "collection_access_key": "ABCD-EFGH-IJKL"
                    }
                }
            },
            {
                "path": "/api/check-airdrop",
                "method": "POST", 
                "description": "Проверить наличие карт из аирдропа у пользователя",
                "parameters": [
                    {"name": "telegram_id", "type": "integer", "required": True},
                    {"name": "airdrop_id", "type": "integer", "required": True}
                ],
                "example": {
                    "url": f"{API_BASE_URL}/api/check-airdrop",
                    "body": {
                        "telegram_id": 123456789,
                        "airdrop_id": 1
                    }
                }
            },
            {
                "path": "/api/collections",
                "method": "GET",
                "description": "Получить список всех коллекций",
                "parameters": [],
                "example": f"{API_BASE_URL}/api/collections"
            },
            {
                "path": "/api/collections/<id>",
                "method": "GET", 
                "description": "Получить детальную информацию о коллекции",
                "parameters": [
                    {"name": "id", "type": "integer", "required": True}
                ],
                "example": f"{API_BASE_URL}/api/collections/1"
            },
            {
                "path": "/api/cards/<access_key>",
                "method": "GET",
                "description": "Получить карту по access key",
                "parameters": [
                    {"name": "access_key", "type": "string", "required": True}
                ],
                "example": f"{API_BASE_URL}/api/cards/ABCD-EFGH-IJKL"
            },
            {
                "path": "/api/user/<telegram_id>/cards",
                "method": "GET",
                "description": "Получить все карты пользователя",
                "parameters": [
                    {"name": "telegram_id", "type": "integer", "required": True}
                ],
                "example": f"{API_BASE_URL}/api/user/123456789/cards"
            }
        ]
    })

def run_api_server():
    """Запуск API сервера"""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Initialize database
    init_db()
    
    logger.info(f"Starting AURA Cards API server on {FLASK_HOST}:{FLASK_PORT}")
    logger.info(f"API documentation available at {API_BASE_URL}/api/docs")
    
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)

if __name__ == "__main__":
    run_api_server()
