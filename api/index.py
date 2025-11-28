from flask import Flask, render_template, request, jsonify
import base64
import os
import fal_client
from dotenv import load_dotenv
import time
import requests

# .env 파일 로드
load_dotenv()

app = Flask(__name__, template_folder='../templates')
app.secret_key = 'ai-4-cut-generator-secret-key-2024'

# FAL AI API 키 설정 (환경변수에서 로드)
FAL_KEY = os.getenv('FAL_KEY')
if FAL_KEY:
    os.environ['FAL_KEY'] = FAL_KEY
else:
    # Vercel 환경에서는 환경변수가 미리 설정되어 있을 수 있음
    if not os.getenv('FAL_KEY'):
        print("WARNING: FAL_KEY not found in environment")

# AI4컷 생성 프롬프트 생성 함수 (날짜, 프레임 색상, 레이아웃, 색상모드, 스타일, 듀오 모드 동적 생성)
def get_ai_4_cut_prompt(frame_color='black', layout='1x4', color_mode='color', style='default', is_duo=False):
    from datetime import datetime
    current_date = datetime.now().strftime('%Y.%m.%d')

    # 프레임 색상 (hex 코드 또는 기본 색상 이름)
    if frame_color.startswith('#'):
        frame_instruction = f"color {frame_color}"
    else:
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
        'ghibli': "IMPORTANT STYLE: Apply STUDIO GHIBLI art style to the person. Convert to 2D hand-drawn animation style like Ghibli films. Keep the same person, pose and expression but render in Ghibli's distinctive drawing style with soft lines and gentle colors.",
        'baby': "IMPORTANT STYLE: Apply CHILD transformation filter. Transform the person to look like a young child version of themselves (age 5-6 years old). Keep the same facial features and identity but make them look like an adorable child with rounder cheeks, bigger eyes relative to face, softer skin, and childlike proportions. Similar to Snapchat baby filter effect.",
        'old': "IMPORTANT STYLE: Apply AGING transformation filter. Transform the person to look like a middle-aged to older version of themselves (age 50-60 years old). Keep the same facial features and identity but add subtle aging effects: some wrinkles, slight graying hair, and mature facial features. Similar to Snapchat old age filter effect."
    }
    style_instruction = style_instructions.get(style, "")

    # 듀오 모드 (두 명) 프롬프트
    duo_instruction = ""
    if is_duo:
        duo_instruction = "IMPORTANT: Two people are provided in the input images. Generate photos featuring BOTH people together naturally in each frame. They should appear as friends, couple, or companions interacting naturally with each other."

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

    # 여성 인물 미묘한 보정
    beauty_instruction = "SUBTLE ENHANCEMENT: If the input is a real female person, apply very subtle and unnoticeable facial enhancement. The enhancement should be imperceptible - just slightly improved skin clarity and natural glow. Must NOT be obvious or detectable."

    return f"""Create an AI-4-cut photo strip. Full frame size {frame_size}.
{layout_instruction}
{duo_instruction}
{image_count_text}, each with {aspect_ratio} with different natural poses and expressions.
{style_instruction}
{color_instruction}
{beauty_instruction}
All frame with {frame_instruction}. No text on top of frame. Top margin should be narrow, similar to side margins, with images positioned accordingly.
Layout structure: {layout_structure}
At the bottom of the frame, add 'MIRAI' (use logo.png) and '{current_date}' in vertical center alignment.
Date should be 10% of logo size, small. Do not include 'AI4컷' text.
QR code should be inserted small and naturally at the bottom right corner of the frame (to the right of the date),
half the size of the logo, as small as possible while maintaining QR functionality."""

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/result')
def result():
    return render_template('result.html')

@app.route('/og-image.png')
def og_image():
    from flask import send_file
    og_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_image', 'og-image.png')
    return send_file(og_path, mimetype='image/png')

@app.route('/robots.txt')
def robots():
    from flask import send_file
    robots_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'robots.txt')
    return send_file(robots_path, mimetype='text/plain')

@app.route('/sitemap.xml')
def sitemap():
    from flask import send_file
    sitemap_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'sitemap.xml')
    return send_file(sitemap_path, mimetype='application/xml')

@app.route('/ads.txt')
def ads_txt():
    from flask import send_file
    ads_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'ads.txt')
    return send_file(ads_path, mimetype='text/plain')

@app.route('/generate', methods=['POST'])
def generate_image():
    """동기 방식으로 AI4컷 생성 - Vercel serverless 환경에서 작동"""
    try:
        # 첫 번째 이미지 파일 읽기 (필수)
        uploaded_file = request.files.get('image')

        if not uploaded_file or not uploaded_file.filename:
            return jsonify({'error': '이미지를 업로드해주세요.'}), 400

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

        # 스타일 가져오기 (기본/애니메이션/실사화/디즈니/지브리)
        style = request.form.get('style', 'default')
        print(f"Style: {style}")

        is_duo = image_data2 is not None
        color_mode_names = {'color': 'Color', 'bw': 'B&W', 'cool': 'Cool Tone', 'warm': 'Warm Tone'}
        style_names = {'default': 'Default', 'animation': 'Animation', 'realistic': 'Realistic', 'disney': 'Disney', 'ghibli': 'Ghibli'}
        print(f"=== STARTING {'DUO' if is_duo else 'SOLO'} AI-4-CUT GENERATION (frame: {frame_color}, layout: {layout}, color: {color_mode_names.get(color_mode, 'Color')}, style: {style_names.get(style, 'Default')}) ===")

        # 1. 첫 번째 사용자 이미지 base64 변환
        mime_type = 'image/jpeg'
        if image_data[:4] == b'\x89PNG':
            mime_type = 'image/png'

        user_image_base64 = base64.b64encode(image_data).decode('utf-8')
        user_image_uri = f"data:{mime_type};base64,{user_image_base64}"
        print(f"User image 1 prepared: {len(image_data)} bytes")

        # 이미지 URL 리스트
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
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_image', 'logo.png')
        with open(logo_path, 'rb') as f:
            logo_data = f.read()
        logo_base64 = base64.b64encode(logo_data).decode('utf-8')
        logo_uri = f"data:image/png;base64,{logo_base64}"
        image_urls.append(logo_uri)
        print(f"Logo image loaded: {len(logo_data)} bytes")

        # 4. QR.png 읽기 및 base64 변환
        qr_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static_image', 'QR.png')
        with open(qr_path, 'rb') as f:
            qr_data = f.read()
        qr_base64 = base64.b64encode(qr_data).decode('utf-8')
        qr_uri = f"data:image/png;base64,{qr_base64}"
        image_urls.append(qr_uri)
        print(f"QR image loaded: {len(qr_data)} bytes")

        print(f"Calling FAL AI with {len(image_urls)} images and prompt...")

        # 프롬프트 생성 (색상 모드, 스타일, 듀오 모드 포함)
        prompt = get_ai_4_cut_prompt(frame_color, layout, color_mode, style, is_duo)

        # FAL AI nano-banana-pro/edit 호출 (동기 방식)
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

            # 이미지 URL 추출
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

                # 모든 이미지를 base64로 변환하여 직접 반환
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
                    print(f"✅ AI-4-cut generation completed successfully ({len(result_data_uris)} images)")

                    # 결과를 직접 반환 (상태 저장 없이)
                    return jsonify({
                        'success': True,
                        'result_ready': True,
                        'result_urls': result_data_uris,
                        'result_url': result_data_uris[0],
                        'result_filename': 'ai_4_cut.png'
                    })
                else:
                    return jsonify({'error': '결과 이미지를 다운로드할 수 없습니다.'}), 500
            else:
                return jsonify({'error': 'AI 응답에서 이미지를 찾을 수 없습니다.'}), 500
        else:
            return jsonify({'error': 'AI 서버에서 유효하지 않은 응답을 받았습니다.'}), 500

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'오류가 발생했습니다: {str(e)}'}), 500

# Vercel 서버리스 함수
application = app
