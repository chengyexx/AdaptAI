// Pipeline UI 辅助函数

function updateStageIcon(agent, state) {
    const icon = document.getElementById('icon-' + agent);
    if (!icon) return;
    switch (state) {
        case 'active': icon.textContent = '●'; icon.style.color = '#1f6feb'; break;
        case 'done': icon.textContent = '✓'; icon.style.color = '#3fb950'; break;
        case 'hitl': icon.textContent = '⏸'; icon.style.color = '#d2991d'; break;
        case 'error': icon.textContent = '✗'; icon.style.color = '#f85149'; break;
        default: icon.textContent = '○'; icon.style.color = '#484f58';
    }
}

function showPipelineError(msg) {
    const area = document.getElementById('content-area');
    if (area) {
        area.innerHTML = '<div class="error-box"><strong>错误</strong><p>' + msg + '</p></div>';
    }
}
