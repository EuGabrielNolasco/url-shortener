# NanoURL — Encurtador de Links

Encurtador de URLs minimalista com painel administrativo. Interface dark com design editorial, construído com FastAPI e SQLite.

![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-latest-009688?style=flat-square&logo=fastapi)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=flat-square&logo=sqlite)

---

## Funcionalidades

- Cole qualquer URL e receba um link curto e permanente
- Redirecionamento rápido (307) com contador de cliques
- Deduplicação: a mesma URL sempre gera o mesmo código
- Painel admin com dashboard de estatísticas e tabela de links
- Sem cadastro, sem rastreamento, sem dependências externas

---

## Como usar

### 1. Instalar dependências

```bash
pip3 install fastapi uvicorn python-multipart --break-system-packages
```

### 2. Iniciar o servidor

```bash
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Acessar

| URL | Descrição |
|-----|-----------|
| `http://localhost:8000` | Página principal |
| `http://localhost:8000/admin` | Painel administrativo |

### 4. Encurtar um link

Cole a URL no campo da página principal e clique em **Encurtar**. O link encurtado aparece imediatamente com botão de copiar.

### 5. Painel Admin

Acesse `/admin` e faça login com:

```
Usuário: admin
Senha:   admin123
```

O dashboard exibe total de links, total de cliques, links criados hoje e uma tabela completa de todas as URLs encurtadas.

---

## API

```bash
# Encurtar uma URL
curl -X POST http://localhost:8000/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://exemplo.com/caminho/muito/longo"}'

# Resposta
{
  "short_url": "http://localhost:8000/K_Ierg",
  "short_code": "K_Ierg"
}

# Consultar info de um link
curl http://localhost:8000/info/K_Ierg
```

---

## Como foi feito

### Backend

O servidor é uma aplicação [FastAPI](https://fastapi.tiangolo.com/) com três camadas:

- **`main.py`** — rotas, autenticação admin e todo o HTML das páginas como strings Python inline. Sem template engine. A URL base é derivada de `request.base_url` em tempo de requisição, garantindo compatibilidade com WSL2 e qualquer ambiente de rede.
- **`shortener.py`** — lógica de geração de códigos (6 caracteres, `secrets.token_urlsafe`), deduplicação por URL original e incremento de cliques no redirecionamento.
- **`database.py`** — acesso ao SQLite via context manager `get_conn()` com auto-commit. Banco criado automaticamente no startup via `init_db()`.

### Autenticação Admin

Sessões em memória com tokens `secrets.token_hex(32)` armazenados em cookie `HttpOnly`. Comparação de credenciais com `secrets.compare_digest` para evitar timing attacks. As rotas `/admin/*` são declaradas antes da rota catch-all `/{short_code}` para garantir prioridade de matching.

### Frontend

HTML, CSS e JS gerados como strings Python — sem bundler, sem framework frontend. O design segue uma estética **dark editorial**:

- Tipografia: `Syne` (títulos) + `JetBrains Mono` (URLs e código) via Google Fonts
- Paleta: fundo `#070b12`, acento verde `#00e87a`, grid de pontos no background
- Animações em CSS puro: `fadeUp`, `fadeDown`, `slideIn`, `pulse`
- JavaScript usa template literals (backticks) para montar HTML dinâmico — evita bugs de escape de aspas que quebram `e.preventDefault()`

---

## Tecnologias

| Tecnologia | Uso |
|------------|-----|
| [Python 3.12](https://python.org) | Linguagem principal |
| [FastAPI](https://fastapi.tiangolo.com) | Framework web / API |
| [Uvicorn](https://www.uvicorn.org) | Servidor ASGI |
| [Pydantic](https://docs.pydantic.dev) | Validação de URLs |
| [SQLite](https://sqlite.org) | Banco de dados |
| [python-multipart](https://github.com/andrew-d/python-multipart) | Parsing de formulários |
| [Syne](https://fonts.google.com/specimen/Syne) | Fonte dos títulos |
| [JetBrains Mono](https://www.jetbrains.com/lp/mono/) | Fonte monospace |

---

## Estrutura

```
url-shortener/
├── main.py          # App FastAPI, rotas e HTML inline
├── shortener.py     # Lógica de encurtamento
├── database.py      # Acesso ao SQLite
├── requirements.txt # Dependências
└── urls.db          # Banco de dados (gerado automaticamente)
```

---

## Licença

MIT
