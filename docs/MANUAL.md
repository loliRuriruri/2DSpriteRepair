# SpriteRepair 사용 메뉴얼

> AI 스프라이트 애니메이션 수리 스튜디오 · 로컬 실행 (`http://127.0.0.1:5190/`)
> 최종 업데이트: 2026-09-11

== 1. 개요 ==

SpriteRepair는 AI가 그린 스프라이트시트를 게임에 바로 쓸 수 있는 프레임으로 뜯어 고치는 도구이다.

||원칙||내용||
||그리드 ≠ 절단선||그리드 칸은 **씨앗(seed)** 일 뿐. 캐릭터가 칸을 넘쳐도 알파 기반으로 확장 추출||
||앵커 ≠ 바운딩박스 중심||발/루트(지면 접촉점) 기준 정렬. 바운딩박스 중앙 정렬 금지||
||캐릭터 ≠ 이펙트||몸통 bbox와 VFX bbox를 분리. VFX는 살리고 몸통 기준으로 앵커를 잡음||
||AI는 판정, 편집은 Pillow||AI는 좌표/판정만 내리고 실제 자르기·합성은 로컬 코드가 수행||

== 2. 실행 방법 ==

=== 2.1. 기본 실행 ===
* `SpriteRepair.bat` 더블클릭 → 브라우저가 자동으로 열림
* 종료는 `SpriteRepairServer` 콘솔 창을 닫으면 됨

=== 2.2. 수동 실행 ===
```bat
cd /d D:\test\SpriteRepair
.venv\Scripts\python.exe server.py
```

=== 2.3. CLI (UI 없이 처리만) ===
```bat
.venv\Scripts\python.exe -m sprite_repair samples\synthetic_4x4.png --cols 4 --rows 4 --out workspace\cli_smoke
```

=== 2.4. 포트 충돌 시 ===
* 5190이 이미 사용 중이면 bat가 기존 서버의 브라우저만 염. 내용이 낡으면 좀비 서버이므로 전부 종료 후 재시작:
```powershell
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
  Where-Object { $_.CommandLine -match "server\.py" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

== 3. 기본 워크플로 ==

1. **시트 올리기**: 4×4(또는 N×M) 스프라이트시트 PNG를 드래그/선택. 배경은 자동 크로마 제거됨
2. **자동 추출**: `AI 정렬 실행` 전이라도 그리드+알파 확장으로 16프레임이 분리됨
3. **앵커 보정**: 발 위치가 틀린 프레임은 앵커 도구(A)로 드래그 보정. `Ctrl+Z`/`Ctrl+Y` 실행취소
4. **AI 정렬 (선택)**: 비전 AI가 전 프레임 발/비율을 자동 보정
5. **QA 확인**: 흔들림·스케일·이펙트 잘림 경고 확인
6. **내보내기**: `에셋 생성 및 다운로드 번들` → frames + animation.json + GIF/APNG/WebP + spritesheet

== 4. 도구 설명 ==

||도구||단축키||용도||
||선택|V|프레임 선택||
||이동|M|프레임 위치 이동||
||앵커|A|발/루트 앵커 드래그 보정||
||크롭|C|크롭·캔버스 조정 + 안전 크롭||
||마스크|B|소유권 마스크 브러시 (이웃 칸 침범 픽셀 제거/복원)||
||차이 검사|-|이전 프레임 또는 기준 프레임과 풋 오프셋 비교||
||재생|Space|타임라인 미리보기 재생/정지||

== 5. AI 기능 ==

=== 5.1. 제공자 (6종) ===
||제공자||특징||키||
||Ollama (내 PC)|RTX 로컬 실행 · 완전 무료|불필요||
||OpenCode Go|36종 게이트웨이 · DeepSeek/Kimi/Qwen/GLM|OPENCODE_GO_API_KEY||
||OpenCode Console|70종 + 무료 그룹|OPENCODE_API_KEY||
||OpenRouter|수백종 · 무료 다수 · 실시간 가격|OPENROUTER_API_KEY||
||NVIDIA Build|고속 비전|NVIDIA_API_KEY||
||사용 안 함|로컬 CV만|-|-|

키는 설정 모달에서 저장하며 `.env`에만 기록됨. 화면·로그에 전체 노출되지 않음.

=== 5.2. 모델 선택 ===
* 상단 제공자/모델 드롭다운 + 새로고침. `비전만` 체크 시 비전 우선 정렬(텍스트 모델도 하단 표시)
* **✨ 빠른 선택** 버튼: 제공자 카드 → 추천 프리셋 카드(가격·한글설명·배지) → 직접입력 → 즉시 적용
* 배지: `LIVE-VERIFIED`(실측 통과) / `VISION` / `TEXT` / `FREE` / `POPULAR` / `CONTRIBUTOR` / `REGION-LIMITED`
* Muse Spark Contributor 선택 시 학습사용·지역제한 경고 후 명시적 확인 필요

=== 5.3. AI 정렬 / QA ===
* **AI 정렬 실행**: 콘택트시트 1장으로 전 프레임 앵커+스케일 요청. 실패 시 1회 재시도, 폴백 모델 순차 시도
* **AI 시트 QA**: 문제 프레임 목록 반환 (결과 캐시됨)
* 설정 모달의 Test Connection / Test JSON / Test Vision으로 모델 실측 가능

== 6. 내보내기 결과물 ==

`workspace/<session>/<name>/` 아래 생성:

||파일||내용||
||`frames/000.png` …|투명 PNG 시퀀스 (마스터)||
||`animation.json`|canvas, rect/anchor/offset/duration (Unity·Godot·엔진용)||
||`preview.gif`|공유용 미리보기 (disposal=배경 복원)||
||`preview.apng.png`|알파 보존 무손실 애니메이션||
||`preview.webp`|경량 웹 표준 애니메이션||
||`spritesheet.png` + `manifest.json`|앵커 정렬 통합 시트 + 팩드 아틀라스||
||`aseprite.json`|Aseprite 임포터 호환||
||`project.spriteproject`|앵커/프레임 상태 저장 (재작업용)||

== 7. 단축키 요약 ==

||키||동작||
||Space|재생/정지||
||Shift+A|AI 정렬||
||V / M / A / C / B|도구 전환||
||Ctrl+Z / Ctrl+Y|실행취소/다시실행||
||F4|단독 미리보기||

== 8. 문제 해결 ==

||증상||대처||
||화면이 낡았거나 API가 예전 동작|좀비 서버 → 2.4 방식으로 전체 종료 후 재시작||
||세션 없음|서버 재시작 시 세션 소멸. 시트 다시 처리||
||AI가 JSON이 아닌 답변|다른 비전 모델로 변경 (gemini/kimi 권장)||
||텍스트 전용 모델 선택|비전 모델로 변경. 서버가 자동 안내||
||OpenCode 403|API 키 저장 여부 확인. 키 없이 Go 추론 불가||
||Console 무료모델 실패|upstream 한시 장애 가능. 잠시 후 재시도||

== 9. 디렉터리 구조 ==

```text
D:\test\SpriteRepair
├─ server.py / SpriteRepair.bat   서버 + 실행기 (:5190)
├─ app/                           웹 UI
├─ sprite_repair/                 파이프라인·AI·내보내기 모듈
│  └─ providers/opencode/         OpenCode Go/Console (어댑터·탐색·레지스트리)
├─ benchmark/                     GPT 4×4 벤치마크 하네스 + 코퍼스
├─ samples/ docs/ tests/
├─ .env                           키 전용 (git 제외)
└─ workspace/                     세션·산출물 (git 제외)
```
