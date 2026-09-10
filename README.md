# Sprite Repair

스프라이트시트 **수리** 도구 (MikuChat Lab).

균등 그리드 절단기가 아닙니다. 그리드 칸은 **시드(seed)** 일 뿐이고, 알파 기반 전경 추출 + 발/루트 앵커 정렬로 프레임을 맞춥니다.

## 실행

```bat
SpriteRepair.bat
```

브라우저가 `http://127.0.0.1:5190/` 로 열립니다.

수동 실행:

```bat
cd /d D:\test\SpriteRepair
.venv\Scripts\python.exe server.py
```

CLI만 쓸 때:

```bat
.venv\Scripts\python.exe -m sprite_repair samples\synthetic_4x4.png --cols 4 --rows 4 --out workspace\cli_smoke
```

## 원칙

1. **그리드 = 힌트/시드** — 캐릭터가 칸 밖으로 넘쳐도 확장 bbox로 잘라냅니다.
2. **앵커(발/루트)** — 자동 추정 후 UI에서 드래그·WASD·버튼으로 보정합니다.
3. **마스터 = PNG 프레임 + `animation.json`** — GIF는 미리보기 전용(disposal=restore background).

## 보내기 결과

`workspace/<session>/<name>/`

- `frames/000.png` …
- `animation.json` — canvas, frame rect/anchor/offset/duration
- `preview.gif`
- `spritesheet.png` — 앵커 정렬된 정규화 시트(옵션)

## 의존성

- Python 3.11+ (로컬 `py -3` / venv)
- Pillow only (`.venv`에 설치)

FastAPI/Flask/Cubism/gorest 불필요.
