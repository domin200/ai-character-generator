# 🎨 AI Character Generator

AI를 이용한 캐릭터 변환기 웹 애플리케이션입니다. 업로드한 이미지를 게임 대화창에 적합한 캐릭터 일러스트로 변환합니다.

## ✨ 주요 기능

- **다중 AI 엔진**: Replicate, FAL AI, Gemini 2.5 Flash를 활용한 3가지 스타일 생성
- **배경 제거**: 모든 생성된 이미지에 자동 배경 제거 적용
- **다중 표정**: Gemini API로 5가지 표정 변화 생성 (기본, 웃음, 슬픔, 화남, 부끄러움)
- **실시간 처리**: 비동기 처리로 완료된 이미지부터 순차적 표시
- **반응형 UI**: 2x2 그리드 레이아웃으로 직관적인 인터페이스
- **드래그앤드롭**: 편리한 이미지 업로드 방식

## 🛠️ 기술 스택

- **Backend**: Flask (Python)
- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **AI APIs**: 
  - Replicate (nano-banana)
  - FAL AI (nano-banana/edit, background removal)
  - Google Gemini 2.5 Flash Image
- **Deployment**: 웹 배포 최적화 완료

## 🚀 배포

이 애플리케이션은 웹 배포에 최적화되어 있습니다:

- 로컬 파일 저장 없음
- 직접 API URL 사용
- 메모리 기반 이미지 처리
- 환경변수를 통한 API 키 관리

### 필요한 환경변수:
```
REPLICATE_API_TOKEN=your_replicate_token
FAL_KEY=your_fal_api_key
```

## 📝 사용법

1. 원본 이미지를 업로드 (드래그앤드롭 또는 클릭)
2. '캐릭터 변환 시작' 버튼 클릭
3. 3개 API가 병렬로 처리하여 완료된 순서대로 결과 표시
4. 생성된 이미지 클릭으로 다운로드 가능

## 🎯 특징

- **병렬 처리**: 3개 API 동시 실행으로 빠른 결과
- **재생성**: 완료 후에도 재생성 가능
- **갤러리**: Gemini 다중 이미지를 갤러리 형태로 표시
- **토스트 알림**: 사용자 친화적 알림 시스템
- **Vercel 배포**: 서버리스 환경 최적화