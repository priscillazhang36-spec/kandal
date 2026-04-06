LANDING_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>kandal</title>
  <meta name="description" content="An AI matchmaker that gets to know you through text.">
  <style>
    *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0f0c15; color: #f5ead6;
      -webkit-font-smoothing: antialiased;
      overflow-x: hidden;
    }

    .bg {
      position: fixed; top: 0; left: 0; width: 100%; height: 100%;
      z-index: 0; overflow: hidden;
    }

    .orb { position: absolute; border-radius: 50%; will-change: transform; }

    .orb-1 {
      width: 400px; height: 400px;
      background: radial-gradient(circle, #3a6e9e 0%, transparent 70%);
      opacity: 0.3; top: -10%; right: -5%;
      animation: float1 12s ease-in-out infinite;
    }
    .orb-2 {
      width: 400px; height: 400px;
      background: radial-gradient(circle, #f0923a 0%, transparent 70%);
      opacity: 0.35; bottom: -10%; left: -5%;
      animation: float2 14s ease-in-out infinite;
    }
    .orb-3 {
      width: 250px; height: 250px;
      background: radial-gradient(circle, #5b8ebf 0%, transparent 70%);
      opacity: 0.2; top: 40%; left: 30%;
      animation: float3 18s ease-in-out infinite;
    }
    .orb-4 {
      width: 200px; height: 200px;
      background: radial-gradient(circle, #f5a640 0%, transparent 70%);
      opacity: 0.2; top: 10%; left: 50%;
      animation: float4 20s ease-in-out infinite;
    }

    @keyframes float1 { 0%,100%{transform:translate(0,0)} 50%{transform:translate(-50px,40px)} }
    @keyframes float2 { 0%{transform:translate(0,0)} 25%{transform:translate(200px,-150px)} 50%{transform:translate(350px,-250px)} 75%{transform:translate(150px,-100px)} 100%{transform:translate(0,0)} }
    @keyframes float3 { 0%,100%{transform:translate(0,0)} 33%{transform:translate(30px,-30px)} 66%{transform:translate(-20px,20px)} }
    @keyframes float4 { 0%{transform:translate(0,0)} 25%{transform:translate(-250px,150px)} 50%{transform:translate(-100px,300px)} 75%{transform:translate(100px,100px)} 100%{transform:translate(0,0)} }

    /* --- Landing view --- */
    .page {
      position: relative; z-index: 1;
      min-height: 100vh; min-height: 100dvh;
      display: flex; flex-direction: column;
    }

    nav {
      display: flex; align-items: center; justify-content: space-between;
      padding: 1.5rem 2.5rem;
    }

    .logo {
      font-size: 1.15rem; font-weight: 700; letter-spacing: -0.03em;
      color: #f5ead6; text-decoration: none;
    }

    main {
      flex: 1; display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      padding: 2rem 2rem 4rem; text-align: center;
    }

    .tagline {
      font-size: clamp(1.6rem, 4vw, 2.8rem);
      font-weight: 600; letter-spacing: -0.03em;
      line-height: 1.3; max-width: 520px; margin-bottom: 1rem;
    }

    .sub {
      font-size: clamp(0.9rem, 1.8vw, 1.05rem);
      color: rgba(245,234,214,0.6);
      line-height: 1.7; max-width: 400px; margin-bottom: 2.5rem;
    }

    .signup { width: 100%; max-width: 360px; }

    .phone-form { display: flex; flex-direction: column; gap: 0.75rem; margin-bottom: 0.6rem; }
    .phone-input-wrap { position: relative; }
    .phone-prefix {
      position: absolute; left: 1rem; top: 50%; transform: translateY(-50%);
      font-size: 1rem; font-weight: 500;
      color: rgba(245,234,214,0.5); pointer-events: none;
    }
    .phone-input {
      width: 100%; font-family: inherit; font-size: 1rem;
      color: #f5ead6; background: rgba(245,234,214,0.08);
      border: 1px solid rgba(245,234,214,0.15);
      border-radius: 10px; padding: 0.85rem 1rem 0.85rem 2.8rem;
      outline: none; transition: border-color 0.15s, background 0.15s;
      -webkit-appearance: none;
    }
    .phone-input:focus {
      border-color: rgba(245,234,214,0.35);
      background: rgba(245,234,214,0.12);
    }
    .phone-input::placeholder { color: rgba(245,234,214,0.3); }

    .form-error {
      margin-top: 0.25rem; font-size: 0.8rem;
      color: rgba(255,120,120,0.9); display: none;
    }
    .form-error.visible { display: block; }

    .start-btn {
      font-family: inherit; font-size: 1rem; font-weight: 600;
      color: #0f0c15; background: #f5ead6; border: none;
      padding: 0.85rem 2rem; border-radius: 10px; width: 100%;
      cursor: pointer; transition: opacity 0.2s;
      -webkit-tap-highlight-color: transparent;
    }
    .start-btn:hover { opacity: 0.85; }
    .start-btn:active { opacity: 0.7; }
    .start-btn:disabled { opacity: 0.4; cursor: not-allowed; }

    .form-hint {
      font-size: 0.7rem; color: rgba(245,234,214,0.3); margin-top: 0.6rem;
    }

    footer {
      position: relative; z-index: 1;
      padding: 1.5rem 2.5rem; display: flex; justify-content: center;
    }
    footer p { font-size: 0.7rem; color: rgba(245,234,214,0.2); }

    /* --- Chat view --- */
    .chat-view {
      display: none;
      position: fixed; top: 0; left: 0; width: 100%; height: 100%;
      height: 100dvh;
      z-index: 10; flex-direction: column;
      background: #0f0c15;
    }
    .chat-view.active { display: flex; }

    .chat-header {
      display: flex; align-items: center; gap: 0.75rem;
      padding: 1rem 1.5rem;
      border-bottom: 1px solid rgba(245,234,214,0.08);
      flex-shrink: 0;
    }
    .chat-header .logo { font-size: 1rem; }
    .chat-status {
      font-size: 0.75rem; color: rgba(245,234,214,0.4);
    }

    .chat-messages {
      flex: 1; overflow-y: auto; padding: 1rem 1rem;
      display: flex; flex-direction: column; gap: 0.75rem;
      -webkit-overflow-scrolling: touch;
    }

    .msg {
      max-width: 85%; padding: 0.75rem 1rem;
      border-radius: 16px; font-size: 0.9rem; line-height: 1.5;
      word-wrap: break-word; white-space: pre-wrap;
    }
    .msg.bot {
      align-self: flex-start;
      background: rgba(245,234,214,0.08);
      border-bottom-left-radius: 4px;
      color: #f5ead6;
    }
    .msg.user {
      align-self: flex-end;
      background: rgba(245,234,214,0.15);
      border-bottom-right-radius: 4px;
      color: #f5ead6;
    }
    .msg.typing {
      align-self: flex-start;
      background: rgba(245,234,214,0.05);
      border-bottom-left-radius: 4px;
      color: rgba(245,234,214,0.4);
      font-style: italic;
    }

    .chat-input-area {
      display: flex; gap: 0.5rem;
      padding: 0.75rem 1rem;
      padding-bottom: max(0.75rem, env(safe-area-inset-bottom));
      border-top: 1px solid rgba(245,234,214,0.08);
      flex-shrink: 0;
      background: #0f0c15;
    }

    .chat-input {
      flex: 1; font-family: inherit; font-size: 1rem;
      color: #f5ead6; background: rgba(245,234,214,0.08);
      border: 1px solid rgba(245,234,214,0.12);
      border-radius: 20px; padding: 0.65rem 1rem;
      outline: none; resize: none;
      min-height: 40px; max-height: 120px;
      -webkit-appearance: none;
    }
    .chat-input:focus {
      border-color: rgba(245,234,214,0.25);
      background: rgba(245,234,214,0.1);
    }
    .chat-input::placeholder { color: rgba(245,234,214,0.25); }

    .send-btn {
      font-family: inherit; font-size: 0.85rem; font-weight: 600;
      color: #0f0c15; background: #f5ead6; border: none;
      padding: 0 1.25rem; border-radius: 20px;
      cursor: pointer; transition: opacity 0.15s;
      -webkit-tap-highlight-color: transparent;
      align-self: flex-end; height: 40px;
    }
    .send-btn:hover { opacity: 0.85; }
    .send-btn:active { opacity: 0.7; }
    .send-btn:disabled { opacity: 0.3; cursor: not-allowed; }

    /* --- Responsive --- */
    @media (max-width: 640px) {
      nav { padding: 1rem 1.5rem; }
      main { padding: 1.5rem 1.5rem 2.5rem; }
      .tagline { max-width: 90%; }
      .sub { max-width: 90%; margin-bottom: 2rem; }
      .signup { max-width: 90%; }
      footer { padding: 1.25rem 1.5rem; }
      .orb-1, .orb-2 { width: 250px; height: 250px; }
      .orb-3 { width: 150px; height: 150px; }
      .orb-4 { width: 120px; height: 120px; }
      .chat-messages { padding: 0.75rem; }
      .msg { max-width: 90%; font-size: 0.88rem; }
    }

    @media (max-width: 380px) {
      .tagline { font-size: 1.4rem; }
      .sub { font-size: 0.85rem; }
    }
  </style>
</head>
<body>

  <div class="bg">
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>
    <div class="orb orb-3"></div>
    <div class="orb orb-4"></div>
  </div>

  <!-- Landing -->
  <div class="page" id="landing">
    <nav>
      <a href="/" class="logo">kandal</a>
    </nav>
    <main>
      <h1 class="tagline">Meet through the you that knows you best</h1>
      <p class="sub">Kandal builds your dating alter ego -- a digital self that knows how you love, what you need, and find the match that you would really fall for.</p>
      <div class="signup" id="signup">
        <form class="phone-form" id="phone-form">
          <div class="phone-input-wrap">
            <span class="phone-prefix">+1</span>
            <input type="tel" inputmode="tel" class="phone-input" id="phone"
              placeholder="Your number" autocomplete="tel-national" required>
          </div>
          <button type="submit" class="start-btn" id="start-btn">Let's go</button>
        </form>
        <p class="form-hint">We'll use this to find you later. Chat happens right here.</p>
        <div class="form-error" id="form-error"></div>
      </div>
    </main>
    <footer><p>kandal &copy; 2026</p></footer>
  </div>

  <!-- Chat -->
  <div class="chat-view" id="chat-view">
    <div class="chat-header">
      <a href="/" class="logo">kandal</a>
      <span class="chat-status">getting to know you...</span>
    </div>
    <div class="chat-messages" id="chat-messages"></div>
    <div class="chat-input-area">
      <input type="text" class="chat-input" id="chat-input"
        placeholder="Type your reply..." autocomplete="off">
      <button class="send-btn" id="send-btn" disabled>Send</button>
    </div>
  </div>

  <script>
    const phoneForm = document.getElementById('phone-form');
    const phoneInput = document.getElementById('phone');
    const startBtn = document.getElementById('start-btn');
    const formError = document.getElementById('form-error');
    const landingEl = document.getElementById('landing');
    const chatView = document.getElementById('chat-view');
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');

    let sessionId = null;
    let waiting = false;

    function addMessage(text, type) {
      const div = document.createElement('div');
      div.className = 'msg ' + type;
      div.textContent = text;
      chatMessages.appendChild(div);
      chatMessages.scrollTop = chatMessages.scrollHeight;
      return div;
    }

    function showTyping() {
      return addMessage('...', 'typing');
    }

    function removeTyping(el) {
      if (el && el.parentNode) el.parentNode.removeChild(el);
    }

    function setWaiting(val) {
      waiting = val;
      sendBtn.disabled = val || !chatInput.value.trim();
      if (val) chatInput.setAttribute('readonly', '');
      else chatInput.removeAttribute('readonly');
    }

    // Start conversation
    phoneForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      formError.className = 'form-error';

      const digits = phoneInput.value.replace(/\D/g, '');
      if (digits.length < 10 || digits.length > 11) {
        formError.textContent = 'Please enter a valid 10-digit phone number.';
        formError.className = 'form-error visible';
        return;
      }

      const phone = '+1' + digits.slice(-10);
      startBtn.disabled = true;
      startBtn.textContent = 'Starting...';

      try {
        const res = await fetch('/chat/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone }),
        });

        if (!res.ok) throw new Error('Failed to start');

        const data = await res.json();
        sessionId = data.session_id;

        // Save to localStorage for session resume
        localStorage.setItem('kandal_session', JSON.stringify({
          session_id: sessionId, phone
        }));

        // Switch to chat view
        landingEl.style.display = 'none';
        chatView.classList.add('active');
        addMessage(data.message, 'bot');
        chatInput.focus();
      } catch (e) {
        startBtn.disabled = false;
        startBtn.textContent = "Let's go";
        formError.textContent = 'Something went wrong. Please try again.';
        formError.className = 'form-error visible';
      }
    });

    // Send message
    async function sendMessage() {
      const text = chatInput.value.trim();
      if (!text || waiting || !sessionId) return;

      addMessage(text, 'user');
      chatInput.value = '';
      sendBtn.disabled = true;
      setWaiting(true);

      const typingEl = showTyping();

      try {
        const res = await fetch('/chat/reply', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId, message: text }),
        });

        removeTyping(typingEl);

        if (!res.ok) throw new Error('Failed to send');

        const data = await res.json();
        addMessage(data.message, 'bot');

        if (data.is_complete) {
          chatInput.placeholder = 'Conversation complete!';
          chatInput.disabled = true;
          sendBtn.disabled = true;
          document.querySelector('.chat-status').textContent = 'all done!';
        }
      } catch (e) {
        removeTyping(typingEl);
        addMessage('Something went wrong. Try sending again.', 'bot');
      }

      setWaiting(false);
    }

    sendBtn.addEventListener('click', sendMessage);

    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    chatInput.addEventListener('input', () => {
      sendBtn.disabled = waiting || !chatInput.value.trim();
    });
  </script>

</body>
</html>'''
