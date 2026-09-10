# AI Sprite Animation Repair Studio — 개발 및 검증 완료 보고서

## 1. 개요 및 달성 성과

사용자의 마스터 지시서에 명시된 핵심 원칙 및 로드맵(Section 66)에 따라, **100% 오프라인 CV 자동 복구 엔진**과 **Aseprite급 타임라인/레이어/셀/양파껍질 편집 UX**를 결합한 **Sprite Animation Repair Studio**를 구현하고 실전 4×4 공격 스프라이트시트(16 프레임)로 검증을 완료했습니다.

---

## 2. 구현 단계별 요약

### Phase 0: 구조 분석 및 설계
- [CURRENT_ARCHITECTURE.md](file:///C:/TEST/MikuChat-Lab/projects/SpriteRepair/docs/CURRENT_ARCHITECTURE.md) 분석 완료.
- 3대 불변 원칙 확립:
  1. `그리드 셀 != 실제 프레임 경계` (인접 VFX 번짐 수용)
  2. `캐릭터 앵커 != 바운딩 박스 중심` (발/지면 접촉 앵커 기반 수평/수직 고정)
  3. `캐릭터 바운딩 박스 != VFX 바운딩 박스` (소유권 분리)

### Phase 1: 도메인 데이터 모델 (`sprite_repair/models.py`)
Aseprite 데이터 계층을 완벽히 투영하는 네이티브 Python 데이터 모델 구축:
- **`Point`, `Rect`, `Anchor`, `Diagnostics`**: 기본 기하 및 QA 진단 구조체.
- **`Layer`**: 레이어 메타데이터 (`id`, `name`, `type` [character/vfx], `opacity`, `visible`, `locked`, `blend_mode`).
- **`Cel`**: 특정 레이어와 프레임이 교차하는 독립 데이터 단위 (`layer_id`, `frame_id`, `x`, `y`, `opacity`).
- **`Frame`**: 타임라인 열 및 프레임 메타데이터 (`index`, `duration`, `rect`, `anchor`, `offset`, `cels`).
- **`Tag`**: 루프 및 모션 태그 (`name`, `from_frame`, `to_frame`, `direction`).
- **`Sprite` & `Project`**: 전체 캔버스, 팔레트, 슬라이스 및 프로젝트 직렬화/역직렬화 (`.spriteproject`).

### Phase 2: 코어 복구 파이프라인 & 실전 4×4 공격 시트 마일스톤
실제 AI 생성 공격 스프라이트시트(`samples/attack_4x4_real.png`, 820×481, 16 프레임)를 대상으로 오프라인 CV 파이프라인 검증 완료:
- **16 프레임 전수 분리**: 그리드 경계를 넘어 튀어나온 검기/이펙트(VFX)를 잘림 없이 안전하게 감지.
- **캔버스 확장**: 프레임별 최대 오프셋을 자동 계산하여 전역 캔버스를 `501×278`로 무손실 확장.
- **발 접지 앵커 고정**: 지면 접촉 Y좌표 표준편차 `stdev = 0.00px` 달성 (완벽한 무흔들림 지면 접지).
- **다중 포맷 출력 엔진 (`sprite_repair/export.py`)**:
  - 개별 PNG 시퀀스 (`frames/000.png` ~ `frames/015.png`)
  - 아틀라스 스프라이트시트 (`spritesheet.png`, 201 KB)
  - 웹/게임 엔진용 `animation.json`
  - Unity / Godot Aseprite Importer 완벽 호환 `aseprite.json` (`meta.layers`, `meta.frameTags`)
  - 애니메이션 미리보기: `preview.gif` (218 KB), `preview.apng.png` (306 KB), `preview.webp` (275 KB)
  - 네이티브 스튜디오 프로젝트 파일 (`project.spriteproject`)

### Phase 3: Aseprite급 편집 UX 및 타임라인 (`app/`)
- **Aseprite 타임라인 위젯 (`aseprite-timeline`)**:
  - **태그 트랙 (`tl-tags-bar`)**: 모션 태그 뱃지 (`[Main: 0-15]`), 클릭 시 해당 구간 이동 및 선택.
  - **레이어 컬럼 (`tl-layers-col`)**: 레이어별 눈 아이콘(표시/숨김 토글), 자물쇠(잠금 토글), 레이어명(Character, VFX 등).
  - **프레임 헤더 (`tl-frames-header`)**: 프레임 번호 (`0`, `1`, ... `15`) 및 밀리초 단위 듀레이션 뱃지 (`80ms`).
  - **셀 매트릭스 그리드 (`tl-cels-grid`)**: 각 (레이어, 프레임) 교차점에 셀 버튼, 내용 점(dot), 현재 선택 셀 및 플레이헤드 하이라이트.
  - **타임라인 조작**: `+ 레이어`, `+ 태그`, `프레임 복제`, `프레임 삭제`.
- **다중 프레임 양파껍질 (Onion Skinning)**:
  - 이전 프레임(과거): 파란색/빨간색 틴트 + 거리별 감쇠 투명도 (1~5프레임 설정 가능).
  - 이후 프레임(미래): 녹색 틴트 + 거리별 감쇠 투명도 (0~5프레임 설정 가능).
  - 기준 프레임(Ref Frame) 고정 양파껍질 지원.
- **전문가용 뷰포트 (Stage Viewport)**:
  - 줌 프리셋 (`1x`, `2x`, `3x`, `4x`, `Fit`) + 마우스 휠 줌.
  - 캔버스 이동(Pan): `Space + 드래그` 또는 마우스 휠 클릭 드래그.
  - 픽셀 그리드: 3배율 이상 확대 시 픽셀 격자망 자동 렌더링.
  - 앵커 가이드: 붉은색 십자 발 접지 앵커 (드래그로 실시간 미세 조정) + 하늘색 중심 피벗 가이드.
  - 실시간 HUD: 마우스 커서 좌표, 프레임 크기, 앵커 좌표, 줌 배율 오버레이.
- **Aseprite 표준 단축키**:
  - `Space`: 재생 / 일시정지
  - `,` / `.`: 이전 / 다음 프레임 이동
  - `Home` / `End`: 첫 / 마지막 프레임 이동
  - `1` ~ `4`: 줌 1x, 2x, 3x, 4x
  - `O`: 양파껍질 온/오프
  - `WASD` / `방향키` (+ `Shift`): 앵커 1px / 5px 미세 이동
  - `Ctrl+Z` / `Ctrl+Y`: 실행 취소 / 다시 실행

---

## 3. 검증 결과 및 테스트 통과 내역

### 1) 단위 테스트 & 데이터 모델 라운드트립 (`test_models.py`)
```text
[OK] Point and Rect passed
[OK] to_dict / from_dict roundtrip passed
[OK] JSON roundtrip passed
[OK] Legacy dict conversion roundtrip passed
ALL MODEL TESTS PASSED!
```

### 2) 4×4 실전 공격 시트 마일스톤 검증 (`test_milestone_attack_4x4.py`)
```text
=== MILESTONE 1: 4x4 AI Attack Sheet Repair Verification ===
Source image: attack_4x4_real.png
[OK] Successfully extracted 16 frames from 4x4 grid
[OK] Project domain model instantiated: Canvas=501x278, Layers=2
[OK] Grounding Y Anchors: mean=269.0px, stdev=0.00px
[OK] Detected VFX in 16/16 frames, Boundary Overflows=0/16
[OK] Global canvas safely expanded to 501x278 without VFX clipping
[OK] PNG Sequence exported: 16 files
[OK] SpriteSheet Atlas exported: 201 KB
[OK] animation.json metadata exported
[OK] aseprite.json exported with frameTags and layers
[OK] preview.gif exported: 218 KB
[OK] preview.apng.png exported: 306 KB
[OK] preview.webp exported: 275 KB
[OK] project.spriteproject saved and roundtrip reloaded successfully
MILESTONE 1 VERIFICATION COMPLETED SUCCESSFULLY!
```

### 3) 라이브 서버 통합 엔드투엔드 검증 (`test_live_server.py`)
```text
Testing live server at http://127.0.0.1:5192...
[OK] GET /api/health returned 200 OK
[OK] POST /api/process returned session_id=a850f153af0f, 16 frames, Project model validated
[OK] POST /api/export returned download_zip=/workspace/a850f153af0f/export.zip
[OK] Aseprite export available at: /workspace/a850f153af0f/export/aseprite.json
[OK] Project file available at: /workspace/a850f153af0f/export/project.spriteproject
[OK] POST /api/save-project returned /workspace/a850f153af0f/Milestone_Attack.spriteproject
ALL LIVE SERVER TESTS PASSED!
```

---

## 4. 접속 및 사용 방법

- **서버 주소**: [http://127.0.0.1:5192](http://127.0.0.1:5192)
- **샘플 파일**: `samples/attack_4x4_real.png` (4열 4행 16프레임 공격 시트)
- **주요 워크플로우**:
  1. 웹 브라우저에서 `http://127.0.0.1:5192` 접속
  2. `PNG 스프라이트시트 선택`에서 시트 파일 업로드 (열: 4, 행: 4 기본값)
  3. `자동 추출 실행` 클릭 → 발 앵커 자동 접지, VFX 경계 자동 확장, 16프레임 분리
  4. 하단 Aseprite 타임라인에서 레이어(Character/VFX), 셀, 태그, 프레임별 듀레이션 제어
  5. 캔버스에서 마우스 휠(줌), Space+드래그(패닝), 붉은 십자 앵커 드래그로 미세 보정
  6. `frames + JSON + GIF/APNG/WebP 보내기` 클릭 → ZIP, `aseprite.json`, GIF, APNG, WebP, `.spriteproject` 다운로드
