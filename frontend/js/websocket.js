// WebSocket 客户端 — 指数退避重连 + 消息处理
let ws = null;
let seq = 0;
let reconnectTimer = null;
let reconnectDelay = 1000;

function connectWS(threadId) {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = protocol + '//' + location.host + '/ws/' + threadId;

    ws = new WebSocket(url);

    ws.onopen = () => {
        console.log('WS connected');
        reconnectDelay = 1000;
        if (seq > 0) {
            ws.send(JSON.stringify({ type: 'resync', thread_id: threadId, last_seq: seq }));
        }
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        seq = msg.seq || seq;

        switch (msg.type) {
            case 'progress':
                renderPipeline({ current_agent: msg.agent, progress: msg.percent }, null);
                break;
            case 'token_stream':
                if (typeof appendToken === 'function') appendToken(msg.chunk);
                break;
            case 'hitl_pause':
                if (typeof renderHITL === 'function') renderHITL(msg, msg.data);
                break;
            case 'stage_complete':
                renderPipeline({ current_agent: msg.agent, progress: AppState.progress + 0.2 }, null);
                break;
            case 'error':
                console.error('Pipeline error:', msg.message);
                break;
            case 'complete':
                if (msg.result?.script_yaml) {
                    const preview = document.getElementById('yaml-preview');
                    const content = document.getElementById('yaml-content');
                    if (preview && content) {
                        preview.style.display = 'block';
                        content.textContent = msg.result.script_yaml;
                    }
                }
                break;
        }
    };

    ws.onclose = () => {
        console.log('WS disconnected, reconnecting in ' + reconnectDelay + 'ms');
        reconnectTimer = setTimeout(() => connectWS(threadId), reconnectDelay);
        reconnectDelay = Math.min(reconnectDelay * 2, 30000);
    };

    ws.onerror = () => { ws.close(); };
}

function disconnectWS() {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    if (ws) ws.close();
}
