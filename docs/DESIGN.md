# Sprite Repair 설계 (MVP)

## 파이프라인

```
spritesheet PNG
    │
    ▼
[1] 그리드 시드 (기본 4×4) ── 칸 중심/영역만 씨앗
    │
    ▼
[2] 알파 전경 추출
    · seed 안 불투명 픽셀에서 flood-fill
    · 확장 검색 영역 허용 (칸 밖 OK)
    · 이웃 시드 코어(안쪽 50%)는 soft-forbid → 몸통 도난 완화
    │
    ▼
[3] VFX 휴리스틱 — 본체 대비 작은 하단 분리 블롭 제거(불완전 OK)
    │
    ▼
[4] 발/루트 앵커 = 바디 마스크 하단 밴드의 중앙(x) + 최하단(y)
    │
    ▼
[5] UI 보정 — 타임라인 / 양파껍질 / 드래그·너지
    │
    ▼
[6] 전역 캔버스 = 앵커 기준 max extents
    │
    ▼
[7] 재합성(앵커 정렬) → frames + animation.json + preview.gif
```

## 왜 균등 크롭이 아닌가

AI/수작업 시트는 프레임마다 실루엣이 칸을 넘나듭니다. 고정 셀 크롭은

- 팔·치마·이펙트를 잘리게 하고
- 빈 여백이 프레임마다 달라 발이 덜렁거리게 만듭니다.

시드+확장 bbox+앵커 정렬이 “수리”의 핵심입니다.

##보내기 포맷

### `animation.json` (발췌)

```json
{
  "version": 1,
  "canvas": {"w": 128, "h": 160, "anchor": {"x": 64, "y": 150}},
  "frames": [
    {
      "frame": 0,
      "file": "frames/000.png",
      "rect": {"x": 0, "y": 0, "w": 128, "h": 160},
      "anchor": {"x": 64, "y": 150},
      "offset": {"x": 10, "y": 5},
      "duration": 80
    }
  ]
}
```

- `rect` / `anchor`: 최종 공유 캔버스 기준
- `offset`: 원본 크롭을 캔버스에 붙인 위치
- GIF는 미리보기; 마스터는 PNG+JSON

## 비범위 (MVP)

- 자동 리깅 / Cubism / Live2D
- 메시 변형 · 본 추정
- 클라우드 업로드
- gorest 전체 설치
