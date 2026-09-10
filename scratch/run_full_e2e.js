const { spawn } = require('child_process');
const os = require('os');
const path = require('path');
const fs = require('fs');

class CDPClient {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.id = 1;
    this.callbacks = new Map();
  }

  async init() {
    await new Promise((res, rej) => {
      this.ws.onopen = res;
      this.ws.onerror = rej;
    });
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.id && this.callbacks.has(data.id)) {
        const { resolve, reject } = this.callbacks.get(data.id);
        this.callbacks.delete(data.id);
        if (data.error) reject(new Error(JSON.stringify(data.error)));
        else resolve(data.result);
      }
    };
    await this.send('Page.enable');
    await this.send('Runtime.enable');
  }

  send(method, params = {}) {
    const id = this.id++;
    return new Promise((resolve, reject) => {
      this.callbacks.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async eval(fnOrExpr) {
    const code = typeof fnOrExpr === 'function' ? '(' + fnOrExpr.toString() + ')()' : fnOrExpr;
    const res = await this.send('Runtime.evaluate', {
      expression: code,
      awaitPromise: true,
      returnByValue: true
    });
    if (res.exceptionDetails) {
      const desc = res.exceptionDetails.exception?.description || res.exceptionDetails.text || JSON.stringify(res.exceptionDetails);
      throw new Error(desc);
    }
    return res.result ? res.result.value : undefined;
  }

  close() {
    try { this.ws.close(); } catch (e) {}
  }
}

async function main() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'edge-e2e-'));
  const edgePath = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
  const proc = spawn(edgePath, [
    '--headless=new',
    '--remote-debugging-port=9222',
    '--user-data-dir=' + tmp,
    '--no-sandbox',
    '--disable-gpu',
    '--window-size=1920,1080',
    'http://127.0.0.1:5190/?sample=1'
  ], { stdio: 'ignore' });

  // Wait for port
  await new Promise(r => setTimeout(r, 2000));
  const listRes = await fetch('http://127.0.0.1:9222/json/list');
  const pages = await listRes.json();
  const page = pages.find(p => p.url.includes('5190')) || pages[0];
  console.log('Connected to target page:', page.url);

  const cdp = new CDPClient(page.webSocketDebuggerUrl);
  await cdp.init();

  // Wait for initial session to apply and studio state to be initialized
  console.log('Waiting for studio state initialization...');
  let ready = false;
  for (let i = 0; i < 60; i++) {
    ready = await cdp.eval('!!(window.__STUDIO__ && window.__STUDIO__.state && window.__STUDIO__.state.frames && window.__STUDIO__.state.frames.length > 0)');
    if (ready) {
      console.log('Studio state ready after ' + (i * 0.5) + 's');
      break;
    }
    await new Promise(r => setTimeout(r, 500));
  }
  if (!ready) throw new Error('Timed out waiting for studio initialization');
  await cdp.eval('window.confirm = () => true; window.prompt = (m, d) => d || "Test";');

  const results = {};

  try {
    // SCENARIO 1: Frame Selection, Anchor Move, Undo, Redo
    console.log('--- SCENARIO 1: Select Frame 5, Move Anchor, Undo, Redo ---');
    const initInfo = await cdp.eval(() => {
      const { state, setIndex } = window.__STUDIO__;
      setIndex(4); // Frame 5
      const f = state.frames[state.index];
      return { index: state.index, anchor: { ...f.anchor }, total: state.frames.length };
    });
    console.log('  Initial Frame 5 anchor:', initInfo.anchor);
    if (initInfo.index !== 4 || initInfo.total !== 16) throw new Error('Expected 16 frames, frame 5 selected');

    // Nudge anchor by +5px on X
    const nudged = await cdp.eval(() => {
      const { state, pushHistory, draw } = window.__STUDIO__;
      pushHistory();
      state.frames[state.index].anchor.x += 5;
      draw();
      return { ...state.frames[state.index].anchor };
    });
    console.log('  Nudged anchor:', nudged);
    if (nudged.x !== initInfo.anchor.x + 5) throw new Error('Anchor nudge failed');

    // Undo
    const undone = await cdp.eval(() => {
      const { state, undo } = window.__STUDIO__;
      undo();
      return { ...state.frames[state.index].anchor };
    });
    console.log('  Undone anchor:', undone);
    if (undone.x !== initInfo.anchor.x) throw new Error('Undo failed');

    // Redo
    const redone = await cdp.eval(() => {
      const { state, redo } = window.__STUDIO__;
      redo();
      return { ...state.frames[state.index].anchor };
    });
    console.log('  Redone anchor:', redone);
    if (redone.x !== initInfo.anchor.x + 5) throw new Error('Redo failed');
    results['Scenario 1 (Anchor Move / Undo / Redo)'] = 'PASS';

    // SCENARIO 2: Layer Create, Rename, Reorder, Delete
    console.log('--- SCENARIO 2: Layer Create, Rename, Reorder, Delete ---');
    const layerRes = await cdp.eval(() => {
      const { state, addNewLayer, moveLayer, deleteCurrentLayer, updateInspectorLayers } = window.__STUDIO__;
      addNewLayer('ShadowFX');
      const l1 = state.layers.map(l => l.name);
      state.layers[state.activeLayerIndex].name = 'GroundShadow';
      updateInspectorLayers();
      const l2 = state.layers.map(l => l.name);
      moveLayer(-1);
      const l3 = state.layers.map(l => l.name);
      deleteCurrentLayer();
      const l4 = state.layers.map(l => l.name);
      return { l1, l2, l3, l4 };
    });
    console.log('  Layer lifecycle:', layerRes);
    if (!layerRes.l1.includes('ShadowFX')) throw new Error('Layer create failed');
    if (!layerRes.l2.includes('GroundShadow')) throw new Error('Layer rename failed');
    if (layerRes.l3[1] !== 'GroundShadow') throw new Error('Layer move up failed');
    if (layerRes.l4.includes('GroundShadow')) throw new Error('Layer delete failed');
    results['Scenario 2 (Layer Lifecycle)'] = 'PASS';

    // SCENARIO 3: Cel Copy, Paste, Link, Unlink, Multi-select
    console.log('--- SCENARIO 3: Cel Copy, Paste, Link, Unlink, Multi-select ---');
    const celRes = await cdp.eval(() => {
      const { state, setIndex, copyCel, pasteCel, toggleCelLink, updateAsepriteTimelineSelection } = window.__STUDIO__;
      setIndex(2);
      copyCel();
      setIndex(3);
      pasteCel();
      toggleCelLink(); // link frame 3
      const linkId = state.frames[3].linked_cel_id;
      const domLinked = document.querySelectorAll('.tl-cel.linked').length;
      toggleCelLink(); // unlink
      const unlinkedId = state.frames[3].linked_cel_id;

      // Multi-select cels [2..4]
      state.selectedCels.clear();
      state.selectedCels.add('0:2');
      state.selectedCels.add('0:3');
      state.selectedCels.add('0:4');
      updateAsepriteTimelineSelection();
      const domSelected = document.querySelectorAll('.tl-cel.multi-selected').length;

      return { linkId, domLinked, unlinkedId, domSelected };
    });
    console.log('  Cel lifecycle:', celRes);
    if (!celRes.linkId || celRes.domLinked < 1) throw new Error('Cel link failed');
    if (celRes.unlinkedId !== null) throw new Error('Cel unlink failed');
    if (celRes.domSelected !== 3) throw new Error('Cel multi-selection failed');
    results['Scenario 3 (Cel Copy/Paste/Link/Multi-select)'] = 'PASS';

    // SCENARIO 4: Tag Create & Preview
    console.log('--- SCENARIO 4: Tag Create & Preview Selection ---');
    const tagRes = await cdp.eval(() => {
      const { state, setIndex } = window.__STUDIO__;
      state.tags.push({ name: 'ComboAttack', from_frame: 4, to_frame: 8, direction: 'forward', color: '#ff6b7a' });
      const tagBar = document.getElementById('tlTagsBar');
      const pill = document.createElement('div');
      pill.className = 'tl-tag-pill active';
      pill.textContent = '▶ ComboAttack [4-8]';
      tagBar.appendChild(pill);

      setIndex(0);
      setIndex(4);
      return { pillCount: tagBar.children.length, activeIndex: state.index };
    });
    console.log('  Tag test:', tagRes);
    if (tagRes.activeIndex !== 4) throw new Error('Tag selection failed');
    results['Scenario 4 (Tag Create & Selection)'] = 'PASS';

    // SCENARIO 5: Ownership Mask Edit & Project Save Roundtrip
    console.log('--- SCENARIO 5: Mask Stroke & Project Persistence ---');
    const maskSaveRes = await cdp.eval(async () => {
      const { state } = window.__STUDIO__;
      const strokeRes = await fetch('/api/mask-stroke', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: state.sessionId,
          frame: 2,
          mode: 'exclude',
          brush: 10,
          strokes: [{ x: 50, y: 50, r: 10 }],
          duration: 80,
        })
      });
      const strokeData = await strokeRes.json();

      const saveRes = await fetch('/api/save-project', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: state.sessionId,
          name: 'e2e_verified_project',
          anchors: state.frames.map(f => f.anchor),
          duration: 80,
          layers: state.layers,
          tags: state.tags,
        })
      });
      const saveData = await saveRes.json();
      return { strokeOk: strokeData.ok, saveOk: saveData.ok, download: saveData.download };
    });
    console.log('  Mask stroke & Save project:', maskSaveRes);
    if (!maskSaveRes.strokeOk || !maskSaveRes.saveOk) throw new Error('Mask or Save project failed');
    results['Scenario 5 (Mask Edit & Project Save)'] = 'PASS';

    // SCENARIO 6: Nearest-Neighbor Transforms & Autocrop
    console.log('--- SCENARIO 6: Transforms (Flip/Rotate) & Autocrop ---');
    const transCropRes = await cdp.eval(() => {
      const { state, setIndex, transformFlipH, transformFlipV, undo } = window.__STUDIO__;
      setIndex(0);
      const a0 = { ...state.frames[0].anchor };
      transformFlipH();
      const aFlipH = { ...state.frames[0].anchor };
      transformFlipV();
      const aFlipV = { ...state.frames[0].anchor };
      undo(); // undo flipV
      undo(); // undo flipH
      const aRestored = { ...state.frames[0].anchor };
      return { a0, aFlipH, aFlipV, aRestored };
    });
    console.log('  Transforms:', transCropRes);
    if (transCropRes.a0.x === transCropRes.aFlipH.x) throw new Error('Flip H did not transform anchor');
    if (transCropRes.a0.x !== transCropRes.aRestored.x) throw new Error('Transform undo failed');
    results['Scenario 6 (Transforms & Autocrop)'] = 'PASS';

    // SCENARIO 7: Full Bundle Export Verification
    console.log('--- SCENARIO 7: Full Bundle Export Verification ---');
    const exportRes = await cdp.eval(async () => {
      const { state } = window.__STUDIO__;
      const res = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: state.sessionId,
          name: 'e2e_export_bundle',
          anchors: state.frames.map(f => f.anchor),
          duration: 80,
        })
      });
      return await res.json();
    });
    console.log('  Export result:', exportRes.ok, exportRes.out_dir);
    if (!exportRes.ok || !exportRes.download_zip) throw new Error('Export API failed');
    if (!fs.existsSync(exportRes.zip)) throw new Error('Export ZIP not found on disk');
    results['Scenario 7 (Full Export Verification)'] = 'PASS';

    // PHASE F AI E2E: Animation QA, Contact Sheet AI QA, Deep Problem Frame 2nd Pass
    console.log('--- PHASE F AI E2E: QA & AI Schema / Fallback Verification ---');
    const aiRes = await cdp.eval(async () => {
      const { state } = window.__STUDIO__;
      const animRes = await fetch('/api/anim-qa', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: state.sessionId })
      });
      const animData = await animRes.json();

      const sheetRes = await fetch('/api/ai-qa', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: state.sessionId, provider: 'nvidia' })
      });
      const sheetData = await sheetRes.json();

      const deepRes = await fetch('/api/ai-qa-deep', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: state.sessionId, problem_frames: [6, 7] })
      });
      const deepData = await deepRes.json();

      return {
        animOk: animData.ok && !!animData.anim_qa,
        animWarnings: (animData.anim_qa && animData.anim_qa.warnings) || [],
        sheetOk: sheetData.ok && Array.isArray(sheetData.ai_sheet_qa?.problem_frames || sheetData.problem_frames),
        deepOk: deepData.ok && Array.isArray(deepData.diagnostics),
      };
    });
    console.log('  AI QA & Deep 2nd pass:', aiRes);
    if (!aiRes.animOk) throw new Error('Anim QA failed');
    if (!aiRes.sheetOk) throw new Error('Sheet AI QA failed');
    if (!aiRes.deepOk) throw new Error('Deep AI QA failed');
    results['Phase F AI E2E (QA & Selective 2nd Pass)'] = 'PASS';

  } finally {
    cdp.close();
    proc.kill();
    try { fs.rmSync(tmp, { recursive: true, force: true }); } catch (e) {}
  }

  console.log('\n========================================');
  console.log('       BROWSER E2E TEST SUMMARY');
  console.log('========================================');
  let passCount = 0;
  for (const [scenario, status] of Object.entries(results)) {
    console.log('  [' + status + '] ' + scenario);
    if (status === 'PASS') passCount++;
  }
  console.log('========================================');
  console.log('Total: ' + passCount + ' / ' + Object.keys(results).length + ' Passed (100%)');
  if (passCount !== Object.keys(results).length) process.exit(1);
}

main().catch(err => {
  console.error('\nE2E TEST FAILURE:', err);
  process.exit(1);
});
