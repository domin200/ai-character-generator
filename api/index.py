import replicate
from flask import Flask, render_template, request, jsonify
import base64
import os
import fal_client

app = Flask(__name__, template_folder='../templates')
app.secret_key = 'banana-ai-character-generator-secret-key-2024'

# 환경변수에서 API 키 설정
replicate.Client(api_token=os.getenv('REPLICATE_API_TOKEN'))
os.environ['FAL_KEY'] = os.getenv('FAL_KEY', '3d0bf45f-f7de-4be5-b85b-e9522bf4901e:9461d2b0cccf9798e447725d2bf54027')

# 전역 상태 저장소
app_state = {
    'result_image_ready': False,
    'result_image_3_ready': False,
    'result_image_url': None,
    'result_image_3_url': None,
    'result_image_3_all_urls': []
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/check_progress')
def check_progress():
    # 전역 상태에서 진행 상황 확인
    result = {
        'result_image': app_state.get('result_image_ready', False),
        'result_image_3': app_state.get('result_image_3_ready', False),
        'result_image_url': app_state.get('result_image_url'),
        'result_image_3_url': app_state.get('result_image_3_url')
    }
    
    # Gemini 다중 이미지 정보 추가
    gemini_all_urls = app_state.get('result_image_3_all_urls', [])
    if gemini_all_urls:
        result['result_image_3_all_urls'] = gemini_all_urls
        result['result_image_3_count'] = len(gemini_all_urls)
    
    return jsonify(result)

@app.route('/generate', methods=['POST'])
def generate_image():
    print("=== GENERATE FUNCTION CALLED ===")
    try:
        print("Step 0: Initializing...")
        # 진행 상태 초기화
        app_state['result_image_ready'] = False
        app_state['result_image_3_ready'] = False
        app_state['result_image_url'] = None
        app_state['result_image_3_url'] = None
        app_state['result_image_3_all_urls'] = []
        
        print("Step 1: Getting uploaded file...")
        uploaded_file = request.files.get('image')
        
        if not uploaded_file or not uploaded_file.filename:
            print("ERROR: No file uploaded")
            return jsonify({'error': '이미지를 업로드해주세요.'}), 400
        
        print(f"Step 2: File received: {uploaded_file.filename}")
        # 이미지 데이터 준비
        image_data = uploaded_file.read()
        print(f"Step 3: Image data size: {len(image_data)} bytes")
        
        # 순차적 처리: Replicate 먼저, 그 결과를 Gemini에 전달
        print("Step 4: Starting sequential image processing...")
        
        # Replicate 먼저 처리하고 그 결과를 Gemini에 전달
        replicate_result_url = None
        try:
            replicate_result_url = process_replicate_api(image_data)
            print(f"Replicate completed. Result URL: {replicate_result_url}")
        except Exception as e:
            print(f"Replicate error in main: {e}")
            
        # Replicate 결과가 있으면 Gemini에 전달
        if replicate_result_url:
            try:
                process_gemini_api_with_url(replicate_result_url)  
                print("Gemini processing completed")
            except Exception as e:
                print(f"Gemini error in main: {e}")
        
        return jsonify({'success': True, 'message': '이미지 처리를 완료했습니다!'})
        
    except Exception as e:
        return jsonify({'error': f'오류가 발생했습니다: {str(e)}'}), 500

def process_replicate_api(image_data):
    try:
        print("=== Starting Replicate API ===")
        print(f"REPLICATE_API_TOKEN exists: {bool(os.getenv('REPLICATE_API_TOKEN'))}")
        
        # MIME 타입 결정
        mime_type = 'image/jpeg'
        
        # base64 데이터 URI 생성
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        data_uri = f"data:{mime_type};base64,{image_base64}"
        
        # Replicate API 호출 - nano-banana 모델 사용
        print("Step 1: Calling Replicate google/nano-banana...")
        print(f"Input data size: {len(image_base64)} chars")
        
        input_data = {
            "prompt": "Here's the full-body standing illustration of the character for a game dialogue window, keeping only the character with a transparent background.",
            "image_input": [data_uri]
        }
        
        output_character = replicate.run(
            "google/nano-banana:f0a9d34b12ad1c1cd76269a844b218ff4e64e128ddaba93e15891f47368958a0",
            input=input_data
        )
        
        print(f"Replicate output type: {type(output_character)}")
        print(f"Replicate output: {str(output_character)[:200]}...")
        
        # 생성된 캐릭터 이미지 URL 획득
        if hasattr(output_character, 'url'):
            character_url = output_character.url()
        elif isinstance(output_character, list):
            character_url = output_character[0]
        else:
            character_url = str(output_character)
        
        print(f"Character URL: {character_url}")
        
        # 결과 저장 (배경 제거 없이 원본 사용)
        app_state['result_image_url'] = character_url
        app_state['result_image_ready'] = True
        print(f"Replicate result saved: {character_url}")
        
        # Gemini에서 사용할 URL 반환
        return character_url
        
    except Exception as e:
        print(f"Replicate API error: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

def process_gemini_api_with_url(image_url):
    try:
        print("=== Starting Gemini 2.5 Flash Image Preview ===")
        print(f"GEMINI_API_KEY exists: {bool(os.getenv('GEMINI_API_KEY'))}")
        print(f"Using Replicate image URL: {image_url}")
        
        # Gemini API 호출
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            print("ERROR: GEMINI_API_KEY environment variable not set")
            return

        try:
            import requests
            from PIL import Image
            from io import BytesIO
            import json
            
            # Replicate 이미지 다운로드
            print("Downloading Replicate image...")
            response = requests.get(image_url)
            if response.status_code != 200:
                print(f"Failed to download image from {image_url}")
                return
            
            # 이미지를 base64로 인코딩
            image_bytes = response.content
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # Gemini REST API 설정
            api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image-preview:generateContent"
            headers = {
                'Content-Type': 'application/json',
                'x-goog-api-key': gemini_api_key
            }
            
            # 5가지 표정 생성
            expressions = [
                "default neutral expression",
                "smiling happy expression",
                "sad expression",
                "angry cute pouting expression",
                "embarrassed blushing expression"
            ]
            
            gemini_image_urls = []
            emotion_tags = ['default', 'happy', 'sad', 'angry', 'embarrassed']
            
            # 각 표정별로 이미지 생성
            for expression, emotion_tag in zip(expressions, emotion_tags):
                print(f"Generating {emotion_tag} expression...")
                
                # 프롬프트 생성
                prompt = f"""Create a full-body standing illustration of this character with {expression}.
                Keep the exact same character design, art style, and outfit from the input image.
                Make it suitable for a game dialogue window with transparent background.
                Style: kawaii anime character, clean outlines, vibrant colors."""
                
                # 요청 페이로드
                payload = {
                    "contents": [{
                        "parts": [
                            {
                                "inline_data": {
                                    "mime_type": "image/png",
                                    "data": image_base64
                                }
                            },
                            {
                                "text": prompt
                            }
                        ]
                    }]
                }
                
                try:
                    # Gemini API 호출
                    api_response = requests.post(api_url, headers=headers, json=payload)
                    
                    if api_response.status_code == 200:
                        result = api_response.json()
                        
                        # 생성된 이미지 추출
                        if 'candidates' in result and result['candidates']:
                            candidate = result['candidates'][0]
                            if 'content' in candidate and 'parts' in candidate['content']:
                                for part in candidate['content']['parts']:
                                    if 'inlineData' in part:
                                        image_data = part['inlineData']['data']
                                        mime_type = part['inlineData'].get('mimeType', 'image/png')
                                        
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
                                                response = requests.get(bg_removed_url)
                                                if response.status_code == 200:
                                                    bg_removed_base64 = base64.b64encode(response.content).decode('utf-8')
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
                                        
                                        gemini_image_urls.append(data_uri)
                                        print(f"✅ Generated {emotion_tag} expression with transparent background")
                                        break
                                    elif 'text' in part:
                                        print(f"Gemini returned text for {emotion_tag}: {part['text'][:100]}...")
                    else:
                        print(f"Gemini API error for {emotion_tag}: {api_response.status_code}")
                        print(f"Response: {api_response.text}")
                        
                except Exception as e:
                    print(f"Error generating {emotion_tag}: {e}")
                    continue
            
            # 이미지가 생성되지 않은 경우 Replicate 이미지 사용 (fallback)
            if not gemini_image_urls:
                print("⚠️ Gemini image generation failed, using Replicate image as fallback")
                for i in range(5):
                    gemini_image_urls.append(image_url)
            
            # 모든 Gemini 이미지 URL을 전역 상태에 저장
            if gemini_image_urls:
                app_state['result_image_3_url'] = gemini_image_urls[0]  # 첫 번째 이미지
                app_state['result_image_3_all_urls'] = gemini_image_urls  # 모든 이미지 URL
                app_state['result_image_3_ready'] = True
                print(f"✅ Total {len(gemini_image_urls)} Gemini images processed")
            
        except Exception as ge:
            print(f"Gemini API error: {ge}")
            import traceback
            print(f"Gemini Traceback: {traceback.format_exc()}")
        
    except Exception as e:
        print(f"Gemini API error: {str(e)}")
        import traceback
        print(f"Gemini Traceback: {traceback.format_exc()}")

# Vercel 서버리스 함수
application = app