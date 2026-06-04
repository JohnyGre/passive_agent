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
        
        title = product.get("title", "Digital Product")
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

            sd_prompt = f"Professional product cover for '{title}', {style}, no text, masterpiece, 8k, sharp focus"
            negative = "text, words, letters, watermark, blurry, low quality, distorted, ugly, messy"
            
            with torch.inference_mode():
                result = pipe(
                    prompt=sd_prompt, 
                    negative_prompt=negative,
                    num_inference_steps=25, 
                    guidance_scale=8.0
                )
            
            image = result.images[0]
            cover_path = folder / "cover.jpg"
            image.save(str(cover_path), "JPEG", quality=95)

            # 2. TOTÁLNE VYČISTENIE VRAM HNEĎ PO GENERÁVANÍ
            del pipe
            gc.collect()
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            
            log.info(f"✅ Cover uložený a VRAM úplne uvoľnená pre ďalšie kroky.")
            return cover_path

        except Exception as e:
            log.error(f"SD memory failure: {e}")
            # Núdzové vyčistenie pri chybe
            gc.collect()
            torch.cuda.empty_cache()
            return None

    def close(self):
        self.ollama.close()
