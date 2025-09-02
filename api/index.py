import replicate
import fal_client
from flask import Flask, render_template, request, session, jsonify
import base64
import threading
import os

app = Flask(__name__, template_folder='../templates')
app.secret_key = 'banana-ai-character-generator-secret-key-2024'


# 웹 배포용 - 로컬 저장 제거

@app.route('/')
def index():
    return render_template('index.html')

# 웹 배포용 - 로컬 파일 서빙 제거

@app.route('/api/check_progress')
def check_progress():
    # 세션에서 진행 상황 확인 - 직접 API URL 반환
    result = {
        'result_image': session.get('result_image_ready', False),
        'result_image_2': session.get('result_image_2_ready', False), 
        'result_image_3': session.get('result_image_3_ready', False),
        'result_image_url': session.get('result_image_url'),
        'result_image_2_url': session.get('result_image_2_url'),
        'result_image_3_url': session.get('result_image_3_url'),
        'result_image_filename': session.get('result_image_filename'),
        'result_image_2_filename': session.get('result_image_2_filename'),
        'result_image_3_filename': session.get('result_image_3_filename')
    }
    
    # Gemini 다중 이미지 정보 추가
    gemini_all_urls = session.get('result_image_3_all_urls', [])
    if gemini_all_urls:
        result['result_image_3_all_urls'] = gemini_all_urls
        result['result_image_3_count'] = len(gemini_all_urls)
        result['result_image_3_filenames'] = session.get('result_image_3_filenames', [])
    
    return jsonify(result)

@app.route('/reset_on_upload', methods=['POST'])
def reset_on_upload():
    """원본 이미지 업로드 시 세션 초기화"""
    try:
        # 이미지 관련 세션 데이터 모두 삭제
        session_keys_to_clear = [
            'result_image_ready', 'result_image_2_ready', 'result_image_3_ready',
            'result_image_url', 'result_image_2_url', 'result_image_3_url',
            'result_image_filename', 'result_image_2_filename', 'result_image_3_filename',
            'result_image_3_all_urls', 'result_image_3_filenames'
        ]
        
        cleared_keys = []
        for key in session_keys_to_clear:
            if key in session:
                session.pop(key, None)
                cleared_keys.append(key)
        
        print(f"Cleared {len(cleared_keys)} session keys on upload: {cleared_keys}")
        
        return jsonify({
            'success': True, 
            'message': f'세션 초기화 완료 ({len(cleared_keys)}개 항목 삭제)',
            'cleared_keys': cleared_keys
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/generate', methods=['POST'])
def generate_image():
    try:
        # 진행 상태 초기화
        session['result_image_ready'] = False
        session['result_image_2_ready'] = False
        session['result_image_3_ready'] = False
        session.pop('result_image_url', None)
        session.pop('result_image_2_url', None)
        session.pop('result_image_3_url', None)
        session.pop('result_image_3_all_urls', None)
        
        # 비동기 처리를 위해 백그라운드 스레드로 시작
        import threading
        
        uploaded_file = request.files.get('image')
        
        if not uploaded_file or not uploaded_file.filename:
            return jsonify({'error': '이미지를 업로드해주세요.'}), 400
        
        # 이미지 데이터 준비
        image_data = uploaded_file.read()
        
        # 각 API를 별도 스레드로 실행
        thread1 = threading.Thread(target=process_replicate_api, args=(image_data,))
        thread2 = threading.Thread(target=process_fal_api, args=(image_data,))
        thread3 = threading.Thread(target=process_gemini_api, args=(image_data, uploaded_file.filename))
        
        thread1.start()
        thread2.start() 
        thread3.start()
        
        return jsonify({'success': True, 'message': '이미지 처리를 시작했습니다!'})
        
    except Exception as e:
        return jsonify({'error': f'오류가 발생했습니다: {str(e)}'}), 500

def process_replicate_api(image_data):
    try:
        # MIME 타입 결정 (기본값)
        mime_type = 'image/jpeg'
        
        # API 입력 파라미터 준비
        api_input = {
            "prompt": "Here's the full-body standing illustration of the character for a game dialogue window, keeping only the character with a transparent background.",
            "output_format": "png"
        }
        
        # base64 데이터 URI 생성
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        data_uri = f"data:{mime_type};base64,{image_base64}"
        api_input["image_input"] = [data_uri]
        
        # 1단계: Replicate API 호출 (캐릭터 생성)
        print("Step 1: Generating character...")
        output_character = replicate.run(
            "google/nano-banana",
            input=api_input
        )
        
        # 생성된 캐릭터 이미지 URL 획득
        character_url = str(output_character)
        
        # 2단계: 배경 제거 API 호출
        print("Step 2: Removing background...")
        
        # fal_client 진행 상황 처리 함수
        def on_queue_update(update):
            if isinstance(update, fal_client.InProgress):
                for log in update.logs:
                    print(log["message"])
        
        # Replicate 결과 URL을 배경 제거 API에 전달
        result = fal_client.subscribe(
            "fal-ai/bria/background/remove",
            arguments={
                "image_url": character_url
            },
            with_logs=True,
            on_queue_update=on_queue_update,
        )
        
        print("Background removal result:", result)
        
        # 첫 번째 이미지 완성 표시 - 직접 URL 저장
        session['result_image_url'] = result['image']['url']
        session['result_image_filename'] = 'mirai_replicate_default.png'
        session['result_image_ready'] = True
        
    except Exception as e:
        print(f"Replicate API error: {str(e)}")

def process_fal_api(image_data):
    try:
        # MIME 타입 결정
        mime_type = 'image/jpeg'
        
        # 원본 이미지를 base64로 인코딩
        original_base64 = base64.b64encode(image_data).decode('utf-8')
        original_data_uri = f"data:{mime_type};base64,{original_base64}"
        
        # fal_client 진행 상황 처리 함수
        def on_queue_update(update):
            if isinstance(update, fal_client.InProgress):
                for log in update.logs:
                    print(log["message"])
        
        # nano-banana/edit API 호출
        edit_result = fal_client.subscribe(
            "fal-ai/nano-banana/edit",
            arguments={
                "prompt": "Here's the full-body standing illustration of the character for a game dialogue window, keeping only the character with a transparent background.",
                "image_urls": [original_data_uri]
            },
            with_logs=True,
            on_queue_update=on_queue_update,
        )
        
        print("nano-banana/edit result:", edit_result)
        
        # 편집된 이미지의 배경 제거
        print("Removing background from edited image...")
        
        # FAL API 결과 URL을 배경 제거 API에 직접 전달
        edit_bg_removed_result = fal_client.subscribe(
            "fal-ai/bria/background/remove",
            arguments={
                "image_url": edit_result['images'][0]['url']
            },
            with_logs=True,
            on_queue_update=on_queue_update,
        )
        
        print("Edit background removal result:", edit_bg_removed_result)
        
        # 두 번째 이미지 완성 표시 - 직접 URL 저장
        session['result_image_2_url'] = edit_bg_removed_result['image']['url']
        session['result_image_2_filename'] = 'mirai_falai_default.png'
        session['result_image_2_ready'] = True
        
    except Exception as e:
        print(f"FAL API error: {str(e)}")

def process_gemini_api(image_data, filename):
    try:
        # MIME 타입 결정
        filename_lower = filename.lower()
        if filename_lower.endswith('.png'):
            mime_type = 'image/png'
        elif filename_lower.endswith('.jpg') or filename_lower.endswith('.jpeg'):
            mime_type = 'image/jpeg'
        elif filename_lower.endswith('.webp'):
            mime_type = 'image/webp'
        elif filename_lower.endswith('.gif'):
            mime_type = 'image/gif'
        else:
            mime_type = 'image/jpeg'  # 기본값
        
        # Gemini API 호출
        gemini_api_key = os.environ.get('GEMINI_API_KEY', 'AIzaSyBIFu5xH4JCu__xfvEnFG1GEQR3APZyKJI')
        gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image-preview:generateContent"
        
        gemini_headers = {
            'Content-Type': 'application/json',
            'X-goog-api-key': gemini_api_key
        }
        
        # 원본 이미지를 Gemini API 형식으로 준비
        image_base64_for_gemini = base64.b64encode(image_data).decode('utf-8')
        
        gemini_payload = {
            "contents": [{
                "parts": [
                    {
                        "text": "Here's the full-body standing illustration of the character for a game dialogue window, keeping only the character with a transparent background. Five standing illustrations should be generated with slight variations in expression and pose: Default, Smiling (happy), Sad, Angry (cute pouting), Embarrassed"
                    },
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": image_base64_for_gemini
                        }
                    }
                ]
            }]
        }
        
        import requests
        gemini_response = requests.post(gemini_url, headers=gemini_headers, json=gemini_payload)
        
        if gemini_response.status_code == 200:
            gemini_result = gemini_response.json()
            
            # base64 데이터 추출 - 여러 이미지 처리
            gemini_image_urls = []
            if 'candidates' in gemini_result and len(gemini_result['candidates']) > 0:
                candidate = gemini_result['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    # fal_client 진행 상황 처리 함수
                    def on_queue_update(update):
                        if isinstance(update, fal_client.InProgress):
                            for log in update.logs:
                                print(log["message"])
                    
                    for part_index, part in enumerate(candidate['content']['parts']):
                        if 'inlineData' in part:
                            print(f"Processing Gemini image {part_index + 1}...")
                            
                            # Gemini 이미지를 base64로 인코딩
                            gemini_image_data = base64.b64decode(part['inlineData']['data'])
                            gemini_base64_for_bg = base64.b64encode(gemini_image_data).decode('utf-8')
                            gemini_data_uri_for_bg = f"data:image/png;base64,{gemini_base64_for_bg}"
                            
                            # 각 Gemini 이미지의 배경 제거
                            print(f"Removing background from Gemini image {part_index + 1}...")
                            
                            # Gemini 이미지의 배경 제거
                            gemini_bg_removed_result = fal_client.subscribe(
                                "fal-ai/bria/background/remove",
                                arguments={
                                    "image_url": gemini_data_uri_for_bg
                                },
                                with_logs=True,
                                on_queue_update=on_queue_update,
                            )
                            
                            print(f"Gemini {part_index + 1} background removal result:", gemini_bg_removed_result)
                            
                            # 배경 제거된 이미지 URL 저장
                            gemini_image_urls.append(gemini_bg_removed_result['image']['url'])
                
                # 모든 Gemini 이미지 URL을 세션에 저장
                if gemini_image_urls:
                    # 감정별 파일명 생성
                    emotion_tags = ['default', 'happy', 'sad', 'angry', 'embarrassed']
                    filenames = []
                    for i in range(len(gemini_image_urls)):
                        emotion = emotion_tags[i] if i < len(emotion_tags) else f'emotion_{i+1}'
                        filenames.append(f'mirai_gemini_{emotion}.png')
                    
                    session['result_image_3_url'] = gemini_image_urls[0]  # 첫 번째 이미지
                    session['result_image_3_all_urls'] = gemini_image_urls  # 모든 이미지 URL
                    session['result_image_3_filename'] = filenames[0] if filenames else 'mirai_gemini_default.png'  # 첫 번째 파일명
                    session['result_image_3_filenames'] = filenames  # 모든 파일명
                    session['result_image_3_ready'] = True
                    print(f"Total {len(gemini_image_urls)} Gemini images processed with filenames: {filenames}")
        
    except Exception as e:
        print(f"Gemini API error: {str(e)}")

# Vercel 서버리스 함수
app = app