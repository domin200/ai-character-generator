from flask import Flask, render_template, request, jsonify
import base64
import os
import fal_client

app = Flask(__name__, template_folder='../templates')
app.secret_key = 'life-4-cut-generator-secret-key-2024'

# 환경변수에서 FAL API 키 설정
os.environ['FAL_KEY'] = os.getenv('FAL_KEY', '3d0bf45f-f7de-4be5-b85b-e9522bf4901e:9461d2b0cccf9798e447725d2bf54027')

# 전역 상태 저장소
app_state = {}

# 인생네컷 생성 프롬프트 (고정)
LIFE_4_CUT_PROMPT = """Create a life-4-cut photo strip. Full frame size 1060x3187 pixels.
4 images arranged vertically. Each image has 4:3 aspect ratio with different natural poses and expressions.
All black frame. No text on top of frame. Top margin should be narrow, similar to side margins, with images positioned accordingly.
At the bottom of the frame, add 'MIRAI logo.' and '2025.11.25' in vertical center alignment.
Date should be 10% of logo size, small. Do not include '인생네컷' text.
QR code should be inserted small and naturally at the bottom right corner of the frame (to the right of the date),
half the size of the logo, as small as possible while maintaining QR functionality."""

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/check_progress')
def check_progress():
    # 단순화된 진행 상황 확인 - 단일 결과 이미지만
    result = {
        'result_ready': app_state.get('result_ready', False),
        'result_url': app_state.get('result_url'),
        'result_filename': app_state.get('result_filename', 'life_4_cut.png'),
        'processing_started': app_state.get('processing_started', False),
        'processing_timestamp': app_state.get('processing_timestamp'),
        'current_image_hash': app_state.get('current_image_hash'),
        'current_processing_id': app_state.get('current_processing_id')
    }

    # 에러 정보 추가
    if app_state.get('error'):
        result['error'] = app_state.get('error')

    return jsonify(result)

@app.route('/generate', methods=['POST'])
def generate_image():
    try:
        # 상태 초기화
        print("=== STARTING LIFE-4-CUT GENERATION ===")
        app_state.clear()
        app_state['result_ready'] = False
        app_state['processing_started'] = True

        # 이미지 파일 읽기
        uploaded_file = request.files.get('image')

        if not uploaded_file or not uploaded_file.filename:
            return jsonify({'error': '이미지를 업로드해주세요.'}), 400

        # 이미지 데이터 읽기
        uploaded_file.seek(0, 0)
        image_data = uploaded_file.read()

        if not image_data or len(image_data) < 100:
            return jsonify({'error': '이미지 데이터를 읽을 수 없습니다.'}), 400

        print(f"Image size: {len(image_data)} bytes, filename: {uploaded_file.filename}")

        # 고유 해시 생성
        import hashlib
        import time
        data_hash = hashlib.sha256(image_data).hexdigest()[:12]
        unique_id = f"{data_hash}_{int(time.time() * 1000)}"

        app_state['current_image_hash'] = data_hash
        app_state['current_processing_id'] = unique_id

        # FAL AI로 인생네컷 생성
        print("Processing with FAL AI nano-banana-pro/edit...")
        process_fal_life_4_cut(image_data)

        return jsonify({'success': True, 'message': '인생네컷 생성을 시작했습니다!'})

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'오류가 발생했습니다: {str(e)}'}), 500

def process_fal_life_4_cut(image_data):
    """FAL AI nano-banana-pro/edit로 인생네컷 생성"""
    try:
        print("=== FAL AI LIFE-4-CUT GENERATION ===")

        # 1. 사용자 이미지 base64 변환
        mime_type = 'image/jpeg'
        if image_data[:4] == b'\x89PNG':
            mime_type = 'image/png'

        user_image_base64 = base64.b64encode(image_data).decode('utf-8')
        user_image_uri = f"data:{mime_type};base64,{user_image_base64}"
        print(f"User image prepared: {len(image_data)} bytes")

        # 2. logo.png 읽기 및 base64 변환
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_image', 'logo.png')
        with open(logo_path, 'rb') as f:
            logo_data = f.read()
        logo_base64 = base64.b64encode(logo_data).decode('utf-8')
        logo_uri = f"data:image/png;base64,{logo_base64}"
        print(f"Logo image loaded: {len(logo_data)} bytes")

        # 3. QR.png 읽기 및 base64 변환
        qr_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_image', 'QR.png')
        with open(qr_path, 'rb') as f:
            qr_data = f.read()
        qr_base64 = base64.b64encode(qr_data).decode('utf-8')
        qr_uri = f"data:image/png;base64,{qr_base64}"
        print(f"QR image loaded: {len(qr_data)} bytes")

        print(f"Calling FAL AI with 3 images (user + logo + QR) and prompt...")

        # FAL AI nano-banana-pro/edit 호출 (3개 이미지 입력)
        result = fal_client.subscribe(
            "fal-ai/nano-banana-pro/edit",
            arguments={
                "prompt": LIFE_4_CUT_PROMPT,
                "image_urls": [user_image_uri, logo_uri, qr_uri]
            },
            with_logs=True,
            on_queue_update=lambda update: print(f"Queue status: {update.get('status', 'unknown')}")
        )

        print(f"FAL AI response received")

        # 결과 처리
        if result and 'data' in result:
            result_data = result['data']

            # 이미지 URL 추출 (FAL AI는 여러 형식으로 반환 가능)
            result_url = None

            if 'image' in result_data:
                if isinstance(result_data['image'], dict) and 'url' in result_data['image']:
                    result_url = result_data['image']['url']
                elif isinstance(result_data['image'], str):
                    result_url = result_data['image']
            elif 'images' in result_data and len(result_data['images']) > 0:
                if isinstance(result_data['images'][0], dict) and 'url' in result_data['images'][0]:
                    result_url = result_data['images'][0]['url']
                elif isinstance(result_data['images'][0], str):
                    result_url = result_data['images'][0]
            elif 'url' in result_data:
                result_url = result_data['url']

            if result_url:
                print(f"Life-4-cut generated: {result_url}")

                # URL을 base64로 변환하여 저장
                import requests
                response = requests.get(result_url)
                if response.status_code == 200:
                    result_base64 = base64.b64encode(response.content).decode('utf-8')
                    data_uri_result = f"data:image/png;base64,{result_base64}"

                    app_state['result_url'] = data_uri_result
                    app_state['result_filename'] = 'life_4_cut.png'
                    app_state['result_ready'] = True

                    print("✅ Life-4-cut generation completed successfully")
                else:
                    raise Exception(f"Failed to download result image: {response.status_code}")
            else:
                raise Exception("No image URL in FAL AI response")
        else:
            raise Exception("Invalid response from FAL AI")

    except Exception as e:
        print(f"=== FAL AI ERROR ===: {str(e)}")
        import traceback
        traceback.print_exc()
        app_state['error'] = str(e)
        app_state['result_ready'] = False

# Vercel 서버리스 함수
application = app
