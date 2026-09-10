# Third-Party Notices & Source Code Adoption Log

**Project**: SpriteRepair / AI Sprite Animation Repair Studio  
**Policy**: In strict compliance with open-source and proprietary software licenses, this document tracks all external specifications, algorithms, and architectural references adopted by SpriteRepair.

---

## 1. Aseprite

- **Project**: Aseprite (`https://github.com/aseprite/aseprite`)
- **Copyright**: (C) 2001-2024 David Capello, Igara Studio S.A.
- **License**: Aseprite EULA (Proprietary) / MIT (select submodules & specifications)
- **Adoption Scope**:
  - **Behavior Reference Only**: Menu naming, keyboard shortcut layout, 2D timeline matrix ergonomics, and command taxonomy.
  - **Specification Reference**: JSON metadata format (`RGBA8888` schema) and binary format chunk specifications.
  - **API Bridge**: External CLI invocation and generated Lua script automation.
- **Restrictions Applied**:
  - **Zero Code Copying**: No C++ source code under the Aseprite EULA has been copied, ported, or translated.
  - **Zero Asset Redistribution**: No Aseprite fonts, icons, themes, or graphics are bundled or distributed.

---

## 2. LibreSprite

- **Project**: LibreSprite (`https://github.com/LibreSprite/LibreSprite`)
- **Copyright**: (C) 2018-2024 LibreSprite Contributors
- **License**: GNU General Public License v2 (GPLv2)
- **Adoption Scope**:
  - **Clean-Room Architectural Reference Only**: Structural models for layer grouping, cel ownership, and 2D selection mask manipulation analyzed conceptually.
- **Restrictions Applied**:
  - **Zero Code Merging**: No LibreSprite C++ source code is merged or compiled into SpriteRepair.
  - **Independent Clean-Room Authorship**: All algorithms, classes, and UI components are authored independently in Python and JavaScript to ensure clean separation and avoid GPL viral contamination.

---

## 3. Python Ecosystem Components

- **Pillow (PIL Fork)**: HPND License (Image processing, GIF/APNG/WebP encoding)
- **OpenCV (cv2)**: Apache 2.0 License (Connected component analysis, edge heuristics)
- **NVIDIA Cloud Functions / OpenAI Python SDK**: Apache 2.0 License (Optional Vision AI API communication)
