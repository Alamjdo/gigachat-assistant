import os
import uuid
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import base64

app = Flask(__name__)
CORS(app)

# Authorization Key уже закодирован в base64
AUTH_KEY = "MDE5ZTQ2M2MtYWYxOS03YzYzLTkxZmQtMzkzYTFhZjQ4YzUxOjUwZDQ2ZDVhLTA1M2EtNDZhOS1hZmM3LTE4ZTM5YmY5ZmY4OQ=="

# Либо можно использовать Client ID + Client Secret отдельно
CLIENT_ID = "019e463c-af19-7c63-91fd-393a1af48c51"
CLIENT_SECRET = "50d46d5a-053a-46a9-afc7-18e39bf9ff89"

# Кэш для токена
cached_token = {"value": None, "expires_at": 0}

def get_gigachat_token():
    """Получает токен GigaChat с кэшированием"""
    global cached_token
    
    # Проверяем, жив ли текущий токен (с запасом 5 минут)
    if cached_token["value"] and cached_token["expires_at"] > datetime.now().timestamp() + 300:
        return cached_token["value"]
    
    # Используем готовый Authorization Key
    auth_string = AUTH_KEY
    
    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'RqUID': str(uuid.uuid4()),
        'Authorization': f'Basic {auth_string}'
    }
    data = {'scope': 'GIGACHAT_API_PERS'}
    
    try:
        response = requests.post(url, headers=headers, data=data, verify=False, timeout=30)
        if response.status_code == 200:
            token_data = response.json()
            cached_token["value"] = token_data["access_token"]
            cached_token["expires_at"] = datetime.now().timestamp() + token_data.get("expires_in", 1800)
            print("Токен GigaChat получен успешно")
            return cached_token["value"]
        else:
            print(f"Ошибка получения токена: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Исключение при получении токена: {e}")
        return None

def ask_gigachat(question):
    """Отправляет вопрос в GigaChat и возвращает ответ"""
    token = get_gigachat_token()
    if not token:
        return "Извините, сервис временно недоступен. Пожалуйста, попробуйте позже."
    
    url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {token}',
        'RqUID': str(uuid.uuid4())
    }
    
    payload = {
        "model": "GigaChat",
        "messages": [
            {
                "role": "system",
                "content": "Ты — полезный ассистент. Отвечай кратко, вежливо и по делу. Помогай находить банкоматы и отвечай на вопросы о работе сервиса."
            },
            {
                "role": "user",
                "content": question
            }
        ],
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, verify=False, timeout=60)
        if response.status_code == 200:
            result = response.json()
            answer = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            return answer if answer else "Не удалось получить ответ от нейросети."
        else:
            print(f"Ошибка GigaChat: {response.status_code} - {response.text}")
            return f"Ошибка при обращении к GigaChat. Код ошибки: {response.status_code}"
    except Exception as e:
        print(f"Исключение при запросе к GigaChat: {e}")
        return "Произошла ошибка при обращении к серверу ИИ."

@app.route('/health', methods=['GET'])
def health_check():
    """Эндпоинт для проверки работоспособности (для keep-alive)"""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

@app.route('/gigachat', methods=['POST'])
def gigachat_endpoint():
    """Основной эндпоинт для AI ассистента"""
    data = request.json
    question = data.get('question', '')
    
    if not question:
        return jsonify({"error": "Вопрос не может быть пустым"}), 400
    
    answer = ask_gigachat(question)
    return jsonify({"answer": answer})

@app.route('/', methods=['GET'])
def index():
    """Корневой эндпоинт"""
    return jsonify({
        "name": "GigaChat Assistant API",
        "status": "running",
        "endpoints": ["/gigachat", "/health"]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
