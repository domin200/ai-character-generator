from flask import Flask, render_template, request, jsonify
import base64
import time
import fal_client
import os
from dotenv import load_dotenv
import threading

# .env 파일 로드
load_dotenv()

app = Flask(__name__)
app.secret_key = 'ai-4-cut-generator-secret-key-2024'

# FAL AI API 키 설정 (환경변수에서 로드)
FAL_KEY = os.getenv('FAL_KEY')
if FAL_KEY:
    os.environ['FAL_KEY'] = FAL_KEY
else:
    raise ValueError("FAL_KEY environment variable is not set. Please check your .env file.")

# 전역 상태 저장소 (각 사용자별로 unique_id로 분리)
app_state = {}

def get_user_state(unique_id):
    """사용자별 상태 가져오기"""
    if unique_id not in app_state:
        app_state[unique_id] = {}
    return app_state[unique_id]

def clean_old_states():
    """1시간 이상 된 상태 삭제"""
    import time
    current_time = time.time()
    to_delete = []
    for uid, state in app_state.items():
        if state.get('processing_timestamp', 0) < current_time - 3600:
            to_delete.append(uid)
    for uid in to_delete:
        del app_state[uid]

# AI4컷 생성 프롬프트 생성 함수 (날짜, 프레임 색상, 레이아웃 동적 생성)
def get_ai_4_cut_prompt(frame_color='black', layout='1x4', color_mode='color', style='default'):
    from datetime import datetime
    current_date = datetime.now().strftime('%Y.%m.%d')

    # 프레임 색상 (hex 코드 또는 기본 색상 이름)
    if frame_color.startswith('#'):
        # Hex 코드인 경우 그대로 사용
        frame_instruction = f"color {frame_color}"
    else:
        # 기존 호환성을 위한 색상 이름 매핑
        color_map = {
            'black': 'color #000000',
            'gray': 'color #808080',
            'white': 'color #FFFFFF'
        }
        frame_instruction = color_map.get(frame_color, 'color #000000')

    # 색상 모드 설정
    color_mode_instructions = {
        'bw': "All photos must be in BLACK AND WHITE (grayscale/monochrome). No color in the photos.",
        'cool': "Apply COOL TONE styling: The person's skin should have a fair, pinkish-rosy undertone typical of cool skin tones. Add subtle blue-ish tint to the overall image. Skin looks best with silver/blue-based tones.",
        'warm': "Apply SUBTLE WARM TONE styling: Add a very gentle, natural warm glow. Slightly enhance skin's healthy peachy-pink tones. Keep skin looking natural and healthy, NOT yellow or orange. Just a hint of warmth.",
        'color': ""
    }
    color_instruction = color_mode_instructions.get(color_mode, "")

    # 스타일 설정
    style_instructions = {
        'default': "",
        'animation': "IMPORTANT STYLE: Transform the person into 2D ANIME/ANIMATION style artwork. Convert to Japanese anime art style with cel-shading, big expressive eyes, and stylized features typical of anime characters.",
        'realistic': "IMPORTANT STYLE: If the input image is an animated character or non-real person, transform them into REALISTIC PHOTOREALISTIC style. Make them look like a real human cosplaying the character, with realistic skin texture, lighting, and human features. If the character's nationality is not clearly identifiable, default to Korean person appearance.",
        'disney': "IMPORTANT STYLE: Transform the person into DISNEY/PIXAR 3D animation style. Apply the characteristic Disney look with big expressive eyes, smooth skin, stylized proportions, and the magical quality typical of Disney and Pixar animated movies.",
        'ghibli': "IMPORTANT STYLE: Apply STUDIO GHIBLI art style to the person. Convert to 2D hand-drawn animation style like Ghibli films. Keep the same person, pose and expression but render in Ghibli's distinctive drawing style with soft lines and gentle colors."
    }
    style_instruction = style_instructions.get(style, "")

    # 레이아웃별 프롬프트 생성
    if layout == '1x3':
        layout_instruction = "IMPORTANT: 3 images arranged in SINGLE COLUMN vertically (1x3 layout). NOT 2x2, NOT any other layout. Only vertical single column with 3 images."
        layout_structure = "[narrow top margin] → [image 1] → [image 2] → [image 3] → [bottom section with logo, date, QR]."
        image_count_text = "3 images"
        aspect_ratio = "1:1 aspect ratio (square)"
        frame_size = "1060x3187 pixels"
    elif layout == '2x2':
        layout_instruction = "IMPORTANT: 4 images arranged in 2x2 grid layout. Two images in first row, two images in second row."
        layout_structure = "[narrow top margin] → [Row 1: image 1 | image 2] → [Row 2: image 3 | image 4] → [bottom section with logo, date, QR]."
        image_count_text = "4 images"
        aspect_ratio = "3:4 aspect ratio (portrait orientation)"
        frame_size = "2120x3187 pixels"
    else:  # 1x4 (default)
        layout_instruction = "IMPORTANT: 4 images arranged in SINGLE COLUMN vertically (1x4 layout). NOT 2x2, NOT 2x3, NOT 2x4. Only vertical single column layout."
        layout_structure = "[narrow top margin] → [image 1] → [image 2] → [image 3] → [image 4] → [bottom section with logo, date, QR]."
        image_count_text = "4 images"
        aspect_ratio = "4:3 aspect ratio"
        frame_size = "1060x3187 pixels"

    return f"""Create an AI-4-cut photo strip. Full frame size {frame_size}.
{layout_instruction}
{image_count_text}, each with {aspect_ratio} with different natural poses and expressions.
{style_instruction}
{color_instruction}
All frame with {frame_instruction}. No text on top of frame. Top margin should be narrow, similar to side margins, with images positioned accordingly.
Layout structure: {layout_structure}
At the bottom of the frame, add 'MIRAI' (use logo.png) and '{current_date}' in vertical center alignment.
Date should be 10% of logo size, small. Do not include 'AI4컷' text.
QR code should be inserted small and naturally at the bottom right corner of the frame (to the right of the date),
half the size of the logo, as small as possible while maintaining QR functionality."""

# 웹 배포용 - 로컬 저장 제거

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/result')
def result():
    return render_template('result.html')

@app.route('/og-image.png')
def og_image():
    from flask import send_file
    import os
    og_path = os.path.join(os.path.dirname(__file__), 'static_image', 'og-image.png')
    return send_file(og_path, mimetype='image/png')

@app.route('/robots.txt')
def robots():
    from flask import send_file
    import os
    robots_path = os.path.join(os.path.dirname(__file__), 'static', 'robots.txt')
    return send_file(robots_path, mimetype='text/plain')

@app.route('/sitemap.xml')
def sitemap():
    from flask import send_file
    import os
    sitemap_path = os.path.join(os.path.dirname(__file__), 'static', 'sitemap.xml')
    return send_file(sitemap_path, mimetype='application/xml')

# 웹 배포용 - 로컬 파일 서빙 제거

@app.route('/api/check_progress')
def check_progress():
    # unique_id를 쿼리 파라미터로 받기
    unique_id = request.args.get('id')

    if not unique_id:
        return jsonify({'error': 'ID가 필요합니다'}), 400

    # 해당 사용자의 상태만 가져오기
    user_state = get_user_state(unique_id)

    result = {
        'result_ready': user_state.get('result_ready', False),
        'result_url': user_state.get('result_url'),
        'result_urls': user_state.get('result_urls', []),
        'result_filename': user_state.get('result_filename', 'ai_4_cut.png'),
        'processing_started': user_state.get('processing_started', False),
        'processing_timestamp': user_state.get('processing_timestamp'),
        'current_image_hash': user_state.get('current_image_hash'),
        'current_processing_id': user_state.get('current_processing_id')
    }

    # 에러 정보 추가
    if user_state.get('error'):
        result['error'] = user_state.get('error')

    return jsonify(result)

@app.route('/reset_on_upload', methods=['POST'])
def reset_on_upload():
    """이미지 업로드시 기존 결과 초기화"""
    try:
        unique_id = request.json.get('id') if request.json else None

        if not unique_id:
            return jsonify({'error': 'ID가 필요합니다'}), 400

        print(f"=== IMAGE UPLOAD RESET for {unique_id}: CLEARING PREVIOUS RESULTS ===")

        # 해당 사용자의 결과만 초기화
        user_state = get_user_state(unique_id)
        user_state['result_ready'] = False
        user_state.pop('result_url', None)
        user_state.pop('error', None)
        user_state['processing_started'] = False
        user_state.pop('processing_timestamp', None)

        print(f"✅ Previous results cleared for user {unique_id}")

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
        # 첫 번째 이미지 파일 읽기 (필수)
        uploaded_file = request.files.get('image')

        if not uploaded_file or not uploaded_file.filename:
            return jsonify({'error': '이미지를 업로드해주세요.'}), 400

        # 이미지 데이터 읽기
        uploaded_file.seek(0, 0)
        image_data = uploaded_file.read()

        if not image_data or len(image_data) < 100:
            return jsonify({'error': '이미지 데이터를 읽을 수 없습니다.'}), 400

        print(f"Image 1 size: {len(image_data)} bytes, filename: {uploaded_file.filename}")

        # 두 번째 이미지 파일 읽기 (선택)
        image_data2 = None
        uploaded_file2 = request.files.get('image2')
        if uploaded_file2 and uploaded_file2.filename:
            uploaded_file2.seek(0, 0)
            image_data2 = uploaded_file2.read()
            if image_data2 and len(image_data2) >= 100:
                print(f"Image 2 size: {len(image_data2)} bytes, filename: {uploaded_file2.filename}")
            else:
                image_data2 = None

        # 프레임 색상 가져오기
        frame_color = request.form.get('frame_color', 'black')
        print(f"Frame color: {frame_color}")

        # 레이아웃 가져오기
        layout = request.form.get('layout', '1x4')
        print(f"Layout: {layout}")

        # 색상 모드 가져오기 (컬러/흑백/쿨톤/웜톤)
        color_mode = request.form.get('color_mode', 'color')
        print(f"Color mode: {color_mode}")

        # 스타일 가져오기 (기본/애니메이션/실사화)
        style = request.form.get('style', 'default')
        print(f"Style: {style}")

        # 고유 해시 생성
        import hashlib
        data_hash = hashlib.sha256(image_data).hexdigest()[:12]
        unique_id = f"{data_hash}_{int(time.time() * 1000)}"

        # 오래된 상태 정리
        clean_old_states()

        # 사용자별 상태 초기화
        user_state = get_user_state(unique_id)
        user_state.clear()
        user_state['result_ready'] = False
        user_state['processing_started'] = True
        user_state['processing_timestamp'] = time.time()
        user_state['current_image_hash'] = data_hash
        user_state['current_processing_id'] = unique_id

        is_duo = image_data2 is not None
        print(f"=== STARTING {'DUO' if is_duo else 'SOLO'} AI-4-CUT GENERATION for {unique_id} ===")

        # FAL AI로 AI4컷 생성 (백그라운드 스레드에서 실행)
        print("Processing with FAL AI nano-banana-pro/edit in background thread...")
        thread = threading.Thread(
            target=process_fal_ai_4_cut,
            args=(image_data, unique_id, frame_color, layout, image_data2, color_mode, style),
            daemon=True
        )
        thread.start()

        return jsonify({
            'success': True,
            'message': 'AI4컷 생성을 시작했습니다!',
            'id': unique_id
        })

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'오류가 발생했습니다: {str(e)}'}), 500

def process_fal_ai_4_cut(image_data, unique_id, frame_color='black', layout='1x4', image_data2=None, color_mode='color', style='default'):
    """FAL AI nano-banana-pro/edit로 AI4컷 생성"""
    try:
        user_state = get_user_state(unique_id)
        is_duo = image_data2 is not None
        color_mode_names = {'color': 'Color', 'bw': 'B&W', 'cool': 'Cool Tone', 'warm': 'Warm Tone'}
        style_names = {'default': 'Default', 'animation': 'Animation', 'realistic': 'Realistic', 'disney': 'Disney', 'ghibli': 'Ghibli'}
        print(f"=== FAL AI {'DUO' if is_duo else 'SOLO'} AI-4-CUT GENERATION for {unique_id} (frame: {frame_color}, layout: {layout}, color: {color_mode_names.get(color_mode, 'Color')}, style: {style_names.get(style, 'Default')}) ===")

        # 1. 첫 번째 사용자 이미지 base64 변환
        mime_type = 'image/jpeg'
        if image_data[:4] == b'\x89PNG':
            mime_type = 'image/png'

        user_image_base64 = base64.b64encode(image_data).decode('utf-8')
        user_image_uri = f"data:{mime_type};base64,{user_image_base64}"
        print(f"User image 1 prepared: {len(image_data)} bytes")

        # 이미지 URL 리스트 (사용자 이미지들)
        image_urls = [user_image_uri]

        # 2. 두 번째 사용자 이미지 (있는 경우)
        if image_data2:
            mime_type2 = 'image/jpeg'
            if image_data2[:4] == b'\x89PNG':
                mime_type2 = 'image/png'

            user_image2_base64 = base64.b64encode(image_data2).decode('utf-8')
            user_image2_uri = f"data:{mime_type2};base64,{user_image2_base64}"
            image_urls.append(user_image2_uri)
            print(f"User image 2 prepared: {len(image_data2)} bytes")

        # 3. logo.png 읽기 및 base64 변환
        logo_path = os.path.join(os.path.dirname(__file__), 'static_image', 'logo.png')
        with open(logo_path, 'rb') as f:
            logo_data = f.read()
        logo_base64 = base64.b64encode(logo_data).decode('utf-8')
        logo_uri = f"data:image/png;base64,{logo_base64}"
        image_urls.append(logo_uri)
        print(f"Logo image loaded: {len(logo_data)} bytes")

        # 4. QR.png 읽기 및 base64 변환
        qr_path = os.path.join(os.path.dirname(__file__), 'static_image', 'QR.png')
        with open(qr_path, 'rb') as f:
            qr_data = f.read()
        qr_base64 = base64.b64encode(qr_data).decode('utf-8')
        qr_uri = f"data:image/png;base64,{qr_base64}"
        image_urls.append(qr_uri)
        print(f"QR image loaded: {len(qr_data)} bytes")

        print(f"Calling FAL AI with {len(image_urls)} images and prompt...")

        # 프롬프트 생성 (1인, 2인 동일 프롬프트 사용)
        prompt = get_ai_4_cut_prompt(frame_color, layout, color_mode, style)

        # FAL AI nano-banana-pro/edit 호출
        handler = fal_client.submit(
            "fal-ai/nano-banana-pro/edit",
            arguments={
                "prompt": prompt,
                "image_urls": image_urls,
                "num_images": 2
            }
        )

        print(f"Waiting for FAL AI response...")
        result = handler.get()
        print(f"FAL AI response received: {result}")

        # 결과 처리
        if result:
            result_data = result

            # 이미지 URL 추출 (FAL AI는 여러 형식으로 반환 가능)
            result_urls = []

            if 'images' in result_data and len(result_data['images']) > 0:
                for img in result_data['images']:
                    if isinstance(img, dict) and 'url' in img:
                        result_urls.append(img['url'])
                    elif isinstance(img, str):
                        result_urls.append(img)
            elif 'image' in result_data:
                if isinstance(result_data['image'], dict) and 'url' in result_data['image']:
                    result_urls.append(result_data['image']['url'])
                elif isinstance(result_data['image'], str):
                    result_urls.append(result_data['image'])
            elif 'url' in result_data:
                result_urls.append(result_data['url'])

            if result_urls:
                print(f"AI-4-cut generated: {len(result_urls)} images")

                # 모든 이미지를 base64로 변환하여 저장
                import requests
                result_data_uris = []
                for i, url in enumerate(result_urls):
                    response = requests.get(url)
                    if response.status_code == 200:
                        result_base64 = base64.b64encode(response.content).decode('utf-8')
                        data_uri_result = f"data:image/png;base64,{result_base64}"
                        result_data_uris.append(data_uri_result)
                        print(f"Image {i+1} downloaded successfully")
                    else:
                        print(f"Failed to download image {i+1}: {response.status_code}")

                if result_data_uris:
                    user_state['result_urls'] = result_data_uris
                    user_state['result_url'] = result_data_uris[0]  # 호환성을 위해 첫번째 이미지
                    user_state['result_filename'] = 'ai_4_cut.png'
                    user_state['result_ready'] = True

                    print(f"✅ AI-4-cut generation completed successfully for {unique_id} ({len(result_data_uris)} images)")
                else:
                    raise Exception("Failed to download any result images")
            else:
                raise Exception("No image URL in FAL AI response")
        else:
            raise Exception("Invalid response from FAL AI")

    except Exception as e:
        print(f"=== FAL AI ERROR for {unique_id} ===: {str(e)}")
        import traceback
        traceback.print_exc()
        user_state['error'] = str(e)
        user_state['result_ready'] = False

if __name__ == '__main__':
    app.run(debug=True, port=5002, threaded=True)

# Vercel 배포를 위한 앱 객체 노출
application = app