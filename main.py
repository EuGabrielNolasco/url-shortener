import secrets
from fastapi import FastAPI, HTTPException, Request, Form, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel, HttpUrl
from database import init_db, get_all_urls, get_stats
from shortener import create_short_url, get_original_url, get_url_info

app = FastAPI(title="URL Shortener")

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

_sessions: set[str] = set()


@app.on_event("startup")
def startup():
    init_db()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def get_admin_token(request: Request) -> str | None:
    token = request.cookies.get("admin_session")
    if token and token in _sessions:
        return token
    return None


def require_admin(request: Request) -> str:
    token = get_admin_token(request)
    if not token:
        raise HTTPException(status_code=307, headers={"Location": "/admin/login"})
    return token


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ShortenRequest(BaseModel):
    url: HttpUrl


class ShortenResponse(BaseModel):
    short_url: str
    short_code: str


# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

_BASE_STYLE = """
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #070b12; --surface: #0d1220; --surface2: #111828;
      --border: #1c2640; --accent: #00e87a; --accent-dim: rgba(0,232,122,0.08);
      --accent-glow: rgba(0,232,122,0.18); --text: #dde5f4;
      --muted: #5a6a8a; --dim: #2a3550;
    }
    html, body { height: 100%; background: var(--bg); color: var(--text);
      font-family: 'Syne', sans-serif; overflow-x: hidden; }
    body::before {
      content: ''; position: fixed; inset: 0;
      background-image: radial-gradient(circle, #1c2a45 1px, transparent 1px);
      background-size: 28px 28px; opacity: 0.45; pointer-events: none; z-index: 0;
    }
    body::after {
      content: ''; position: fixed; top: -15%; left: 50%; transform: translateX(-50%);
      width: 700px; height: 420px;
      background: radial-gradient(ellipse, rgba(0,232,122,0.055) 0%, transparent 70%);
      pointer-events: none; z-index: 0;
    }
    @keyframes fadeUp { from { opacity:0; transform:translateY(22px); } to { opacity:1; transform:translateY(0); } }
    @keyframes fadeDown { from { opacity:0; transform:translateY(-12px); } to { opacity:1; transform:translateY(0); } }
    @keyframes slideIn { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }
    @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.35; } }
"""

_FONTS = """
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;500;700;800&family=JetBrains+Mono:wght@300;400;500&display=swap" rel="stylesheet">
"""

PAGE_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NanoURL &mdash; Encurtador de Links</title>
""" + _FONTS + """
  <style>
""" + _BASE_STYLE + """
    .wrapper { position:relative; z-index:1; min-height:100vh; display:flex; flex-direction:column; }
    header { padding:28px 40px; display:flex; align-items:center; animation:fadeDown 0.6s ease both; }
    .logo { display:flex; align-items:center; gap:10px; text-decoration:none; }
    .logo-mark {
      width:34px; height:34px; background:var(--accent); border-radius:7px;
      display:flex; align-items:center; justify-content:center;
      font-family:'JetBrains Mono',monospace; font-size:13px; font-weight:500;
      color:#070b12; letter-spacing:-1px; flex-shrink:0;
    }
    .logo-text { font-size:18px; font-weight:700; color:var(--text); letter-spacing:-0.5px; }
    .logo-text span { color:var(--accent); }
    main { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; padding:48px 20px; gap:52px; }
    .hero { text-align:center; max-width:640px; animation:fadeUp 0.7s ease 0.1s both; }
    .hero-badge {
      display:inline-flex; align-items:center; gap:7px;
      background:var(--accent-dim); border:1px solid rgba(0,232,122,0.2);
      border-radius:100px; padding:5px 16px 5px 11px;
      font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--accent);
      letter-spacing:0.06em; text-transform:uppercase; margin-bottom:28px;
    }
    .hero-badge::before {
      content:''; width:6px; height:6px; background:var(--accent);
      border-radius:50%; flex-shrink:0; animation:pulse 2s ease infinite;
    }
    h1 { font-size:clamp(36px,6vw,62px); font-weight:800; line-height:1.06;
      letter-spacing:-2.5px; color:var(--text); margin-bottom:18px; }
    h1 em { font-style:normal; color:var(--accent); }
    .hero p { font-size:16px; color:var(--muted); line-height:1.65; font-weight:400; max-width:440px; margin:0 auto; }
    .card { width:100%; max-width:660px; animation:fadeUp 0.7s ease 0.22s both; }
    .input-group {
      display:flex; background:var(--surface); border:1px solid var(--border);
      border-radius:14px; padding:6px; transition:border-color 0.3s,box-shadow 0.3s;
    }
    .input-group:focus-within {
      border-color:rgba(0,232,122,0.45);
      box-shadow:0 0 0 3px var(--accent-dim),0 0 48px var(--accent-glow);
    }
    #url {
      flex:1; background:transparent; border:none; outline:none;
      padding:15px 18px; font-size:14px; font-family:'JetBrains Mono',monospace;
      color:var(--text); letter-spacing:-0.2px; min-width:0;
    }
    #url::placeholder { color:var(--muted); font-family:'Syne',sans-serif; font-size:15px; }
    button[type="submit"] {
      background:var(--accent); color:#070b12; border:none; border-radius:9px;
      padding:14px 26px; font-family:'Syne',sans-serif; font-size:14px; font-weight:700;
      cursor:pointer; transition:opacity 0.2s,transform 0.15s; white-space:nowrap; flex-shrink:0;
    }
    button[type="submit"]:hover { opacity:0.85; }
    button[type="submit"]:active { transform:scale(0.97); }
    #result { margin-top:10px; }
    .result-card {
      background:var(--surface); border:1px solid var(--border); border-radius:12px;
      padding:16px 20px; display:flex; align-items:center; gap:14px;
      animation:slideIn 0.4s cubic-bezier(0.16,1,0.3,1) both;
    }
    .result-icon {
      width:38px; height:38px; background:var(--accent-dim);
      border:1px solid rgba(0,232,122,0.2); border-radius:9px;
      display:flex; align-items:center; justify-content:center;
      flex-shrink:0; color:var(--accent); font-size:17px;
    }
    .result-label { font-size:10px; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted); margin-bottom:4px; }
    .result-url { font-family:'JetBrains Mono',monospace; font-size:14px; color:var(--accent); text-decoration:none; font-weight:500; word-break:break-all; }
    .result-url:hover { text-decoration:underline; }
    .copy-btn {
      margin-left:auto; background:var(--surface2); border:1px solid var(--border);
      border-radius:7px; padding:8px 16px; font-family:'JetBrains Mono',monospace;
      font-size:11px; color:var(--muted); cursor:pointer; transition:all 0.2s;
      flex-shrink:0; white-space:nowrap;
    }
    .copy-btn:hover, .copy-btn.copied { border-color:var(--accent); color:var(--accent); background:var(--accent-dim); }
    .error-card {
      background:rgba(255,80,80,0.05); border:1px solid rgba(255,80,80,0.2);
      border-radius:12px; padding:14px 20px; font-size:14px; color:#ff7070;
      animation:slideIn 0.3s ease both;
    }
    .trust-badges {
      display:flex; align-items:center; justify-content:center;
      gap:8px; flex-wrap:wrap; animation:fadeUp 0.7s ease 0.38s both;
    }
    .badge {
      display:inline-flex; align-items:center; gap:7px; background:var(--surface);
      border:1px solid var(--border); border-radius:100px; padding:7px 15px;
      font-size:12px; color:var(--muted); font-weight:500; transition:border-color 0.2s,color 0.2s;
    }
    .badge:hover { border-color:rgba(0,232,122,0.25); color:var(--text); }
    .badge svg { width:13px; height:13px; stroke:var(--accent); flex-shrink:0; }
    footer { padding:24px 40px; text-align:center; font-size:12px; color:var(--dim); animation:fadeDown 0.6s ease 0.45s both; }
    @media (max-width:600px) {
      header { padding:20px 24px; }
      .input-group { flex-direction:column; }
      button[type="submit"] { width:100%; text-align:center; }
      .result-card { flex-wrap:wrap; }
      .copy-btn { margin-left:0; width:100%; text-align:center; }
    }
  </style>
</head>
<body>
  <div class="wrapper">
    <header>
      <a href="/" class="logo">
        <div class="logo-mark">url</div>
        <span class="logo-text">nano<span>url</span></span>
      </a>
    </header>
    <main>
      <div class="hero">
        <div class="hero-badge">Encurtador seguro e gratuito</div>
        <h1>Links menores,<br><em>mais confian&ccedil;a.</em></h1>
        <p>Cole qualquer URL e receba um link limpo, curto e permanente. Sem cadastro, sem rastreamento, sem complica&ccedil;&atilde;o.</p>
      </div>
      <div class="card">
        <form id="form">
          <div class="input-group">
            <input type="url" id="url" placeholder="https://seu-link-longo-aqui.com/caminho/enorme..." required autocomplete="off" spellcheck="false">
            <button type="submit">Encurtar &rarr;</button>
          </div>
        </form>
        <div id="result"></div>
      </div>
      <div class="trust-badges">
        <span class="badge">
          <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          HTTPS seguro
        </span>
        <span class="badge">
          <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>
          Sem rastreamento
        </span>
        <span class="badge">
          <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
          Redirecionamento r&aacute;pido
        </span>
        <span class="badge">
          <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
          Links permanentes
        </span>
      </div>
    </main>
    <footer>&copy; 2025 NanoURL &mdash; Todos os links s&atilde;o permanentes e gratuitos.</footer>
  </div>
  <script>
    document.getElementById('form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const urlInput = document.getElementById('url');
      const resultDiv = document.getElementById('result');
      const btn = e.target.querySelector('button[type="submit"]');
      btn.textContent = 'Gerando...';
      btn.style.opacity = '0.6';
      btn.disabled = true;
      try {
        const res = await fetch('/shorten', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ url: urlInput.value })
        });
        const data = await res.json();
        if (res.ok) {
          resultDiv.innerHTML = `
            <div class="result-card">
              <div class="result-icon">&#10003;</div>
              <div style="min-width:0;flex:1">
                <div class="result-label">Seu link encurtado</div>
                <a href="${data.short_url}" class="result-url" target="_blank" rel="noopener">${data.short_url}</a>
              </div>
              <button class="copy-btn" data-url="${data.short_url}">copiar</button>
            </div>`;
          resultDiv.querySelector('.copy-btn').addEventListener('click', function() {
            navigator.clipboard.writeText(this.dataset.url).then(() => {
              this.textContent = 'copiado ✓';
              this.classList.add('copied');
              setTimeout(() => { this.textContent = 'copiar'; this.classList.remove('copied'); }, 2000);
            });
          });
        } else {
          resultDiv.innerHTML = '<div class="error-card">URL inválida. Verifique o endereço e tente novamente.</div>';
        }
      } catch (_) {
        resultDiv.innerHTML = '<div class="error-card">Erro de conexão. Tente novamente.</div>';
      } finally {
        btn.textContent = 'Encurtar →';
        btn.style.opacity = '1';
        btn.disabled = false;
      }
    });
  </script>
</body>
</html>"""


def _admin_login_html(error: str = "") -> str:
    error_block = (
        f'<div class="login-error">{error}</div>' if error else ""
    )
    return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Admin &mdash; NanoURL</title>
""" + _FONTS + """
  <style>
""" + _BASE_STYLE + """
    .wrapper { position:relative; z-index:1; min-height:100vh; display:flex; flex-direction:column; align-items:center; justify-content:center; padding:20px; }
    .login-card {
      width:100%; max-width:400px; background:var(--surface); border:1px solid var(--border);
      border-radius:16px; padding:40px 36px; animation:fadeUp 0.6s ease both;
    }
    .login-logo { display:flex; align-items:center; gap:10px; margin-bottom:32px; }
    .logo-mark {
      width:34px; height:34px; background:var(--accent); border-radius:7px;
      display:flex; align-items:center; justify-content:center;
      font-family:'JetBrains Mono',monospace; font-size:13px; font-weight:500; color:#070b12;
    }
    .logo-text { font-size:18px; font-weight:700; color:var(--text); letter-spacing:-0.5px; }
    .logo-text span { color:var(--accent); }
    .login-title { font-size:22px; font-weight:800; letter-spacing:-1px; margin-bottom:6px; }
    .login-sub { font-size:13px; color:var(--muted); margin-bottom:28px; }
    label { display:block; font-size:11px; text-transform:uppercase; letter-spacing:0.08em; color:var(--muted); margin-bottom:6px; }
    .field { margin-bottom:16px; }
    input[type="text"], input[type="password"] {
      width:100%; background:var(--surface2); border:1px solid var(--border);
      border-radius:9px; padding:13px 16px; font-size:14px;
      font-family:'JetBrains Mono',monospace; color:var(--text); outline:none;
      transition:border-color 0.2s,box-shadow 0.2s;
    }
    input[type="text"]:focus, input[type="password"]:focus {
      border-color:rgba(0,232,122,0.45);
      box-shadow:0 0 0 3px var(--accent-dim);
    }
    .btn-login {
      width:100%; background:var(--accent); color:#070b12; border:none;
      border-radius:9px; padding:14px; font-family:'Syne',sans-serif;
      font-size:14px; font-weight:700; cursor:pointer; margin-top:8px;
      transition:opacity 0.2s,transform 0.15s;
    }
    .btn-login:hover { opacity:0.85; }
    .btn-login:active { transform:scale(0.98); }
    .login-error {
      background:rgba(255,80,80,0.05); border:1px solid rgba(255,80,80,0.2);
      border-radius:8px; padding:10px 14px; font-size:13px; color:#ff7070; margin-bottom:16px;
    }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="login-card">
      <div class="login-logo">
        <div class="logo-mark">url</div>
        <span class="logo-text">nano<span>url</span></span>
      </div>
      <div class="login-title">Acesso Admin</div>
      <div class="login-sub">Entre com suas credenciais para acessar o painel.</div>
      """ + error_block + """
      <form method="POST" action="/admin/login">
        <div class="field">
          <label>Usu&aacute;rio</label>
          <input type="text" name="username" autocomplete="username" required autofocus>
        </div>
        <div class="field">
          <label>Senha</label>
          <input type="password" name="password" autocomplete="current-password" required>
        </div>
        <button type="submit" class="btn-login">Entrar &rarr;</button>
      </form>
    </div>
  </div>
</body>
</html>"""


def _admin_dashboard_html(stats: dict, urls: list[dict]) -> str:
    rows_html = ""
    for u in urls:
        original = u["original_url"]
        truncated = original if len(original) <= 60 else original[:57] + "..."
        rows_html += (
            f'<tr>'
            f'<td><a href="/{u["short_code"]}" target="_blank" class="code-link">{u["short_code"]}</a></td>'
            f'<td title="{original}"><span class="url-cell">{truncated}</span></td>'
            f'<td class="mono">{u["created_at"][:16] if u["created_at"] else "-"}</td>'
            f'<td class="mono clicks">{u["clicks"]}</td>'
            f'</tr>'
        )
    if not rows_html:
        rows_html = '<tr><td colspan="4" class="empty">Nenhum link encurtado ainda.</td></tr>'

    return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Admin Dashboard &mdash; NanoURL</title>
""" + _FONTS + """
  <style>
""" + _BASE_STYLE + """
    .wrapper { position:relative; z-index:1; min-height:100vh; display:flex; flex-direction:column; }
    header {
      padding:20px 40px; display:flex; align-items:center; justify-content:space-between;
      border-bottom:1px solid var(--border); animation:fadeDown 0.5s ease both;
    }
    .logo { display:flex; align-items:center; gap:10px; text-decoration:none; }
    .logo-mark {
      width:34px; height:34px; background:var(--accent); border-radius:7px;
      display:flex; align-items:center; justify-content:center;
      font-family:'JetBrains Mono',monospace; font-size:13px; font-weight:500; color:#070b12;
    }
    .logo-text { font-size:18px; font-weight:700; color:var(--text); letter-spacing:-0.5px; }
    .logo-text span { color:var(--accent); }
    .header-right { display:flex; align-items:center; gap:12px; }
    .admin-badge {
      font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted);
      background:var(--surface); border:1px solid var(--border); border-radius:100px;
      padding:4px 12px;
    }
    .logout-btn {
      background:transparent; border:1px solid var(--border); border-radius:8px;
      padding:7px 14px; font-family:'Syne',sans-serif; font-size:12px;
      color:var(--muted); cursor:pointer; transition:all 0.2s; text-decoration:none;
    }
    .logout-btn:hover { border-color:rgba(255,80,80,0.4); color:#ff7070; }
    main { flex:1; padding:40px; max-width:1200px; width:100%; margin:0 auto; }
    .page-title { font-size:28px; font-weight:800; letter-spacing:-1px; margin-bottom:8px; animation:fadeUp 0.5s ease 0.05s both; }
    .page-sub { font-size:14px; color:var(--muted); margin-bottom:36px; animation:fadeUp 0.5s ease 0.1s both; }
    .stats-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin-bottom:36px; animation:fadeUp 0.5s ease 0.15s both; }
    .stat-card {
      background:var(--surface); border:1px solid var(--border); border-radius:14px;
      padding:24px; transition:border-color 0.2s;
    }
    .stat-card:hover { border-color:rgba(0,232,122,0.25); }
    .stat-label { font-size:11px; text-transform:uppercase; letter-spacing:0.08em; color:var(--muted); margin-bottom:10px; }
    .stat-value { font-size:40px; font-weight:800; letter-spacing:-2px; color:var(--text); line-height:1; }
    .stat-value.accent { color:var(--accent); }
    .table-section { animation:fadeUp 0.5s ease 0.2s both; }
    .table-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
    .table-title { font-size:16px; font-weight:700; letter-spacing:-0.5px; }
    .table-count { font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted);
      background:var(--surface); border:1px solid var(--border); border-radius:100px; padding:3px 10px; }
    .table-wrap { background:var(--surface); border:1px solid var(--border); border-radius:14px; overflow:hidden; }
    table { width:100%; border-collapse:collapse; }
    thead { border-bottom:1px solid var(--border); }
    th {
      padding:12px 20px; text-align:left; font-size:10px; text-transform:uppercase;
      letter-spacing:0.1em; color:var(--muted); font-weight:600;
    }
    td { padding:14px 20px; font-size:13px; border-bottom:1px solid var(--border); vertical-align:middle; }
    tr:last-child td { border-bottom:none; }
    tr:hover td { background:rgba(255,255,255,0.015); }
    .code-link {
      font-family:'JetBrains Mono',monospace; font-size:13px; color:var(--accent);
      text-decoration:none; font-weight:500;
    }
    .code-link:hover { text-decoration:underline; }
    .url-cell { color:var(--muted); font-size:12px; }
    .mono { font-family:'JetBrains Mono',monospace; font-size:12px; color:var(--muted); }
    .clicks { color:var(--text) !important; font-weight:500; }
    .empty { text-align:center; color:var(--dim); padding:40px !important; font-size:13px; }
    @media (max-width:768px) {
      header { padding:16px 20px; }
      main { padding:24px 20px; }
      .stats-grid { grid-template-columns:1fr; }
    }
  </style>
</head>
<body>
  <div class="wrapper">
    <header>
      <a href="/" class="logo">
        <div class="logo-mark">url</div>
        <span class="logo-text">nano<span>url</span></span>
      </a>
      <div class="header-right">
        <span class="admin-badge">admin</span>
        <a href="/admin/logout" class="logout-btn">Sair</a>
      </div>
    </header>
    <main>
      <div class="page-title">Dashboard</div>
      <div class="page-sub">Vis&atilde;o geral dos links encurtados e acessos.</div>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">Total de Links</div>
          <div class="stat-value accent">""" + str(stats["total_links"]) + """</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Total de Cliques</div>
          <div class="stat-value">""" + str(stats["total_clicks"]) + """</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Links Hoje</div>
          <div class="stat-value">""" + str(stats["today_links"]) + """</div>
        </div>
      </div>
      <div class="table-section">
        <div class="table-header">
          <div class="table-title">Links Encurtados</div>
          <span class="table-count">""" + str(stats["total_links"]) + """ registros</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>C&oacute;digo</th>
                <th>URL Original</th>
                <th>Criado em</th>
                <th>Cliques</th>
              </tr>
            </thead>
            <tbody>
              """ + rows_html + """
            </tbody>
          </table>
        </div>
      </div>
    </main>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Routes — public (non-catch-all)
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE_HTML


@app.post("/shorten", response_model=ShortenResponse)
def shorten(body: ShortenRequest, request: Request):
    code = create_short_url(str(body.url))
    base = str(request.base_url).rstrip("/")
    return ShortenResponse(short_url=f"{base}/{code}", short_code=code)


@app.get("/info/{short_code}")
def info(short_code: str):
    data = get_url_info(short_code)
    if not data:
        raise HTTPException(status_code=404, detail="Short code not found")
    return data


# ---------------------------------------------------------------------------
# Routes — admin (must come before /{short_code} catch-all)
# ---------------------------------------------------------------------------

@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page():
    return _admin_login_html()


@app.post("/admin/login")
def admin_login(username: str = Form(...), password: str = Form(...)):
    user_ok = secrets.compare_digest(username, ADMIN_USER)
    pass_ok = secrets.compare_digest(password, ADMIN_PASS)
    if not (user_ok and pass_ok):
        return HTMLResponse(_admin_login_html("Usuário ou senha incorretos."), status_code=401)
    token = secrets.token_hex(32)
    _sessions.add(token)
    response = RedirectResponse(url="/admin", status_code=303)
    response.set_cookie("admin_session", token, httponly=True, samesite="lax")
    return response


@app.get("/admin/logout")
def admin_logout(request: Request):
    token = request.cookies.get("admin_session")
    if token:
        _sessions.discard(token)
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie("admin_session")
    return response


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, _token: str = Depends(require_admin)):
    stats = get_stats()
    urls = get_all_urls()
    return _admin_dashboard_html(stats, urls)


# ---------------------------------------------------------------------------
# Catch-all redirect (must be last)
# ---------------------------------------------------------------------------

@app.get("/{short_code}")
def redirect(short_code: str):
    url = get_original_url(short_code)
    if not url:
        raise HTTPException(status_code=404, detail="Short code not found")
    return RedirectResponse(url=url, status_code=307)
