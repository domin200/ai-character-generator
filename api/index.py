import replicate
from flask import Flask, render_template, request, jsonify
import base64
import os

app = Flask(__name__, template_folder='../templates')
app.secret_key = 'banana-ai-character-generator-secret-key-2024'

# 환경변수에서 API 키 설정
replicate.Client(api_token=os.getenv('REPLICATE_API_TOKEN'))

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
        print("=== Starting Gemini API with Replicate URL ===")
        print(f"GEMINI_API_KEY exists: {bool(os.getenv('GEMINI_API_KEY'))}")
        print(f"Using Replicate image URL: {image_url}")
        
        # Gemini API 호출 - 새로운 genai 라이브러리 사용
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            print("ERROR: GEMINI_API_KEY environment variable not set")
            return

        try:
            from google import genai
            from PIL import Image
            from io import BytesIO
            import io
            
            # Gemini 클라이언트 초기화
            client = genai.Client(api_key=gemini_api_key)
            
            print("Calling Gemini 2.5 Flash Image Preview...")
            
            # Replicate에서 생성된 이미지를 기반으로 텍스트 프롬프트로 이미지 생성
            response = client.models.generate_content(
                model="gemini-2.5-flash-image-preview",
                contents=f"Based on this character image: {image_url}, create five standing illustrations with slight variations in expression and pose: Default, Smiling (happy), Sad, Angry (cute pouting), Embarrassed. Keep the same character design and art style. Style: kawaii anime character, clean outlines, vibrant colors, transparent background."
            )
            
            print(f"Gemini response: {response}")
            
            # 생성된 이미지들 추출
            image_parts = [
                part.inline_data.data
                for part in response.candidates[0].content.parts
                if part.inline_data
            ]
            
            print(f"Found {len(image_parts)} generated images")
            
            gemini_image_urls = []
            
            for i, image_data_bytes in enumerate(image_parts):
                print(f"Processing Gemini image {i + 1}...")
                
                # PIL Image로 변환
                image = Image.open(BytesIO(image_data_bytes))
                
                # PNG로 저장하여 base64 인코딩
                png_buffer = io.BytesIO()
                image.save(png_buffer, format='PNG')
                png_data = png_buffer.getvalue()
                
                # base64 데이터 URI 생성
                gemini_base64 = base64.b64encode(png_data).decode('utf-8')
                gemini_data_uri = f"data:image/png;base64,{gemini_base64}"
                
                # 배경 제거 없이 base64 데이터 URI 저장
                print(f"Saving Gemini image {i + 1}...")
                gemini_image_urls.append(gemini_data_uri)
            
            # 모든 Gemini 이미지 URL을 전역 상태에 저장
            if gemini_image_urls:
                app_state['result_image_3_url'] = gemini_image_urls[0]  # 첫 번째 이미지
                app_state['result_image_3_all_urls'] = gemini_image_urls  # 모든 이미지 URL
                app_state['result_image_3_ready'] = True
                print(f"Total {len(gemini_image_urls)} Gemini images processed")
            
        except ImportError as ie:
            print(f"Gemini library import error: {ie}")
            print("Falling back to REST API...")
            # 기존 REST API 코드를 여기에 유지할 수 있음
        except Exception as ge:
            print(f"Gemini genai API error: {ge}")
            import traceback
            print(f"Gemini Traceback: {traceback.format_exc()}")
        
    except Exception as e:
        print(f"Gemini API error: {str(e)}")
        import traceback
        print(f"Gemini Traceback: {traceback.format_exc()}")

# Vercel 서버리스 함수
application = app