// HITL 编辑器组件

function renderHITL(hitlMsg, artifacts) {
    const editor = document.getElementById('hitl-editor');
    if (!editor) return;
    editor.style.display = 'block';

    const agent = hitlMsg.agent || hitlMsg.node || '';
    const data = hitlMsg.data || {};
    const reason = hitlMsg.reason || 'low_confidence';
    const confidence = hitlMsg.confidence || 0;

    let html = '<div class="hitl-card"><h3>需要你的审阅</h3>';
    html += '<p class="hitl-reason">原因: ' + reason + ' (置信度: ' + Math.round(confidence * 100) + '%)</p>';

    if (agent === 'character_agent' && data.characters) {
        html += '<h4>角色列表</h4>';
        data.characters.forEach((c, i) => {
            html += '<div class="edit-card">';
            html += '<label>姓名 <input value="' + esc(c.name || '') + '" data-char="' + i + '" data-field="name"></label>';
            html += '<label>别称 <input value="' + esc((c.aliases || []).join(', ')) + '" data-char="' + i + '" data-field="aliases"></label>';
            html += '<label>外貌 <input value="' + esc((c.description || {}).physical || '') + '" data-char="' + i + '" data-field="physical"></label>';
            html += '<label>性格 <input value="' + esc((c.description || {}).personality || '') + '" data-char="' + i + '" data-field="personality"></label>';
            html += '</div>';
        });
    } else if (agent === 'scene_agent' && data.scenes) {
        html += '<h4>场景列表</h4>';
        data.scenes.forEach((s, i) => {
            html += '<div class="edit-card">';
            html += '<label>地点 <input value="' + esc((s.heading || {}).location || '') + '" data-scene="' + i + '" data-field="location"></label>';
            html += '<label>时段 <input value="' + esc((s.heading || {}).time_of_day || '') + '" data-scene="' + i + '" data-field="time"></label>';
            html += '<label>氛围 <input value="' + esc(s.mood || '') + '" data-scene="' + i + '" data-field="mood"></label>';
            html += '</div>';
        });
    }

    html += '<div class="hitl-actions">';
    html += '<button class="btn-primary" onclick="submitHITL(\'' + agent + '\')">确认并继续</button>';
    html += '<button class="btn-secondary" onclick="skipHITL()">跳过</button>';
    html += '</div></div>';
    editor.innerHTML = html;
}

function esc(str) {
    return String(str).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

async function submitHITL(agent) {
    const edits = {};
    // 收集编辑
    document.querySelectorAll('[data-char]').forEach(el => {
        const i = el.dataset.char;
        if (!edits[i]) edits[i] = {};
        edits[i][el.dataset.field] = el.value;
    });
    document.querySelectorAll('[data-scene]').forEach(el => {
        const i = el.dataset.scene;
        if (!edits[i]) edits[i] = {};
        edits[i][el.dataset.field] = el.value;
    });

    try {
        await fetch('/api/sessions/' + AppState.threadId + '/hitl/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ edits })
        });
        document.getElementById('hitl-editor').style.display = 'none';
        await fetch('/api/sessions/' + AppState.threadId + '/start', { method: 'POST' });
    } catch (e) {
        console.error('HITL submit error:', e);
    }
}

async function skipHITL() {
    await fetch('/api/sessions/' + AppState.threadId + '/start', { method: 'POST' });
    document.getElementById('hitl-editor').style.display = 'none';
}
