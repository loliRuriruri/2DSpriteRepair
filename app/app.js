/* Sprite Repair UI */
(() => {
  const $ = (id) => document.getElementById(id);
  const state = {
    activeTool: "anchor",
    diffViewEnabled: false,
    file: null,
    sessionId: null,
    frames: [],
    frameUrls: [],
    composedUrls: [],
    canvas: null,
    index: 0,
    activeLayerIndex: 0,
    images: [], // HTMLImageElement for raw frames
    composedImages: [], // HTMLImageElement for composed frames
    project: null,
    layers: [
      { id: "layer_character", name: "Character", visible: true, locked: false, opacity: 1.0, type: "character" },
      { id: "layer_vfx", name: "VFX", visible: true, locked: false, opacity: 1.0, type: "vfx" },
    ],
    tags: [
      { name: "Main", from_frame: 0, to_frame: 15, direction: "forward", color: "#6aa8ff" },
    ],
    zoom: 2,
    pan: { x: 0, y: 0 },
    isPanning: false,
    panStart: { x: 0, y: 0 },
    playing: false,
    playTimer: null,
    playDir: 1,
    loopMode: "loop",
    fps: 12,
    drag: false,
    refIndex: null,
    history: [],
    future: [],
    historyLock: false,
    maskStrokes: [],
    maskPainting: false,
    celClipboard: null,
    selectedCels: new Set(),
    lastSelectedCel: null,
    previewPlaying: false,
    previewTimer: null,
    previewIndex: 0,
    previewScale: 2,
    selection: null,
    selectionDraft: null,
  };

  const status = (msg) => { $("status").textContent = msg; };

  function notifyUser(msg, isError = false) {
    console.warn("[SpriteRepair]", msg);
    status(msg);
    const hud = $("stageHud");
    if (hud && isError) {
      hud.style.borderColor = "var(--danger)";
      setTimeout(() => { if (hud) hud.style.borderColor = "var(--border)"; }, 3500);
    }
  }

  function captureSnapshot() {
    return {
      frames: JSON.parse(JSON.stringify(state.frames)),
      layers: JSON.parse(JSON.stringify(state.layers)),
      tags: JSON.parse(JSON.stringify(state.tags)),
      index: state.index,
      activeLayerIndex: state.activeLayerIndex,
      refIndex: state.refIndex,
      images: state.images.slice(),
      frameUrls: state.frameUrls.slice(),
      composedUrls: state.composedUrls.slice(),
    };
  }

  function pushHistory() {
    if (state.historyLock || !state.frames.length) return;
    state.history.push(captureSnapshot());
    if (state.history.length > 50) state.history.shift();
    state.future = [];
  }

  function applySnapshot(snap) {
    state.historyLock = true;
    try {
      state.frames = JSON.parse(JSON.stringify(snap.frames));
      state.layers = JSON.parse(JSON.stringify(snap.layers));
      state.tags = JSON.parse(JSON.stringify(snap.tags));
      state.images = snap.images.slice();
      state.frameUrls = snap.frameUrls.slice();
      state.composedUrls = snap.composedUrls.slice();
      state.refIndex = snap.refIndex;
      state.activeLayerIndex = snap.activeLayerIndex;
      if ($("refLabel")) {
        $("refLabel").textContent = state.refIndex == null ? "기준: 없음" : `기준: 프레임 ${state.refIndex + 1}`;
      }
      buildTimeline();
      buildAsepriteTimeline();
      updateInspectorLayers();
      setIndex(snap.index);
    } finally {
      state.historyLock = false;
    }
  }

  function undo() {
    if (!state.history.length) return;
    const cur = captureSnapshot();
    const prev = state.history.pop();
    state.future.push(cur);
    applySnapshot(prev);
    status("실행취소 (Undo)");
  }

  function redo() {
    if (!state.future.length) return;
    const cur = captureSnapshot();
    const next = state.future.pop();
    state.history.push(cur);
    applySnapshot(next);
    status("다시실행 (Redo)");
  }



  $("file").addEventListener("change", (e) => {
    state.file = e.target.files[0] || null;
    $("btnProcess").disabled = !state.file;
    status(state.file ? `선택됨: ${state.file.name}` : "대기 중");
  });

  $("btnProcess").addEventListener("click", async () => {
    if (!state.file) return;
    status("처리 중…");
    $("btnProcess").disabled = true;
    try {
      const fd = new FormData();
      fd.append("file", state.file);
      fd.append("cols", $("cols").value);
      fd.append("rows", $("rows").value);
      fd.append("duration", $("duration").value);
      fd.append("pad", $("pad").value);
    if ($("expand_ratio")) fd.append("expand_ratio", $("expand_ratio").value);
      fd.append("alpha", $("alpha").value);
      if ($("autoGrid") && $("autoGrid").checked) fd.append("auto_grid", "1");
      const res = await fetch("/api/process", { method: "POST", body: fd });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "process failed");
      await applySession(data, { resetHistory: true });
      status(`추출 완료 · ${data.frames.length}프레임 · 캔버스 ${data.canvas.w}×${data.canvas.h}`);
      $("btnExport").disabled = false;
      if ($("btnAiAlign")) $("btnAiAlign").disabled = false;
    } catch (err) {
      console.error(err);
      status("오류: " + err.message);
      notifyUser("처리 실패: " + err.message);
    } finally {
      $("btnProcess").disabled = !state.file;
    }
  });

  async function applySession(data, opts) {
    try { renderQa(data); } catch (e) { console.warn(e); }
    if (opts && opts.resetHistory) {
      state.history = [];
      state.future = [];
    }
    state.sessionId = data.session_id;
    if ($("btnAiAlign")) $("btnAiAlign").disabled = !state.sessionId;
    state.frames = (data.frames || []).map((f) => ({ ...f, anchor: { ...f.anchor } }));
    state.frameUrls = data.frame_urls || [];
    state.composedUrls = data.composed_urls || [];
    state.canvas = data.canvas;
    state.images = await Promise.all(state.frameUrls.map(loadImage));
    state.composedImages = await Promise.all((state.composedUrls.length ? state.composedUrls : state.frameUrls).map(loadImage));

    if (data.project) {
      state.project = data.project;
      if (data.project.layers && data.project.layers.length) {
        state.layers = data.project.layers.map(l => ({
          id: l.id,
          name: l.name,
          visible: l.visible !== false,
          locked: !!l.locked,
          opacity: l.opacity != null ? (l.opacity > 1 ? l.opacity / 255 : l.opacity) : 1.0,
          type: l.type || "character",
          blend_mode: l.blend_mode || "normal",
        }));
      }
      if (data.project.tags && data.project.tags.length) {
        state.tags = data.project.tags.map(t => ({
          name: t.name,
          from_frame: t.from_frame,
          to_frame: t.to_frame,
          direction: t.direction || "forward",
          color: t.color || "#6aa8ff",
        }));
      }
    } else {
      state.tags = [
        { name: "Main", from_frame: 0, to_frame: Math.max(0, state.frames.length - 1), direction: "forward", color: "#6aa8ff" }
      ];
    }

    buildTimeline();
    buildAsepriteTimeline();
    setIndex(0);
    $("meta").textContent = JSON.stringify(
      { source: data.source, sheet_size: data.sheet_size, grid: data.grid, canvas: data.canvas },
      null,
      2
    );
  }

  function loadImage(url) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = url;
    });
  }

  function buildTimeline() {
    const tl = $("timeline");
    if (!tl) return;
    tl.innerHTML = "";
    (state.composedUrls.length ? state.composedUrls : state.frameUrls).forEach((url, i) => {
      const img = document.createElement("img");
      img.className = "thumb" + (i === state.index ? " active" : "");
      img.src = url;
      img.title = `프레임 ${i} (${state.frames[i]?.duration || 80}ms)`;
      img.addEventListener("click", () => setIndex(i));
      tl.appendChild(img);
    });
  }

  function buildAsepriteTimeline() {
    // 1. Tags Bar
    const tagBar = $("tlTagsBar");
    if (tagBar) {
      tagBar.innerHTML = "";
      state.tags.forEach((t) => {
        const pill = document.createElement("div");
        pill.className = "tl-tag-pill" + (state.index >= t.from_frame && state.index <= t.to_frame ? " active" : "");
        pill.style.borderLeftColor = t.color || "#6aa8ff";
        pill.textContent = `▶ ${t.name} [${t.from_frame}-${t.to_frame}]`;
        pill.title = `태그 '${t.name}' 구간 선택 및 이동`;
        pill.addEventListener("click", () => setIndex(t.from_frame));
        tagBar.appendChild(pill);
      });
    }

    // 2. Layers Column
    const layersCol = $("tlLayersCol");
    if (layersCol) {
      layersCol.innerHTML = '<div class="tl-layer-header-top">레이어 (Layers)</div>';
      state.layers.forEach((layer, lIdx) => {
        const row = document.createElement("div");
        row.className = "tl-layer-item" + (lIdx === state.activeLayerIndex ? " active" : "");
        if (layer.type === "group") row.classList.add("is-group");
        if (layer.type === "reference") row.classList.add("is-ref");
        if (layer.parent_id) row.classList.add("is-child");

        // Hide if parent group is collapsed
        const parent = layer.parent_id ? state.layers.find(p => p.id === layer.parent_id) : null;
        if (parent && parent.collapsed) {
          row.style.display = "none";
        }

        const eye = document.createElement("span");
        eye.className = "tl-layer-icon" + (!layer.visible ? " hidden" : "");
        eye.textContent = layer.visible ? "👁️" : "🚫";
        eye.title = layer.visible ? "레이어 숨기기" : "레이어 보이기";
        eye.addEventListener("click", (e) => {
          e.stopPropagation();
          layer.visible = !layer.visible;
          eye.className = "tl-layer-icon" + (!layer.visible ? " hidden" : "");
          eye.textContent = layer.visible ? "👁️" : "🚫";
          draw();
        });

        const lock = document.createElement("span");
        lock.className = "tl-layer-icon";
        lock.textContent = layer.locked ? "🔒" : "🔓";
        lock.title = layer.locked ? "잠금 해제" : "잠금";
        lock.addEventListener("click", (e) => {
          e.stopPropagation();
          layer.locked = !layer.locked;
          lock.textContent = layer.locked ? "🔒" : "🔓";
        });

        row.appendChild(eye);
        row.appendChild(lock);

        // Group folder toggle
        if (layer.type === "group") {
          const folder = document.createElement("span");
          folder.className = "tl-folder-toggle";
          folder.textContent = layer.collapsed ? "📁" : "📂";
          folder.title = layer.collapsed ? "그룹 펼치기" : "그룹 접기";
          folder.addEventListener("click", (e) => {
            e.stopPropagation();
            layer.collapsed = !layer.collapsed;
            buildAsepriteTimeline();
            updateInspectorLayers();
          });
          row.appendChild(folder);
        }

        const name = document.createElement("span");
        name.className = "tl-layer-name";
        name.textContent = layer.name;
        row.appendChild(name);

        if (layer.type === "reference") {
          const badge = document.createElement("span");
          badge.className = "tl-layer-badge ref";
          badge.textContent = "REF";
          row.appendChild(badge);
        } else if (layer.type === "group") {
          const badge = document.createElement("span");
          badge.className = "tl-layer-badge group";
          badge.textContent = "GRP";
          row.appendChild(badge);
        }

        row.addEventListener("click", () => {
          state.activeLayerIndex = lIdx;
          updateAsepriteTimelineSelection();
          updateInspectorProperties();
        });

        layersCol.appendChild(row);
      });
    }

    // 3. Frames Header
    const framesHdr = $("tlFramesHeader");
    if (framesHdr) {
      framesHdr.innerHTML = "";
      state.frames.forEach((f, fIdx) => {
        const col = document.createElement("div");
        col.className = "tl-frame-col-header" + (fIdx === state.index ? " active" : "");
        col.innerHTML = `<span>${fIdx}</span><span style="opacity:0.6;font-size:8px">${f.duration || 80}ms</span>`;
        col.title = `프레임 ${fIdx} 선택 (${f.duration || 80}ms)`;
        col.addEventListener("click", () => setIndex(fIdx));
        framesHdr.appendChild(col);
      });
    }

    // 4. Cels Grid
    const celsGrid = $("tlCelsGrid");
    if (celsGrid) {
      celsGrid.innerHTML = "";
      state.layers.forEach((layer, lIdx) => {
        const row = document.createElement("div");
        row.className = "tl-cels-row";
        if (layer.type === "group") row.classList.add("is-group-row");

        // Hide if parent group is collapsed
        const parent = layer.parent_id ? state.layers.find(p => p.id === layer.parent_id) : null;
        if (parent && parent.collapsed) {
          row.style.display = "none";
        }

        state.frames.forEach((f, fIdx) => {
          const cel = document.createElement("div");
          const key = `${lIdx}:${fIdx}`;
          cel.className = "tl-cel" + (fIdx === state.index ? " active-col" : "") +
            (fIdx === state.index && lIdx === state.activeLayerIndex ? " active" : "") +
            (state.selectedCels.has(key) ? " multi-selected" : "");

          const isOccupied = !f.empty;
          if (isOccupied) cel.classList.add("occupied");

          if (f.linked_cel_id) {
            cel.classList.add("linked");
            const prevL = fIdx > 0 && state.frames[fIdx - 1]?.linked_cel_id === f.linked_cel_id;
            const nextL = fIdx + 1 < state.frames.length && state.frames[fIdx + 1]?.linked_cel_id === f.linked_cel_id;
            if (!prevL) cel.classList.add("link-start");
            if (!nextL) cel.classList.add("link-end");
          }

          const dot = document.createElement("div");
          dot.className = "tl-cel-dot";
          cel.appendChild(dot);

          cel.title = `${layer.name} - 프레임 ${fIdx}${f.linked_cel_id ? ` (연결: ${f.linked_cel_id})` : ""}`;
          cel.addEventListener("click", (e) => {
            handleCelClick(e, lIdx, fIdx);
          });

          row.appendChild(cel);
        });
        celsGrid.appendChild(row);
      });
    }
  }

  function handleCelClick(e, lIdx, fIdx) {
    const key = `${lIdx}:${fIdx}`;
    if (e.shiftKey && state.lastSelectedCel) {
      const startF = Math.min(state.lastSelectedCel.frameIdx, fIdx);
      const endF = Math.max(state.lastSelectedCel.frameIdx, fIdx);
      const startL = Math.min(state.lastSelectedCel.layerIdx, lIdx);
      const endL = Math.max(state.lastSelectedCel.layerIdx, lIdx);
      for (let l = startL; l <= endL; l++) {
        for (let f = startF; f <= endF; f++) {
          state.selectedCels.add(`${l}:${f}`);
        }
      }
    } else if (e.ctrlKey || e.metaKey) {
      if (state.selectedCels.has(key)) {
        state.selectedCels.delete(key);
      } else {
        state.selectedCels.add(key);
      }
      state.lastSelectedCel = { layerIdx: lIdx, frameIdx: fIdx };
    } else {
      state.selectedCels.clear();
      state.selectedCels.add(key);
      state.lastSelectedCel = { layerIdx: lIdx, frameIdx: fIdx };
    }
    state.activeLayerIndex = lIdx;
    setIndex(fIdx);
  }

  function updateAsepriteTimelineSelection() {
    const layersCol = $("tlLayersCol");
    if (layersCol) {
      const items = layersCol.querySelectorAll(".tl-layer-item");
      items.forEach((it, idx) => it.classList.toggle("active", idx === state.activeLayerIndex));
    }

    const framesHdr = $("tlFramesHeader");
    if (framesHdr) {
      const cols = framesHdr.children;
      for (let i = 0; i < cols.length; i++) {
        cols[i].classList.toggle("active", i === state.index);
      }
      if (cols[state.index]) {
        cols[state.index].scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
      }
    }

    const celsGrid = $("tlCelsGrid");
    if (celsGrid) {
      const rows = celsGrid.querySelectorAll(".tl-cels-row");
      rows.forEach((r, lIdx) => {
        const cels = r.querySelectorAll(".tl-cel");
        cels.forEach((c, fIdx) => {
          const key = `${lIdx}:${fIdx}`;
          c.classList.toggle("active-col", fIdx === state.index);
          c.classList.toggle("active", fIdx === state.index && lIdx === state.activeLayerIndex);
          c.classList.toggle("multi-selected", state.selectedCels.has(key));
        });
      });
    }

    const tagBar = $("tlTagsBar");
    if (tagBar) {
      const pills = tagBar.querySelectorAll(".tl-tag-pill");
      state.tags.forEach((t, i) => {
        if (pills[i]) pills[i].classList.toggle("active", state.index >= t.from_frame && state.index <= t.to_frame);
      });
    }
  }

  function setIndex(i) {
    if (!state.frames.length) return;
    state.index = (i + state.frames.length) % state.frames.length;
    const f = state.frames[state.index];
    $("frameLabel").textContent = `프레임 ${state.index + 1} / ${state.frames.length}`;
    $("ax").value = f.anchor.x;
    $("ay").value = f.anchor.y;
    [...$("timeline").children].forEach((el, idx) => {
      el.classList.toggle("active", idx === state.index);
    });
    updateAsepriteTimelineSelection();
    updateInspectorProperties();
    updateInspectorLayers();
    draw();
  }

  function currentScale() {
    const img = state.images[state.index];
    if (!img) return 1;
    if (state.zoom === "fit") {
      const wrap = $("canvasWrap");
      const maxW = (wrap ? wrap.clientWidth : 512) - 40;
      const maxH = (wrap ? wrap.clientHeight : 480) - 40;
      return Math.max(1, Math.min(maxW / img.width, maxH / img.height));
    }
    return Number(state.zoom) || 2;
  }

  function draw() {
    const canvas = $("view");
    const ctx = canvas.getContext("2d");
    const img = state.images[state.index];
    if (!img) return;

    const scale = currentScale();
    const cw = Math.round(img.width * scale);
    const ch = Math.round(img.height * scale);
    if (canvas.width !== cw || canvas.height !== ch) {
      canvas.width = cw;
      canvas.height = ch;
    }
    canvas.style.transform = `translate(${state.pan.x}px, ${state.pan.y}px)`;
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const curA = state.frames[state.index].anchor;

    // 1. Multi-Frame Onion Skinning (Past & Future)
    const onionOn = ($("onionSkinToggle") && $("onionSkinToggle").checked) || ($("onion") && $("onion").checked);
    if (onionOn) {
      const pastCount = Number($("onionPast") ? $("onionPast").value : 1) || 1;
      const futCount = Number($("onionFuture") ? $("onionFuture").value : 0) || 0;

      // Reference frame onion skin
      if ($("onionRef") && $("onionRef").checked && state.refIndex != null && state.refIndex !== state.index) {
        const refImg = state.images[state.refIndex];
        const refA = state.frames[state.refIndex].anchor;
        if (refImg) {
          ctx.save();
          ctx.globalAlpha = 0.35;
          const ox = (curA.x - refA.x) * scale;
          const oy = (curA.y - refA.y) * scale;
          ctx.drawImage(refImg, ox, oy, refImg.width * scale, refImg.height * scale);
          ctx.restore();
        }
      }

      // Past frames (tinted blue/red)
      for (let p = pastCount; p >= 1; p--) {
        const oi = state.index - p;
        if (oi >= 0 && oi < state.images.length && oi !== state.index) {
          const pastImg = state.images[oi];
          const pastA = state.frames[oi].anchor;
          ctx.save();
          ctx.globalAlpha = 0.35 / p;
          const ox = (curA.x - pastA.x) * scale;
          const oy = (curA.y - pastA.y) * scale;
          ctx.drawImage(pastImg, ox, oy, pastImg.width * scale, pastImg.height * scale);
          ctx.fillStyle = "rgba(70, 130, 255, 0.25)";
          ctx.fillRect(ox, oy, pastImg.width * scale, pastImg.height * scale);
          ctx.restore();
        }
      }

      // Future frames (tinted green)
      for (let f = 1; f <= futCount; f++) {
        const fi = state.index + f;
        if (fi >= 0 && fi < state.images.length && fi !== state.index) {
          const futImg = state.images[fi];
          const futA = state.frames[fi].anchor;
          ctx.save();
          ctx.globalAlpha = 0.35 / f;
          const ox = (curA.x - futA.x) * scale;
          const oy = (curA.y - futA.y) * scale;
          ctx.drawImage(futImg, ox, oy, futImg.width * scale, futImg.height * scale);
          ctx.fillStyle = "rgba(70, 240, 140, 0.25)";
          ctx.fillRect(ox, oy, futImg.width * scale, futImg.height * scale);
          ctx.restore();
        }
      }
    }

    // 2. Render Current Frame / Layers
    const charLayer = state.layers.find(l => l.type === "character") || state.layers[0];
    if (charLayer && charLayer.visible) {
      ctx.save();
      ctx.globalAlpha = charLayer.opacity;
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      ctx.restore();
    }

    // 3. Pixel Grid when zoomed >= 3x (Aseprite style)
    if (scale >= 3) {
      ctx.save();
      ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
      ctx.lineWidth = 1;
      for (let x = 0; x <= canvas.width; x += scale) {
        ctx.beginPath();
        ctx.moveTo(x + 0.5, 0);
        ctx.lineTo(x + 0.5, canvas.height);
        ctx.stroke();
      }
      for (let y = 0; y <= canvas.height; y += scale) {
        ctx.beginPath();
        ctx.moveTo(0, y + 0.5);
        ctx.lineTo(canvas.width, y + 0.5);
        ctx.stroke();
      }
      ctx.restore();
    }

    // 4. Center / VFX Pivot Guide (Cyan Circle)
    const cx = Math.round(img.width / 2) * scale;
    const cy = Math.round(img.height / 2) * scale;
    ctx.strokeStyle = "rgba(0, 220, 255, 0.4)";
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.arc(cx, cy, 6, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // 5. Foot Anchor Guide (Red Crosshair)
    const ax = curA.x * scale + scale / 2;
    const ay = curA.y * scale + scale / 2;
    ctx.strokeStyle = "#ff4d5e";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(ax - 14, ay);
    ctx.lineTo(ax + 14, ay);
    ctx.moveTo(ax, ay - 14);
    ctx.lineTo(ax, ay + 14);
    ctx.stroke();

    ctx.fillStyle = "rgba(255,77,94,0.9)";
    ctx.beginPath();
    ctx.arc(ax, ay, 4, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#ff4d5e";
    ctx.font = "10px monospace";
    ctx.fillText(`⚓ (${curA.x}, ${curA.y})`, ax + 6, ay - 6);


    // 5b. Difference View Overlay (Delta highlight & foot offset)
    const diffActive = state.activeTool === "diff" || ($("chkDiffView") && $("chkDiffView").checked);
    if (diffActive && state.frames.length > 1) {
      const targetType = ($("diffTargetSelect") && $("diffTargetSelect").value) || "prev";
      let targetIdx = targetType === "ref" && state.refIndex != null ? state.refIndex : state.index - 1;
      if (targetIdx < 0) targetIdx = state.frames.length - 1;
      if (targetIdx >= 0 && targetIdx < state.images.length && targetIdx !== state.index) {
        const targetImg = state.images[targetIdx];
        const targetA = state.frames[targetIdx].anchor;
        if (targetImg) {
          ctx.save();
          ctx.globalCompositeOperation = "difference";
          const ox = (curA.x - targetA.x) * scale;
          const oy = (curA.y - targetA.y) * scale;
          ctx.drawImage(targetImg, ox, oy, targetImg.width * scale, targetImg.height * scale);
          ctx.restore();

          const dx = curA.x - targetA.x;
          const dy = curA.y - targetA.y;
          if ($("diffReadout")) {
            $("diffReadout").textContent = `풋 오프셋 (F${targetIdx + 1} 대비): ΔX: ${dx >= 0 ? "+" : ""}${dx}px, ΔY: ${dy >= 0 ? "+" : ""}${dy}px`;
          }
        }
      }
    }

    // 5c. Advanced Selection Overlay & Marching Ants
    if (state.selection || state.selectionDraft) {
      ctx.save();
      if (state.selection && state.selection.bounds) {
        const { mask, w, h, bounds } = state.selection;
        const selCanvas = document.createElement("canvas");
        selCanvas.width = w;
        selCanvas.height = h;
        const sctx = selCanvas.getContext("2d");
        const sData = sctx.createImageData(w, h);
        for (let i = 0; i < mask.length; i++) {
          if (mask[i]) {
            sData.data[i * 4] = 65;
            sData.data[i * 4 + 1] = 135;
            sData.data[i * 4 + 2] = 255;
            sData.data[i * 4 + 3] = 90;
          }
        }
        sctx.putImageData(sData, 0, 0);
        ctx.drawImage(selCanvas, 0, 0, w * scale, h * scale);

        ctx.strokeStyle = "#4aa8ff";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 4]);
        ctx.strokeRect(bounds.x * scale, bounds.y * scale, bounds.w * scale, bounds.h * scale);
      }

      if (state.selectionDraft) {
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 4]);
        if (state.selectionDraft.type === "rect") {
          const s = state.selectionDraft.start;
          const c = state.selectionDraft.current;
          const rx = Math.min(s.x, c.x) * scale;
          const ry = Math.min(s.y, c.y) * scale;
          const rw = (Math.abs(c.x - s.x) + 1) * scale;
          const rh = (Math.abs(c.y - s.y) + 1) * scale;
          ctx.strokeRect(rx, ry, rw, rh);
        } else if (state.selectionDraft.type === "lasso" || state.selectionDraft.type === "polygon") {
          const pts = state.selectionDraft.points;
          if (pts && pts.length > 0) {
            ctx.beginPath();
            ctx.moveTo(pts[0].x * scale, pts[0].y * scale);
            for (let i = 1; i < pts.length; i++) {
              ctx.lineTo(pts[i].x * scale, pts[i].y * scale);
            }
            if (state.selectionDraft.type === "polygon" && state.selectionDraft.current) {
              ctx.lineTo(state.selectionDraft.current.x * scale, state.selectionDraft.current.y * scale);
            }
            ctx.stroke();

            if (state.selectionDraft.type === "polygon") {
              ctx.setLineDash([]);
              ctx.fillStyle = "#ffffff";
              for (const p of pts) {
                ctx.fillRect(p.x * scale - 2, p.y * scale - 2, 4, 4);
              }
              ctx.setLineDash([4, 4]);
            }
          }
        }
      }
      ctx.restore();
    }

    // 6. Update HUD & Zoom label
    const hud = $("stageHud");
    if (hud) {
      hud.textContent = `앵커: (${curA.x}, ${curA.y}) | 크기: ${img.width}x${img.height} | 줌: ${Math.round(scale * 100)}%`;
    }
    const zoomLbl = $("zoomLabel");
    if (zoomLbl) {
      zoomLbl.textContent = state.zoom === "fit" ? "Fit" : `${Math.round(scale * 100)}%`;
    }
  }

  if ($("onion")) $("onion").addEventListener("change", draw);
  if ($("onionSkinToggle")) $("onionSkinToggle").addEventListener("change", draw);
  if ($("onionPast")) $("onionPast").addEventListener("change", draw);
  if ($("onionFuture")) $("onionFuture").addEventListener("change", draw);

  if ($("firstFrame")) $("firstFrame").addEventListener("click", () => setIndex(0));
  if ($("lastFrame")) $("lastFrame").addEventListener("click", () => setIndex(state.frames.length - 1));
  if ($("prevFrame")) $("prevFrame").addEventListener("click", () => setIndex(state.index - 1));
  if ($("nextFrame")) $("nextFrame").addEventListener("click", () => setIndex(state.index + 1));

  if ($("loopMode")) {
    $("loopMode").addEventListener("change", (e) => {
      state.loopMode = e.target.value;
    });
  }

  if ($("fpsInput")) {
    $("fpsInput").addEventListener("input", (e) => {
      const v = Number(e.target.value);
      if (v > 0) {
        state.fps = v;
        const dur = Math.round(1000 / v);
        $("duration").value = dur;
      }
    });
  }

  // Zoom controls
  document.querySelectorAll(".btn-zoom").forEach(btn => {
    btn.addEventListener("click", () => {
      const z = btn.getAttribute("data-zoom");
      state.zoom = z === "fit" ? "fit" : Number(z);
      document.querySelectorAll(".btn-zoom").forEach(b => b.classList.toggle("active", b === btn));
      draw();
    });
  });

  // Mouse wheel zoom & pan on canvasWrap
  const wrap = $("canvasWrap");
  if (wrap) {
    wrap.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      if (typeof state.zoom !== "number") state.zoom = currentScale();
      if (ev.deltaY < 0) {
        state.zoom = Math.min(8, Math.round(state.zoom + 1));
      } else if (ev.deltaY > 0) {
        state.zoom = Math.max(1, Math.round(state.zoom - 1));
      }
      draw();
    }, { passive: false });

    window.addEventListener("keydown", (ev) => {
      if (ev.code === "Space" && ev.target.tagName !== "INPUT" && ev.target.tagName !== "TEXTAREA") {
        wrap.classList.add("panning");
      }
    });
    window.addEventListener("keyup", (ev) => {
      if (ev.code === "Space") {
        wrap.classList.remove("panning");
        state.isPanning = false;
      }
    });

    wrap.addEventListener("mousedown", (ev) => {
      if (ev.button === 1 || wrap.classList.contains("panning")) {
        state.isPanning = true;
        wrap.classList.add("is-panning");
        state.panStart = { x: ev.clientX - state.pan.x, y: ev.clientY - state.pan.y };
        ev.preventDefault();
      }
    });
    window.addEventListener("mousemove", (ev) => {
      if (state.isPanning) {
        state.pan.x = ev.clientX - state.panStart.x;
        state.pan.y = ev.clientY - state.panStart.y;
        $("view").style.transform = `translate(${state.pan.x}px, ${state.pan.y}px)`;
      }
    });
    window.addEventListener("mouseup", () => {
      if (state.isPanning) {
        state.isPanning = false;
        wrap.classList.remove("is-panning");
      }
    });
  }

  // ==================== LAYER OPERATIONS ====================
  function addNewLayer(name) {
    pushHistory();
    const id = `layer_${Date.now()}`;
    const layerName = name || `Layer ${state.layers.length + 1}`;
    state.layers.push({
      id,
      name: layerName,
      visible: true,
      locked: false,
      opacity: 1.0,
      type: "custom",
      blend_mode: "normal",
      parent_id: null,
      collapsed: false,
    });
    state.activeLayerIndex = state.layers.length - 1;
    buildAsepriteTimeline();
    updateInspectorLayers();
    status(`새 레이어 '${layerName}' 추가됨`);
  }

  function addNewLayerGroup(name) {
    pushHistory();
    const id = `group_${Date.now()}`;
    const groupName = name || `Group ${state.layers.filter(l => l.type === "group").length + 1}`;
    state.layers.push({
      id,
      name: groupName,
      visible: true,
      locked: false,
      opacity: 1.0,
      type: "group",
      parent_id: null,
      collapsed: false,
      blend_mode: "normal",
    });
    state.activeLayerIndex = state.layers.length - 1;
    buildAsepriteTimeline();
    updateInspectorLayers();
    status(`새 레이어 그룹 '${groupName}' 추가됨`);
  }

  function addNewReferenceLayer(name) {
    pushHistory();
    const id = `ref_${Date.now()}`;
    const refName = name || `Ref Art ${state.layers.filter(l => l.type === "reference").length + 1}`;
    state.layers.push({
      id,
      name: refName,
      visible: true,
      locked: false,
      opacity: 0.6,
      type: "reference",
      parent_id: null,
      collapsed: false,
      blend_mode: "normal",
    });
    state.activeLayerIndex = state.layers.length - 1;
    buildAsepriteTimeline();
    updateInspectorLayers();
    status(`새 참조 레이어 '${refName}' 추가됨`);
  }

  function renameCurrentLayer() {
    const cur = state.layers[state.activeLayerIndex];
    if (!cur) return;
    const newName = prompt("레이어 이름 변경:", cur.name);
    if (newName && newName.trim() && newName.trim() !== cur.name) {
      pushHistory();
      cur.name = newName.trim();
      buildAsepriteTimeline();
      updateInspectorLayers();
      updateInspectorProperties();
      status(`레이어 이름 변경: ${cur.name}`);
    }
  }

  function moveLayer(dir) {
    const idx = state.activeLayerIndex;
    const target = idx + dir;
    if (target < 0 || target >= state.layers.length) return;
    pushHistory();
    const tmp = state.layers[idx];
    state.layers[idx] = state.layers[target];
    state.layers[target] = tmp;
    state.activeLayerIndex = target;
    buildAsepriteTimeline();
    updateInspectorLayers();
    draw();
    status(`레이어 순서 변경: ${state.layers[target].name}`);
  }

  function duplicateCurrentLayer() {
    const cur = state.layers[state.activeLayerIndex];
    if (!cur) return;
    pushHistory();
    const dup = JSON.parse(JSON.stringify(cur));
    dup.id = `layer_${Date.now()}`;
    dup.name = `${cur.name} 복사본`;
    state.layers.splice(state.activeLayerIndex + 1, 0, dup);
    state.activeLayerIndex = state.activeLayerIndex + 1;
    buildAsepriteTimeline();
    updateInspectorLayers();
    status(`레이어 '${dup.name}' 복제됨`);
  }

  function deleteCurrentLayer() {
    if (state.layers.length <= 1) {
      notifyUser("최소 1개의 레이어가 필요합니다.");
      return;
    }
    const cur = state.layers[state.activeLayerIndex];
    if (confirm(`레이어 '${cur.name}'을 삭제하시겠습니까?`)) {
      pushHistory();
      state.layers.splice(state.activeLayerIndex, 1);
      state.activeLayerIndex = Math.max(0, state.activeLayerIndex - 1);
      buildAsepriteTimeline();
      updateInspectorLayers();
      draw();
      status("레이어 삭제 완료");
    }
  }

  // ==================== FRAME OPERATIONS ====================
  function insertBlankFrame() {
    if (!state.frames.length) return;
    pushHistory();
    const w = state.canvas ? state.canvas.w : 64;
    const h = state.canvas ? state.canvas.h : 64;
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    const dataUrl = c.toDataURL("image/png");
    const img = new Image();
    img.src = dataUrl;

    const newFrame = {
      frame: state.index + 1,
      duration: state.frames[state.index]?.duration || 80,
      anchor: { x: Math.round(w / 2), y: Math.round(h - 2) },
      content_rect: { x: 0, y: 0, width: w, height: h },
      qa_warnings: [],
      empty: true,
    };
    state.frames.splice(state.index + 1, 0, newFrame);
    state.images.splice(state.index + 1, 0, img);
    state.frameUrls.splice(state.index + 1, 0, dataUrl);
    buildTimeline();
    buildAsepriteTimeline();
    setIndex(state.index + 1);
    status(`새 빈 프레임 삽입 (프레임 ${state.index + 1})`);
  }

  function duplicateCurrentFrame() {
    if (!state.frames.length) return;
    pushHistory();
    const cur = state.frames[state.index];
    const dup = JSON.parse(JSON.stringify(cur));
    dup.frame = state.frames.length;
    state.frames.splice(state.index + 1, 0, dup);
    state.images.splice(state.index + 1, 0, state.images[state.index]);
    state.frameUrls.splice(state.index + 1, 0, state.frameUrls[state.index]);
    buildTimeline();
    buildAsepriteTimeline();
    setIndex(state.index + 1);
    status(`프레임 ${state.index} 복제됨`);
  }

  function deleteCurrentFrame() {
    if (state.frames.length <= 1) {
      notifyUser("최소 1개의 프레임이 필요합니다.");
      return;
    }
    if (confirm(`프레임 ${state.index + 1}을 삭제하시겠습니까?`)) {
      pushHistory();
      state.frames.splice(state.index, 1);
      state.images.splice(state.index, 1);
      state.frameUrls.splice(state.index, 1);
      const next = Math.min(state.index, state.frames.length - 1);
      buildTimeline();
      buildAsepriteTimeline();
      setIndex(next);
      status(`프레임 삭제 완료 (${state.frames.length}개 남음)`);
    }
  }

  function moveFrame(dir) {
    const idx = state.index;
    const target = idx + dir;
    if (target < 0 || target >= state.frames.length) return;
    pushHistory();
    const [f] = state.frames.splice(idx, 1);
    state.frames.splice(target, 0, f);
    const [img] = state.images.splice(idx, 1);
    state.images.splice(target, 0, img);
    const [url] = state.frameUrls.splice(idx, 1);
    state.frameUrls.splice(target, 0, url);
    buildTimeline();
    buildAsepriteTimeline();
    setIndex(target);
    status(`프레임 이동: ${idx + 1} → ${target + 1}`);
  }

  function reverseFrameSequence() {
    if (state.frames.length < 2) return;
    pushHistory();
    state.frames.reverse();
    state.images.reverse();
    state.frameUrls.reverse();
    buildTimeline();
    buildAsepriteTimeline();
    setIndex(0);
    status("프레임 순서 전체 반전 완료");
  }

  // ==================== CEL OPERATIONS ====================
  function copyCel() {
    const f = state.frames[state.index];
    const img = state.images[state.index];
    if (!f || !img) return;
    state.celClipboard = {
      layerId: state.layers[state.activeLayerIndex]?.id,
      anchor: { ...f.anchor },
      image: img,
      dataUrl: state.frameUrls[state.index],
      duration: f.duration,
      empty: f.empty,
    };
    status(`셀 복사됨 (${state.layers[state.activeLayerIndex]?.name} - 프레임 ${state.index + 1})`);
  }

  function pasteCel() {
    if (!state.celClipboard) {
      notifyUser("복사된 셀이 없습니다.");
      return;
    }
    pushHistory();
    const clip = state.celClipboard;
    const f = state.frames[state.index];
    if (f) {
      f.anchor = { ...clip.anchor };
      f.empty = clip.empty;
    }
    if (clip.image) {
      state.images[state.index] = clip.image;
      state.frameUrls[state.index] = clip.dataUrl;
    }
    buildTimeline();
    buildAsepriteTimeline();
    draw();
    status(`셀 붙여넣기 완료 (프레임 ${state.index + 1})`);
  }

  function syncLinkedCelImages(sourceIndex) {
    const srcFrame = state.frames[sourceIndex];
    if (!srcFrame || !srcFrame.linked_cel_id) return;
    const linkId = srcFrame.linked_cel_id;
    const srcImg = state.images[sourceIndex];
    const srcUrl = state.frameUrls[sourceIndex];
    state.frames.forEach((f, i) => {
      if (i !== sourceIndex && f.linked_cel_id === linkId) {
        state.images[i] = srcImg;
        state.frameUrls[i] = srcUrl;
      }
    });
  }

  function clearCel() {
    const f = state.frames[state.index];
    if (!f) return;
    pushHistory();
    f.empty = true;
    const c = document.createElement("canvas");
    c.width = state.images[state.index]?.width || 64;
    c.height = state.images[state.index]?.height || 64;
    const url = c.toDataURL("image/png");
    state.images[state.index] = c;
    state.frameUrls[state.index] = url;
    syncLinkedCelImages(state.index);
    buildTimeline();
    buildAsepriteTimeline();
    draw();
    status(`셀 지우기 완료 (프레임 ${state.index + 1})`);
  }

  function toggleCelLink() {
    const f = state.frames[state.index];
    if (!f) return;
    pushHistory();
    if (f.linked_cel_id) {
      f.linked_cel_id = null;
      // Deep-clone image buffer so unlinked cel is fully decoupled
      if (state.images[state.index]) {
        const cur = state.images[state.index];
        const cloneCanvas = document.createElement("canvas");
        cloneCanvas.width = cur.width || 64;
        cloneCanvas.height = cur.height || 64;
        const cctx = cloneCanvas.getContext("2d");
        cctx.drawImage(cur, 0, 0);
        state.images[state.index] = cloneCanvas;
        state.frameUrls[state.index] = cloneCanvas.toDataURL("image/png");
      }
      status(`프레임 ${state.index + 1} 연결 해제됨 (독립 복사본 생성)`);
    } else {
      const prevId = state.index > 0 ? state.frames[state.index - 1]?.linked_cel_id : null;
      const targetId = prevId || `link_${Date.now()}`;
      if (state.index > 0 && !prevId) {
        state.frames[state.index - 1].linked_cel_id = targetId;
      }
      f.linked_cel_id = targetId;
      // Synchronize image buffer from partner cel
      const partnerIdx = state.frames.findIndex((other, oi) => oi !== state.index && other.linked_cel_id === targetId);
      if (partnerIdx !== -1 && state.images[partnerIdx]) {
        state.images[state.index] = state.images[partnerIdx];
        state.frameUrls[state.index] = state.frameUrls[partnerIdx];
      }
      status(`프레임 ${state.index + 1} 연결됨 (${targetId})`);
    }
    buildAsepriteTimeline();
    updateInspectorProperties();
  }

  // ==================== NEAREST-NEIGHBOR TRANSFORMS ====================
  function transformFlipH() {
    const img = state.images[state.index];
    const f = state.frames[state.index];
    if (!img || !f) return;
    const w = img.width || (f.size && f.size.w) || (f.rect && f.rect.w) || state.canvas?.w || 1;
    const h = img.height || (f.size && f.size.h) || (f.rect && f.rect.h) || state.canvas?.h || 1;
    pushHistory();
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    const ctx = c.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    ctx.translate(w, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(img, 0, 0, w, h);
    const dataUrl = c.toDataURL("image/png");
    state.images[state.index] = c;
    state.frameUrls[state.index] = dataUrl;
    if (f.size) { f.size.w = w; f.size.h = h; }
    f.anchor.x = w - 1 - f.anchor.x;
    // Invariant assertions
    if (f.anchor.x < 0 || f.anchor.x >= w || f.anchor.y < 0 || f.anchor.y >= h) {
      throw new Error(`FlipH invariant violation: anchor (${f.anchor.x}, ${f.anchor.y}) out of bounds (${w}x${h})`);
    }
    if (f.pivot) {
      f.pivot.x = w - 1 - f.pivot.x;
    }
    $("ax").value = f.anchor.x;
    syncLinkedCelImages(state.index);
    buildTimeline();
    draw();
    status(`좌우 반전 적용 (프레임 ${state.index + 1})`);
  }

  function transformFlipV() {
    const img = state.images[state.index];
    const f = state.frames[state.index];
    if (!img || !f) return;
    const w = img.width || (f.size && f.size.w) || (f.rect && f.rect.w) || state.canvas?.w || 1;
    const h = img.height || (f.size && f.size.h) || (f.rect && f.rect.h) || state.canvas?.h || 1;
    pushHistory();
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    const ctx = c.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    ctx.translate(0, h);
    ctx.scale(1, -1);
    ctx.drawImage(img, 0, 0, w, h);
    const dataUrl = c.toDataURL("image/png");
    state.images[state.index] = c;
    state.frameUrls[state.index] = dataUrl;
    if (f.size) { f.size.w = w; f.size.h = h; }
    f.anchor.y = h - 1 - f.anchor.y;
    // Invariant assertions
    if (f.anchor.x < 0 || f.anchor.x >= w || f.anchor.y < 0 || f.anchor.y >= h) {
      throw new Error(`FlipV invariant violation: anchor (${f.anchor.x}, ${f.anchor.y}) out of bounds (${w}x${h})`);
    }
    if (f.pivot) {
      f.pivot.y = h - 1 - f.pivot.y;
    }
    $("ay").value = f.anchor.y;
    syncLinkedCelImages(state.index);
    buildTimeline();
    draw();
    status(`상하 반전 적용 (프레임 ${state.index + 1})`);
  }

  function transformRotate90() {
    const img = state.images[state.index];
    const f = state.frames[state.index];
    if (!img || !f) return;
    const w = img.width || (f.size && f.size.w) || (f.rect && f.rect.w) || state.canvas?.w || 1;
    const h = img.height || (f.size && f.size.h) || (f.rect && f.rect.h) || state.canvas?.h || 1;
    pushHistory();
    const c = document.createElement("canvas");
    c.width = h;
    c.height = w;
    const ctx = c.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    ctx.translate(h, 0);
    ctx.rotate(Math.PI / 2);
    ctx.drawImage(img, 0, 0, w, h);
    const dataUrl = c.toDataURL("image/png");
    state.images[state.index] = c;
    state.frameUrls[state.index] = dataUrl;
    if (f.size) { f.size.w = h; f.size.h = w; }
    const oldX = f.anchor.x;
    const oldY = f.anchor.y;
    f.anchor.x = h - 1 - oldY;
    f.anchor.y = oldX;
    // Invariant assertions
    if (f.anchor.x < 0 || f.anchor.x >= h || f.anchor.y < 0 || f.anchor.y >= w) {
      throw new Error(`Rotate90 invariant violation: anchor (${f.anchor.x}, ${f.anchor.y}) out of bounds (${h}x${w})`);
    }
    if (f.pivot) {
      const pOldX = f.pivot.x;
      const pOldY = f.pivot.y;
      f.pivot.x = h - 1 - pOldY;
      f.pivot.y = pOldX;
    }
    $("ax").value = f.anchor.x;
    $("ay").value = f.anchor.y;
    syncLinkedCelImages(state.index);
    buildTimeline();
    draw();
    status(`90도 회전 적용 (프레임 ${state.index + 1})`);
  }

  function setPivot(x, y) {
    const f = state.frames[state.index];
    const img = state.images[state.index];
    if (!f || !img) return;
    pushHistory();
    const w = img.width || (f.size && f.size.w) || state.canvas?.w || 64;
    const h = img.height || (f.size && f.size.h) || state.canvas?.h || 64;
    f.pivot = {
      x: Math.max(0, Math.min(w - 1, Math.round(Number(x)))),
      y: Math.max(0, Math.min(h - 1, Math.round(Number(y))))
    };
    draw();
    updateInspectorProperties();
  }

  function getPixelData(frameIndex) {
    const idx = frameIndex != null ? frameIndex : state.index;
    const img = state.images[idx];
    if (!img) return null;
    const c = document.createElement("canvas");
    c.width = img.width;
    c.height = img.height;
    const ctx = c.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(img, 0, 0);
    const idata = ctx.getImageData(0, 0, c.width, c.height);
    return Array.from(idata.data);
  }

  // ==================== STANDALONE PREVIEW WINDOW ====================
  function openPreviewModal() {
    if (!state.frames.length) return;
    state.previewIndex = state.index;
    openModal("previewModal");
    renderPreviewFrame();
    startPreviewPlay();
  }

  function closePreviewModal() {
    stopPreviewPlay();
    closeModal("previewModal");
  }

  function renderPreviewFrame() {
    const canvas = $("previewView");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const img = (state.composedImages && state.composedImages[state.previewIndex]) || state.images[state.previewIndex];
    if (!img) return;

    const scale = Number(state.previewScale) || 2;
    const cw = Math.round(img.width * scale);
    const ch = Math.round(img.height * scale);
    if (canvas.width !== cw || canvas.height !== ch) {
      canvas.width = cw;
      canvas.height = ch;
    }
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    if ($("previewFrameTag")) {
      $("previewFrameTag").textContent = `프레임 ${state.previewIndex + 1} / ${state.frames.length}`;
    }
  }

  function startPreviewPlay() {
    if (state.previewPlaying) return;
    state.previewPlaying = true;
    if ($("btnPreviewPlay")) $("btnPreviewPlay").textContent = "■ 정지";
    let dir = 1;
    const tick = () => {
      if (!state.previewPlaying) return;
      const loop = ($("previewLoopMode") && $("previewLoopMode").value) || "loop";
      if (loop === "pingpong") {
        let next = state.previewIndex + dir;
        if (next >= state.frames.length || next < 0) {
          dir *= -1;
          next = state.previewIndex + dir;
        }
        state.previewIndex = Math.max(0, Math.min(state.frames.length - 1, next));
      } else if (loop === "once") {
        if (state.previewIndex + 1 >= state.frames.length) {
          stopPreviewPlay();
          return;
        }
        state.previewIndex++;
      } else {
        state.previewIndex = (state.previewIndex + 1) % state.frames.length;
      }
      renderPreviewFrame();
      const fps = Number($("previewFpsInput") ? $("previewFpsInput").value : 12) || 12;
      const dur = Math.round(1000 / fps);
      state.previewTimer = setTimeout(tick, dur);
    };
    tick();
  }

  function stopPreviewPlay() {
    state.previewPlaying = false;
    if (state.previewTimer) {
      clearTimeout(state.previewTimer);
      state.previewTimer = null;
    }
    if ($("btnPreviewPlay")) $("btnPreviewPlay").textContent = "▶ 재생";
  }

  // Hook Timeline buttons
  if ($("btnAddLayer")) $("btnAddLayer").addEventListener("click", () => addNewLayer());
  if ($("btnAddBlankFrame")) $("btnAddBlankFrame").addEventListener("click", insertBlankFrame);
  if ($("btnDupFrame")) $("btnDupFrame").addEventListener("click", duplicateCurrentFrame);
  if ($("btnDelFrame")) $("btnDelFrame").addEventListener("click", deleteCurrentFrame);
  if ($("btnMoveFrameLeft")) $("btnMoveFrameLeft").addEventListener("click", () => moveFrame(-1));
  if ($("btnMoveFrameRight")) $("btnMoveFrameRight").addEventListener("click", () => moveFrame(1));
  if ($("btnReverseFrames")) $("btnReverseFrames").addEventListener("click", reverseFrameSequence);
  if ($("btnOpenPreviewTl")) $("btnOpenPreviewTl").addEventListener("click", openPreviewModal);
  if ($("btnToggleCelLink")) $("btnToggleCelLink").addEventListener("click", toggleCelLink);

  // Hook Context Bar buttons
  if ($("btnFlipH")) $("btnFlipH").addEventListener("click", transformFlipH);
  if ($("btnFlipV")) $("btnFlipV").addEventListener("click", transformFlipV);
  if ($("btnRot90")) $("btnRot90").addEventListener("click", transformRotate90);

  // Hook Inspector Layer buttons
  if ($("btnAddLayerInsp")) $("btnAddLayerInsp").addEventListener("click", () => addNewLayer());
  if ($("btnAddGroupInsp")) $("btnAddGroupInsp").addEventListener("click", () => addNewLayerGroup());
  if ($("btnAddRefInsp")) $("btnAddRefInsp").addEventListener("click", () => addNewReferenceLayer());
  if ($("btnRenameLayerInsp")) $("btnRenameLayerInsp").addEventListener("click", renameCurrentLayer);
  if ($("btnMoveLayerUpInsp")) $("btnMoveLayerUpInsp").addEventListener("click", () => moveLayer(-1));
  if ($("btnMoveLayerDownInsp")) $("btnMoveLayerDownInsp").addEventListener("click", () => moveLayer(1));
  if ($("btnDupLayerInsp")) $("btnDupLayerInsp").addEventListener("click", duplicateCurrentLayer);
  if ($("btnDelLayerInsp")) $("btnDelLayerInsp").addEventListener("click", deleteCurrentLayer);

  // Hook Timeline Layer buttons
  if ($("btnAddLayerGroup")) $("btnAddLayerGroup").addEventListener("click", () => addNewLayerGroup());
  if ($("btnAddRefLayer")) $("btnAddRefLayer").addEventListener("click", () => addNewReferenceLayer());

  // Hook Selection Tool Context buttons
  if ($("btnSelAssignChar")) $("btnSelAssignChar").addEventListener("click", () => applySelectionAsMask("include"));
  if ($("btnSelAssignVfx")) $("btnSelAssignVfx").addEventListener("click", () => applySelectionAsMask("include"));
  if ($("btnSelExclude")) $("btnSelExclude").addEventListener("click", () => applySelectionAsMask("exclude"));
  if ($("btnSelCrop")) $("btnSelCrop").addEventListener("click", cropToSelection);
  if ($("btnSelInvert")) $("btnSelInvert").addEventListener("click", invertSelection);
  if ($("btnSelClear")) $("btnSelClear").addEventListener("click", clearSelection);

  // Hook Preview controls
  if ($("btnPreviewPlay")) {
    $("btnPreviewPlay").addEventListener("click", () => {
      if (state.previewPlaying) stopPreviewPlay();
      else startPreviewPlay();
    });
  }
  if ($("previewBgSelect")) {
    $("previewBgSelect").addEventListener("change", (e) => {
      const wrap = $("previewStageWrap");
      if (wrap) {
        wrap.className = `preview-stage-wrap ${e.target.value}`;
      }
    });
  }
  if ($("previewScaleSelect")) {
    $("previewScaleSelect").addEventListener("change", (e) => {
      state.previewScale = Number(e.target.value) || 2;
      renderPreviewFrame();
    });
  }

  $("playBtn").addEventListener("click", () => {
    if (state.playing) {
      stopPlay();
      return;
    }
    state.playing = true;
    $("playBtn").textContent = "■ 정지";
    state.playDir = 1;
    const tick = () => {
      if (state.loopMode === "pingpong" || ($("pingpong") && $("pingpong").checked)) {
        let next = state.index + state.playDir;
        if (next >= state.frames.length || next < 0) {
          state.playDir *= -1;
          next = state.index + state.playDir;
        }
        setIndex(next);
      } else if (state.loopMode === "once") {
        if (state.index + 1 >= state.frames.length) {
          stopPlay();
          return;
        }
        setIndex(state.index + 1);
      } else {
        setIndex(state.index + 1);
      }
      const dur = Number(state.frames[state.index]?.duration || $("duration").value || 80);
      state.playTimer = setTimeout(tick, dur);
    };
    tick();
  });

  function setAnchorFromEvent(ev, opts) {
    const canvas = $("view");
    const rect = canvas.getBoundingClientRect();
    const scale = currentScale();
    const x = Math.round((ev.clientX - rect.left) * (canvas.width / rect.width) / scale);
    const y = Math.round((ev.clientY - rect.top) * (canvas.height / rect.height) / scale);
    const img = state.images[state.index];
    const ax = Math.max(0, Math.min(img.width - 1, x));
    const ay = Math.max(0, Math.min(img.height - 1, y));
    if (opts && opts.record) pushHistory();
    state.frames[state.index].anchor = { x: ax, y: ay };
    $("ax").value = ax;
    $("ay").value = ay;
    draw();
  }

  function maskMode() {
    const el = document.querySelector('input[name="maskMode"]:checked');
    return el ? el.value : "exclude";
  }

  function brushRadius() {
    return Math.max(1, Number(($("brushSize") && $("brushSize").value) || 8));
  }

  function paintModeOn() {
    return !!($("maskPaint") && $("maskPaint").checked);
  }

  function eventToFrameXY(ev) {
    const canvas = $("view");
    const rect = canvas.getBoundingClientRect();
    const scale = currentScale();
    const x = Math.round((ev.clientX - rect.left) * (canvas.width / rect.width) / scale);
    const y = Math.round((ev.clientY - rect.top) * (canvas.height / rect.height) / scale);
    const img = state.images[state.index];
    return {
      x: Math.max(0, Math.min(img.width - 1, x)),
      y: Math.max(0, Math.min(img.height - 1, y)),
      r: brushRadius(),
    };
  }

  function drawBrushCursor(ev) {
    draw();
    if (!paintModeOn() || !state.frames.length) return;
    const canvas = $("view");
    const ctx = canvas.getContext("2d");
    const scale = currentScale();
    const pt = eventToFrameXY(ev);
    ctx.strokeStyle = maskMode() === "include" || maskMode() === "restore" ? "rgba(125,222,162,.9)" : "rgba(255,107,122,.9)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(pt.x * scale + scale / 2, pt.y * scale + scale / 2, brushRadius() * scale, 0, Math.PI * 2);
    ctx.stroke();
  }

  async function flushMaskStrokes() {
    if (!state.sessionId || !state.maskStrokes.length) {
      state.maskStrokes = [];
      return;
    }
    const strokes = state.maskStrokes.slice();
    state.maskStrokes = [];
    status("Mask...");
    try {
      const res = await fetch("/api/mask-stroke", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: state.sessionId,
          frame: state.index,
          mode: maskMode(),
          brush: brushRadius(),
          strokes,
          duration: Number($("duration").value),
        }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "mask failed");
      const keep = state.index;
      await applySession(data);
      setIndex(keep);
      status(`Mask ${maskMode()} · ${strokes.length} pts`);
    } catch (err) {
      console.error(err);
      status("Error: " + err.message);
      notifyUser(err.message);
    }
  }

  // ==================== ADVANCED SELECTION ENGINE ====================
  function getSelectionMode() {
    const radio = document.querySelector('input[name="selectMode"]:checked');
    return radio ? radio.value : "new";
  }

  function getSelectionShape() {
    return ($("selectShape") && $("selectShape").value) || "rect";
  }

  function getSelectionTolerance() {
    return Number(($("selectTolerance") && $("selectTolerance").value) || 16);
  }

  function combineMask(baseMask, newMask, w, h, mode) {
    const len = w * h;
    const out = new Uint8Array(len);
    if (mode === "new") {
      for (let i = 0; i < len; i++) out[i] = newMask[i];
    } else if (mode === "add") {
      for (let i = 0; i < len; i++) out[i] = baseMask[i] | newMask[i];
    } else if (mode === "sub") {
      for (let i = 0; i < len; i++) out[i] = baseMask[i] && !newMask[i] ? 1 : 0;
    }
    return out;
  }

  function computeBounds(mask, w, h) {
    let minX = w, maxX = -1, minY = h, maxY = -1;
    let count = 0;
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        if (mask[y * w + x]) {
          count++;
          if (x < minX) minX = x;
          if (x > maxX) maxX = x;
          if (y < minY) minY = y;
          if (y > maxY) maxY = y;
        }
      }
    }
    if (count === 0) return null;
    return { x: minX, y: minY, w: maxX - minX + 1, h: maxY - minY + 1, count };
  }

  function applyRectSelection(minX, minY, maxX, maxY, mode) {
    const img = state.images[state.index];
    if (!img) return;
    const w = img.width, h = img.height;
    const newMask = new Uint8Array(w * h);
    for (let y = minY; y <= maxY; y++) {
      for (let x = minX; x <= maxX; x++) {
        newMask[y * w + x] = 1;
      }
    }
    const baseMask = (state.selection && state.selection.mask && state.selection.w === w && state.selection.h === h)
      ? state.selection.mask
      : new Uint8Array(w * h);
    const combined = combineMask(baseMask, newMask, w, h, mode);
    const bounds = computeBounds(combined, w, h);
    state.selection = bounds ? { mask: combined, bounds, w, h } : null;
    status(`선택 영역: ${bounds ? `${bounds.w}×${bounds.h} (${bounds.count}px)` : "없음"}`);
  }

  function applyLassoSelection(pts, mode) {
    const img = state.images[state.index];
    if (!img || pts.length < 3) return;
    const w = img.width, h = img.height;
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    ctx.beginPath();
    ctx.moveTo(pts[0].x, pts[0].y);
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y);
    ctx.closePath();
    ctx.fillStyle = "#fff";
    ctx.fill();
    const idata = ctx.getImageData(0, 0, w, h).data;
    const newMask = new Uint8Array(w * h);
    for (let i = 0; i < w * h; i++) {
      if (idata[i * 4 + 3] > 128) newMask[i] = 1;
    }
    const baseMask = (state.selection && state.selection.mask && state.selection.w === w && state.selection.h === h)
      ? state.selection.mask
      : new Uint8Array(w * h);
    const combined = combineMask(baseMask, newMask, w, h, mode);
    const bounds = computeBounds(combined, w, h);
    state.selection = bounds ? { mask: combined, bounds, w, h } : null;
    status(`올가미 선택: ${bounds ? `${bounds.w}×${bounds.h} (${bounds.count}px)` : "없음"}`);
  }

  function applyPolygonSelection(pts, mode) {
    const img = state.images[state.index];
    if (!img || pts.length < 3) return;
    const w = img.width, h = img.height;
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    ctx.beginPath();
    ctx.moveTo(pts[0].x, pts[0].y);
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y);
    ctx.closePath();
    ctx.fillStyle = "#fff";
    ctx.fill();
    const idata = ctx.getImageData(0, 0, w, h).data;
    const newMask = new Uint8Array(w * h);
    for (let i = 0; i < w * h; i++) {
      if (idata[i * 4 + 3] > 128) newMask[i] = 1;
    }
    const baseMask = (state.selection && state.selection.mask && state.selection.w === w && state.selection.h === h)
      ? state.selection.mask
      : new Uint8Array(w * h);
    const combined = combineMask(baseMask, newMask, w, h, mode);
    const bounds = computeBounds(combined, w, h);
    state.selection = bounds ? { mask: combined, bounds, w, h } : null;
    status(`다각형 선택: ${bounds ? `${bounds.w}×${bounds.h} (${bounds.count}px)` : "없음"}`);
  }

  function getPixelDataAt(img) {
    const c = document.createElement("canvas");
    c.width = img.width;
    c.height = img.height;
    const cx = c.getContext("2d");
    cx.drawImage(img, 0, 0);
    return cx.getImageData(0, 0, img.width, img.height).data;
  }

  function colorDiff(r1, g1, b1, a1, r2, g2, b2, a2) {
    if (a1 < 10 && a2 < 10) return 0;
    if ((a1 < 10) !== (a2 < 10)) return 255;
    return Math.max(Math.abs(r1 - r2), Math.abs(g1 - g2), Math.abs(b1 - b2), Math.abs(a1 - a2));
  }

  function applyWandSelection(startX, startY, mode, tolerance) {
    const img = state.images[state.index];
    if (!img) return;
    const w = img.width, h = img.height;
    const data = getPixelDataAt(img);
    const sIdx = (startY * w + startX) * 4;
    const sr = data[sIdx], sg = data[sIdx + 1], sb = data[sIdx + 2], sa = data[sIdx + 3];

    const visited = new Uint8Array(w * h);
    const newMask = new Uint8Array(w * h);
    const queue = [startX, startY];
    visited[startY * w + startX] = 1;

    let head = 0;
    while (head < queue.length) {
      const x = queue[head++];
      const y = queue[head++];
      newMask[y * w + x] = 1;

      const neighbors = [
        [x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]
      ];
      for (let i = 0; i < 4; i++) {
        const nx = neighbors[i][0], ny = neighbors[i][1];
        if (nx >= 0 && nx < w && ny >= 0 && ny < h) {
          const npos = ny * w + nx;
          if (!visited[npos]) {
            visited[npos] = 1;
            const idx = npos * 4;
            const diff = colorDiff(sr, sg, sb, sa, data[idx], data[idx + 1], data[idx + 2], data[idx + 3]);
            if (diff <= tolerance) {
              queue.push(nx, ny);
            }
          }
        }
      }
    }

    const baseMask = (state.selection && state.selection.mask && state.selection.w === w && state.selection.h === h)
      ? state.selection.mask
      : new Uint8Array(w * h);
    const combined = combineMask(baseMask, newMask, w, h, mode);
    const bounds = computeBounds(combined, w, h);
    state.selection = bounds ? { mask: combined, bounds, w, h } : null;
    status(`마술봉 선택: ${bounds ? `${bounds.w}×${bounds.h} (${bounds.count}px)` : "없음"}`);
  }

  function applyColorSelection(startX, startY, mode, tolerance) {
    const img = state.images[state.index];
    if (!img) return;
    const w = img.width, h = img.height;
    const data = getPixelDataAt(img);
    const sIdx = (startY * w + startX) * 4;
    const sr = data[sIdx], sg = data[sIdx + 1], sb = data[sIdx + 2], sa = data[sIdx + 3];

    const newMask = new Uint8Array(w * h);
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const idx = (y * w + x) * 4;
        const diff = colorDiff(sr, sg, sb, sa, data[idx], data[idx + 1], data[idx + 2], data[idx + 3]);
        if (diff <= tolerance) {
          newMask[y * w + x] = 1;
        }
      }
    }

    const baseMask = (state.selection && state.selection.mask && state.selection.w === w && state.selection.h === h)
      ? state.selection.mask
      : new Uint8Array(w * h);
    const combined = combineMask(baseMask, newMask, w, h, mode);
    const bounds = computeBounds(combined, w, h);
    state.selection = bounds ? { mask: combined, bounds, w, h } : null;
    status(`색상 범위 선택: ${bounds ? `${bounds.w}×${bounds.h} (${bounds.count}px)` : "없음"}`);
  }

  function invertSelection() {
    const img = state.images[state.index];
    if (!img) return;
    const w = img.width, h = img.height;
    const curMask = (state.selection && state.selection.mask) ? state.selection.mask : new Uint8Array(w * h);
    const newMask = new Uint8Array(w * h);
    for (let i = 0; i < w * h; i++) {
      newMask[i] = curMask[i] ? 0 : 1;
    }
    const bounds = computeBounds(newMask, w, h);
    state.selection = bounds ? { mask: newMask, bounds, w, h } : null;
    draw();
    status("선택 반전 (Invert Selection)");
  }

  function clearSelection() {
    state.selection = null;
    state.selectionDraft = null;
    draw();
    status("선택 해제 (Deselect)");
  }

  async function applySelectionAsMask(mode) {
    if (!state.selection || !state.sessionId) {
      notifyUser("선택 영역이 없습니다. 먼저 선택 도구로 영역을 지정하세요.");
      return;
    }
    const { mask, w, h, bounds } = state.selection;
    const strokes = [];
    for (let y = bounds.y; y < bounds.y + bounds.h; y++) {
      for (let x = bounds.x; x < bounds.x + bounds.w; x++) {
        if (mask[y * w + x]) {
          strokes.push({ x, y, r: 1 });
        }
      }
    }
    if (!strokes.length) return;
    status(`선택 영역 소유권 적용 (${mode}) · ${strokes.length}px…`);
    try {
      const res = await fetch("/api/mask-stroke", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: state.sessionId,
          frame: state.index,
          mode,
          brush: 1,
          strokes,
          duration: Number($("duration").value),
        }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "mask application failed");
      const keep = state.index;
      await applySession(data);
      setIndex(keep);
      status(`선택 영역 ${mode} 적용 완료 (${strokes.length}px)`);
    } catch (err) {
      console.error(err);
      notifyUser(err.message);
    }
  }

  async function cropToSelection() {
    if (!state.selection || !state.sessionId) {
      notifyUser("선택 영역이 없습니다.");
      return;
    }
    const b = state.selection.bounds;
    const img = state.images[state.index];
    if (!b || !img) return;

    const left = -b.x;
    const top = -b.y;
    const right = -(img.width - (b.x + b.w));
    const bottom = -(img.height - (b.y + b.h));

    status("선택 영역으로 크롭 중…");
    try {
      const res = await fetch("/api/crop-frame", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: state.sessionId,
          frame: state.index,
          mode: "pad",
          left, top, right, bottom,
          duration: Number($("duration").value),
        }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "crop failed");
      const keep = state.index;
      await applySession(data);
      setIndex(keep);
      clearSelection();
      status(`선택 영역 크롭 완료 (${b.w}×${b.h})`);
    } catch (err) {
      notifyUser(err.message);
    }
  }

  function handleSelectionMouseDown(ev) {
    const pt = eventToFrameXY(ev);
    const shape = getSelectionShape();
    const mode = getSelectionMode();
    const tol = getSelectionTolerance();
    const img = state.images[state.index];
    if (!img) return;

    if (shape === "rect") {
      state.selectionDraft = { type: "rect", start: pt, current: pt };
      draw();
    } else if (shape === "lasso") {
      state.selectionDraft = { type: "lasso", points: [pt] };
      draw();
    } else if (shape === "polygon") {
      if (state.selectionDraft && state.selectionDraft.type === "polygon") {
        const p0 = state.selectionDraft.points[0];
        const dist = Math.hypot(pt.x - p0.x, pt.y - p0.y);
        if (state.selectionDraft.points.length >= 3 && dist <= 4) {
          finishPolygonSelection();
          return;
        }
        state.selectionDraft.points.push(pt);
        state.selectionDraft.current = pt;
      } else {
        state.selectionDraft = { type: "polygon", points: [pt], current: pt };
      }
      draw();
    } else if (shape === "wand") {
      applyWandSelection(pt.x, pt.y, mode, tol);
      draw();
    } else if (shape === "color") {
      applyColorSelection(pt.x, pt.y, mode, tol);
      draw();
    }
  }

  function handleSelectionMouseMove(ev) {
    if (!state.selectionDraft) return;
    const pt = eventToFrameXY(ev);
    if (state.selectionDraft.type === "rect") {
      state.selectionDraft.current = pt;
      draw();
    } else if (state.selectionDraft.type === "lasso") {
      state.selectionDraft.points.push(pt);
      draw();
    } else if (state.selectionDraft.type === "polygon") {
      state.selectionDraft.current = pt;
      draw();
    }
  }

  function finishPolygonSelection() {
    if (!state.selectionDraft || state.selectionDraft.type !== "polygon") return;
    const pts = state.selectionDraft.points;
    state.selectionDraft = null;
    if (pts && pts.length >= 3) {
      applyPolygonSelection(pts, getSelectionMode());
    }
    draw();
  }

  function finishSelectionDraft() {
    if (!state.selectionDraft) return;
    if (state.selectionDraft.type === "polygon") {
      return;
    }
    const draft = state.selectionDraft;
    state.selectionDraft = null;
    const img = state.images[state.index];
    if (!img) return;
    const w = img.width;
    const h = img.height;
    const mode = getSelectionMode();

    if (draft.type === "rect") {
      const minX = Math.max(0, Math.min(draft.start.x, draft.current.x));
      const maxX = Math.min(w - 1, Math.max(draft.start.x, draft.current.x));
      const minY = Math.max(0, Math.min(draft.start.y, draft.current.y));
      const maxY = Math.min(h - 1, Math.max(draft.start.y, draft.current.y));
      applyRectSelection(minX, minY, maxX, maxY, mode);
    } else if (draft.type === "lasso") {
      applyLassoSelection(draft.points, mode);
    }
    draw();
  }

  const view = $("view");
  view.addEventListener("mousedown", (ev) => {
    if (!state.frames.length) return;
    if (state.activeTool === "select") {
      handleSelectionMouseDown(ev);
      ev.preventDefault();
      return;
    }
    if (paintModeOn()) {
      state.maskPainting = true;
      state.maskStrokes = [eventToFrameXY(ev)];
      drawBrushCursor(ev);
      ev.preventDefault();
      return;
    }
    if (state.activeTool === "anchor") {
      state.drag = true;
      setAnchorFromEvent(ev, { record: true });
    }
  });
  view.addEventListener("dblclick", (ev) => {
    if (state.activeTool === "select" && state.selectionDraft && state.selectionDraft.type === "polygon") {
      finishPolygonSelection();
      ev.preventDefault();
    }
  });
  window.addEventListener("mouseup", async () => {
    state.drag = false;
    if (state.activeTool === "select" && state.selectionDraft) {
      finishSelectionDraft();
    }
    if (state.maskPainting) {
      state.maskPainting = false;
      await flushMaskStrokes();
    }
  });
  view.addEventListener("mousemove", (ev) => {
    if (state.activeTool === "select" && state.selectionDraft) {
      handleSelectionMouseMove(ev);
      return;
    }
    if (state.maskPainting) {
      state.maskStrokes.push(eventToFrameXY(ev));
      drawBrushCursor(ev);
      return;
    }
    if (state.drag && state.activeTool === "anchor") setAnchorFromEvent(ev);
    else if (paintModeOn()) drawBrushCursor(ev);
  });
  if ($("maskPaint")) {
    $("maskPaint").addEventListener("change", () => {
      const wrap = $("canvasWrap");
      if (wrap) wrap.classList.toggle("painting", paintModeOn());
      draw();
    });
  }

  $("ax").addEventListener("change", () => {
    if (!state.frames.length) return;
    pushHistory();
    state.frames[state.index].anchor.x = Number($("ax").value);
    draw();
  });
  $("ay").addEventListener("change", () => {
    if (!state.frames.length) return;
    pushHistory();
    state.frames[state.index].anchor.y = Number($("ay").value);
    draw();
  });

  document.querySelectorAll("[data-nudge]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!state.frames.length) return;
      pushHistory();
      const [dx, dy] = btn.getAttribute("data-nudge").split(",").map(Number);
      const a = state.frames[state.index].anchor;
      const img = state.images[state.index];
      a.x = Math.max(0, Math.min(img.width - 1, a.x + dx));
      a.y = Math.max(0, Math.min(img.height - 1, a.y + dy));
      $("ax").value = a.x;
      $("ay").value = a.y;
      draw();
    });
  });

  $("btnRecompose").addEventListener("click", async () => {
    if (!state.sessionId) return;
    status("재구성 중…");
    try {
      const res = await fetch("/api/recompose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: state.sessionId,
          anchors: state.frames.map((f) => f.anchor),
          duration: Number($("duration").value),
        }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "recompose failed");
      // Keep user anchors from response raw frames
      await applySession(data);
      status(`재구성 완료 · 캔버스 ${data.canvas.w}×${data.canvas.h}`);
    } catch (err) {
      status("오류: " + err.message);
      notifyUser(err.message);
    }
  });

  async function checkAsepriteBridgeStatus() {
    const bar = $("aseBridgeStatus");
    if (!bar) return;
    try {
      const res = await fetch("/api/aseprite-bridge/status");
      const data = await res.json();
      if (data.installed) {
        bar.innerHTML = `<span>🖥️ 호스트 Aseprite: <span class="bridge-badge-ok">CLI 연동 가능</span> (${data.version || "v1.x"})</span><span style="font-size:10px;opacity:0.8">${data.path}</span>`;
      } else {
        bar.innerHTML = `<span>🖥️ Aseprite 브릿지: <span class="bridge-badge-info">클린룸 호환 모드</span> (Aseprite 미설치 시 독립 Lua 스크립트 및 표준 아틀라스/JSON 자동 출력)</span>`;
      }
    } catch {
      bar.innerHTML = `<span>🖥️ Aseprite 브릿지: 클린룸 호환 모드</span>`;
    }
  }

  $("btnExport").addEventListener("click", async () => {
    if (!state.sessionId) return;
    status("에셋 번들 내보내기 중…");
    try {
      const payload = {
        session_id: state.sessionId,
        anchors: state.frames.map((f) => f.anchor),
        duration: Number($("duration").value),
        name: $("exportName").value || "export",
        pack_mode: ($("expPackMode") && $("expPackMode").value) || "packed",
        padding: Number(($("expPadding") && $("expPadding").value) || 2),
        extrude: Number(($("expExtrude") && $("expExtrude").value) || 1),
        color_mode: ($("expColorMode") && $("expColorMode").value) || "RGBA",
        palette_colors: Number(($("expColors") && $("expColors").value) || 256),
        dither: ($("expDither") && $("expDither").value) || "none",
        merge_duplicates: !($("expMergeDup") && !$("expMergeDup").checked),
        split_tags: !!($("expSplitTags") && $("expSplitTags").checked),
        bridge_aseprite: !($("expBridgeAseprite") && !$("expBridgeAseprite").checked),
      };

      const res = await fetch("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "export failed");
      const box = $("exportLinks");
      box.innerHTML = "";
      const add = (href, label) => {
        if (!href) return;
        const a = document.createElement("a");
        a.href = href;
        a.textContent = `⬇️ ${label}`;
        a.target = "_blank";
        box.appendChild(a);
      };
      add(data.download_zip, "전체 ZIP 번들 (Full Package)");
      add(data.download_sheet, "스프라이트시트 (spritesheet.png)");
      add(data.download_json, "엔진용 메타데이터 (animation.json)");
      add(data.download_aseprite, "Aseprite 규격 메타데이터 (aseprite.json)");
      if (data.download_bridge_lua) add(data.download_bridge_lua, "Aseprite 자동 복원 Lua 스크립트 (import_to_aseprite.lua)");
      add(data.download_gif, "애니메이션 GIF (preview.gif)");
      if (data.download_apng) add(data.download_apng, "무손실 APNG (preview.apng.png)");
      if (data.download_webp) add(data.download_webp, "고효율 WebP (preview.webp)");
      if (data.download_project) add(data.download_project, "SpriteRepair 프로젝트 (project.spriteproject)");
      status(`내보내기 완료 · ${data.out_dir}`);
    } catch (err) {
      status("오류: " + err.message);
      notifyUser(err.message);
    }
  });

  window.addEventListener("keydown", (ev) => {
    const tag = (ev.target && ev.target.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

    // Undo / Redo
    if ((ev.ctrlKey || ev.metaKey) && (ev.key === "z" || ev.key === "Z")) {
      if (ev.shiftKey) redo(); else undo();
      ev.preventDefault();
      return;
    }
    if ((ev.ctrlKey || ev.metaKey) && (ev.key === "y" || ev.key === "Y")) {
      redo();
      ev.preventDefault();
      return;
    }

    // Selection Deselect (Ctrl+D) and Invert (Ctrl+Shift+I)
    if ((ev.ctrlKey || ev.metaKey) && (ev.key === "d" || ev.key === "D")) {
      ev.preventDefault();
      clearSelection();
      return;
    }
    if ((ev.ctrlKey || ev.metaKey) && ev.shiftKey && (ev.key === "i" || ev.key === "I")) {
      ev.preventDefault();
      invertSelection();
      return;
    }
    if (ev.key === "Enter" && state.selectionDraft && state.selectionDraft.type === "polygon") {
      ev.preventDefault();
      finishPolygonSelection();
      return;
    }
    if (ev.key === "Escape" && state.selectionDraft && state.selectionDraft.type === "polygon") {
      ev.preventDefault();
      state.selectionDraft = null;
      draw();
      return;
    }

    // New layer shortcut (Shift+N)
    if (ev.shiftKey && (ev.key === "n" || ev.key === "N") && !ev.ctrlKey && !ev.altKey) {
      ev.preventDefault();
      addNewLayer();
      return;
    }

    // Rename layer (F2)
    if (ev.key === "F2") {
      ev.preventDefault();
      renameCurrentLayer();
      return;
    }

    // Standalone preview (F4)
    if (ev.key === "F4") {
      ev.preventDefault();
      openPreviewModal();
      return;
    }

    // Play/Pause with Space
    if (ev.code === "Space") {
      ev.preventDefault();
      $("playBtn").click();
      return;
    }

    if (!state.frames.length) return;

    // Stepping with Arrow keys or comma / period
    if (ev.key === "ArrowLeft" || ev.key === ",") {
      setIndex(state.index - 1);
      ev.preventDefault();
      return;
    }
    if (ev.key === "ArrowRight" || ev.key === ".") {
      setIndex(state.index + 1);
      ev.preventDefault();
      return;
    }
    if (ev.key === "Home") {
      setIndex(0);
      ev.preventDefault();
      return;
    }
    if (ev.key === "End") {
      setIndex(state.frames.length - 1);
      ev.preventDefault();
      return;
    }

    // Onion skin toggle with 'o' or 'O'
    if (ev.key === "o" || ev.key === "O") {
      const toggle = $("onionSkinToggle") || $("onion");
      if (toggle) {
        toggle.checked = !toggle.checked;
        draw();
        status(`양파껍질: ${toggle.checked ? "켜짐" : "꺼짐"}`);
      }
      return;
    }

    // Zoom shortcuts '1' - '4'
    if (["1", "2", "3", "4"].includes(ev.key)) {
      state.zoom = Number(ev.key);
      document.querySelectorAll(".btn-zoom").forEach(b => b.classList.toggle("active", b.getAttribute("data-zoom") === ev.key));
      draw();
      return;
    }

    // Anchor nudge (WASD or Arrow keys with Shift)
    const a = state.frames[state.index]?.anchor;
    const img = state.images[state.index];
    if (!a || !img) return;
    let used = true;
    const before = { x: a.x, y: a.y };
    if (ev.key === "w" || ev.key === "W") a.y = Math.max(0, a.y - (ev.shiftKey ? 5 : 1));
    else if (ev.key === "s" || ev.key === "S") a.y = Math.min(img.height - 1, a.y + (ev.shiftKey ? 5 : 1));
    else if (ev.key === "a" || ev.key === "A") a.x = Math.max(0, a.x - (ev.shiftKey ? 5 : 1));
    else if (ev.key === "d" || ev.key === "D") a.x = Math.min(img.width - 1, a.x + (ev.shiftKey ? 5 : 1));
    else used = false;
    if (used) {
      if (before.x !== a.x || before.y !== a.y) {
        state.historyLock = true;
        state.frames[state.index].anchor = before;
        state.historyLock = false;
        pushHistory();
        state.frames[state.index].anchor = a;
      }
      $("ax").value = a.x;
      $("ay").value = a.y;
      draw();
      ev.preventDefault();
    }
  });


  async function cropFrame(body) {
    if (!state.sessionId) return;
    status("Crop...");
    try {
      const res = await fetch("/api/crop-frame", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.assign({
          session_id: state.sessionId,
          frame: state.index,
          duration: Number($("duration").value),
        }, body)),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "crop failed");
      const keepIndex = state.index;
      await applySession(data);
      setIndex(keepIndex);
      status(`Crop OK · canvas ${data.canvas.w}x${data.canvas.h}`);
    } catch (err) {
      console.error(err);
      status("Error: " + err.message);
      notifyUser(err.message);
    }
  }

  if ($("btnUndo")) $("btnUndo").addEventListener("click", undo);
  if ($("btnRedo")) $("btnRedo").addEventListener("click", redo);
  if ($("btnCropApply")) $("btnCropApply").addEventListener("click", () => cropFrame({
    mode: "pad",
    left: Number($("cropL").value || 0),
    right: Number($("cropR").value || 0),
    top: Number($("cropT").value || 0),
    bottom: Number($("cropB").value || 0),
  }));
  if ($("btnCropExpand1")) $("btnCropExpand1").addEventListener("click", () => cropFrame({ mode: "pad", left: 1, right: 1, top: 1, bottom: 1 }));
  if ($("btnCropExpand5")) $("btnCropExpand5").addEventListener("click", () => cropFrame({ mode: "safe", amount: 5 }));
  if ($("btnCropTight")) $("btnCropTight").addEventListener("click", () => cropFrame({ mode: "tight", margin: 0 }));
  if ($("btnCropSafe")) $("btnCropSafe").addEventListener("click", () => cropFrame({ mode: "safe", amount: 8 }));
  if ($("btnSetRef")) $("btnSetRef").addEventListener("click", () => {
    if (!state.frames.length) return;
    pushHistory();
    state.refIndex = state.index;
    if ($("refLabel")) $("refLabel").textContent = `Ref: frame ${state.refIndex + 1}`;
    status(`Reference = frame ${state.refIndex + 1}`);
    draw();
  });
  if ($("btnAlignRef")) $("btnAlignRef").addEventListener("click", () => {
    if ($("btnRecompose")) $("btnRecompose").click();
  });
  if ($("onionRef")) $("onionRef").addEventListener("change", draw);

  // --- AI align ---

  
  function renderQa(data) {
    const box = $("qaBox");
    if (!box) return;
    const frames = (data && data.frames) || [];
    const lines = [];
    let warnCount = 0;
    for (const f of frames) {
      const w = f.qa_warnings || [];
      if (!w.length) continue;
      warnCount += w.length;
      lines.push(`Frame ${String(f.frame).padStart(2, "0")}: ${w.join("; ")}`);
    }
    const anim = data && data.anim_qa;
    if (anim && anim.warnings && anim.warnings.length) {
      for (const w of anim.warnings) {
        warnCount += 1;
        lines.push(`Anim f${String(w.frame).padStart(2,"0")}: ${w.message || w.type}`);
      }
    }
    const sheetQa = data && data.ai_sheet_qa;
    if (sheetQa && sheetQa.problem_frames && sheetQa.problem_frames.length) {
      lines.unshift(`AI Sheet QA review: [${sheetQa.problem_frames.join(", ")}]${sheetQa.cached ? " (cache)" : ""}`);
      warnCount += sheetQa.problem_frames.length;
    }
    if (!lines.length) {
      box.textContent = "QA: clean (overflow/VFX/jitter)";
      return;
    }
    box.innerHTML = `<strong>QA ${warnCount}</strong><br>` + lines.map((l) => escapeHtml(l)).join("<br>");
  }
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  async function fillModelSelect(models, preferred, metas, prov) {
    const model = $("aiModel");
    if (!model) return;
    const isOpencode = prov === "opencode_go" || prov === "opencode";
    const list = Array.isArray(models) && models.length ? models : [preferred || "moonshotai/kimi-k3"];
    const want = preferred || list[0];
    model.innerHTML = "";
    for (const id of list) {
      if (!id) continue;
      const opt = document.createElement("option");
      opt.value = id;
      const meta = ((metas || []).find((x) => x.id === id)) || {};
      let label = id;
      if (isOpencode) {
        const badges = meta.badges || [];
        const parts = [];
        if (meta.vision_verified) parts.push("LIVE-VERIFIED");
        else if (meta.vision) parts.push("VISION");
        else parts.push("TEXT");
        if (badges.includes("CONTRIBUTOR")) parts.push("CONTRIBUTOR");
        if (badges.includes("REGION-LIMITED")) parts.push("REGION-LIMITED");
        if (meta.free) parts.push("FREE");
        if (badges.includes("POPULAR")) parts.push("POPULAR");
        if (meta.recommended) parts.push("추천");
        if (meta.status === "TEMPORARILY_UNAVAILABLE") parts.push("일시불가");
        label = `[${parts.join("/")}] ${meta.name || id} · ${id}`;
        if (meta.price) label += ` · ${meta.price}`;
        else if (meta.free) label += " · 무료";
        opt.title = meta.desc || meta.status || id;
      } else if (meta && meta.price) {
        label = `${id} · ${meta.price}`;
        if (meta.desc) opt.title = meta.desc;
      }
      opt.textContent = label;
      if (id === want) opt.selected = true;
      model.appendChild(opt);
    }
    if (![...model.options].some((o) => o.value === want) && want) {
      const opt = document.createElement("option");
      opt.value = want;
      opt.textContent = want + " (default)";
      opt.selected = true;
      model.insertBefore(opt, model.firstChild);
    }
  }

  async function loadAiModels() {
    const prov = ($("aiProvider") && $("aiProvider").value) || "nvidia";
    const visionOnly = !($("visionOnly") && !$("visionOnly").checked);
    const isOpencode = prov === "opencode_go" || prov === "opencode";
    if ($("modelGroup")) $("modelGroup").style.display = isOpencode ? "" : "none";
    if (prov === "disabled") {
      if ($("aiStatus")) $("aiStatus").textContent = "AI 사용 안 함 — 로컬 CV만 사용";
      await fillModelSelect([], "", [], prov);
      return null;
    }
    try {
      const res = await fetch("/api/ai-models?provider=" + encodeURIComponent(prov));
      const data = await res.json();
      state.lastModelCatalog = data;
      const metas = data.models_meta || [];
      let list = data.models || data.curated || [];
      let preferred =
        (state.aiConfig && state.aiConfig.models && state.aiConfig.models[prov]) ||
        (data && data.default) ||
        (prov === "nvidia" ? "moonshotai/kimi-k3" : "google/gemini-2.5-flash-lite");
      if (isOpencode) {
        const group = ($("modelGroup") && $("modelGroup").value) || "all";
        if (group === "recommended") {
          list = data.vision_models && data.vision_models.length ? data.vision_models : list;
        } else if (group === "vision") {
          const vv = (data.vision_models || []).filter((m) => {
            const mm = metas.find((x) => x.id === m);
            return mm && mm.vision_verified;
          });
          list = vv.length ? vv : (data.vision_models || []);
        } else if (group === "free") {
          list = data.free_models && data.free_models.length ? data.free_models : list.filter((m) => (metas.find((x) => x.id === m) || {}).free);
        } else if (group === "popular") {
          list = data.popular_models && data.popular_models.length ? data.popular_models : list;
        }
        if (visionOnly && group !== "vision") {
          const isV = (m) => {
            const mm = metas.find((x) => x.id === m);
            return mm ? (mm.vision || mm.vision_verified) : true;
          };
          list = [...list.filter(isV), ...list.filter((m) => !isV(m))];
        }
        if (visionOnly && data.vision_default && list.includes(data.vision_default)) {
          preferred = data.vision_default;
        } else if (!list.includes(preferred)) {
          preferred = list[0] || preferred;
        }
      } else if (prov === "openrouter" && visionOnly) {
        list = data.vision_models && data.vision_models.length ? data.vision_models : list.filter((m) => {
          const meta = (data.models_meta || []).find((x) => x.id === m);
          return meta ? meta.vision : true;
        });
        preferred = data.vision_default || preferred;
        // never keep text-only nemotron selected for align
        if (String(preferred).includes("nemotron") && !String(preferred).includes("vision")) {
          preferred = data.vision_default || "google/gemini-2.5-flash-lite";
        }
      }
      await fillModelSelect(list, preferred, metas, prov);
      if ($("aiStatus")) {
        const n = list.length;
        if (data.ok) {
          $("aiStatus").textContent = `${prov} ${visionOnly ? "비전우선 " : ""}${n}개 · 선택기본 ${preferred}`;
        } else {
          $("aiStatus").textContent = `${prov} 큐레이션 · ${data.error || "스캔 실패"}`;
        }
      }
      return data;
    } catch (err) {
      const fb = prov === "nvidia"
        ? ["moonshotai/kimi-k3", "meta/llama-3.2-11b-vision-instruct"]
        : (isOpencode
          ? ["deepseek-v4-flash-vision-exp", "kimi-k3", "qwen3.8-flash", "mimo-v2.5", "glm-5.3-flash"]
          : ["google/gemini-2.5-flash-lite", "deepseek/deepseek-v4-flash-vision-exp", "moonshotai/kimi-k3"]);
      await fillModelSelect(fb, fb[0], [], prov);
      if ($("aiStatus")) $("aiStatus").textContent = "모델 스캔 실패 · 비전 폴백";
      return null;
    }
  }



  async function loadAiConfig() {
    try {
      const res = await fetch("/api/ai-config");
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      if (!data || data.ok === false) throw new Error((data && data.error) || "ai-config not ok");
      state.aiConfig = data;
      const sel = $("aiProvider");
      if (sel && data.default_provider) sel.value = data.default_provider;
      const nOk = data.providers && data.providers.nvidia;
      const oOk = data.providers && data.providers.openrouter;
      const goOk = data.providers && data.providers.opencode_go;
      const coOk = data.providers && data.providers.opencode;
      const tip = [];
      tip.push(goOk ? "OpenCode Go: OK" : "OpenCode Go: no key");
      tip.push(coOk ? "OpenCode Console: OK" : "OpenCode Console: no key");
      tip.push(oOk ? "OpenRouter: OK" : "OpenRouter: no key");
      tip.push(nOk ? "NVIDIA: OK" : "NVIDIA: no key");
      if ($("aiStatus")) $("aiStatus").textContent = tip.join(" · ");
      if (sel) {
        sel.addEventListener("change", async () => { await loadAiModels(); });
      }
      await loadAiModels();
    } catch (err) {
      console.error(err);
      if ($("aiStatus")) $("aiStatus").textContent = "AI config load failed: " + (err && err.message ? err.message : err);
      await fillModelSelect(["moonshotai/kimi-k3"], "moonshotai/kimi-k3");
    }
  }
  loadAiConfig();
  if ($("btnAiModels")) {
    $("btnAiModels").addEventListener("click", () => { loadAiModels(); });
  }
  if ($("visionOnly")) {
    $("visionOnly").addEventListener("change", () => { loadAiModels(); });
  }

  
  if ($("btnAiQa")) {
    $("btnAiQa").addEventListener("click", async () => {
      if (!state.sessionId) return;
      status("AI Sheet QA...");
      try {
        const res = await fetch("/api/ai-qa", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: state.sessionId,
            provider: $("aiProvider") && $("aiProvider").value,
            model: $("aiModel") && $("aiModel").value,
            duration: Number($("duration").value),
          }),
        });
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || "ai-qa failed");
        await applySession(data);
        const pf = (data.ai_sheet_qa && data.ai_sheet_qa.problem_frames) || [];
        status(`AI Sheet QA · review ${pf.length} frames${data.ai_sheet_qa && data.ai_sheet_qa.cached ? " (cache)" : ""}`);
      } catch (err) {
        status("Error: " + err.message);
        notifyUser(err.message);
      }
    });
  }
  if ($("btnAnimQa")) {
    $("btnAnimQa").addEventListener("click", async () => {
      if (!state.sessionId) return;
      try {
        const res = await fetch("/api/anim-qa", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: state.sessionId }),
        });
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || "anim-qa failed");
        renderQa({ frames: state.frames, anim_qa: data.anim_qa });
        status(data.anim_qa.summary || "Anim QA done");
      } catch (err) {
        status("Error: " + err.message);
        notifyUser(err.message);
      }
    });
  }
  if ($("btnSaveProject")) {
    $("btnSaveProject").addEventListener("click", async () => {
      if (!state.sessionId) return;
      try {
        const res = await fetch("/api/save-project", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: state.sessionId,
            name: ($("exportName") && $("exportName").value) || "project",
            anchors: state.frames.map((f) => f.anchor),
            duration: Number($("duration").value),
            layers: state.layers,
            tags: state.tags,
            frames: state.frames.map((f) => ({
              anchor: f.anchor,
              pivot: f.pivot || null,
              duration: f.duration || Number($("duration").value),
              duration_ms: f.duration || Number($("duration").value),
              linked_cel_id: f.linked_cel_id || null,
              mask_strokes: f.mask_strokes || [],
              rect: f.rect || f.content_rect || null,
              crop: f.content_rect || f.rect || null,
            })),
            canvas: state.canvas,
          }),
        });
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || "save failed");
        status("Saved project");
        const box = $("exportLinks");
        if (box && data.download) {
          const a = document.createElement("a");
          a.href = data.download;
          a.textContent = ".spriteproject";
          a.target = "_blank";
          box.appendChild(a);
        }
      } catch (err) {
        status("Error: " + err.message);
        notifyUser(err.message);
      }
    });
  }

  /* ---- AI 모델 빠른 선택 모달 (제공자 카드 + 프리셋 + 가격/설명) ---- */
  const mpState = { provider: "opencode_go", catalog: null, sel: "" };
  const MP_PROVIDERS = [
    { id: "opencode_go", name: "OpenCode Go", desc: "36종 게이트웨이 · DeepSeek/Kimi/Qwen/GLM" },
    { id: "opencode", name: "OpenCode Console", desc: "70종 + 무료 그룹" },
    { id: "openrouter", name: "OpenRouter", desc: "수백종 · 무료 다수 · 실시간 가격" },
    { id: "nvidia", name: "NVIDIA Build", desc: "고속 비전" },
    { id: "ollama", name: "Ollama (로컬)", desc: "내 PC · 무료" },
  ];

  function mpChips(meta, prov) {
    const chips = [];
    if (meta.recommended) chips.push('<span class="chip rec">⭐ 기본추천</span>');
    if (meta.vision_verified) chips.push('<span class="chip vv">LIVE-VERIFIED</span>');
    else if (meta.vision) chips.push('<span class="chip">👁️ VISION</span>');
    const badges = meta.badges || [];
    if (badges.includes("POPULAR")) chips.push('<span class="chip">🔥 인기</span>');
    if (meta.free) chips.push('<span class="chip free">무료</span>');
    if (meta.contributor) chips.push('<span class="chip warn">CONTRIBUTOR</span>');
    if (meta.region_limited) chips.push('<span class="chip warn">REGION-LIMITED</span>');
    let price = meta.price;
    if (!price) price = prov === "ollama" ? "로컬 무료" : (meta.free ? "무료" : null);
    if (price) chips.push(`<span class="chip price">💰 ${escapeHtml(price)}</span>`);
    return chips.join("");
  }

  function mpDesc(meta, prov) {
    if (meta.desc) return meta.desc;
    if (prov === "ollama") return "내 PC 로컬 AI · 완전 무료";
    if (meta.status === "UNAVAILABLE") return "현재 카탈로그에 없음 (UNAVAILABLE)";
    const parts = [];
    if (meta.vision) parts.push("이미지 입력 가능");
    if (meta.free) parts.push("무료");
    return parts.join(" · ") || (meta.name && meta.name !== meta.id ? meta.name : "");
  }

  function renderMpProviders() {
    const box = $("mpProviders");
    if (!box) return;
    const cfg = state.aiConfig || {};
    const provOk = cfg.providers || {};
    box.innerHTML = "";
    for (const p of MP_PROVIDERS) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "mp-prov" + (mpState.provider === p.id ? " sel" : "");
      const ok = p.id === "ollama" ? (cfg.ollama_online || provOk.ollama) : provOk[p.id];
      b.innerHTML = `<div class="pn"><span class="dot ${ok ? "ok" : "no"}"></span>${escapeHtml(p.name)}</div><div class="pd">${escapeHtml(p.desc)}</div>`;
      b.addEventListener("click", async () => {
        mpState.provider = p.id;
        renderMpProviders();
        await loadMpCatalog();
      });
      box.appendChild(b);
    }
  }

  function mpSort(list, metas) {
    const byId = {};
    for (const m of metas) byId[m.id] = m;
    const score = (id) => {
      const m = byId[id] || {};
      let s = 0;
      if (m.recommended) s += 100;
      if (m.vision_verified) s += 50;
      else if (m.vision) s += 20;
      if ((m.badges || []).includes("POPULAR")) s += 10;
      if (m.free) s += 5;
      if (m.status === "UNAVAILABLE") s -= 100;
      return s;
    };
    return [...list].sort((a, b) => score(b) - score(a)).slice(0, 60);
  }

  function renderMpPresets() {
    const box = $("mpPresets");
    const cnt = $("mpCount");
    if (!box) return;
    const cat = mpState.catalog || {};
    const metas = cat.models_meta || [];
    const list = mpSort(cat.models || cat.curated || [], metas);
    if (cnt) cnt.textContent = `(${list.length}개 표시)`;
    box.innerHTML = "";
    const byId = {};
    for (const m of metas) byId[m.id] = m;
    for (const id of list) {
      const meta = byId[id] || { id: id, name: id };
      const d = document.createElement("div");
      d.className = "mp-item" + (mpState.sel === id ? " sel" : "");
      d.innerHTML = `
        <div class="mi-top">
          <span class="mi-id">${escapeHtml(meta.name && meta.name !== id ? meta.name + " · " : "")}${escapeHtml(id)}</span>
          <span class="mi-badges">${mpChips(meta, mpState.provider)}</span>
        </div>
        <div class="mi-desc">${escapeHtml(mpDesc(meta, mpState.provider))}</div>`;
      d.addEventListener("click", () => {
        mpState.sel = id;
        if ($("mpCustom")) $("mpCustom").value = id;
        renderMpPresets();
        if (meta.contributor) {
          if ($("mpWarn")) $("mpWarn").textContent = "⚠ CONTRIBUTOR 모델: 학습사용 동의·지역제한 조건을 확인하세요.";
          notifyUser("⚠ CONTRIBUTOR 모델: 학습사용 동의·지역제한 조건을 확인하세요.");
        } else if ($("mpWarn")) {
          $("mpWarn").textContent = "";
        }
      });
      box.appendChild(d);
    }
  }

  async function loadMpCatalog() {
    const box = $("mpPresets");
    if (box) box.innerHTML = '<div class="mi-desc">카탈로그 로드 중…</div>';
    try {
      const res = await fetch("/api/ai-models?provider=" + encodeURIComponent(mpState.provider));
      mpState.catalog = await res.json();
    } catch (err) {
      mpState.catalog = { models: [], models_meta: [] };
    }
    renderMpPresets();
  }

  async function openModelPicker() {
    const cur = ($("aiProvider") && $("aiProvider").value) || "opencode_go";
    if (MP_PROVIDERS.some((p) => p.id === cur)) mpState.provider = cur;
    const curModel = ($("aiModel") && $("aiModel").value) || "";
    mpState.sel = curModel;
    if ($("mpCustom")) $("mpCustom").value = curModel;
    if ($("mpWarn")) $("mpWarn").textContent = "";
    openModal("modelPickerModal");
    renderMpProviders();
    await loadMpCatalog();
  }

  if ($("btnQuickPick")) $("btnQuickPick").addEventListener("click", openModelPicker);
  if ($("modelGroup")) $("modelGroup").addEventListener("change", () => { loadAiModels(); });
  if ($("mpCustom")) {
    $("mpCustom").addEventListener("input", () => {
      mpState.sel = ($("mpCustom").value || "").trim();
      document.querySelectorAll(".mp-item.sel").forEach((el) => el.classList.remove("sel"));
    });
  }
  if ($("mpApply")) {
    $("mpApply").addEventListener("click", async () => {
      const model = (($("mpCustom") && $("mpCustom").value) || mpState.sel || "").trim();
      if (!model) {
        notifyUser("적용할 모델을 선택하세요.");
        return;
      }
      const metaActive = ((mpState.catalog && mpState.catalog.models_meta) || []).find((x) => x.id === model)
        || ((state.lastModelCatalog && state.lastModelCatalog.models_meta) || []).find((x) => x.id === model) || {};
      if ((metaActive.badges || []).includes("CONTRIBUTOR")) {
        const ok = confirm(
          "Muse Spark CONTRIBUTOR 모델 경고:\n\n" +
          "- prompts/completions가 미래 Meta 모델 학습에 사용될 수 있습니다.\n" +
          "- 지역 제한(REGION-LIMITED)이 있을 수 있습니다.\n\n" +
          "민감/개인 이미지에는 사용하지 마세요. 그래도 적용할까요?"
        );
        if (!ok) return;
      }
      try {
        const res = await fetch("/api/ai-set-model", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider: mpState.provider, model: model }),
        });
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || "apply failed");
        state.aiConfig = data.config;
        await loadAiConfig();
        await loadAiModels();
        status(`모델 적용 완료: [${mpState.provider}] ${model}`);
        closeModal("modelPickerModal");
      } catch (err) {
        notifyUser("모델 적용 실패: " + err.message);
      }
    });
  }

  if ($("btnSaveKeys")) {
    $("btnSaveKeys").addEventListener("click", async () => {
      const nv = ($("keyNvidia") && $("keyNvidia").value) || "";
      const or = ($("keyOpenrouter") && $("keyOpenrouter").value) || "";
      const go = ($("keyOpencodeGo") && $("keyOpencodeGo").value) || "";
      const oc = ($("keyOpencode") && $("keyOpencode").value) || "";
      if (!nv.trim() && !or.trim() && !go.trim() && !oc.trim()) {
        notifyUser("저장할 키를 입력하세요. 빈 칸은 기존 값을 유지합니다.");
        return;
      }
      try {
        const res = await fetch("/api/ai-keys", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            nvidia_key: nv.trim() || null,
            openrouter_key: or.trim() || null,
            opencode_go_key: go.trim() || null,
            opencode_key: oc.trim() || null,
            provider: $("aiProvider") && $("aiProvider").value,
          }),
        });
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || "save failed");
        if ($("keyNvidia")) $("keyNvidia").value = "";
        if ($("keyOpenrouter")) $("keyOpenrouter").value = "";
        if ($("keyOpencodeGo")) $("keyOpencodeGo").value = "";
        if ($("keyOpencode")) $("keyOpencode").value = "";
        if ($("keyStatus")) $("keyStatus").textContent = "키 저장됨 (.env) — 목록 새로고침 중";
        state.aiConfig = data.config;
        await loadAiConfig();
        await loadAiModels();
        if ($("keyStatus")) $("keyStatus").textContent = "키 저장 완료";
        status("AI 키 저장 완료");
      } catch (err) {
        if ($("keyStatus")) $("keyStatus").textContent = "저장 실패: " + err.message;
        notifyUser(err.message);
      }
    });
  }

  async function loadProjectData(proj) {
    if (!proj) return;
    pushHistory();
    // 1. Canvas
    if (proj.sprite && proj.sprite.size) {
      state.canvas = { w: proj.sprite.size.width || proj.sprite.size.w, h: proj.sprite.size.height || proj.sprite.size.h };
    } else if (proj.canvas) {
      state.canvas = { ...proj.canvas };
    }
    // 2. Layers
    const layers = (proj.meta && proj.meta.layers) || proj.layers || [];
    if (layers.length) {
      state.layers = layers.map((l, i) => ({
        id: l.id || `layer_${i}`,
        name: l.name || `Layer ${i+1}`,
        type: l.type || "character",
        visible: l.visible !== false,
        locked: !!l.locked,
        opacity: l.opacity != null ? (l.opacity > 1 ? l.opacity / 255 : l.opacity) : 1.0,
        blend_mode: l.blend_mode || "normal",
      }));
      state.activeLayerIndex = 0;
    }
    // 3. Tags
    const tags = (proj.meta && proj.meta.tags) || proj.tags || [];
    if (tags.length) {
      state.tags = tags.map(t => ({
        name: t.name,
        from_frame: t.from_frame != null ? t.from_frame : (t.from != null ? t.from : 0),
        to_frame: t.to_frame != null ? t.to_frame : (t.to != null ? t.to : 0),
        direction: t.direction || "forward",
        color: t.color || "#6aa8ff",
      }));
    }
    // 4. Frames & Cels & Anchors & Pivots & Durations & Linked Cels & Mask Strokes & Crops
    const frames = proj.frames || [];
    frames.forEach((pf, i) => {
      if (!state.frames[i] || !pf) return;
      if (pf.anchor) state.frames[i].anchor = { x: Number(pf.anchor.x), y: Number(pf.anchor.y) };
      if (pf.pivot) state.frames[i].pivot = { x: Number(pf.pivot.x), y: Number(pf.pivot.y) };
      if (pf.duration != null || pf.duration_ms != null) {
        state.frames[i].duration = Number(pf.duration != null ? pf.duration : pf.duration_ms);
      }
      if (pf.linked_cel_id !== undefined) state.frames[i].linked_cel_id = pf.linked_cel_id;
      if (pf.mask_strokes) state.frames[i].mask_strokes = pf.mask_strokes;
      if (pf.content_rect || pf.rect || pf.crop) {
        state.frames[i].content_rect = pf.content_rect || pf.rect || pf.crop;
      }
    });
    buildTimeline();
    buildAsepriteTimeline();
    updateInspectorLayers();
    updateInspectorProperties();
    draw();
    status("프로젝트 완벽 복원 완료 (Full Project Restored)");
  }

  if ($("loadProject")) {
    $("loadProject").addEventListener("change", async (e) => {
      const f = e.target.files && e.target.files[0];
      if (!f) return;
      try {
        const text = await f.text();
        const proj = JSON.parse(text);
        await loadProjectData(proj);
      } catch (err) {
        notifyUser("프로젝트 로드 실패: " + err.message);
      }
    });
  }

  $("btnAiAlign").addEventListener("click", async () => {
    if (!state.sessionId) return;
    const btn = $("btnAiAlign");
    if ($("aiProvider") && $("aiProvider").value === "disabled") {
      notifyUser("AI 사용 안 함 상태입니다. 제공자를 선택하세요.");
      return;
    }
    btn.disabled = true;
    status("AI 정렬 중…");
    if ($("aiStatus")) $("aiStatus").textContent = "비전 모델 호출 중… (수 초~수십 초)";
    try {

      // OpenRouter text-only guard (Nemotron free etc.)
      if ($("aiProvider") && $("aiProvider").value === "openrouter") {
        let model = $("aiModel").value;
        const low = (model || "").toLowerCase();
        const textOnly = (low.includes("nemotron") && !low.includes("vision"))
          || (low.includes("deepseek-v4-flash") && !low.includes("vision") && !low.includes("vl"))
          || (low.includes("deepseek-v4-pro") && !low.includes("vision"));
        if (textOnly) {
          const vd = (state.lastModelCatalog && state.lastModelCatalog.vision_default) || "google/gemini-2.5-flash-lite";
          if ($("aiStatus")) $("aiStatus").textContent = `텍스트 전용 모델 → 비전으로 전환: ${vd}`;
          model = vd;
          if ($("aiModel")) {
            // ensure option exists
            if (![...$("aiModel").options].some((o) => o.value === vd)) {
              const opt = document.createElement("option");
              opt.value = vd; opt.textContent = vd + " (vision)";
              $("aiModel").appendChild(opt);
            }
            $("aiModel").value = vd;
          }
        }
      }

      const res = await fetch("/api/ai-align", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: state.sessionId,
          provider: $("aiProvider").value,
          model: $("aiModel").value,
          duration: Number($("duration").value),
        }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "ai-align failed");
      await applySession(data);
      $("btnExport").disabled = false;
      const n = (data.ai_alignments || []).length;
      status(`AI 정렬 완료 · ${n}프레임 · 캔버스 ${data.canvas.w}×${data.canvas.h}`);
      if ($("aiStatus")) {
        $("aiStatus").textContent = `완료 · ${data.ai_provider || ""} / ${data.ai_model || ""}`;
      }
    } catch (err) {
      console.error(err);
      status("오류: " + err.message);
      if ($("aiStatus")) $("aiStatus").textContent = "실패: " + err.message;
      {
        const tip = /vision|이미지|image input|NoneType|empty content|content=null/i.test(String(err.message))
          ? "\n\n팁: 비전(이미지) 모델인지 확인하고, 응답이 비면 gemini/kimi로 바꾸세요."
          : "";
        notifyUser("AI 정렬 실패: " + err.message + tip);
      }
    } finally {
      btn.disabled = !state.sessionId;
    }
  });


  // ==================== STUDIO PRO INTEGRATION ====================

  function updateInspectorProperties() {
    const f = state.frames[state.index];
    if (!f) return;
    const activeLayer = state.layers[state.activeLayerIndex] || state.layers[0];
    if ($("propCelLayer")) $("propCelLayer").textContent = activeLayer ? activeLayer.name : "-";
    if ($("propCelOffset")) $("propCelOffset").textContent = `${f.anchor.x}, ${f.anchor.y}`;
    if ($("propCelLink")) $("propCelLink").textContent = f.linked_cel_id ? `연결: ${f.linked_cel_id}` : "독립 셀";
    if ($("propFrameIndex")) $("propFrameIndex").textContent = `${state.index} (총 ${state.frames.length})`;
    const bw = f.content_rect ? (f.content_rect.width ?? f.content_rect.w) : (state.canvas ? state.canvas.w : "-");
    const bh = f.content_rect ? (f.content_rect.height ?? f.content_rect.h) : (state.canvas ? state.canvas.h : "-");
    if ($("propFrameBBox")) $("propFrameBBox").textContent = `${bw}×${bh}`;
    const vw = f.effect_bbox ? (f.effect_bbox.width ?? f.effect_bbox.w) : null;
    const vh = f.effect_bbox ? (f.effect_bbox.height ?? f.effect_bbox.h) : null;
    if ($("propFrameVfx")) $("propFrameVfx").textContent = vw && vh ? `감지됨 (${vw}×${vh})` : "없음";
    if ($("propSpriteCanvas")) $("propSpriteCanvas").textContent = state.canvas ? `${state.canvas.w}×${state.canvas.h}` : "-";
    if ($("propSpriteFrames")) $("propSpriteFrames").textContent = `${state.frames.length}`;
    if ($("statusCoords")) $("statusCoords").textContent = `캔버스: ${state.canvas ? `${state.canvas.w}×${state.canvas.h}` : "0×0"} px | 앵커: (${f.anchor.x}, ${f.anchor.y})`;
    if ($("statusFrameInfo")) $("statusFrameInfo").textContent = `프레임 ${state.index + 1} / ${state.frames.length}`;
  }

  function updateInspectorLayers() {
    const list = $("inspectorLayersList");
    if (!list) return;
    list.innerHTML = "";
    state.layers.forEach((layer, idx) => {
      const row = document.createElement("div");
      row.className = "insp-layer-row" + (idx === state.activeLayerIndex ? " active" : "");
      if (layer.parent_id) row.style.paddingLeft = "20px";

      // Hide if parent group is collapsed
      const parent = layer.parent_id ? state.layers.find(p => p.id === layer.parent_id) : null;
      if (parent && parent.collapsed) {
        row.style.display = "none";
      }
      
      const eye = document.createElement("span");
      eye.className = "tl-layer-icon" + (!layer.visible ? " hidden" : "");
      eye.textContent = layer.visible ? "👁️" : "🚫";
      eye.addEventListener("click", (e) => {
        e.stopPropagation();
        layer.visible = !layer.visible;
        updateInspectorLayers();
        buildAsepriteTimeline();
        draw();
      });

      const lock = document.createElement("span");
      lock.className = "tl-layer-icon";
      lock.textContent = layer.locked ? "🔒" : "🔓";
      lock.addEventListener("click", (e) => {
        e.stopPropagation();
        layer.locked = !layer.locked;
        updateInspectorLayers();
        buildAsepriteTimeline();
      });

      row.appendChild(eye);
      row.appendChild(lock);

      if (layer.type === "group") {
        const folder = document.createElement("span");
        folder.className = "tl-folder-toggle";
        folder.style.cursor = "pointer";
        folder.textContent = layer.collapsed ? "📁" : "📂";
        folder.addEventListener("click", (e) => {
          e.stopPropagation();
          layer.collapsed = !layer.collapsed;
          updateInspectorLayers();
          buildAsepriteTimeline();
        });
        row.appendChild(folder);
      }

      const name = document.createElement("span");
      name.style.flex = "1";
      name.style.fontWeight = idx === state.activeLayerIndex ? "600" : "normal";
      name.textContent = layer.name;
      row.appendChild(name);

      if (layer.type === "reference") {
        const b = document.createElement("span");
        b.className = "tl-layer-badge ref";
        b.textContent = "REF";
        row.appendChild(b);
      } else if (layer.type === "group") {
        const b = document.createElement("span");
        b.className = "tl-layer-badge group";
        b.textContent = "GRP";
        row.appendChild(b);
      }

      const op = document.createElement("span");
      op.style.fontSize = "10px";
      op.style.color = "var(--text-muted)";
      op.textContent = `${Math.round(layer.opacity * 100)}%`;
      row.appendChild(op);

      row.addEventListener("click", () => {
        state.activeLayerIndex = idx;
        updateInspectorLayers();
        updateAsepriteTimelineSelection();
        updateInspectorProperties();
        if ($("layerOpacitySlider")) $("layerOpacitySlider").value = Math.round(layer.opacity * 100);
        if ($("layerOpacityVal")) $("layerOpacityVal").textContent = `${Math.round(layer.opacity * 100)}%`;
        if ($("layerBlendSelect")) $("layerBlendSelect").value = layer.blend_mode || "normal";
        draw();
      });

      list.appendChild(row);
    });
  }

  function setActiveTool(tool) {
    state.activeTool = tool;
    if (tool !== "select" && state.selectionDraft) state.selectionDraft = null;
    document.querySelectorAll(".studio-tool-rail .tool-btn").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.tool === tool);
    });
    document.querySelectorAll(".studio-context-bar .ctx-group").forEach(grp => {
      grp.classList.toggle("active", grp.dataset.tool === tool);
    });
    const view = $("view");
    if (view) {
      if (tool === "mask") {
        view.style.cursor = "crosshair";
        if ($("maskPaint")) $("maskPaint").checked = true;
      } else if (tool === "select") {
        view.style.cursor = "crosshair";
        if ($("maskPaint")) $("maskPaint").checked = false;
      } else if (tool === "move") {
        view.style.cursor = "move";
        if ($("maskPaint")) $("maskPaint").checked = false;
      } else if (tool === "anchor") {
        view.style.cursor = "crosshair";
        if ($("maskPaint")) $("maskPaint").checked = false;
      } else {
        view.style.cursor = "default";
        if ($("maskPaint")) $("maskPaint").checked = false;
      }
    }
    draw();
  }

  document.querySelectorAll(".studio-tool-rail .tool-btn[data-tool]").forEach(btn => {
    btn.addEventListener("click", () => setActiveTool(btn.dataset.tool));
  });

  // Modal dialog controllers
  function openModal(id) {
    const m = $(id);
    if (m) {
      m.style.display = "flex";
      if (id === "exportModal") checkAsepriteBridgeStatus();
    }
  }
  function closeModal(id) {
    const m = $(id);
    if (m) m.style.display = "none";
  }

  document.querySelectorAll("[data-close]").forEach(el => {
    el.addEventListener("click", () => closeModal(el.getAttribute("data-close")));
  });

  document.querySelectorAll(".studio-modal-overlay").forEach(overlay => {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) overlay.style.display = "none";
    });
  });

  async function loadSampleAttack() {
    status("공격 4×4 샘플 분석 중…");
    try {
      const res = await fetch("/api/load-sample");
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "sample load failed");
      await applySession(data, { resetHistory: true });
      status(`샘플 로드 완료 · ${data.frames.length}프레임 · 캔버스 ${data.canvas.w}×${data.canvas.h}`);
      $("btnExport").disabled = false;
      if ($("btnAiAlign")) $("btnAiAlign").disabled = false;
    } catch (err) {
      console.error(err);
      status("샘플 로드 오류: " + err.message);
    }
  }

  if ($("menuLoadSample")) $("menuLoadSample").addEventListener("click", loadSampleAttack);

  if (window.__INITIAL_SESSION__) {
    applySession(window.__INITIAL_SESSION__, { resetHistory: true });
    status(`샘플 로드 완료 · ${window.__INITIAL_SESSION__.frames.length}프레임 · 캔버스 ${window.__INITIAL_SESSION__.canvas.w}×${window.__INITIAL_SESSION__.canvas.h}`);
    if ($("btnExport")) $("btnExport").disabled = false;
    if ($("btnAiAlign")) $("btnAiAlign").disabled = false;
  } else {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get("sample") === "1" || urlParams.get("demo") === "1") {
      setTimeout(loadSampleAttack, 100);
    }
  }

  // Menu item bindings
  if ($("menuImport")) $("menuImport").addEventListener("click", () => openModal("importModal"));
  if ($("menuExport")) $("menuExport").addEventListener("click", () => openModal("exportModal"));
  if ($("btnQuickExportTop")) $("btnQuickExportTop").addEventListener("click", () => openModal("exportModal"));
  if ($("menuAiSettings")) $("menuAiSettings").addEventListener("click", () => openModal("aiSettingsModal"));

  if ($("menuNewFrame")) $("menuNewFrame").addEventListener("click", () => {
    if ($("btnDupFrame")) $("btnDupFrame").click();
  });
  if ($("menuDupFrame")) $("menuDupFrame").addEventListener("click", () => {
    if ($("btnDupFrame")) $("btnDupFrame").click();
  });
  if ($("menuNewFrame")) $("menuNewFrame").addEventListener("click", insertBlankFrame);
  if ($("menuDupFrame")) $("menuDupFrame").addEventListener("click", duplicateCurrentFrame);
  if ($("menuDelFrame")) $("menuDelFrame").addEventListener("click", deleteCurrentFrame);
  if ($("menuMoveFrameLeft")) $("menuMoveFrameLeft").addEventListener("click", () => moveFrame(-1));
  if ($("menuMoveFrameRight")) $("menuMoveFrameRight").addEventListener("click", () => moveFrame(1));
  if ($("menuReverseFrames")) $("menuReverseFrames").addEventListener("click", reverseFrameSequence);

  if ($("menuNewLayer")) $("menuNewLayer").addEventListener("click", () => addNewLayer());
  if ($("menuNewLayerGroup")) $("menuNewLayerGroup").addEventListener("click", () => addNewLayerGroup());
  if ($("menuNewRefLayer")) $("menuNewRefLayer").addEventListener("click", () => addNewReferenceLayer());
  if ($("menuRenameLayer")) $("menuRenameLayer").addEventListener("click", renameCurrentLayer);
  if ($("menuMoveLayerUp")) $("menuMoveLayerUp").addEventListener("click", () => moveLayer(-1));
  if ($("menuMoveLayerDown")) $("menuMoveLayerDown").addEventListener("click", () => moveLayer(1));
  if ($("menuDupLayer")) $("menuDupLayer").addEventListener("click", duplicateCurrentLayer);
  if ($("menuDelLayer")) $("menuDelLayer").addEventListener("click", deleteCurrentLayer);

  if ($("menuCopyCel")) $("menuCopyCel").addEventListener("click", copyCel);
  if ($("menuPasteCel")) $("menuPasteCel").addEventListener("click", pasteCel);
  if ($("menuClearCel")) $("menuClearCel").addEventListener("click", clearCel);
  if ($("menuFlipH")) $("menuFlipH").addEventListener("click", transformFlipH);
  if ($("menuFlipV")) $("menuFlipV").addEventListener("click", transformFlipV);
  if ($("menuRot90")) $("menuRot90").addEventListener("click", transformRotate90);
  if ($("menuOpenPreview")) $("menuOpenPreview").addEventListener("click", openPreviewModal);

  if ($("menuRunAiAlign")) $("menuRunAiAlign").addEventListener("click", () => {
    if ($("btnAiAlign") && !$("btnAiAlign").disabled) $("btnAiAlign").click();
  });
  if ($("menuRunAiQa")) $("menuRunAiQa").addEventListener("click", () => {
    if ($("btnAiQa")) $("btnAiQa").click();
  });
  if ($("menuRunAnimQa")) $("menuRunAnimQa").addEventListener("click", () => {
    if ($("btnAnimQa")) $("btnAnimQa").click();
  });

  if ($("btnOpenQa")) $("btnOpenQa").addEventListener("click", () => {
    const btn = document.querySelector('.insp-tab-btn[data-tab="aiqa"]');
    if (btn) btn.click();
  });

  // Inspector tab switcher
  document.querySelectorAll(".insp-tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      document.querySelectorAll(".insp-tab-btn").forEach(b => b.classList.toggle("active", b === btn));
      document.querySelectorAll(".insp-pane").forEach(p => p.classList.remove("active"));
      if (tab === "properties" && $("tabProperties")) $("tabProperties").classList.add("active");
      if (tab === "layers" && $("tabLayers")) $("tabLayers").classList.add("active");
      if (tab === "aiqa" && $("tabAiQa")) $("tabAiQa").classList.add("active");
    });
  });

  // Layer opacity slider in inspector
  if ($("layerOpacitySlider")) {
    $("layerOpacitySlider").addEventListener("input", (e) => {
      const layer = state.layers[state.activeLayerIndex];
      if (layer) {
        layer.opacity = Number(e.target.value) / 100;
        if ($("layerOpacityVal")) $("layerOpacityVal").textContent = `${e.target.value}%`;
        draw();
      }
    });
  }

  // Layer blend select in inspector
  if ($("layerBlendSelect")) {
    $("layerBlendSelect").addEventListener("change", (e) => {
      const layer = state.layers[state.activeLayerIndex];
      if (layer) {
        layer.blend_mode = e.target.value;
        draw();
      }
    });
  }

  // Animation Safe Autocrop Button
  if ($("btnCropSafe")) {
    $("btnCropSafe").addEventListener("click", async () => {
      if (!state.sessionId || !state.frames.length) return;
      status("애니메이션 안전 크롭 계산 중…");
      try {
        if ($("btnCropTight")) $("btnCropTight").click();
      } catch (err) {
        console.error(err);
        status("오류: " + err.message);
      }
    });
  }

  // Simple Mode / Pro Mode switcher
  if ($("btnModeToggle")) {
    $("btnModeToggle").addEventListener("click", () => {
      const root = $("studioRoot");
      const isPro = root.classList.contains("pro-mode");
      if (isPro) {
        root.classList.remove("pro-mode");
        root.classList.add("simple-mode");
        $("btnModeToggle").textContent = "🛠️ 프로 모드로 전환";
        status("간편 모드 활성 (Simple Mode)");
      } else {
        root.classList.remove("simple-mode");
        root.classList.add("pro-mode");
        $("btnModeToggle").textContent = "⚡ 간편 모드로 전환";
        status("프로 스튜디오 모드 활성 (Pro Mode)");
      }
    });
  }

  // View check options
  if ($("chkPixelGrid")) $("chkPixelGrid").addEventListener("change", draw);
  if ($("chkOnionSkin")) $("chkOnionSkin").addEventListener("change", (e) => {
    if ($("onionSkinToggle")) $("onionSkinToggle").checked = e.target.checked;
    draw();
  });
  if ($("chkDiffView")) $("chkDiffView").addEventListener("change", draw);
  if ($("diffTargetSelect")) $("diffTargetSelect").addEventListener("change", draw);

  // Zoom preset menu items
  if ($("menuZoom100")) $("menuZoom100").addEventListener("click", () => { state.zoom = 1; draw(); });
  if ($("menuZoom200")) $("menuZoom200").addEventListener("click", () => { state.zoom = 2; draw(); });
  if ($("menuZoomFit")) $("menuZoomFit").addEventListener("click", () => { state.zoom = "fit"; draw(); });

  // Keyboard shortcuts
  window.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "i") {
      e.preventDefault();
      openModal("importModal");
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "e") {
      e.preventDefault();
      openModal("exportModal");
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      if ($("btnSaveProject")) $("btnSaveProject").click();
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
      e.preventDefault();
      undo();
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") {
      e.preventDefault();
      redo();
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "c") {
      e.preventDefault();
      copyCel();
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "v") {
      e.preventDefault();
      pasteCel();
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "l") {
      e.preventDefault();
      toggleCelLink();
    } else if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      clearCel();
    } else if (e.altKey && e.key.toLowerCase() === "n") {
      e.preventDefault();
      insertBlankFrame();
    } else if (e.altKey && (e.key === "[" || e.key === "{")) {
      e.preventDefault();
      moveFrame(-1);
    } else if (e.altKey && (e.key === "]" || e.key === "}")) {
      e.preventDefault();
      moveFrame(1);
    } else if (e.key === "F2") {
      e.preventDefault();
      renameCurrentLayer();
    } else if (e.key === "F3") {
      e.preventDefault();
      const chk = $("onionSkinToggle");
      if (chk) { chk.checked = !chk.checked; draw(); }
    } else if (e.key === "F4") {
      e.preventDefault();
      openPreviewModal();
    } else if (!e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "n") {
      e.preventDefault();
      addNewLayer();
    } else if (e.key === "Tab") {
      e.preventDefault();
      const tl = $("timelinePanel");
      if (tl) tl.style.display = tl.style.display === "none" ? "flex" : "none";
    } else if (!e.ctrlKey && !e.shiftKey && !e.altKey && e.key.toLowerCase() === "a") {
      setActiveTool("anchor");
    } else if (!e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "a") {
      if ($("btnAiAlign") && !$("btnAiAlign").disabled) $("btnAiAlign").click();
    } else if (e.key.toLowerCase() === "j") {
      if ($("btnAnimQa")) $("btnAnimQa").click();
    } else if (e.key === "ArrowLeft" || e.key === ",") {
      setIndex(state.index - 1);
    } else if (e.key === "ArrowRight" || e.key === ".") {
      setIndex(state.index + 1);
    } else if (e.key === "Home") {
      setIndex(0);
    } else if (e.key === "End") {
      setIndex(state.frames.length - 1);
    }
  });

  // Expose studio methods for dev & automated E2E testing
  window.__STUDIO__ = {
    state,
    setIndex,
    draw,
    undo,
    redo,
    pushHistory,
    addNewLayer,
    renameCurrentLayer,
    moveLayer,
    deleteCurrentLayer,
    duplicateCurrentLayer,
    insertBlankFrame,
    duplicateCurrentFrame,
    deleteCurrentFrame,
    moveFrame,
    reverseFrameSequence,
    copyCel,
    pasteCel,
    clearCel,
    toggleCelLink,
    syncLinkedCelImages,
    setPivot,
    getPixelData,
    transformFlipH,
    transformFlipV,
    transformRotate90,
    openPreviewModal,
    closePreviewModal,
    loadProjectData,
    applySession,
    updateAsepriteTimelineSelection,
    updateInspectorLayers,
    updateInspectorProperties,
  };

})();
