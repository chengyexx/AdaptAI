// Streaming JSON 增量渲染器 —— 接收 token 流，逐步显示生成的剧本内容

let yamlBuffer = '';

function appendToken(chunk) {
    yamlBuffer += chunk;
    const preview = document.getElementById('yaml-preview');
    const content = document.getElementById('yaml-content');
    if (preview && content) {
        preview.style.display = 'block';
        content.textContent = yamlBuffer;
        // 自动滚动到底部
        content.scrollTop = content.scrollHeight;
    }
}

function resetStream() {
    yamlBuffer = '';
    const preview = document.getElementById('yaml-preview');
    if (preview) preview.style.display = 'none';
}
