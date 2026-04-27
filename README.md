# 🎬 YouTube Shorts Bot — Guía completa

Bot automatizado que genera YouTube Shorts de ~50 segundos controlado desde Telegram.
**100% gratuito** — sin gastar un peso.

---

## 🏗 Arquitectura

```
Telegram (tú)
    │  /video tema aquí
    ▼
Webhook Server (Railway/Render — gratis)
    │  repository_dispatch
    ▼
GitHub Actions (2000 min/mes gratis)
    ├── Grok API  → guion + imagen de miniatura + clips de video
    ├── Edge TTS  → narración de voz (Microsoft, gratis)
    ├── FFmpeg    → concatena clips + mezcla audio
    └── YouTube Data API v3 → publica el Short
    │
    ▼
Telegram (tú) ← notificación con el link del Short publicado
```

---

## 📋 Requisitos (todos gratuitos)

| Servicio | Para qué | Tier gratuito |
|---|---|---|
| **GitHub** | Alojar el bot + CI | 2000 min/mes Actions |
| **Grok (x.ai)** | Guion, imagen, video | Tier gratuito |
| **Edge TTS** | Narración de voz | Sin límite |
| **YouTube Data API** | Publicar el Short | 10.000 unidades/día |
| **Telegram** | Control del bot | Gratuito |
| **Railway / Render** | Webhook server | Tier gratuito |

---

## 🚀 Instalación paso a paso

### 1. Clonar el repositorio
```bash
git clone https://github.com/TU_USUARIO/youtube-shorts-bot.git
cd youtube-shorts-bot
```

### 2. Crear el bot de Telegram
1. Abre Telegram → busca **@BotFather**
2. Envía `/newbot` y sigue las instrucciones
3. Guarda el **token** del bot
4. Envía un mensaje a tu bot y visita:
   `https://api.telegram.org/botTOKEN/getUpdates`
   Copia tu **chat_id** del campo `"id"`

### 3. Obtener API key de Grok
1. Ve a **https://x.ai** → Console
2. Crea una API key gratuita
3. Guárdala

### 4. Configurar YouTube OAuth2 (una sola vez)

```bash
pip install google-auth-oauthlib
python scripts/get_youtube_token.py
```

Esto abrirá el navegador para autorizar. Al terminar, el script imprime
`client_id`, `client_secret` y `refresh_token`.

> Si no tienes el script aún, usa **Google OAuth Playground**:
> https://developers.google.com/oauthplayground
> Scope: `https://www.googleapis.com/auth/youtube.upload`

### 5. Configurar secretos en GitHub

Ve a tu repo → **Settings → Secrets and variables → Actions** → New secret:

| Secret | Valor |
|---|---|
| `GROK_API_KEY` | Tu API key de x.ai |
| `TELEGRAM_BOT_TOKEN` | Token de BotFather |
| `TELEGRAM_CHAT_ID` | Tu chat_id personal |
| `YOUTUBE_CLIENT_ID` | OAuth2 client_id |
| `YOUTUBE_CLIENT_SECRET` | OAuth2 client_secret |
| `YOUTUBE_REFRESH_TOKEN` | OAuth2 refresh_token |
| `GITHUB_TOKEN_DISPATCH` | PAT con permiso `repo` |

### 6. Desplegar el webhook en Railway (gratis)

1. Ve a **https://railway.app** → New Project → Deploy from GitHub
2. Selecciona tu repo
3. Configura las variables de entorno:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_SECRET` (inventa un string secreto)
   - `GITHUB_TOKEN` (PAT con permiso `repo`)
   - `GITHUB_OWNER` (tu usuario)
   - `GITHUB_REPO` (nombre del repo)
   - `ALLOWED_CHAT_ID` (tu chat_id)
4. Start command: `uvicorn bot.telegram_webhook:app --host 0.0.0.0 --port $PORT`
5. Copia la URL pública de Railway (ej: `https://tubot.up.railway.app`)

### 7. Registrar el webhook en Telegram

```bash
curl -X POST "https://api.telegram.org/botTU_TOKEN/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://tubot.up.railway.app/webhook",
    "secret_token": "TU_TELEGRAM_SECRET"
  }'
```

### 8. Personalizar el canal

Edita `config/channel_context.txt` con la info de tu canal.

---

## 💬 Comandos de Telegram

| Comando | Descripción |
|---|---|
| `/video curiosidades del sol` | Short con instrucción corta |
| `/video Quiero un video sobre agujeros negros, enfocado en qué pasaría si la Tierra cayera en uno, tono dramático` | Instrucción detallada |
| `/pregunta ¿Qué temas funcionan mejor en mi canal?` | Pregunta al asistente |
| `/estado` | Info del último Short publicado |
| `/ayuda` | Lista de comandos |

---

## 📁 Estructura del proyecto

```
youtube-shorts-bot/
├── .github/workflows/run_bot.yml   ← GitHub Actions
├── bot/
│   ├── main.py                     ← Orquestador
│   ├── dispatcher.py               ← Router de comandos
│   ├── telegram_webhook.py         ← Servidor webhook
│   ├── telegram_notifier.py        ← Notificaciones
│   ├── grok_client.py              ← API Grok unificada
│   ├── script_writer.py            ← Generador de guion
│   ├── thumbnail_maker.py          ← Miniatura con Pillow
│   ├── video_generator.py          ← Clips + técnica último fotograma
│   ├── audio_generator.py          ← Narración Edge TTS
│   ├── video_mixer.py              ← FFmpeg mezcla final
│   └── uploader.py                 ← YouTube Data API
├── config/
│   ├── channel_context.txt         ← Info de tu canal
│   └── last_video.json             ← Estado del último video (auto)
├── requirements.txt
└── README.md
```

---

## ⚙️ Técnica del último fotograma (detalle)

Grok Aurora en tier gratuito genera clips de ~5-10 segundos.
El bot los encadena así:

```
Prompt seg.1 → Clip1.mp4 → [extrae último frame con FFmpeg]
                                        │
Prompt seg.2 + frame1 → Clip2.mp4 → [extrae último frame]
                                        │
Prompt seg.3 + frame2 → Clip3.mp4 → ...
                                        │
FFmpeg concat → video_50seg.mp4
```

Esto da continuidad visual entre clips sin usar tiers de pago.
