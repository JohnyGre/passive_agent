"""
COVER AGENT - MEMORY OPTIMIZED
Automaticky uvoľňuje VRAM po každom obrázku pre RTX 3050 stabilitu.
"""

import logging
import httpx
import gc
import torch
from pathlib import Path

from config import OLLAMA_URL, OLLAMA_MODEL

log = logging.getLogger("CoverAgent")

SD_MODEL = "runwayml/stable-diffusion-v1-5"

TYPE_STYLE = {
    "prompt_pack": "sleek digital 3D icon, vibrant glowing cyber blue and purple, high-tech workspace, minimalist design, professional 4k render",
    "mini_guide":  "minimalist book cover, elegant typography, clean white and teal background, soft studio lighting, professional business aesthetic",
    "cheatsheet":  "organized technical infographic, blueprint style, neon accents, sharp details, high quality data visualization",
}

class CoverAgent:
    def __init__(self):
        self.ollama = httpx.Client(timeout=60.0)

    def generate_cover(self, product: dict, folder: Path) -> Path | None:
        from diffusers import StableDiffusionPipeline
        from PIL import Image
        
        meta = product.get("metadata", {})
        title = meta.get("title") or product.get("title", "Digital Product")
        ptype = product.get("_meta", {}).get("type", "prompt_pack")
        style = TYPE_STYLE.get(ptype, TYPE_STYLE["prompt_pack"])
        
        log.info(f"Generujem cover pre: {title}")

        try:
            # 1. NAČÍTANIE MODELU DO VRAM (vždy čisté pre maximálnu stabilitu pri 4GB)
            pipe = StableDiffusionPipeline.from_pretrained(
                SD_MODEL, 
                torch_dtype=torch.float16,
                safety_checker=None
            ).to("cuda")
            
            pipe.enable_attention_slicing()
            pipe.vae.enable_slicing()
            # Nová optimalizácia pre nízku VRAM
            pipe.enable_sequential_cpu_offload()

            sd_prompt = (
                f"Professional product cover for '{title}', {style}, "
                "premium digital product packaging, clean centered composition, "
                "soft studio lighting, subtle depth of field, trending on artstation, "
                "marketing hero image, no text, masterpiece, ultra detailed, 8k, sharp focus"
            )
            negative = (
                "text, words, letters, typography, watermark, signature, logo, "
                "blurry, low quality, jpeg artifacts, distorted, deformed, ugly, "
                "messy, cluttered, duplicate, cropped, out of frame"
            )
            
            with torch.inference_mode():
                result = pipe(
                    prompt=sd_prompt, 
                    negative_prompt=negative,
                    num_inference_steps=30,
                    guidance_scale=7.5,
                    height=512,
                    width=512
                )
            
            image = result.images[0]
            # Upscale na prémiové rozlíšenie pre predaj (ostrejší vzhľad na Gumroad)
            image = image.resize((1024, 1024), Image.LANCZOS)
            cover_path = folder / "cover.jpg"
            image.save(str(cover_path), "JPEG", quality=95)

            # 2. TOTÁLNE VYČISTENIE VRAM HNEĎ PO GENERÁVANÍ
            del pipe
            gc.collect()
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            
            log.info("✅ Cover uložený (1024x1024) a VRAM úplne uvoľnená.")
            return cover_path

        except Exception as e:
            log.error(f"SD memory failure: {e}")
            # Núdzové vyčistenie pri chybe
            gc.collect()
            torch.cuda.empty_cache()
            return None

    def close(self):
        self.ollama.close()