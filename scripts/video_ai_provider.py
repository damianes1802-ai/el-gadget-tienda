#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIDEO AI PROVIDER — Capa de abstracción para generación de video con IA

Despacha la generación de video al provider configurado:
  - "local"   → Pillow + MoviePy (gratis, siempre disponible)
  - "heygen"  → HeyGen API (talking head con avatar)
  - "kling"   → Kling AI API (image-to-video desde foto de producto)

Configuración via config/.env:
  VIDEO_AI_PROVIDER=local          (default, usa el sistema actual)
  HEYGEN_API_KEY=xxx               (necesario para provider heygen)
  KLING_API_KEY=xxx                (necesario para provider kling)

Uso:
  from video_ai_provider import generar_video
  path = generar_video(
      provider="local",            # o "heygen" o "kling"
      persona="maria",
      reel_type="R01",
      data={...},                  # campos generados por Claude
      producto={...},              # datos del producto (opcional)
  )
"""

import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger

logger = get_logger('video_ai_provider')

OUTPUT_DIR = Path(__file__).parent.parent / "marketing_app" / "data" / "generated_reels"


def generar_video(provider="local", persona="lucas", reel_type="R01",
                  data=None, producto=None, output_filename=None):
    """
    Genera un video usando el provider especificado.

    Args:
        provider: "local" | "heygen" | "kling"
        persona: buyer persona key
        reel_type: R01-R10
        data: dict con campos generados por Claude (hook, dolor, etc.)
        producto: dict con datos del producto (nombre, precio, imagen_principal)
        output_filename: nombre del archivo de salida

    Returns:
        dict con:
          path: ruta al .mp4 generado
          provider: provider usado
          duration: duración en segundos
          cost: costo estimado (0 para local)
    """
    data = data or {}
    producto = producto or {}

    if provider == "heygen":
        return _generar_heygen(persona, reel_type, data, producto, output_filename)
    elif provider == "kling":
        return _generar_kling(persona, reel_type, data, producto, output_filename)
    else:
        return _generar_local(persona, reel_type, data, producto, output_filename)


def _generar_local(persona, reel_type, data, producto, output_filename):
    """Provider local: Pillow + MoviePy (sistema actual)."""
    from reel_composer import compose_reel, compose_reel_variant

    ts = int(time.time())
    if not output_filename:
        sku = producto.get("sku", f"GEN-{ts}")
        output_filename = f"{reel_type}_{sku}_{ts}.mp4"

    if reel_type == "R01":
        path = compose_reel(
            persona=persona,
            hook=data.get("hook", ""),
            dolor=data.get("dolor", ""),
            solucion=data.get("solucion", ""),
            numero_grande=data.get("numero_grande", ""),
            subtexto_proof=data.get("subtexto_proof", ""),
            beneficio=data.get("beneficio", ""),
            dato_extra=data.get("dato_extra", ""),
            cta_text=data.get("cta_text", ""),
            voiceover_text=data.get("voiceover", ""),
            output_filename=output_filename,
            reel_type=reel_type,
        )
    else:
        path = compose_reel_variant(
            reel_type=reel_type,
            persona=persona,
            hook=data.get("hook", ""),
            antes_texto=data.get("antes_texto", ""),
            despues_texto=data.get("despues_texto", ""),
            numero_grande=data.get("numero_grande", ""),
            subtexto_proof=data.get("subtexto_proof", ""),
            bullets=data.get("bullets"),
            historia_slides=data.get("historia_slides"),
            pasos=data.get("pasos"),
            mitos=data.get("mitos"),
            realidades=data.get("realidades"),
            producto_nombre=data.get("producto_nombre", ""),
            precio_original=data.get("precio_original", ""),
            precio_descuento=data.get("precio_descuento", ""),
            comision=data.get("comision", ""),
            beneficio=data.get("beneficio", ""),
            otros_stats=data.get("otros_stats", ""),
            gadget_stats=data.get("gadget_stats", ""),
            items_check=data.get("items_check"),
            dato_grande=data.get("dato_grande", ""),
            dato_contexto=data.get("dato_contexto", ""),
            dato_como=data.get("dato_como", ""),
            voiceover_text=data.get("voiceover", ""),
            output_filename=output_filename,
        )

    return {"path": path, "provider": "local", "duration": 0, "cost": 0}


def _generar_heygen(persona, reel_type, data, producto, output_filename):
    """
    Provider HeyGen: Talking head con avatar IA.

    Requiere HEYGEN_API_KEY en config/.env.
    Genera un video de avatar hablando el script del voiceover.

    API docs: https://docs.heygen.com/reference/create-an-avatar-video-v2
    """
    env = Config.cargar_env()
    api_key = env.get('HEYGEN_API_KEY', '')
    if not api_key:
        logger.warning("HEYGEN_API_KEY no configurada, fallback a local")
        return _generar_local(persona, reel_type, data, producto, output_filename)

    # Mapeo persona → avatar_id (configurar cuando se tengan los avatares)
    AVATAR_MAP = {
        "maria": env.get("HEYGEN_AVATAR_MARIA", ""),
        "lucas": env.get("HEYGEN_AVATAR_LUCAS", ""),
        "ana": env.get("HEYGEN_AVATAR_ANA", ""),
        "sofi": env.get("HEYGEN_AVATAR_SOFI", ""),
        "martin": env.get("HEYGEN_AVATAR_MARTIN", ""),
    }

    # Mapeo persona → voice_id (voces en español)
    VOICE_MAP = {
        "maria": env.get("HEYGEN_VOICE_MARIA", ""),
        "lucas": env.get("HEYGEN_VOICE_LUCAS", ""),
        "ana": env.get("HEYGEN_VOICE_ANA", ""),
        "sofi": env.get("HEYGEN_VOICE_SOFI", ""),
        "martin": env.get("HEYGEN_VOICE_MARTIN", ""),
    }

    avatar_id = AVATAR_MAP.get(persona, "")
    voice_id = VOICE_MAP.get(persona, "")
    script = data.get("voiceover", "")

    if not avatar_id or not voice_id or not script:
        logger.warning(f"HeyGen: faltan datos para {persona} (avatar={bool(avatar_id)}, voice={bool(voice_id)}), fallback a local")
        return _generar_local(persona, reel_type, data, producto, output_filename)

    try:
        import requests

        # 1. Crear video
        response = requests.post(
            "https://api.heygen.com/v2/video/generate",
            headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
            json={
                "video_inputs": [{
                    "character": {"type": "avatar", "avatar_id": avatar_id},
                    "voice": {"type": "text", "input_text": script, "voice_id": voice_id},
                    "background": {"type": "color", "value": "#14151A"},
                }],
                "dimension": {"width": 1080, "height": 1920},
            },
            timeout=30,
        )

        if response.status_code != 200:
            logger.error(f"HeyGen create error: {response.status_code} {response.text}")
            return _generar_local(persona, reel_type, data, producto, output_filename)

        video_id = response.json().get("data", {}).get("video_id", "")
        if not video_id:
            logger.error("HeyGen: no video_id returned")
            return _generar_local(persona, reel_type, data, producto, output_filename)

        # 2. Poll hasta que esté listo (max 5 minutos)
        for _ in range(60):
            time.sleep(5)
            status_resp = requests.get(
                f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
                headers={"X-Api-Key": api_key},
                timeout=15,
            )
            status_data = status_resp.json().get("data", {})
            if status_data.get("status") == "completed":
                video_url = status_data.get("video_url", "")
                break
            elif status_data.get("status") == "failed":
                logger.error(f"HeyGen video failed: {status_data}")
                return _generar_local(persona, reel_type, data, producto, output_filename)
        else:
            logger.error("HeyGen: timeout waiting for video")
            return _generar_local(persona, reel_type, data, producto, output_filename)

        # 3. Descargar video
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        if not output_filename:
            output_filename = f"heygen_{persona}_{int(time.time())}.mp4"
        output_path = str(OUTPUT_DIR / output_filename)

        dl = requests.get(video_url, timeout=60)
        Path(output_path).write_bytes(dl.content)

        duration = status_data.get("duration", 0)
        logger.info(f"HeyGen video OK: {output_path} ({duration}s)")

        return {"path": output_path, "provider": "heygen", "duration": duration, "cost": 0.05 * duration}

    except Exception as e:
        logger.error(f"HeyGen exception: {e}, fallback a local")
        return _generar_local(persona, reel_type, data, producto, output_filename)


def _generar_kling(persona, reel_type, data, producto, output_filename):
    """
    Provider Kling: Image-to-video desde foto real de producto.

    Requiere KLING_API_KEY en config/.env.
    Toma la imagen del producto y genera un video con movimiento.

    API docs: https://docs.qingque.cn/d/home/eZQBMnJker7t_BVbvPdLNKfvj
    """
    env = Config.cargar_env()
    api_key = env.get('KLING_API_KEY', '')
    if not api_key:
        logger.warning("KLING_API_KEY no configurada, fallback a local")
        return _generar_local(persona, reel_type, data, producto, output_filename)

    image_url = producto.get("imagen_principal", "")
    if not image_url:
        logger.warning("Kling: no hay imagen de producto, fallback a local")
        return _generar_local(persona, reel_type, data, producto, output_filename)

    # Prompt de movimiento basado en el tipo de reel
    MOTION_PROMPTS = {
        "R02": "Slowly reveal the product with a smooth camera pan, before and after comparison",
        "R07": "Smooth 360 degree rotation of the product on a clean background, professional product showcase",
        "R09": "Hands picking up and using the product, demonstrating its features step by step",
    }
    motion_prompt = MOTION_PROMPTS.get(reel_type, "Smooth zoom in on the product with subtle camera movement, professional product video")

    try:
        import requests

        # 1. Crear tarea image-to-video
        response = requests.post(
            "https://api.klingai.com/v1/videos/image2video",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model_name": "kling-v3",
                "image": image_url,
                "prompt": motion_prompt,
                "duration": "5",
                "aspect_ratio": "9:16",
                "mode": "standard",
            },
            timeout=30,
        )

        if response.status_code != 200:
            logger.error(f"Kling create error: {response.status_code} {response.text}")
            return _generar_local(persona, reel_type, data, producto, output_filename)

        task_id = response.json().get("data", {}).get("task_id", "")
        if not task_id:
            logger.error("Kling: no task_id returned")
            return _generar_local(persona, reel_type, data, producto, output_filename)

        # 2. Poll hasta que esté listo (max 10 minutos)
        for _ in range(120):
            time.sleep(5)
            status_resp = requests.get(
                f"https://api.klingai.com/v1/videos/image2video/{task_id}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=15,
            )
            status_data = status_resp.json().get("data", {})
            task_status = status_data.get("task_status", "")
            if task_status == "succeed":
                videos = status_data.get("task_result", {}).get("videos", [])
                video_url = videos[0].get("url", "") if videos else ""
                break
            elif task_status in ("failed", "timeout"):
                logger.error(f"Kling video failed: {status_data}")
                return _generar_local(persona, reel_type, data, producto, output_filename)
        else:
            logger.error("Kling: timeout waiting for video")
            return _generar_local(persona, reel_type, data, producto, output_filename)

        # 3. Descargar video
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        if not output_filename:
            output_filename = f"kling_{persona}_{int(time.time())}.mp4"
        output_path = str(OUTPUT_DIR / output_filename)

        dl = requests.get(video_url, timeout=60)
        Path(output_path).write_bytes(dl.content)

        duration = int(status_data.get("task_result", {}).get("videos", [{}])[0].get("duration", 5))
        cost = duration * 0.075
        logger.info(f"Kling video OK: {output_path} ({duration}s, ~${cost:.2f})")

        return {"path": output_path, "provider": "kling", "duration": duration, "cost": cost}

    except Exception as e:
        logger.error(f"Kling exception: {e}, fallback a local")
        return _generar_local(persona, reel_type, data, producto, output_filename)


def get_available_providers():
    """Retorna lista de providers disponibles según las API keys configuradas."""
    env = Config.cargar_env()
    available = ["local"]
    if env.get("HEYGEN_API_KEY"):
        available.append("heygen")
    if env.get("KLING_API_KEY"):
        available.append("kling")
    return available


def get_provider_status():
    """Retorna estado de cada provider para mostrar en la consola."""
    env = Config.cargar_env()
    return {
        "local": {"enabled": True, "status": "ok", "cost": "Gratis"},
        "heygen": {
            "enabled": bool(env.get("HEYGEN_API_KEY")),
            "status": "configurado" if env.get("HEYGEN_API_KEY") else "sin API key",
            "cost": "~$0.05/seg de video",
        },
        "kling": {
            "enabled": bool(env.get("KLING_API_KEY")),
            "status": "configurado" if env.get("KLING_API_KEY") else "sin API key",
            "cost": "~$0.075/seg de video",
        },
    }
