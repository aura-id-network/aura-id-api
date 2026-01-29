import logging
import os
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from config import FLASK_HOST, FLASK_PORT, API_BASE_URL
from database import init_db, User, Card, Collection

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
        "version": "1.2.0",
        "endpoints": [
            "GET /api/health",
            "POST /api/check-card",
            "POST /api/check-collection",
            "GET /api/collections",
            "GET /api/collections/<id>",
            "GET /api/cards/<access_key>",
            "GET /api/user/<telegram_id>/cards",
            "POST /api/user/aura",
            "GET /api/collections/<id>/available",
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
                "access_key": "ABCD-EFGH-IJKL",
                "star_price": 100,
                "is_purchased": false,
                "collection_id": 1,
                "collection_name": "Collection Name",
                "collection_author": "Author Name"
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
            # Get collection info
            collection_name = None
            collection_author = None
            if card.collection_id:
                collection = Collection.get_by_id(card.collection_id)
                if collection:
                    collection_name = collection.name
                    author = collection.get_author()
                    collection_author = author.first_name if author else "Unknown"
            
            card_data.append({
                "id": card.id,
                "card_number": card.card_number,
                "name": card.name,
                "access_key": card.access_key,
                "registration_date": card.registration_date,
                "star_price": getattr(card, 'star_price', 1),
                "is_purchased": getattr(card, 'is_purchased', False),
                "collection_id": card.collection_id,
                "collection_name": collection_name,
                "collection_author": collection_author
            })
        
        return jsonify({
            "has_card": len(cards) > 0,
            "card_count": len(cards),
            "cards": card_data,
            "message": f"Found {len(cards)} cards"
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
            "card_count": 5,
            "aura_balance": 1000
        },
        "cards": [
            {
                "id": 1,
                "card_number": 1,
                "name": "Card Name",
                "access_key": "ABCD-EFGH-IJKL",
                "registration_date": "01.01.2024",
                "collection_id": 1,
                "collection_name": "Collection Name",
                "star_price": 100,
                "is_purchased": false,
                "can_edit": true,
                "can_trade": true
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
            # Get collection info
            collection_name = None
            if card.collection_id:
                collection = Collection.get_by_id(card.collection_id)
                if collection:
                    collection_name = collection.name
            
            # Check if user can edit/trade the card
            from utils import can_edit_card
            can_edit = can_edit_card(card, telegram_id)
            can_trade = not getattr(card, 'is_purchased', False)
            
            card_data.append({
                "id": card.id,
                "card_number": card.card_number,
                "name": card.name,
                "access_key": card.access_key,
                "registration_date": card.registration_date,
                "collection_id": card.collection_id,
                "collection_name": collection_name,
                "star_price": getattr(card, 'star_price', 1),
                "is_purchased": getattr(card, 'is_purchased', False),
                "can_edit": can_edit,
                "can_trade": can_trade
            })
        
        return jsonify({
            "user": {
                "telegram_id": telegram_id,
                "card_count": len(cards),
                "aura_balance": user.aura_balance
            },
            "cards": card_data
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/user/aura', methods=['POST'])
def get_user_aura():
    """
    Получить баланс аур пользователя
    
    Request body:
    {
        "telegram_id": 123456789
    }
    
    Response:
    {
        "telegram_id": 123456789,
        "aura_balance": 1000,
        "username": "username",
        "first_name": "John"
    }
    """
    try:
        data = request.get_json()
        if not data or 'telegram_id' not in data:
            return jsonify({"error": "telegram_id is required"}), 400
        
        telegram_id = int(data['telegram_id'])
        
        user = User.get_by_telegram_id(telegram_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        return jsonify({
            "telegram_id": telegram_id,
            "aura_balance": user.aura_balance,
            "username": user.username,
            "first_name": user.first_name
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/collections/<int:collection_id>/available', methods=['GET'])
def get_available_collection_cards(collection_id):
    """
    Получить только доступные для покупки карты из коллекции
    
    Response:
    {
        "collection_id": 1,
        "available_cards": [
            {
                "id": 1,
                "card_number": 1,
                "name": "Card Name",
                "access_key": "ABCD-EFGH-IJKL",
                "star_price": 100
            }
        ],
        "count": 3
    }
    """
    try:
        collection = Collection.get_by_id(collection_id)
        if not collection:
            return jsonify({"error": "Collection not found"}), 404
        
        # Get only available cards (not purchased)
        all_cards = collection.get_cards()
        available_cards = [card for card in all_cards if not getattr(card, 'is_purchased', False)]
        
        card_data = []
        for card in available_cards:
            card_data.append({
                "id": card.id,
                "card_number": card.card_number,
                "name": card.name,
                "access_key": card.access_key,
                "star_price": getattr(card, 'star_price', 1)
            })
        
        return jsonify({
            "collection_id": collection_id,
            "available_cards": card_data,
            "count": len(card_data)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Keep existing endpoints with updates for new fields
@app.route('/api/check-collection', methods=['POST'])
def check_collection():
    """Check collection cards with new fields support"""
    try:
        data = request.get_json()
        if not data or 'telegram_id' not in data or 'collection_access_key' not in data:
            return jsonify({"error": "telegram_id and collection_access_key are required"}), 400
        
        telegram_id = int(data['telegram_id'])
        collection_access_key = data['collection_access_key']
        
        user = User.get_by_telegram_id(telegram_id)
        if not user:
            return jsonify({"has_collection_card": False, "collection": None, "cards": []})
        
        collection = Collection.get_by_access_key(collection_access_key)
        if not collection:
            return jsonify({"has_collection_card": False, "collection": None, "cards": []})
        
        collection_cards = collection.get_cards()
        user_cards_in_collection = []
        
        for card in collection_cards:
            if card.owner_id == user.id:
                user_cards_in_collection.append({
                    "id": card.id,
                    "card_number": card.card_number,
                    "name": card.name,
                    "access_key": card.access_key,
                    "registration_date": card.registration_date,
                    "star_price": getattr(card, 'star_price', 1),
                    "is_purchased": getattr(card, 'is_purchased', False)
                })
        
        author = collection.get_author()
        author_name = author.first_name if author else "Unknown"
        
        collection_data = {
            "id": collection.id,
            "name": collection.name,
            "description": collection.description,
            "author_id": collection.author_id,
            "author_name": author_name,
            "star_price": collection.star_price,
            "link_id": collection.link_id
        }
        
        return jsonify({
            "has_collection_card": len(user_cards_in_collection) > 0,
            "collection": collection_data,
            "cards": user_cards_in_collection
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/collections', methods=['GET'])
def get_collections():
    """Get collections with availability info"""
    try:
        from database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT c.id, c.name, c.description, c.star_price, c.link_id, c.author_id,
                   COUNT(cards.id) as total_cards,
                   SUM(CASE WHEN cards.is_purchased = 0 THEN 1 ELSE 0 END) as available_cards
            FROM collections c
            LEFT JOIN cards ON c.id = cards.collection_id
            GROUP BY c.id, c.name, c.description, c.star_price, c.link_id, c.author_id
            ORDER BY c.created_at DESC
        """)
        
        collections = []
        for row in cursor.fetchall():
            author = User.get_by_id(row[5])
            author_name = author.first_name if author else "Unknown"
            
            collections.append({
                "id": row[0],
                "name": row[1],
                "description": row[2] or "",
                "star_price": row[3],
                "link_id": row[4],
                "author_id": row[5],
                "author_name": author_name,
                "total_cards": row[6],
                "available_cards": row[7]
            })
        
        conn.close()
        return jsonify({"collections": collections, "count": len(collections)})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/collections/<int:collection_id>', methods=['GET'])
def get_collection(collection_id):
    """Get collection with new fields"""
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
                "registration_date": card.registration_date,
                "star_price": getattr(card, 'star_price', 1),
                "is_purchased": getattr(card, 'is_purchased', False),
                "is_available": not getattr(card, 'is_purchased', False)
            })
        
        author = collection.get_author()
        author_name = author.first_name if author else "Unknown"
        
        collection_data = {
            "id": collection.id,
            "name": collection.name,
            "description": collection.description or "",
            "star_price": collection.star_price,
            "link_id": collection.link_id,
            "author_id": collection.author_id,
            "author_name": author_name,
            "cards": card_data
        }
        
        return jsonify({"collection": collection_data})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/cards/<access_key>', methods=['GET'])
def get_card_by_access_key(access_key):
    """Get card with new fields"""
    try:
        from database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, card_number, name, access_key, registration_date, 
                   collection_id, owner_id, star_price, is_purchased
            FROM cards 
            WHERE access_key = ?
        """, (access_key,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({"error": "Card not found"}), 404
        
        collection_name = None
        if row[5]:  # collection_id
            collection = Collection.get_by_id(row[5])
            if collection:
                collection_name = collection.name
        
        card_data = {
            "id": row[0],
            "card_number": row[1],
            "name": row[2],
            "access_key": row[3],
            "registration_date": row[4],
            "collection_id": row[5],
            "collection_name": collection_name,
            "owner_id": row[6],
            "star_price": row[7] if row[7] is not None else 1,
            "is_purchased": bool(row[8]) if row[8] is not None else False
        }
        
        return jsonify({"card": card_data})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/docs', methods=['GET'])
def api_docs():
    """Updated API documentation"""
    return jsonify({
        "title": "AURA Cards API",
        "version": "1.2.0",
        "description": "API для интеграции с AURA Cards - системой генерации ID карт с поддержкой коллекций",
        "base_url": API_BASE_URL,
        "endpoints": [
            {
                "path": "/api/health",
                "method": "GET",
                "description": "Проверка работоспособности API",
                "example": f"{API_BASE_URL}/api/health"
            },
            {
                "path": "/api/check-card",
                "method": "POST",
                "description": "Проверить наличие карт у пользователя",
                "example": {
                    "url": f"{API_BASE_URL}/api/check-card",
                    "body": {"telegram_id": 123456789}
                }
            },
            {
                "path": "/api/user/<telegram_id>/cards",
                "method": "GET",
                "description": "Получить все карты пользователя с правами",
                "example": f"{API_BASE_URL}/api/user/123456789/cards"
            },
            {
                "path": "/api/user/aura",
                "method": "POST",
                "description": "Получить баланс аур пользователя",
                "example": {
                    "url": f"{API_BASE_URL}/api/user/aura",
                    "body": {"telegram_id": 123456789}
                }
            },
            {
                "path": "/api/collections/<id>/available",
                "method": "GET",
                "description": "Получить доступные для покупки карты из коллекции",
                "example": f"{API_BASE_URL}/api/collections/1/available"
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
