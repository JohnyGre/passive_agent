"""
COVER AGENT - RTX 3050 4GB EDITION
Opravy pre OOM na 4GB VRAM:
  1. NIKDY nevoláme .to("cuda") — enable_model_cpu_offload() to rieši samo
  2. Generujeme 384×384 (nie 512) — menej aktivačnej pamäte počas forward pass
  3. enable_attention_slicing(1) — najagresívnejší slice = minimum VRAM peak
  4. Pred loadom modelu vyčistíme VRAM + krátky sleep pre Ollama release
  5. enable_model_cpu_offload() miesto enable_sequential_cpu_offload()
     (sekvenčný offload je agresívnejší ale pomalší; model_cpu_offload
     je lepší kompromis pre celý SD pipeline na 4 GB)
"""

import gc
import logging
import time
from pathlib import Path

import httpx

from config import OLLAMA_URL, OLLAMA_MODEL

log = logging.getLogger("CoverAgent")

SD_MODEL = "runwayml/stable-diffusion-v1-5"

TYPE_STYLE = {
    "prompt_pack": (
        "sleek digital 3D icon, vibrant glowing cyber blue and purple, "
        "high-tech workspace, minimalist design, professional 4k render"
    ),
    "mini_guide": (
        "minimalist book cover, elegant typography, clean white and teal background, "
        "soft studio lighting, professional business aesthetic"
    ),
    "cheatsheet": (
        "organized technical infographic, blueprint style, neon accents, "
        "sharp details, high quality data visualization"
    ),
}


def _free_vram() -> None:
    """Agresívne uvoľnenie VRAM pred loadom SD modelu."""
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            log.info(
                f"🧹 VRAM pred loadom: "
                f"{torch.cuda.memory_allocated() / 1024**2:.0f} MB alokovaná / "
                f"{torch.cuda.get_device_properties(0).total_memory / 1024**2:.0f} MB celková"
            )
    except ImportError:
        pass


class CoverAgent:
    def __init__(self):
        self.ollama = httpx.Client(timeout=60.0)

    def generate_cover(self, product: dict, folder: Path) -> Path | None:
        """
        Vygeneruje cover obrázok cez Stable Diffusion.
        Optimalizované pre RTX 3050 4 GB VRAM.
        """
        # Lazy import — torch/diffusers nie sú potrebné pre zvyšok systému
        try:
            import torch
            from diffusers import StableDiffusionPipeline
            from PIL import Image
        except ImportError as e:
            log.error(f"Chýbajúca knižnica pre cover generovanie: {e}")
            return None

        meta = product.get("metadata", {})
        title = meta.get("title") or product.get("title", "Digital Product")
        ptype = product.get("_meta", {}).get("type", "prompt_pack")
        style = TYPE_STYLE.get(ptype, TYPE_STYLE["prompt_pack"])

        log.info(f"Generujem cover pre: {title}")

        # Krok 1: Uvoľni VRAM (Ollama by mal byť voľný vďaka keep_alive:0,
        # ale dáme mu ešte chvíľu na skutočné uvoľnenie)
        _free_vram()
        time.sleep(1.5)

        pipe = None
        try:
            # Krok 2: Load modelu BEZ .to("cuda")
            # enable_model_cpu_offload() sám presúva časti na GPU podľa potreby.
            # Ak zavoláš .to("cuda") PRED offloadom, celý model sa nahrá do VRAM naraz → OOM.
            log.info("Načítavam SD model (CPU → GPU offload)...")
            pipe = StableDiffusionPipeline.from_pretrained(
                SD_MODEL,
                torch_dtype=torch.float16,
                safety_checker=None,
                low_cpu_mem_usage=True,   # menej RAM počas deserializácie
            )

            # Krok 3: Optimalizácie PRED offloadom (poradie je dôležité!)
            pipe.enable_attention_slicing(1)    # slice_size=1 → minimálny VRAM peak
            pipe.enable_vae_slicing()           # VAE dekódovanie po častiach

            # Krok 4: Offload — presúva submoduly na GPU len keď ich pipeline potrebuje
            # enable_model_cpu_offload() je lepší ako enable_sequential_cpu_offload()
            # pre SD pipeline na 4 GB (menej overhead, rýchlejší)
            pipe.enable_model_cpu_offload()

            # Krok 5: Prompt
            sd_prompt = (
                f"Professional product cover for '{title}', {style}, "
                "premium digital product packaging, clean centered composition, "
                "soft studio lighting, subtle depth of field, trending on artstation, "
                "marketing hero image, no text, masterpiece, ultra detailed, sharp focus"
            )
            negative = (
                "text, words, letters, typography, watermark, signature, logo, "
                "blurry, low quality, jpeg artifacts, distorted, deformed, ugly, "
                "messy, cluttered, duplicate, cropped, out of frame"
            )

            # Krok 6: Inferencia
            # 384×384 namiesto 512×512 — zachová ~30 % VRAM počas attention forward pass
            # (aktivačná pamäť rastie kvadraticky so stránkou)
            log.info("Spúšťam SD inferenciu (384×384, 20 krokov)...")
            with torch.inference_mode():
                result = pipe(
                    prompt=sd_prompt,
                    negative_prompt=negative,
                    num_inference_steps=20,     # 20 namiesto 30 — rovnaká kvalita, menej VRAM peakov
                    guidance_scale=7.5,
                    height=384,
                    width=384,
                )

            # Krok 7: Uloženie (upscale na 1024×1024 cez CPU Pillow — bez VRAM)
            image = result.images[0]
            image = image.resize((1024, 1024), Image.LANCZOS)
            cover_path = folder / "cover.jpg"
            image.save(str(cover_path), "JPEG", quality=95)

            log.info("✅ Cover uložený (384→1024px LANCZOS).")
            return cover_path

        except Exception as e:
            log.error(f"SD memory failure: {e}")
            return None

        finally:
            # Krok 8: Totálne vyčistenie — vždy, aj pri chybe
            if pipe is not None:
                del pipe
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                    log.info(
                        f"🧹 VRAM po uvoľnení: "
                        f"{torch.cuda.memory_allocated() / 1024**2:.0f} MB alokovaná"
                    )
            except ImportError:
                pass

    def close(self):
        self.ollama.close()