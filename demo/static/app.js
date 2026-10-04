/**
 * app.js — Redfox AI Interactive Cockpit Controller
 *
 * Coordinates real-time SSE telemetry, reactive pipeline node states,
 * verification chamber animations, and executive report downloads.
 */

// ── State Management ────────────────────────────────────────────────────────

const state = {
  isRunning: false,
  target: 'http://httpbin.org',
  maxSteps: 6,
  currentStep: 0,
  engine: 'auto',
  groqKey: localStorage.getItem('redfox_groq_key') || '',
  openaiKey: localStorage.getItem('redfox_openai_key') || '',
  audioEnabled: true,
  eventSource: null,
  confirmedFindings: [],
  rejectedFindings: [],
  toolCount: 0,
  observations: [],
};

// ── Web Audio Synth (Subtle Cockpit Audio Feedback) ─────────────────────────

class CockpitAudio {
  constructor() {
    this.ctx = null;
  }
  init() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) this.ctx = new AudioCtx();
    }
  }
  playBlip(freq = 600, duration = 0.06, type = 'sine') {
    if (!state.audioEnabled) return;
    try {
      this.init();
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
      gain.gain.setValueAtTime(0.04, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, this.ctx.currentTime + duration);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + duration);
    } catch (e) {
      // Ignore audio policy blocks
    }
  }
  playSuccess() {
    this.playBlip(784, 0.08);
    setTimeout(() => this.playBlip(1046, 0.12), 80);
  }
  playAlert() {
    this.playBlip(320, 0.12, 'sawtooth');
  }
}

const audio = new CockpitAudio();

// ── DOM References ──────────────────────────────────────────────────────────

const dom = {
  // Navigation & Badges
  statusPill: document.getElementById('system-status-pill'),
  statusText: document.getElementById('system-status-text'),
  engineBadge: document.getElementById('active-engine-badge'),
  btnAudio: document.getElementById('btn-audio-toggle'),
  audioIcon: document.getElementById('audio-icon'),

  // Command Bar
  inputTarget: document.getElementById('input-target-url'),
  presetHttpbin: document.getElementById('preset-httpbin'),
  presetVulnweb: document.getElementById('preset-vulnweb'),
  selectEngine: document.getElementById('select-llm-engine'),
  inputMaxSteps: document.getElementById('input-max-steps'),
  stepsCounterVal: document.getElementById('steps-counter-val'),
  btnStartScan: document.getElementById('btn-start-scan'),
  btnStopScan: document.getElementById('btn-stop-scan'),
  btnResetView: document.getElementById('btn-reset-view'),

  // Pipeline Flow
  liveStepLabel: document.getElementById('live-step-label'),
  liveStepBar: document.getElementById('live-step-bar'),
  pipelineNodes: {
    planner: document.getElementById('node-planner'),
    scope_check: document.getElementById('node-scope_check'),
    execute_tool: document.getElementById('node-execute_tool'),
    reflector: document.getElementById('node-reflector'),
    verify: document.getElementById('node-verify'),
  },

  // Tabs
  tabBtns: document.querySelectorAll('.tab-btn'),
  tabContents: document.querySelectorAll('.tab-content'),
  tabFindingsCounter: document.getElementById('tab-findings-counter'),

  // Cockpit Widgets
  telemetryObjective: document.getElementById('telemetry-objective'),
  telemetryTool: document.getElementById('telemetry-tool'),
  telemetryReasoning: document.getElementById('telemetry-reasoning'),
  scopeDecisionBox: document.getElementById('scope-decision-box'),
  scopeVerdictIcon: document.getElementById('scope-verdict-icon'),
  scopeVerdictText: document.getElementById('scope-verdict-text'),
  scopeReasonText: document.getElementById('scope-reason-text'),
  scopeAllowedList: document.getElementById('scope-allowed-list'),
  scopeLatency: document.getElementById('scope-latency'),
  toolLatencyBadge: document.getElementById('tool-latency-badge'),
  terminalToolName: document.getElementById('terminal-tool-name'),
  toolOutputJson: document.getElementById('tool-output-json'),
  verifierEmpty: document.getElementById('verifier-empty-state'),
  verifierActive: document.getElementById('verifier-active-state'),
  vCurrentSev: document.getElementById('v-current-sev'),
  vCurrentTitle: document.getElementById('v-current-title'),
  vProgressStatus: document.getElementById('v-progress-status'),
  vCurrentReasoning: document.getElementById('v-current-reasoning'),
  vCurrentHash: document.getElementById('v-current-hash'),
  liveLogStream: document.getElementById('live-log-stream'),
  btnClearLogs: document.getElementById('btn-clear-logs'),

  // Findings Tab
  statConfirmed: document.getElementById('stat-confirmed-count'),
  statRejected: document.getElementById('stat-rejected-count'),
  statTools: document.getElementById('stat-tools-count'),
  statHashes: document.getElementById('stat-hashes-count'),
  reportTargetMeta: document.getElementById('report-target-meta'),
  reportStatusMeta: document.getElementById('report-status-meta'),
  btnDownloadMd: document.getElementById('btn-download-md'),
  btnDownloadJson: document.getElementById('btn-download-json'),
  findingsCardsList: document.getElementById('findings-cards-list'),
  noFindingsSplash: document.getElementById('no-findings-splash'),
  rejectedContainer: document.getElementById('rejected-findings-container'),
  rejectedList: document.getElementById('rejected-findings-list'),

  // Settings Modal
  modalSettings: document.getElementById('modal-settings'),
  btnOpenSettings: document.getElementById('btn-open-settings'),
  btnCloseSettings: document.getElementById('btn-close-settings'),
  btnCancelSettings: document.getElementById('btn-cancel-settings'),
  btnSaveSettings: document.getElementById('btn-save-settings'),
  inputGroqKey: document.getElementById('input-groq-key'),
  inputOpenaiKey: document.getElementById('input-openai-key'),
};

// ── SSE Connection Handler ──────────────────────────────────────────────────

function connectSSE() {
  if (state.eventSource) {
    state.eventSource.close();
  }

  const sse = new EventSource('/api/scan/events');
  state.eventSource = sse;

  sse.onopen = () => {
    console.log('[SSE] Stream connected to Redfox Engine');
  };

  sse.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      handleServerEvent(payload);
    } catch (err) {
      console.error('[SSE] Failed to parse event payload:', err);
    }
  };

  sse.onerror = (err) => {
    console.warn('[SSE] EventSource disconnected, retrying in 2s...', err);
    sse.close();
    setTimeout(connectSSE, 2000);
  };
}

// ── Dispatch Events to Cockpit Components ───────────────────────────────────

function handleServerEvent(event) {
  const { type, data } = event;

  switch (type) {
    case 'connected':
      break;

    case 'session_start':
      onSessionStart(data);
      break;

    case 'node_transition':
      onNodeTransition(data);
      break;

    case 'plan_decided':
      onPlanDecided(data);
      break;

    case 'scope_checked':
      onScopeChecked(data);
      break;

    case 'tool_executed':
      onToolExecuted(data);
      break;

    case 'reflector_result':
      onReflectorResult(data);
      break;

    case 'verification_start':
      onVerificationStart(data);
      break;

    case 'verification_result':
      onVerificationResult(data);
      break;

    case 'state_update':
      onStateUpdate(data);
      break;

    case 'session_complete':
      onSessionComplete(data);
      break;

    case 'log':
      appendLog(data.level, data.message);
      break;

    case 'error':
      appendLog('error', `Server Exception: ${data.message}`);
      setSystemStatus('idle');
      break;
  }
}

// ── Event Handlers ──────────────────────────────────────────────────────────

function onSessionStart(data) {
  state.isRunning = true;
  state.target = data.target;
  state.currentStep = 1;
  state.maxSteps = data.max_steps;
  state.confirmedFindings = [];
  state.rejectedFindings = [];
  state.toolCount = 0;

  setSystemStatus('scanning');
  updateEngineBadge(data.engine);
  updateStepProgress(1, data.max_steps);
  resetPipelineNodes();

  dom.btnStartScan.classList.add('hidden');
  dom.btnStopScan.classList.remove('hidden');

  dom.scopeAllowedList.textContent = (data.scope || []).join(', ');
  dom.reportTargetMeta.textContent = `Target: ${data.target}`;
  dom.reportStatusMeta.textContent = `Status: In-Progress (${data.engine.toUpperCase()})`;

  renderFindings();
  audio.playSuccess();
}

function onNodeTransition(data) {
  const { node, step, phase, icon } = data;
  setActiveNode(node);
  audio.playBlip(520, 0.04);
}

function onPlanDecided(data) {
  dom.telemetryObjective.textContent = data.objective || 'N/A';
  dom.telemetryTool.textContent = data.tool_name || 'N/A';
  dom.telemetryReasoning.textContent = data.reasoning || 'Evaluating next action in accordance with OWASP web reconnaissance methodology.';
}

function onScopeChecked(data) {
  const { decision, reason, latency_ms } = data;
  dom.scopeLatency.textContent = `${latency_ms} ms`;
  dom.scopeVerdictText.textContent = `DECISION: ${decision}`;
  dom.scopeReasonText.textContent = reason;

  if (decision === 'ALLOW') {
    dom.scopeVerdictIcon.textContent = '✅';
    dom.scopeDecisionBox.style.borderColor = 'var(--green-border)';
    dom.scopeDecisionBox.style.background = 'var(--green-light)';
    dom.scopeVerdictText.style.color = 'var(--green)';
  } else if (decision === 'DENY') {
    dom.scopeVerdictIcon.textContent = '❌';
    dom.scopeDecisionBox.style.borderColor = 'var(--red-border)';
    dom.scopeDecisionBox.style.background = 'var(--red-light)';
    dom.scopeVerdictText.style.color = 'var(--red-primary)';
    audio.playAlert();
  } else {
    dom.scopeVerdictIcon.textContent = '⚠️';
    dom.scopeDecisionBox.style.borderColor = 'var(--amber-border)';
    dom.scopeDecisionBox.style.background = 'var(--amber-light)';
    dom.scopeVerdictText.style.color = 'var(--amber)';
  }
}

function onToolExecuted(data) {
  state.toolCount++;
  dom.statTools.textContent = state.toolCount;
  dom.toolLatencyBadge.textContent = `${data.elapsed_ms} ms`;
  dom.terminalToolName.textContent = `ephemeral_container@redfox-agent: run_tool("${data.tool_name}")`;

  // Syntax-highlighted output preview
  dom.toolOutputJson.textContent = JSON.stringify(data.output, null, 2);
  audio.playBlip(880, 0.05);
}

function onReflectorResult(data) {
  // If suspected findings are discovered
  if (data.new_suspected_count > 0) {
    audio.playAlert();
  }
}

function onVerificationStart(data) {
  dom.verifierEmpty.classList.add('hidden');
  dom.verifierActive.classList.remove('hidden');

  dom.vCurrentSev.textContent = data.severity;
  dom.vCurrentSev.className = `v-claim-badge sev-badge ${data.severity}`;
  dom.vCurrentTitle.textContent = data.title;
  dom.vProgressStatus.textContent = `Performing independent reproduction (${data.index}/${data.total})...`;
  dom.vCurrentReasoning.textContent = 'Contacting target directly with isolated probe to prevent hallucination...';
  dom.vCurrentHash.textContent = 'Computing SHA-256 hash...';
}

function onVerificationResult(data) {
  const { finding, verdict, reasoning, evidence_hash } = data;

  dom.vProgressStatus.textContent = `Verification Complete: ${verdict}`;
  dom.vCurrentReasoning.textContent = reasoning;
  dom.vCurrentHash.textContent = `sha256:${(evidence_hash || '').substring(0, 32)}...`;

  if (verdict === 'CONFIRMED') {
    state.confirmedFindings.push(finding);
    dom.statConfirmed.textContent = state.confirmedFindings.length;
    dom.tabFindingsCounter.textContent = state.confirmedFindings.length;
    dom.statHashes.textContent = state.confirmedFindings.length;
    audio.playSuccess();
  } else if (verdict === 'REJECTED') {
    state.rejectedFindings.push(finding);
    dom.statRejected.textContent = state.rejectedFindings.length;
    audio.playAlert();
  }

  renderFindings();
}

function onStateUpdate(data) {
  state.currentStep = data.step_number;
  updateStepProgress(data.step_number, state.maxSteps);
}

function onSessionComplete(data) {
  state.isRunning = false;
  setSystemStatus('completed');
  clearActiveNodes();

  dom.btnStartScan.classList.remove('hidden');
  dom.btnStopScan.classList.add('hidden');
  dom.reportStatusMeta.textContent = `Status: Completed (${data.stop_reason || 'Finished'})`;

  appendLog('success', `Assessment finished: ${data.steps_executed} steps executed. Findings verified.`);
  renderFindings();
  audio.playSuccess();
}

// ── UI Updates ──────────────────────────────────────────────────────────────

function setSystemStatus(status) {
  dom.statusPill.className = `status-pill ${status}`;
  if (status === 'scanning') {
    dom.statusText.textContent = 'SCAN IN PROGRESS';
  } else if (status === 'completed') {
    dom.statusText.textContent = 'SCAN COMPLETE';
  } else {
    dom.statusText.textContent = 'SYSTEM READY';
  }
}

function updateEngineBadge(engine) {
  dom.engineBadge.className = `engine-badge ${engine}`;
  if (engine === 'groq') {
    dom.engineBadge.textContent = 'Groq (LLaMA-3.3 70B)';
  } else if (engine === 'openai') {
    dom.engineBadge.textContent = 'OpenAI (GPT-4o-mini)';
  } else {
    dom.engineBadge.textContent = 'Methodology Mode';
  }
}

function updateStepProgress(curr, max) {
  dom.liveStepLabel.textContent = `Step ${curr} / ${max}`;
  const pct = Math.min(100, Math.round((curr / max) * 100));
  dom.liveStepBar.style.width = `${pct}%`;
}

function setActiveNode(nodeId) {
  // Reset all
  Object.keys(dom.pipelineNodes).forEach((key) => {
    const el = dom.pipelineNodes[key];
    if (el) {
      if (key === nodeId) {
        el.classList.add('active');
        el.classList.remove('completed');
        const badge = el.querySelector('.node-status-badge');
        if (badge) badge.textContent = 'ACTIVE';
      } else if (el.classList.contains('active')) {
        el.classList.remove('active');
        el.classList.add('completed');
        const badge = el.querySelector('.node-status-badge');
        if (badge) badge.textContent = 'PASSED';
      }
    }
  });
}

function clearActiveNodes() {
  Object.values(dom.pipelineNodes).forEach((el) => {
    if (el) {
      el.classList.remove('active');
      const badge = el.querySelector('.node-status-badge');
      if (badge) badge.textContent = 'COMPLETE';
    }
  });
}

function resetPipelineNodes() {
  Object.values(dom.pipelineNodes).forEach((el) => {
    if (el) {
      el.classList.remove('active', 'completed');
      const badge = el.querySelector('.node-status-badge');
      if (badge) badge.textContent = 'STANDBY';
    }
  });
}

function appendLog(level, message) {
  const entry = document.createElement('div');
  entry.className = `log-entry ${level}`;

  const now = new Date();
  const timeStr = now.toTimeString().split(' ')[0];

  entry.innerHTML = `
    <span class="log-time">${timeStr}</span>
    <span class="log-badge ${level}">${level}</span>
    <span class="log-msg">${escapeHtml(message)}</span>
  `;

  dom.liveLogStream.appendChild(entry);
  dom.liveLogStream.scrollTop = dom.liveLogStream.scrollHeight;
}

// ── Render Findings ─────────────────────────────────────────────────────────

function renderFindings() {
  const confirmed = state.confirmedFindings;
  const rejected = state.rejectedFindings;

  if (confirmed.length === 0) {
    dom.noFindingsSplash.classList.remove('hidden');
    dom.findingsCardsList.innerHTML = '';
    dom.findingsCardsList.appendChild(dom.noFindingsSplash);
  } else {
    dom.noFindingsSplash.classList.add('hidden');
    dom.findingsCardsList.innerHTML = '';

    confirmed.forEach((f, idx) => {
      const card = document.createElement('div');
      card.className = 'finding-card';
      const sev = f.severity || 'INFO';
      const cwe = f.cwe_id || 'N/A';
      const hash = f.evidence_hash ? `sha256:${f.evidence_hash.substring(0, 16)}...` : 'N/A';

      card.innerHTML = `
        <div class="finding-card-header" onclick="this.nextElementSibling.classList.toggle('hidden')">
          <div class="fc-left">
            <span class="sev-badge ${sev}">${sev}</span>
            <span class="cwe-badge">${cwe}</span>
            <span class="fc-title">${escapeHtml(f.title)}</span>
          </div>
          <div class="fc-right">
            <span class="verdict-tag">✅ ${f.status || 'CONFIRMED'}</span>
            <span class="mono" style="font-size:0.75rem; color:var(--text-dim);">${Math.round((f.confidence || 1) * 100)}% Conf</span>
          </div>
        </div>
        <div class="finding-card-details">
          <div>
            <div class="f-section-title">Vulnerability Description</div>
            <div class="f-desc-text">${escapeHtml(f.description || 'No description provided.')}</div>
          </div>
          <div>
            <div class="f-section-title">Independent Verifier Proof &amp; Chain of Custody</div>
            <div class="f-proof-box">
              <strong>Reproduction Test:</strong> ${escapeHtml(f.reasoning || 'Independently confirmed.')}
              <div style="margin-top:6px; font-family:var(--font-mono); font-size:0.75rem; color:var(--text-muted);">
                Evidence Fingerprint: <code style="background:#f1f5f9; padding:2px 6px; border-radius:4px; border:1px solid #e2e8f0; color:#0f172a;">${hash}</code>
              </div>
            </div>
          </div>
          <div>
            <div class="f-section-title">Remediation Recommendation</div>
            <div class="f-remediation-box">${escapeHtml(f.remediation || 'Harden server response headers.')}</div>
          </div>
        </div>
      `;
      dom.findingsCardsList.appendChild(card);
    });
  }

  // Render Rejected (False Positives)
  if (rejected.length > 0) {
    dom.rejectedContainer.classList.remove('hidden');
    dom.rejectedList.innerHTML = '';
    rejected.forEach((r) => {
      const item = document.createElement('div');
      item.className = 'rejected-item';
      item.innerHTML = `
        <span class="r-icon">❌</span>
        <span class="r-title">${escapeHtml(r.title)}</span>
        <span class="r-reason">— ${escapeHtml(r.reasoning || 'Filtered as false positive.')}</span>
      `;
      dom.rejectedList.appendChild(item);
    });
  } else {
    dom.rejectedContainer.classList.add('hidden');
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ── API Actions ─────────────────────────────────────────────────────────────

async function startScan() {
  const target = dom.inputTarget.value.trim() || 'http://httpbin.org';
  const steps = parseInt(dom.inputMaxSteps.value, 10) || 6;
  const engine = dom.selectEngine.value;

  const payload = {
    target: target,
    max_steps: steps,
    engine: engine,
    groq_api_key: state.groqKey || null,
    openai_api_key: state.openaiKey || null,
  };

  try {
    dom.btnStartScan.disabled = true;
    const resp = await fetch('/api/scan/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      const errData = await resp.json();
      throw new Error(errData.detail || 'Failed to start scan.');
    }

    const data = await resp.json();
    appendLog('info', `Scan initiated against ${data.target} using ${data.engine.toUpperCase()}.`);
  } catch (err) {
    alert(`Could not start scan: ${err.message}`);
    appendLog('error', `Start scan error: ${err.message}`);
  } finally {
    dom.btnStartScan.disabled = false;
  }
}

async function stopScan() {
  try {
    const resp = await fetch('/api/scan/stop', { method: 'POST' });
    if (resp.ok) {
      appendLog('warn', 'Abort command sent to agent engine.');
    }
  } catch (err) {
    console.error('Stop error:', err);
  }
}

async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    if (res.ok) {
      const data = await res.json();
      updateEngineBadge(data.engine);
      if (data.is_running) {
        setSystemStatus('scanning');
        dom.btnStartScan.classList.add('hidden');
        dom.btnStopScan.classList.remove('hidden');
      }
    }
  } catch (e) {
    // Server initializing
  }
}

// ── Event Listeners ─────────────────────────────────────────────────────────

function setupEventListeners() {
  // Tabs
  dom.tabBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      dom.tabBtns.forEach((b) => b.classList.remove('active'));
      dom.tabContents.forEach((c) => c.classList.remove('active'));

      btn.classList.add('active');
      const targetId = btn.getAttribute('data-tab');
      const content = document.getElementById(targetId);
      if (content) content.classList.add('active');
      audio.playBlip(700, 0.03);
    });
  });

  // Presets
  dom.presetHttpbin.addEventListener('click', () => {
    dom.inputTarget.value = 'http://httpbin.org';
    dom.presetHttpbin.classList.add('active');
    dom.presetVulnweb.classList.remove('active');
    audio.playBlip(600, 0.03);
  });

  dom.presetVulnweb.addEventListener('click', () => {
    dom.inputTarget.value = 'http://testphp.vulnweb.com';
    dom.presetVulnweb.classList.add('active');
    dom.presetHttpbin.classList.remove('active');
    audio.playBlip(600, 0.03);
  });

  // Max Steps Slider
  dom.inputMaxSteps.addEventListener('input', (e) => {
    dom.stepsCounterVal.textContent = e.target.value;
  });

  // Control Actions
  dom.btnStartScan.addEventListener('click', startScan);
  dom.btnStopScan.addEventListener('click', stopScan);
  dom.btnResetView.addEventListener('click', () => {
    state.confirmedFindings = [];
    state.rejectedFindings = [];
    state.toolCount = 0;
    dom.statConfirmed.textContent = '0';
    dom.statRejected.textContent = '0';
    dom.statTools.textContent = '0';
    dom.statHashes.textContent = '0';
    dom.tabFindingsCounter.textContent = '0';
    resetPipelineNodes();
    updateStepProgress(0, state.maxSteps);
    renderFindings();
    setSystemStatus('idle');
    appendLog('info', 'Cockpit display reset to initial state.');
  });

  // Audio Toggle
  dom.btnAudio.addEventListener('click', () => {
    state.audioEnabled = !state.audioEnabled;
    dom.audioIcon.textContent = state.audioEnabled ? '🔊' : '🔇';
    if (state.audioEnabled) audio.playSuccess();
  });

  // Clear Logs
  dom.btnClearLogs.addEventListener('click', () => {
    dom.liveLogStream.innerHTML = '';
  });

  // Reports
  dom.btnDownloadMd.addEventListener('click', () => {
    window.open('/api/scan/report/markdown', '_blank');
  });

  dom.btnDownloadJson.addEventListener('click', () => {
    window.open('/api/scan/report/json', '_blank');
  });

  // Settings Modal
  dom.btnOpenSettings.addEventListener('click', () => {
    dom.inputGroqKey.value = state.groqKey;
    dom.inputOpenaiKey.value = state.openaiKey;
    dom.modalSettings.classList.remove('hidden');
  });

  dom.btnCloseSettings.addEventListener('click', () => {
    dom.modalSettings.classList.add('hidden');
  });

  dom.btnCancelSettings.addEventListener('click', () => {
    dom.modalSettings.classList.add('hidden');
  });

  dom.btnSaveSettings.addEventListener('click', () => {
    const groqVal = dom.inputGroqKey.value.trim();
    const openaiVal = dom.inputOpenaiKey.value.trim();

    state.groqKey = groqVal;
    state.openaiKey = openaiVal;

    if (groqVal) localStorage.setItem('redfox_groq_key', groqVal);
    else localStorage.removeItem('redfox_groq_key');

    if (openaiVal) localStorage.setItem('redfox_openai_key', openaiVal);
    else localStorage.removeItem('redfox_openai_key');

    dom.modalSettings.classList.add('hidden');
    appendLog('success', 'API credentials updated.');
    audio.playSuccess();
  });
}

// ── Initialization ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  connectSSE();
  fetchStatus();
  console.log('🦊 Redfox AI Cockpit loaded successfully.');
});
