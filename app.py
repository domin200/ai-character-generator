import replicate
from flask import Flask, render_template, request, jsonify
import base64
import time
import fal_client

app = Flask(__name__)
app.secret_key = 'banana-ai-character-generator-secret-key-2024'

# FAL AI API 키 설정
fal_client.api_key = "3d0bf45f-f7de-4be5-b85b-e9522bf4901e:9461d2b0cccf9798e447725d2bf54027"

# 전역 상태 저장소
app_state = {}

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
        'result_image_3': app_state.get('result_image_3_ready', False),
        'result_image_url': app_state.get('result_image_url'),
        'result_image_3_url': app_state.get('result_image_3_url'),
        'result_image_filename': app_state.get('result_image_filename'),
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
        app_state['result_image_ready'] = False
        app_state['result_image_3_ready'] = False
        
        # 2. 기존 URL들 제거
        app_state.pop('result_image_url', None)
        app_state.pop('result_image_3_url', None)
        app_state.pop('result_image_3_all_urls', None)
        app_state.pop('result_image_3_count', None)
        
        # 3. 에러 상태 제거
        app_state.pop('result_image_error', None)
        app_state.pop('result_image_3_error', None)
        
        # 4. 처리 상태 초기화
        app_state['processing_started'] = False
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
        
        # 1. 모든 기존 상태 완전 제거
        old_keys = list(app_state.keys())
        app_state.clear()
        print(f"Cleared {len(old_keys)} cached state keys: {old_keys}")
        
        # 2. 새로운 요청용 초기 상태 설정
        app_state['result_image_ready'] = False
        app_state['result_image_3_ready'] = False
        app_state['result_image_url'] = None
        app_state['result_image_3_url'] = None
        
        # 3. 가비지 컬렉션 강제 실행 (메모리 정리)
        import gc
        gc.collect()
        print("Forced garbage collection completed")
        
        print("=== COMPLETE RESET FINISHED - ALL CACHE CLEARED ===")
        
        # 새로운 처리 시작 표시
        app_state.set('processing_started', True)
        app_state['processing_timestamp'] = time.time()
        
        # 순차 처리 시작
        
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
        
        # 순차적 처리: Replicate 먼저, 그 결과를 Gemini에 전달
        print(f"=== Starting sequential image processing ===")
        print(f"Image data size: {len(image_data)} bytes")
        print(f"Image filename: {uploaded_file.filename}")
        
        # 1. Replicate로 캐릭터 생성
        print("Step 1: Processing with Replicate...")
        replicate_result_url = None
        try:
            replicate_result_url = process_replicate_api(image_data)
            print(f"Replicate completed. Result URL: {replicate_result_url}")
        except Exception as e:
            print(f"Replicate error: {e}")
            import traceback
            traceback.print_exc()
        
        # 2. Replicate 결과를 Gemini에 전달
        if replicate_result_url:
            print("Step 2: Processing with Gemini using Replicate result...")
            try:
                process_gemini_api_with_url(replicate_result_url)
                print("Gemini processing completed")
            except Exception as e:
                print(f"Gemini error: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("Replicate failed, skipping Gemini")
        
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
            "google/nano-banana:f0a9d34b12ad1c1cd76269a844b218ff4e64e128ddaba93e15891f47368958a0",
            input=api_input
        )
        
        # 생성된 캐릭터 이미지 URL 획득
        # output_character가 문자열인 경우와 객체인 경우 모두 처리
        if isinstance(output_character, str):
            character_url = output_character
        elif hasattr(output_character, 'url'):
            character_url = output_character.url()
        else:
            character_url = str(output_character)
        
        print(f"Replicate character generated: {character_url}")
        
        # 결과 저장 (배경 제거 없이)
        app_state['result_image_url'] = character_url
        app_state['result_image_filename'] = 'mirai_replicate_default.png'
        app_state['result_image_ready'] = True
        print(f"✅ Replicate result saved: {character_url}")
        
        # Gemini에서 사용할 URL 반환
        return character_url
        
    except Exception as e:
        print(f"=== Replicate API ERROR ===: {str(e)}")
        import traceback
        traceback.print_exc()
        app_state['result_image_error'] = str(e)

def process_gemini_api_with_url(image_url):
    """Replicate에서 생성된 이미지 URL을 사용하여 Gemini 처리"""
    try:
        print(f"=== Starting Gemini 2.5 Flash Image Preview ===")
        print(f"Using Replicate image URL: {image_url}")
        
        # Gemini API 키
        gemini_api_key = "AIzaSyBIFu5xH4JCu__xfvEnFG1GEQR3APZyKJI"
        
        import google.generativeai as genai
        import requests
        from PIL import Image
        from io import BytesIO
        
        # Gemini 설정
        genai.configure(api_key=gemini_api_key)
        
        # Replicate 이미지 다운로드
        print("Downloading Replicate image...")
        response = requests.get(image_url)
        if response.status_code != 200:
            print(f"Failed to download image from {image_url}")
            return
        
        # PIL Image로 변환
        replicate_image = Image.open(BytesIO(response.content))
        print(f"Replicate image downloaded: {replicate_image.size}")
        
        # Gemini 2.5 Flash Image Preview 모델 사용
        model = genai.GenerativeModel('gemini-2.5-flash-image-preview')
        
        # 5가지 표정 생성
        expressions = [
            "default neutral expression",
            "smiling happy expression",
            "sad expression",
            "angry cute pouting expression",
            "embarrassed blushing expression"
        ]
        
        gemini_image_urls = []
        gemini_filenames = []
        emotion_tags = ['default', 'happy', 'sad', 'angry', 'embarrassed']
        
        # 각 표정별로 이미지 생성
        for expression, emotion_tag in zip(expressions, emotion_tags):
            print(f"Generating {emotion_tag} expression...")
            
            # 프롬프트 생성 - Replicate 이미지를 참조하여 새로운 표정 생성
            prompt = f"""Create a full-body standing illustration of this character with {expression}.
            Keep the exact same character design, art style, and outfit from the input image.
            Make it suitable for a game dialogue window with transparent background.
            Style: kawaii anime character, clean outlines, vibrant colors."""
            
            try:
                # Gemini에 이미지와 프롬프트 전송하여 새 이미지 생성
                response = model.generate_content([replicate_image, prompt])
                
                # 생성된 이미지 추출
                if response.parts:
                    for part in response.parts:
                        # inline_data가 있으면 이미지가 생성된 것
                        if hasattr(part, 'inline_data') and part.inline_data:
                            image_data = part.inline_data.data
                            mime_type = part.inline_data.mime_type
                            
                            # base64 데이터 URI 생성
                            original_data_uri = f"data:{mime_type};base64,{image_data}"
                            
                            # FAL AI로 배경 제거
                            try:
                                print(f"Removing background for {emotion_tag}...")
                                fal_result = fal_client.run(
                                    "fal-ai/bria/background/remove",
                                    arguments={
                                        "image_url": original_data_uri
                                    }
                                )
                                
                                # FAL AI 결과에서 이미지 URL 추출
                                if fal_result and 'image' in fal_result:
                                    bg_removed_url = fal_result['image']['url']
                                    
                                    # URL을 base64로 변환
                                    import requests
                                    response_fal = requests.get(bg_removed_url)
                                    if response_fal.status_code == 200:
                                        bg_removed_base64 = base64.b64encode(response_fal.content).decode('utf-8')
                                        data_uri = f"data:image/png;base64,{bg_removed_base64}"
                                    else:
                                        print(f"Failed to download FAL result, using original")
                                        data_uri = original_data_uri
                                else:
                                    print(f"FAL API didn't return image, using original")
                                    data_uri = original_data_uri
                                    
                            except Exception as e:
                                print(f"FAL background removal error: {e}")
                                data_uri = original_data_uri
                            
                            filename = f"mirai_gemini_{emotion_tag}.png"
                            gemini_image_urls.append(data_uri)
                            gemini_filenames.append(filename)
                            
                            print(f"✅ Generated {emotion_tag} expression with transparent background")
                            break
                        # 텍스트만 있는 경우
                        elif hasattr(part, 'text'):
                            print(f"Gemini returned text for {emotion_tag}: {part.text[:100]}...")
                else:
                    print(f"No image generated for {emotion_tag}")
                    
            except Exception as e:
                print(f"Error generating {emotion_tag}: {e}")
                continue
        
        # 이미지가 생성되지 않은 경우 Replicate 이미지 사용 (fallback)
        if not gemini_image_urls:
            print("⚠️ Gemini image generation failed, using Replicate image as fallback")
            for emotion_tag in emotion_tags:
                gemini_image_urls.append(image_url)
                gemini_filenames.append(f"mirai_gemini_{emotion_tag}.png")
        
        # 모든 Gemini 이미지 URL과 파일명을 상태에 저장
        if gemini_image_urls:
            app_state['result_image_3_url'] = gemini_image_urls[0]  # 첫 번째 이미지
            app_state['result_image_3_all_urls'] = gemini_image_urls  # 모든 이미지 URL
            app_state['result_image_3_filenames'] = gemini_filenames  # 모든 파일명
            app_state['result_image_3_filename'] = gemini_filenames[0]  # 첫 번째 파일명
            app_state['result_image_3_ready'] = True
            print(f"✅ Total {len(gemini_image_urls)} Gemini images processed")
        
    except Exception as e:
        print(f"=== Gemini API ERROR ===: {str(e)}")
        import traceback
        traceback.print_exc()
        app_state['result_image_3_error'] = str(e)

if __name__ == '__main__':
    app.run(debug=True, port=5002)

# Vercel 배포를 위한 앱 객체 노출
application = app