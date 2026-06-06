const AppState = { threadId: null, session: null, currentAgent: '', progress: 0 };

function renderPipeline(pipelineState, status) {
    const agents = ['chapter_parser', 'character_agent', 'scene_agent', 'script_agent', 'validator'];
    const currentAgent = pipelineState?.current_agent || '';
    const progress = pipelineState?.progress || 0;

    const fill = document.getElementById('progress-fill');
    if (fill) fill.style.width = (progress * 100) + '%';
    const ptext = document.getElementById('progress-text');
    if (ptext) ptext.textContent = Math.round(progress * 100) + '%';

    const badge = document.getElementById('stage-badge');
    const labelMap = { parsing:'章节解析中', char_extracting:'角色识别中', scene_segmenting:'场景切分中',
        script_generating:'剧本生成中', validating:'校验中', completed:'已完成', error:'错误' };
    if (badge) badge.textContent = labelMap[status] || (status || '等待中');

    agents.forEach((agent, i) => {
        const icon = document.getElementById('icon-' + agent);
        if (!icon) return;
        const idx = agents.indexOf(currentAgent);
        if (i < idx || status === 'completed') { icon.textContent = '✓'; icon.style.color = '#3fb950'; }
        else if (i === idx && status !== 'completed') { icon.textContent = '●'; icon.style.color = '#1f6feb'; }
        else { icon.textContent = '○'; icon.style.color = '#484f58'; }
        if (status && status.includes('hitl') && agent === currentAgent) {
            icon.textContent = '⏸'; icon.style.color = '#d2991d'; }
    });
    AppState.currentAgent = currentAgent;
    AppState.progress = progress;
}
