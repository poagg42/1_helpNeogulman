import jwt
import requests
import os
import certifi
from dotenv import load_dotenv
from flask import Flask, render_template, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from pymongo import MongoClient 
from flask_cors import CORS
from pymongo import MongoClient

# .env 파일 로드
load_dotenv()

# 환경 변수 사용

KAKAO_API_URL = os.getenv('KAKAO_API_URL')
KAKAO_API_KEY = os.getenv('KAKAO_API_KEY')

mongo_connect = os.getenv('DB_INFO')
client = MongoClient(mongo_connect, tlsCAFile=certifi.where())
db = client.sample_mflix

app = Flask(__name__)
CORS(app)

#토큰 생성에 사용될 Secret Key를 flask 환경 변수에 등록
app.config.update(
            DEBUG = True,
            JWT_SECRET_KEY = "hello"
)
#JWT 확장 모듈을 flask 애플리케이션에 등록
jwt = JWTManager(app)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/getPath')
def path():
    return render_template('getPath.html')

@app.route('/signup', methods=['POST'])
def sign_up_test():
    id = request.form['id']
    pw = request.form['pw']
    
    # id 중복 확인
    dup = list(db.users.find({'id': id}))
    if dup:
        return jsonify({'result': 'fail'})
    
    db.users.insert_one({'id': id, 'pw': pw})
    return jsonify({'result': 'success'})
    

@app.route('/signin', methods=['POST'])
def sign_in():
    id = request.form['id']
    pw = request.form['pw']
    
    dup = db.users.find_one({'id':id, 'pw': pw})
    
    if dup:
        return jsonify(result = "success", access_token = create_access_token(identity = id, expires_delta = False))
        
    else:
        return jsonify({'result': 'fail'})
    
@app.route('/user_only', methods=['GET'])
@jwt_required()
def login():
    return render_template('searchLocation.html')


# 입력된 검색어 | 클라이언트 -> 서버
@app.route('/keyword', methods=['POST'])
def save_keyword():
    # 클라이언트로부터 데이터 받기
    keyword_receive = request.form.get('keyword_give')
    
    if not keyword_receive:
        return jsonify({'result': 'fail', 'msg': 'No keyword provided'}), 400
    
    existing_data = db.keywords.find_one({'keyword': keyword_receive}, {'_id': 0})
    
    if existing_data:
        # 이미 존재하는 데이터가 있으면 그대로 반환
        return jsonify({'result': 'success', 'keydata': existing_data['data']})
    
    # Kakao API 조회
    headers = {
        'Authorization': f'KakaoAK {KAKAO_API_KEY}'
    }
    params = {
        'query': keyword_receive
    }
    response = requests.get(KAKAO_API_URL, headers=headers, params=params)
    
    if response.status_code != 200:
        return jsonify({'result': 'fail', 'msg': 'Kakao API request failed'}), response.status_code

    # Kakao API 응답 데이터 MongoDB에 저장
    kakao_data = response.json().get('documents', [])
    db.keywords.insert_one({'keyword': keyword_receive, 'data': kakao_data})

    return jsonify({'result': 'success', 'keydata': kakao_data})

@app.route('/keyword', methods=['GET'])
def search_keyword():
    place_name = request.args.get('keyword_give')  # 클라이언트에서 전달된 place_name 파라미터
    pipeline = [
        {"$match": {"data.place_name": place_name}},  # data 배열에서 place_name이 일치하는 문서 선택
        {"$project": {
            "_id": 0,
            "keyword": 1,
            "data": {
                "$filter": {
                    "input": "$data",  # data 배열 필터링
                    "as": "item",
                    "cond": {"$eq": ["$$item.place_name", place_name]}  # place_name이 일치하는 요소만 선택
                }
            }
        }}
    ]
    result = list(db.keywords.aggregate(pipeline))
    return jsonify({'result': 'success', 'data': result})


# 상세보기 선택한 키워드 | 클라이언트 -> 서버
@app.route('/detailKeyword', methods=['POST'])
def save_detailkeyword():
    # 1. 클라이언트로부터 데이터를 받기
    deatilKeyword_receive = request.form['detailKeyword_give']  # 클라이언트로부터 keyword을 받는 부분
    
    detailKeyword = {'detailKeyword': deatilKeyword_receive}

    # 2. mongoDB에 데이터를 넣기
    db.detailKeywords.insert_one(detailKeyword)

    return jsonify({'result': 'success'})        

# 상세보기 데이터 서버 -> 클라이언트
@app.route('/detailKeyword', methods=['GET'])
def get_detailkeyword():
    # 1. mongoDB에서 _id 값을 제외한 모든 데이터 조회해오기 (Read)
    result = list(db.detailKeywords.find({}, {'_id': 0}))

    # 2. detailKeywords라는 키 값으로 detailKeyword 정보 보내주기
    return jsonify({'result': 'success', 'detailKeywords': result})



if __name__ == '__main__':  
    app.run('0.0.0.0',port=5000,debug=True)