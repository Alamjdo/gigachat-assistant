import os
import uuid
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import base64
import csv
import io

app = Flask(__name__)
CORS(app)

AUTH_KEY = "MDE5ZTQ2M2MtYWYxOS03YzYzLTkxZmQtMzkzYTFhZjQ4YzUxOjUwZDQ2ZDVhLTA1M2EtNDZhOS1hZmM3LTE4ZTM5YmY5ZmY4OQ=="

cached_token = {"value": None, "expires_at": 0}

def get_gigachat_token():
    global cached_token
    if cached_token["value"] and cached_token["expires_at"] > datetime.now().timestamp() + 300:
        return cached_token["value"]
    
    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'RqUID': str(uuid.uuid4()),
        'Authorization': f'Basic {AUTH_KEY}'
    }
    data = {'scope': 'GIGACHAT_API_PERS'}
    
    try:
        response = requests.post(url, headers=headers, data=data, verify=False, timeout=30)
        if response.status_code == 200:
            token_data = response.json()
            cached_token["value"] = token_data["access_token"]
            cached_token["expires_at"] = datetime.now().timestamp() + token_data.get("expires_in", 1800)
            return cached_token["value"]
        return None
    except Exception as e:
        print(f"Ошибка: {e}")
        return None

def ask_gigachat(question):
    token = get_gigachat_token()
    if not token:
        return "Извините, сервис временно недоступен."
    
    url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {token}',
        'RqUID': str(uuid.uuid4())
    }
    
    payload = {
        "model": "GigaChat",
        "messages": [{"role": "user", "content": question}],
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, verify=False, timeout=60)
        if response.status_code == 200:
            result = response.json()
            return result.get('choices', [{}])[0].get('message', {}).get('content', "Не удалось получить ответ")
        return f"Ошибка: {response.status_code}"
    except Exception as e:
        return f"Ошибка: {str(e)}"

# ========== ЭНДПОИНТЫ ДЛЯ ФАЙЛОВ ==========

# Хранилище загруженных данных (в памяти)
uploaded_data = {}

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Загрузка файла"""
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "Файл не выбран"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "Файл не выбран"}), 400
    
    try:
        content = file.read().decode('utf-8')
        lines = content.split('\n')
        data = []
        
        # Парсим CSV
        if file.filename.endswith('.csv'):
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                data.append(row)
        else:
            # Для TXT файлов
            for i, line in enumerate(lines):
                if line.strip():
                    data.append({"line": i+1, "text": line.strip()})
        
        filename = file.filename
        uploaded_data[filename] = {
            'data': data,
            'timestamp': datetime.now().isoformat()
        }
        
        preview = data[:5] if len(data) > 5 else data
        
        return jsonify({
            "success": True,
            "filename": filename,
            "rows": len(data),
            "preview": preview
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/search-in-file', methods=['GET'])
def search_in_file():
    """Поиск в загруженном файле"""
    filename = request.args.get('filename', '')
    query = request.args.get('q', '')
    
    if not filename or not query:
        return jsonify({"success": False, "message": "Укажите файл и запрос"}), 400
    
    if filename not in uploaded_data:
        return jsonify({"success": False, "message": "Файл не найден"}), 404
    
    data = uploaded_data[filename]['data']
    q = query.lower()
    results = []
    
    for item in data:
        if q in str(item).lower():
            results.append(item)
        if len(results) >= 50:
            break
    
    return jsonify({"success": True, "data": results, "count": len(results)})

@app.route('/api/export', methods=['POST'])
def export_results():
    """Экспорт результатов в CSV"""
    data = request.json.get('data', [])
    if not data:
        return jsonify({"success": False, "message": "Нет данных"}), 400
    
    output = io.StringIO()
    
    if data and isinstance(data[0], dict):
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    else:
        writer = csv.writer(output)
        for item in data:
            if isinstance(item, dict):
                writer.writerow(item.values())
            else:
                writer.writerow([str(item)])
    
    output.seek(0)
    return jsonify({
        "success": True,
        "data": output.getvalue(),
        "message": f"Экспортировано {len(data)} записей"
    })

# ========== ОСНОВНЫЕ ЭНДПОИНТЫ ==========

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

@app.route('/gigachat', methods=['POST'])
def gigachat_endpoint():
    data = request.json
    question = data.get('question', '')
    if not question:
        return jsonify({"error": "Вопрос не может быть пустым"}), 400
    answer = ask_gigachat(question)
    return jsonify({"answer": answer})

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "name": "GigaChat Assistant API",
        "status": "running",
        "endpoints": ["/health", "/gigachat", "/api/upload", "/api/search-in-file", "/api/export"]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
