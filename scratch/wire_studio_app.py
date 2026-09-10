import re
from pathlib import Path

app_js_path = Path(r"C:\TEST\MikuChat-Lab\projects\SpriteRepair\app\app.js")
content = app_js_path.read_text(encoding="utf-8")

# 1. Ensure state has activeTool and diffViewEnabled
if 'activeTool: "anchor"' not in content:
    content = content.replace(
        'const state = {\n',
        'const state = {\n    activeTool: "anchor",\n    diffViewEnabled: false,\n',
        1
    )

# 2. Add updateInspectorProperties() call inside setIndex()
if 'updateInspectorProperties()' not in content:
    content = content.replace(
        'updateAsepriteTimelineSelection();\n    draw();',
        'updateAsepriteTimelineSelection();\n    updateInspectorProperties();\n    updateInspectorLayers();\n    draw();'
    )

# 3. Add difference view block inside draw() before update HUD
diff_snippet = '''
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
'''

if 'Difference View Overlay' not in content:
    content = content.replace(
        '    // 6. Update HUD & Zoom label',
        diff_snippet + '\n    // 6. Update HUD & Zoom label'
    )

# 4. Add comprehensive Studio Pro functions before the closing `})();`
studio_functions = '''
  // ==================== STUDIO PRO INTEGRATION ====================

  function updateInspectorProperties() {
    const f = state.frames[state.index];
    if (!f) return;
    const activeLayer = state.layers[state.activeLayerIndex] || state.layers[0];
    if ($("propCelLayer")) $("propCelLayer").textContent = activeLayer ? activeLayer.name : "-";
    if ($("propCelOffset")) $("propCelOffset").textContent = `${f.anchor.x}, ${f.anchor.y}`;
    if ($("propCelLink")) $("propCelLink").textContent = f.linked_cel_id ? `연결: ${f.linked_cel_id}` : "독립 셀";
    if ($("propFrameIndex")) $("propFrameIndex").textContent = `${state.index} (총 ${state.frames.length})`;
    if ($("propFrameDuration")) $("propFrameDuration").textContent = `${f.duration || 80}ms`;
    if ($("propFrameBBox")) $("propFrameBBox").textContent = f.content_rect ? `${f.content_rect.w}×${f.content_rect.h}` : (state.canvas ? `${state.canvas.w}×${state.canvas.h}` : "-");
    if ($("propFrameVfx")) $("propFrameVfx").textContent = f.effect_bbox ? `감지됨 (${f.effect_bbox.w}×${f.effect_bbox.h})` : "없음";
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

      const name = document.createElement("span");
      name.style.flex = "1";
      name.style.fontWeight = idx === state.activeLayerIndex ? "600" : "normal";
      name.textContent = layer.name;

      const op = document.createElement("span");
      op.style.fontSize = "10px";
      op.style.color = "var(--text-muted)";
      op.textContent = `${Math.round(layer.opacity * 100)}%`;

      row.appendChild(eye);
      row.appendChild(lock);
      row.appendChild(name);
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
      } else if (tool === "move") {
        view.style.cursor = "move";
        if ($("maskPaint")) $("maskPaint").checked = false;
      } else if (tool === "anchor") {
        view.style.cursor = "crosshair";
        if ($("maskPaint")) $("maskPaint").checked = false;
      } else if (tool === "diff") {
        view.style.cursor = "default";
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
    if (m) m.style.display = "flex";
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
  if ($("menuDelFrame")) $("menuDelFrame").addEventListener("click", () => {
    if ($("btnDelFrame")) $("btnDelFrame").click();
  });
  if ($("menuNewLayer")) $("menuNewLayer").addEventListener("click", () => {
    if ($("btnAddLayer")) $("btnAddLayer").click();
  });
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
    } else if (e.key === "F3") {
      e.preventDefault();
      const chk = $("onionSkinToggle");
      if (chk) { chk.checked = !chk.checked; draw(); }
    } else if (e.key === "Tab") {
      e.preventDefault();
      const tl = $("timelinePanel");
      if (tl) tl.style.display = tl.style.display === "none" ? "flex" : "none";
    } else if (!e.ctrlKey && !e.shiftKey && e.key.toLowerCase() === "a") {
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

'''

if '// ==================== STUDIO PRO INTEGRATION ====================' not in content:
    content = content.replace('\n})();', '\n' + studio_functions + '\n})();')

app_js_path.write_text(content, encoding="utf-8")
print("app.js updated successfully!")
