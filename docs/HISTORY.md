# SpriteRepair 작업 이력

> 프로젝트 연혁 · 의사결정 기록 · 남은 과제
> 최종 업데이트: 2026-09-11

== 1. 한눈에 보기 ==

||시기||내용||상태||
||2026-09-09|UX 패치 (프레임 삭제 등), 스모크 테스트, AI 캐시 체계|완료||
||2026-09-10 새벽|이펙트 모듈군 추가 (breathe/recolor/chromakey/motion/palette)|완료||
||2026-09-10 오전|Ollama 로컬 연동 (기본 비전 모델)|완료||
||2026-09-10|OpenCode Go/Console 멀티모델 확장|완료·실측 검증||
||2026-09-10|실측 GPT 4×4 벤치마크 하네스 + 코퍼스 27종|하네스 완료·사람 검수 대기||
||2026-09-10|모델 빠른선택 모달 + 공식 가격표 반영|완료||
||2026-09-10~11|Studio UI 재구성 (별도 작업)|완료||
||2026-09-11|프론트 OpenCode 연동 재구현 (재구성본 적응)|완료||
||2026-09-11|독립 승격 (`MikuChat-Lab` → `D:\test\SpriteRepair`) + GitHub Private 푸시|완료||

== 2. 시기별 상세 ==

=== 2.1. 코어 파이프라인 (Phase 1~5) ===
* 그리드=시드, 알파 확장 bbox, 캐릭터/VFX 분리, 풋 앵커, 전역 안전 캔버스
* 소유권 마스크 브러시, Undo/Redo, 크롭 pad/tight/safe, 기준 프레임
* AI 콘택트시트 QA, 흔들림/스케일 QA, APNG·WebP, `.spriteproject`
* 원칙 고정: AI는 판정, 편집은 Pillow. 오프라인 CV+수동 폴백 유지

=== 2.2. 2026-09-09 — UX 패치 ===
* `/api/delete-frames` 등 라우트 추가 (`workspace/ux_patch`에 원본 보관)
* 스모크 export (GIF/APNG/WebP/시트) 동작 확인, 서버 로그상 밤 11시까지 가동

=== 2.3. 2026-09-10 새벽 — 이펙트 모듈군 ===
* `breathe.py` (호흡 애니메이션), `recolor.py`, `chromakey.py` (배경 자동 제거),
  `motion.py`, `palette.py` (인덱스드 팔레트) 추가 및 서버 라우트 연결

=== 2.4. 2026-09-10 오전 — Ollama 연동 ===
* 로컬 Ollama 프로바이더 추가, 기본 비전 모델 `huihui_ai/qwen3-vl-abliterated`
* 키 불필요·무료·수 초 응답을 기본값으로 승격

=== 2.5. 2026-09-10 — OpenCode 확장 ===
* `sprite_repair/providers/opencode/` 신설: registry / discovery / adapters(chat·responses·messages) / provider
* `GET /models` 동적 탐색이 정적 목록보다 우선. Go 36종·Console 70종 확인
* 필수 헤더 규명: 브라우저 User-Agent + `x-opencode-session` (없으면 403/1010)
* 비전 프로브(4프레임 시프트 시트)로 5종 `VISION_VERIFIED`:
  DeepSeek V4 Flash Vision Exp, Kimi K3, Qwen3.8 Flash, MiMo-V2.5, GLM-5.3-Flash
* 텍스트 5종 + Console `big-pickle` 실측 통과. Console 무료 2종은 upstream 500으로 일시불가 기록
* 폴백 체인 (`AI_FALLBACK_*`), `/api/ai-probe`, 검증 상태 파일 영속화
* E2E: 실측 GPT 시트 16프레임 AI 정렬 성공

=== 2.6. 2026-09-10 — 벤치마크 ===
* Downloads 실측 GPT 시트에서 그리드 검출로 27종 선별 (합성 제외, 20종 기준 초과)
* `run_benchmark.py`: 파이프라인+전포맷 재디코드 검증+자동 메트릭+before/after+`review.html`
* 결과: 27/27 파이프라인 OK, 16/16 검출, 27/27 export OK
* `aggregate.py`: results.csv/json + KPI 보고서. 사람 검수 대기 중

=== 2.7. 2026-09-10 — 빠른선택 모달 ===
* 제공자 카드 + 프리셋 카드(가격·한글설명·배지) + 직접입력 구조
* Go 공식 가격표 스냅샷 내장, OpenRouter 실시간 가격 표시
* 공식 엔드포인트표 대조로 프로토콜 정정 (minimax/qwen→messages, kimi-k2.6→chat 등)

=== 2.8. 2026-09-10~11 — Studio UI 재구성 (별도 작업) ===
* 프론트 전체가 Studio 구조로 재작성됨. 이 과정에서 OpenCode 프론트 연동이 소실됨

=== 2.9. 2026-09-11 — 프론트 재구현 + 독립 승격 ===
* 새 구조(`ctx-*`, `studio-modal-*`)에 맞춰 제공자 6종·라벨·그룹필터·모달·키저장·가드 재구현
* 전체 목록 표시로 변경 (비전 숨김 → 비전우선 정렬)
* `D:\test\SpriteRepair`로 이동, GitHub Private (`loliRuriruri/2DSpriteRepair`) main 푸시

== 3. 주요 의사결정 기록 ==

||결정||이유||
||그리드는 자르지 않는다|GPT 시트는 칸을 넘치는 게 정상이므로 씨앗+확장으로 처리||
||AI는 좌표만, 편집은 로컬|재현성·오프라인 동작·비용 통제||
||모델 목록 하드코딩 금지|`/models`가 수시로 바뀌므로 탐색 우선, 레지스트리는 부트스트랩||
||이름으로 비전 추정 금지|런타임 프로브 통과만 `VISION_VERIFIED`||
||합성 코퍼스 금지|실측 20종 미만이면 `BENCHMARK_CORPUS_INCOMPLETE` 선언||
||키는 .env 전용|로그·응답·커밋에 절대 노출 금지 (마스크 힌트만)||
||좀비 서버는 cmdline 기준 kill|fork 구조라 부모 PID만 죽이면 리스너가 잔류||

== 4. 남은 과제 ==

1. `benchmark/review.html` 사람 검수 → `aggregate.py` → 최종 KPI 확정
2. 브라우저에서 빠른선택 모달 렌더링 육안 확인
3. Console 무료모델 장애 경과 관찰
4. 실패 Top 유형 확인 후 다음 개발 Phase 결정 (에디터 기능 추가는 그 이후)
