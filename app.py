import replicate
import fal_client
from flask import Flask, render_template, request, jsonify
import base64
import threading
import time

app = Flask(__name__)
app.secret_key = 'banana-ai-character-generator-secret-key-2024'

# 스레드 안전한 상태 저장용
class ThreadSafeState:
    def __init__(self):
        self._data = {}
        self._lock = threading.Lock()
        
    def set(self, key, value):
        with self._lock:
            self._data[key] = value
            
    def get(self, key, default=None):
        with self._lock:
            return self._data.get(key, default)
            
    def pop(self, key, default=None):
        with self._lock:
            return self._data.pop(key, default)

app_state = ThreadSafeState()

# 웹 배포용 - 로컬 저장 제거

@app.route('/')
def index():
    return render_template('index.html')

# 웹 배포용 - 로컬 파일 서빙 제거

@app.route('/api/check_progress')
def check_progress():
    # 상태에서 진행 상황 확인 - 직접 API URL 반환
    result = {
        'result_image': app_state.get('result_image_ready', False),
        'result_image_2': app_state.get('result_image_2_ready', False), 
        'result_image_3': app_state.get('result_image_3_ready', False),
        'result_image_url': app_state.get('result_image_url'),
        'result_image_2_url': app_state.get('result_image_2_url'),
        'result_image_3_url': app_state.get('result_image_3_url'),
        'result_image_filename': app_state.get('result_image_filename'),
        'result_image_2_filename': app_state.get('result_image_2_filename'),
        'result_image_3_filename': app_state.get('result_image_3_filename'),
        'processing_started': app_state.get('processing_started', False),
        'processing_timestamp': app_state.get('processing_timestamp'),
        'current_image_hash': app_state.get('current_image_hash'),
        'current_processing_id': app_state.get('current_processing_id'),
        'image_size': app_state.get('image_size'),
        'image_filename': app_state.get('image_filename')
    }
    
    # 에러 정보 추가
    errors = {}
    if app_state.get('result_image_error'):
        errors['replicate_error'] = app_state.get('result_image_error')
    if app_state.get('result_image_2_error'):
        errors['fal_error'] = app_state.get('result_image_2_error')
    if app_state.get('result_image_3_error'):
        errors['gemini_error'] = app_state.get('result_image_3_error')
    
    if errors:
        result['errors'] = errors
    
    # Gemini 다중 이미지 정보 추가
    gemini_all_urls = app_state.get('result_image_3_all_urls', [])
    gemini_all_filenames = app_state.get('result_image_3_filenames', [])
    if gemini_all_urls:
        result['result_image_3_all_urls'] = gemini_all_urls
        result['result_image_3_filenames'] = gemini_all_filenames
        result['result_image_3_count'] = len(gemini_all_urls)
    
    return jsonify(result)

@app.route('/reset_on_upload', methods=['POST'])
def reset_on_upload():
    """이미지 업로드시 기존 결과 초기화"""
    try:
        print("=== IMAGE UPLOAD RESET: CLEARING PREVIOUS RESULTS ===")
        
        # 1. 기존 결과만 초기화 (처리 상태는 유지)
        app_state.set('result_image_ready', False)
        app_state.set('result_image_2_ready', False)
        app_state.set('result_image_3_ready', False)
        
        # 2. 기존 URL들 제거
        app_state.pop('result_image_url', None)
        app_state.pop('result_image_2_url', None)
        app_state.pop('result_image_3_url', None)
        app_state.pop('result_image_3_all_urls', None)
        app_state.pop('result_image_3_count', None)
        
        # 3. 에러 상태 제거
        app_state.pop('result_image_error', None)
        app_state.pop('result_image_2_error', None)
        app_state.pop('result_image_3_error', None)
        
        # 4. 처리 상태 초기화
        app_state.set('processing_started', False)
        app_state.pop('processing_timestamp', None)
        app_state.pop('current_processing_id', None)
        
        print("✅ Previous results cleared for new image upload")
        
        return jsonify({
            'success': True, 
            'message': '새로운 이미지 업로드를 위해 이전 결과를 초기화했습니다.'
        })
        
    except Exception as e:
        print(f"Upload reset error: {str(e)}")
        return jsonify({'error': f'초기화 중 오류가 발생했습니다: {str(e)}'}), 500

@app.route('/generate', methods=['POST'])
def generate_image():
    try:
        # ============ 완전한 상태 및 캐시 초기화 ============
        print("=== COMPLETE RESET: CLEARING ALL STATES AND CACHE ===")
        
        # 1. 모든 기존 상태 완전 제거 (ThreadSafeState 내부 데이터 완전 초기화)
        with app_state._lock:
            old_keys = list(app_state._data.keys())
            app_state._data.clear()
            print(f"Cleared {len(old_keys)} cached state keys: {old_keys}")
        
        # 2. 새로운 요청용 초기 상태 설정
        app_state.set('result_image_ready', False)
        app_state.set('result_image_2_ready', False)
        app_state.set('result_image_3_ready', False)
        app_state.set('result_image_url', None)
        app_state.set('result_image_2_url', None)
        app_state.set('result_image_3_url', None)
        
        # 3. 가비지 컬렉션 강제 실행 (메모리 정리)
        import gc
        gc.collect()
        print("Forced garbage collection completed")
        
        print("=== COMPLETE RESET FINISHED - ALL CACHE CLEARED ===")
        
        # 새로운 처리 시작 표시
        app_state.set('processing_started', True)
        app_state.set('processing_timestamp', time.time())
        
        # 비동기 처리를 위해 백그라운드 스레드로 시작
        import threading
        
        uploaded_file = request.files.get('image')
        
        if not uploaded_file or not uploaded_file.filename:
            return jsonify({'error': '이미지를 업로드해주세요.'}), 400
        
        # ============ 강력한 이미지 파일 처리 (캐싱 완전 방지) ============
        print("=== READING NEW IMAGE FILE (ANTI-CACHE) ===")
        
        # 1. 파일 스트림을 여러 방법으로 리셋
        try:
            uploaded_file.seek(0, 0)  # 시작 지점으로 이동
            if hasattr(uploaded_file, 'stream'):
                uploaded_file.stream.seek(0, 0)  # 내부 스트림도 리셋
        except Exception as e:
            print(f"Stream reset warning: {e}")
        
        # 2. 첫 번째 읽기 시도
        image_data = uploaded_file.read()
        original_size = len(image_data)
        print(f"First read attempt - Size: {original_size} bytes, Filename: {uploaded_file.filename}")
        
        # 3. 파일 데이터가 비어있거나 의심스럽게 작으면 재시도
        if not image_data or original_size < 100:
            print("⚠️  Data seems invalid or cached, forcing re-read...")
            try:
                uploaded_file.seek(0, 0)
                if hasattr(uploaded_file, 'stream'):
                    uploaded_file.stream.seek(0, 0)
                # 강제로 다시 읽기
                image_data = uploaded_file.read()
                print(f"Second read attempt - Size: {len(image_data)} bytes")
            except Exception as e:
                print(f"Re-read failed: {e}")
        
        # 4. 데이터 유효성 최종 검증
        if not image_data or len(image_data) < 100:
            return jsonify({'error': '이미지 데이터를 읽을 수 없습니다. 브라우저를 새로고침하고 다시 시도해주세요.'}), 400
        
        # 5. 이미지 파일 헤더 및 무결성 검증
        file_header = image_data[:16] if len(image_data) >= 16 else b''
        print(f"File header (first 16 bytes): {file_header}")
        
        # 6. 고유 해시 생성으로 캐싱 감지
        import hashlib
        data_hash = hashlib.sha256(image_data).hexdigest()[:12]  # SHA256으로 더 정확하게
        current_timestamp = time.time()
        unique_id = f"{data_hash}_{int(current_timestamp * 1000)}"
        
        print(f"✅ NEW IMAGE CONFIRMED - Hash: {data_hash}, Size: {len(image_data)} bytes")
        print(f"✅ Unique processing ID: {unique_id}")
        
        # 7. 현재 이미지 정보 저장
        app_state.set('current_image_hash', data_hash)
        app_state.set('current_processing_id', unique_id)
        app_state.set('image_size', len(image_data))
        app_state.set('image_filename', uploaded_file.filename)
        
        # 각 API를 별도 스레드로 실행
        print(f"=== Starting background threads for image processing ===")
        print(f"Image data size: {len(image_data)} bytes")
        print(f"Image filename: {uploaded_file.filename}")
        
        thread1 = threading.Thread(target=process_replicate_api, args=(image_data,))
        thread2 = threading.Thread(target=process_fal_api, args=(image_data,))
        thread3 = threading.Thread(target=process_gemini_api, args=(image_data, uploaded_file.filename))
        
        print("Starting Replicate thread...")
        thread1.start()
        print("Starting FAL thread...")
        thread2.start() 
        print("Starting Gemini thread...")
        thread3.start()
        print("All threads started successfully!")
        
        return jsonify({'success': True, 'message': '이미지 처리를 시작했습니다!'})
        
    except Exception as e:
        return jsonify({'error': f'오류가 발생했습니다: {str(e)}'}), 500

def process_replicate_api(image_data):
    try:
        # 이미지 데이터 무결성 확인
        import hashlib
        data_hash = hashlib.md5(image_data).hexdigest()[:8]
        print(f"=== Starting Replicate API processing === (hash: {data_hash})")
        print(f"Replicate - Processing image data: {len(image_data)} bytes")
        
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
            "google/nano-banana:85b55096",
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
        
        # 첫 번째 이미지 완성 표시 - 상태에 저장 (Replicate = default 감정)
        app_state.set('result_image_url', result['image']['url'])
        app_state.set('result_image_filename', 'mirai_replicate_default.png')
        app_state.set('result_image_ready', True)
        print(f"✅ Replicate result saved as: mirai_replicate_default.png")
        
    except Exception as e:
        print(f"=== Replicate API ERROR ===: {str(e)}")
        import traceback
        traceback.print_exc()
        app_state.set('result_image_error', str(e))

def process_fal_api(image_data):
    try:
        # 이미지 데이터 무결성 확인
        import hashlib
        data_hash = hashlib.md5(image_data).hexdigest()[:8]
        print(f"=== Starting FAL API processing === (hash: {data_hash})")
        print(f"FAL - Processing image data: {len(image_data)} bytes")
        
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
        
        # 두 번째 이미지 완성 표시 - 상태에 저장 (FAL = default 감정)
        app_state.set('result_image_2_url', edit_bg_removed_result['image']['url'])
        app_state.set('result_image_2_filename', 'mirai_falai_default.png')
        app_state.set('result_image_2_ready', True)
        print(f"✅ FAL result saved as: mirai_falai_default.png")
        
    except Exception as e:
        print(f"=== FAL API ERROR ===: {str(e)}")
        import traceback
        traceback.print_exc()
        app_state.set('result_image_2_error', str(e))

def process_gemini_api(image_data, filename):
    try:
        # 이미지 데이터 무결성 확인  
        import hashlib
        data_hash = hashlib.md5(image_data).hexdigest()[:8]
        print(f"=== Starting Gemini API processing === (hash: {data_hash})")
        print(f"Gemini - Processing image data: {len(image_data)} bytes, filename: {filename}")
        
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
        gemini_api_key = "AIzaSyBIFu5xH4JCu__xfvEnFG1GEQR3APZyKJI"
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
                    # Gemini 5가지 감정 매핑 (Default, Happy, Sad, Angry, Embarrassed 순서)
                    emotion_tags = ['default', 'happy', 'sad', 'angry', 'embarrassed']
                    
                    # fal_client 진행 상황 처리 함수
                    def on_queue_update(update):
                        if isinstance(update, fal_client.InProgress):
                            for log in update.logs:
                                print(log["message"])
                    
                    gemini_filenames = []  # 파일명 저장용
                    
                    for part_index, part in enumerate(candidate['content']['parts']):
                        if 'inlineData' in part:
                            # 현재 감정 태그 결정 (5개를 초과하면 default로)
                            emotion_index = min(part_index, len(emotion_tags) - 1)
                            current_emotion = emotion_tags[emotion_index]
                            filename = f"mirai_gemini_{current_emotion}.png"
                            
                            print(f"Processing Gemini image {part_index + 1} ({current_emotion} emotion)...")
                            
                            # Gemini 이미지를 base64로 인코딩
                            gemini_image_data = base64.b64decode(part['inlineData']['data'])
                            gemini_base64_for_bg = base64.b64encode(gemini_image_data).decode('utf-8')
                            gemini_data_uri_for_bg = f"data:image/png;base64,{gemini_base64_for_bg}"
                            
                            # 각 Gemini 이미지의 배경 제거
                            print(f"Removing background from Gemini image {part_index + 1} ({current_emotion})...")
                            
                            # Gemini 이미지의 배경 제거
                            gemini_bg_removed_result = fal_client.subscribe(
                                "fal-ai/bria/background/remove",
                                arguments={
                                    "image_url": gemini_data_uri_for_bg
                                },
                                with_logs=True,
                                on_queue_update=on_queue_update,
                            )
                            
                            print(f"✅ Gemini {current_emotion} result saved as: {filename}")
                            print(f"Gemini {part_index + 1} background removal result:", gemini_bg_removed_result)
                            
                            # 배경 제거된 이미지 URL과 파일명 저장
                            gemini_image_urls.append(gemini_bg_removed_result['image']['url'])
                            gemini_filenames.append(filename)
                
                # 모든 Gemini 이미지 URL과 파일명을 상태에 저장
                if gemini_image_urls:
                    app_state.set('result_image_3_url', gemini_image_urls[0])  # 첫 번째 이미지
                    app_state.set('result_image_3_all_urls', gemini_image_urls)  # 모든 이미지 URL
                    app_state.set('result_image_3_filenames', gemini_filenames)  # 모든 파일명
                    app_state.set('result_image_3_filename', gemini_filenames[0])  # 첫 번째 파일명
                    app_state.set('result_image_3_ready', True)
                    print(f"✅ Total {len(gemini_image_urls)} Gemini images processed with filenames: {gemini_filenames}")
        
    except Exception as e:
        print(f"=== Gemini API ERROR ===: {str(e)}")
        import traceback
        traceback.print_exc()
        app_state.set('result_image_3_error', str(e))

if __name__ == '__main__':
    app.run(debug=True, port=5002)

# Vercel 배포를 위한 앱 객체 노출
application = app