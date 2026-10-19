// COMET chat UI. Plain vanilla JS: POSTs the conversation to /api/agent and
// renders the reply plus any tool calls (name, args, raw output).
const chat = document.getElementById('chat');
const form = document.getElementById('composer');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');

const history = []; // [{role: 'user'|'assistant', content: string}]

function addMsg(role, label) {
  const wrap = document.createElement('div');
  wrap.className = `msg ${role}`;
  const lbl = document.createElement('div');
  lbl.className = 'msg-label';
  lbl.textContent = label;
  const body = document.createElement('div');
  body.className = 'msg-body';
  wrap.append(lbl, body);
  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;
  return body;
}

function addToolCalls(toolCalls, parent) {
  for (const call of toolCalls || []) {
    const details = document.createElement('details');
    details.className = 'tool-call';
    const summary = document.createElement('summary');
    const name = document.createElement('span');
    name.className = 'tool-name';
    name.textContent = call.name;
    const args = document.createElement('span');
    args.className = 'tool-args';
    args.textContent = JSON.stringify(call.args || {});
    summary.append(name, args);
    const pre = document.createElement('pre');
    pre.textContent = call.output ?? '';
    details.append(summary, pre);
    parent.appendChild(details);
  }
}

async function send(text) {
  history.push({ role: 'user', content: text });
  const userBody = addMsg('user', 'You');
  userBody.textContent = text;

  const assistantBody = addMsg('assistant', 'COMET');
  assistantBody.classList.add('typing');
  assistantBody.textContent = '';
  sendBtn.disabled = true;

  try {
    const resp = await fetch('/api/agent', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: history }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    const data = await resp.json();
    assistantBody.classList.remove('typing');
    assistantBody.textContent = data.reply || '(no reply)';
    history.push({ role: 'assistant', content: data.reply || '' });
    if (data.tool_calls && data.tool_calls.length) {
      const wrap = document.createElement('div');
      wrap.className = 'tool-calls';
      assistantBody.appendChild(wrap);
      addToolCalls(data.tool_calls, wrap);
    }
  } catch (err) {
    assistantBody.classList.remove('typing');
    assistantBody.textContent = `Something went wrong: ${err.message}`;
  } finally {
    sendBtn.disabled = false;
    input.focus();
    chat.scrollTop = chat.scrollHeight;
  }
}

form.addEventListener('submit', (ev) => {
  ev.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  send(text);
});
