"""
instruction_parser.py
──────────────────────
Analiza el mensaje del usuario y construye un plan de generación.

Reglas:
  - Instrucción CORTA  (<= 10 palabras): 1 ángulo, tono neutro, 1 prompt de guion
  - Instrucción MEDIA  (11-30 palabras) : 2-3 ángulos extraídos del texto
  - Instrucción LARGA  (>30 palabras)   : múltiples ángulos, tono y detalles
                                          detectados desde el mensaje
"""

import re

# Palabras clave para detectar tono
TONE_KEYWORDS = {
    "juvenil":    ["joven", "juvenil", "divertido", "gracioso", "meme", "viral"],
    "educativo":  ["educativo", "aprende", "tutorial", "explica", "enseña", "paso a paso"],
    "motivador":  ["motiva", "inspirador", "empodera", "logra", "éxito"],
    "serio":      ["serio", "formal", "profesional", "técnico", "experto"],
    "narrativo":  ["historia", "cuento", "anécdota", "caso real", "experiencia"],
}

# Palabras clave para detectar ángulos adicionales explícitos
ANGLE_MARKERS = [
    r"enfocado en (.+?)(?:,|$|\.|y )",
    r"habla(?:ndo)? (?:de|sobre|acerca de) (.+?)(?:,|$|\.)",
    r"menciona(?:ndo)? (.+?)(?:,|$|\.)",
    r"incluye? (.+?)(?:,|$|\.)",
    r"con ejemplos? (?:de|sobre)? (.+?)(?:,|$|\.)",
]

TARGET_DURATION = 50   # segundos objetivo del Short
SECONDS_PER_SEGMENT = 8  # Grok free genera ~5-10s por clip


def detect_tone(text: str) -> str:
    text_lower = text.lower()
    for tone, keywords in TONE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return tone
    return "neutro"


def extract_angles(text: str, topic: str) -> list[str]:
    """Extrae sub-ángulos mencionados explícitamente en la instrucción."""
    angles = []
    for pattern in ANGLE_MARKERS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        angles.extend([m.strip() for m in matches if m.strip()])

    # Si no detectó ángulos específicos, crea uno genérico
    if not angles:
        angles = [topic]

    return angles[:4]   # máximo 4 ángulos


def extract_topic(text: str) -> str:
    """
    Extrae el tema central limpiando frases de relleno.
    Ej: 'Quiero un video sobre Python para principiantes' → 'Python para principiantes'
    """
    fillers = [
        r"quiero un video (?:sobre|de|acerca de)\s*",
        r"haz(?:me)? un video (?:sobre|de|acerca de)\s*",
        r"crea(?:me)? un video (?:sobre|de|acerca de)\s*",
        r"genera(?:me)? un video (?:sobre|de|acerca de)\s*",
        r"(?:un |el )?video (?:sobre|de|acerca de)\s*",
        r"quiero (?:hablar|que hables) (?:sobre|de)\s*",
    ]
    cleaned = text
    for filler in fillers:
        cleaned = re.sub(filler, "", cleaned, flags=re.IGNORECASE).strip()

    # El tema es la primera oración o cláusula (hasta coma, punto o conector)
    topic = re.split(r"[,\.\n]|,\s*enfocado|,\s*con tono|,\s*incluye", cleaned)[0].strip()
    return topic[:120]   # máximo 120 caracteres


def parse_instruction(raw: str) -> dict:
    """
    Entrada : string libre del usuario
    Salida  : dict con el plan completo de generación

    Campos:
      topic     — tema central limpio
      raw       — instrucción original completa
      tone      — tono detectado
      angles    — lista de sub-ángulos o puntos a cubrir
      duration  — duración objetivo en segundos
      segments  — cantidad de clips Grok necesarios
      detail    — "short" | "medium" | "long"
      extra_ctx — contexto adicional para el prompt de Grok
    """
    raw = raw.strip()
    word_count = len(raw.split())

    # Clasificación de extensión
    if word_count <= 10:
        detail = "short"
    elif word_count <= 30:
        detail = "medium"
    else:
        detail = "long"

    topic  = extract_topic(raw)
    tone   = detect_tone(raw)
    angles = extract_angles(raw, topic)

    # Calcular segmentos necesarios
    segments = max(1, TARGET_DURATION // SECONDS_PER_SEGMENT)  # ≈ 6 segmentos

    # Contexto extra: todo lo que hay después del tema (para el prompt de Grok)
    extra_ctx = raw[len(topic):].strip().lstrip(",.- ") if len(raw) > len(topic) else ""

    plan = {
        "topic":     topic,
        "raw":       raw,
        "tone":      tone,
        "angles":    angles,
        "duration":  TARGET_DURATION,
        "segments":  segments,
        "detail":    detail,
        "extra_ctx": extra_ctx,
    }

    return plan


# ── Test rápido ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        "Los 3 errores de Python para principiantes",
        "Quiero un video sobre Python para principiantes, enfocado en errores comunes de listas y bucles, con ejemplos divertidos y tono juvenil",
        "historia de la inteligencia artificial desde los años 50 hasta hoy, menciona a Turing, menciona a Hinton, tono educativo pero entretenido para jóvenes de 15 a 25 años",
    ]
    for t in tests:
        plan = parse_instruction(t)
        print(f"\nInput  : {t[:60]}...")
        print(f"Detail : {plan['detail']}")
        print(f"Topic  : {plan['topic']}")
        print(f"Tone   : {plan['tone']}")
        print(f"Angles : {plan['angles']}")
        print(f"Segs   : {plan['segments']}")
