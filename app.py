import jwt
import requests
import os
import certifi
import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from pymongo import MongoClient 
from flask_cors import CORS
from pymongo import MongoClient

# .env 파일 로드
load_dotenv()

KAKAO_API_URL = os.getenv('KAKAO_API_URL')
KAKAO_API_KEY = os.getenv('KAKAO_API_KEY')

mongo_connect = os.getenv('DB_INFO')
client = MongoClient(mongo_connect , tlsCAFile=certifi.where())
db = client.sample_mflix

app = Flask(__name__)
CORS(app)

# 토큰 생성에 사용될 Secret Key를 flask 환경 변수에 등록
app.config.update(
            DEBUG = True,
            JWT_SECRET_KEY = "hello"
)

jwt = JWTManager(app)

@app.route('/')
def home():
    return render_template('index.html')


# 회원가입 함수
@app.route('/signup', methods=['POST'])
def sign_up():
    id = request.form['id']
    pw = request.form['pw']

    dup = list(db.users.find({'id': id}))
    if dup:
        return jsonify({'result': 'fail'})
    
    db.users.insert_one({'id': id, 'pw': pw})
    return jsonify({'result': 'success'})
    
# 회원가입 함수
@app.route('/signin', methods=['POST'])
def sign_in():
    id = request.form['id']
    pw = request.form['pw']
    
    dup = db.users.find_one({'id':id, 'pw': pw})
    
    if dup:
        return jsonify(result = "success", access_token = create_access_token(identity = id, expires_delta = datetime.timedelta(weeks=1)))
        
    else:
        return jsonify({'result': 'fail'})

# 로그인 이후 발급 된 토큰을 확인하고 메인 지도로 보내는 함수
@app.route('/user_only', methods=['GET'])
@jwt_required()
def login():
    return render_template('searchLocation.html')

@app.route('/getPath', methods=['GET'])
def detail():
    return render_template('getPath.html')


# 클라이언트로부터 검색어와 경위도를 받아 DB에 저장하고 반환하는 함수
@app.route('/keyword', methods=['POST'])
def save_keyword():
    keyword_receive = request.form.get('keyword_give')
    latitude = request.form.get('Lat')
    longitude = request.form.get('Lon')
    
    if not keyword_receive:
        return jsonify({'result': 'fail', 'msg': 'No keyword provided'}), 400
    
    existing_data = db.keywords.find_one({'keyword': keyword_receive}, {'_id': 0})
    
    if existing_data:
        return jsonify({'result': 'success', 'keydata': existing_data['data']})

    headers = {
        'Authorization': f'KakaoAK {KAKAO_API_KEY}'
    }
    params = {
        'query': keyword_receive,
        'y': latitude,
        'x': longitude,
        'radius': 700
    }
    response = requests.get(KAKAO_API_URL, headers=headers, params=params)
    
    if response.status_code != 200:
        return jsonify({'result': 'fail', 'msg': 'Kakao API request failed'}), response.status_code
    kakao_data = response.json().get('documents', [])
    if (kakao_data):
        db.keywords.insert_one({'keyword': keyword_receive, 'data': kakao_data})
        return jsonify({'result': 'success', 'keydata': kakao_data})
    else:
        return jsonify({'result': 'error', 'msg': '검색결과가 없습니다.'})


# 저장된 DB에서 상세보기를 선택한 키워드를 가진 세부필드를 클라이언트로 전송
@app.route('/keyword', methods=['GET'])
def search_keyword():
    place_name = request.args.get('keyword_give') 
    pipeline = [
        {"$match": {"data.place_name": place_name}},
        {"$project": {
            "_id": 0,
            "keyword": 1,
            "data": {
                "$filter": {
                    "input": "$data",
                    "as": "item",
                    "cond": {"$eq": ["$$item.place_name", place_name]}
                }
            }
        }}
    ]
    result = list(db.keywords.aggregate(pipeline))
    return jsonify({'result': 'success', 'data': result})


if __name__ == '__main__':  
    app.run('0.0.0.0',port=5000,debug=True)