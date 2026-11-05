"""Local generative rendering. Imported only in the isolated AI worker process."""
from __future__ import annotations

import gc
import hashlib
import json
import math
import os
from pathlib import Path
import time

os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
                  TOKENIZERS_PARALLELISM="false")
import cv2
import numpy as np
from PIL import Image, ImageOps
import torch

CONTRACT = "manga-studio/generation-2.2-v2"
MODELS = {
    "flux": ("black-forest-labs/FLUX.2-klein-4B", "e7b7dc27f91deacad38e78976d1f2b499d76a294"),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() if path else ""


def image(path):
    with Image.open(path) as im:
        return ImageOps.exif_transpose(im).convert("RGB")


def fit(im, area=1024*1024, max_side=1536):
    scale = min(1., math.sqrt(area/(im.width*im.height)), max_side/max(im.size))
    w, h = max(64, int(im.width*scale)//16*16), max(64, int(im.height*scale)//16*16)
    content = ImageOps.contain(im, (w, h), Image.Resampling.LANCZOS)
    box = ((w-content.width)//2, (h-content.height)//2)
    canvas = Image.new("RGB", (w,h), "white")
    canvas.paste(content, box)
    return canvas, (*box, box[0]+content.width, box[1]+content.height)


def reference_image(path, role):
    ref = image(path)
    if role == "palette":
        # Remove all identity/layout information, keeping a deterministic color swatch sheet.
        colors = ref.resize((160,160)).quantize(colors=12, method=Image.Quantize.MEDIANCUT).convert("RGB")
        counts = sorted(colors.getcolors(25600), reverse=True)
        sheet = Image.new("RGB", (384,256), "white")
        for i, (_, rgb) in enumerate(counts):
            sheet.paste(rgb, ((i%4)*96, (i//4)*85, (i%4+1)*96, min(256,(i//4+1)*85)))
        return sheet
    if role == "light":
        ref = ref.convert("L").convert("RGB")
    return fit(ref, area=640*640, max_side=896)[0]


def instruction(mode, has_reference, has_anchor, notes="", role="style", correction="", palette=""):
    tasks = {
        "skin": "Correct only the skin colors in image 1: unify the base complexion of each person's face, neck, hands and legs. Keep natural shadow and highlight variation. Do not recolor garments or the background.",
        "face": "Restore the exact original eyes, mouth, smile and face proportions from image 2 in image 1. Retain image 1's colors and rendering. Do not redesign the character.",
        "hands": "Restore the original finger count, hand contours and cropped limb endpoints from image 2 in image 1. Keep the same pose and colors. Never extend a cropped body.",
        "clothes": "Correct color bleeding between skin, hair and clothing in image 1. Use image 2 to identify the original garment boundaries, folds and coverage. Preserve each material's shading.",
    }
    if correction:
        if correction not in tasks:
            raise ValueError("Unknown correction")
        start = tasks[correction]+" Image 2 is the original drawing. Keep all unrelated parts of image 1 unchanged. "
        index = 3
    else:
        start = ("Colorize image 1, keeping its exact eyes, smile, fingers, pose and original contours. " if mode != "redraw" else
                 "Repaint image 1 as a polished color illustration, retaining its identity, expression, pose and proportions. ")
        index = 2
    style = "Use dimensional soft cel shading and natural coherent colors. "
    if has_reference:
        treatment = {"style":"painting technique and shading", "palette":"color harmony from the color swatches", "light":"light direction, shadow softness and highlights; choose natural colors independently", "all":"painting technique, lighting and color harmony"}[role]
        style = f"Image {index} supplies only {treatment}. Never copy its person, pose, body, garment or background. "
        index += 1
    anchor = f"Image {index} is a chapter color guide: match the colors of the same characters and garments, not their pose or layout. " if has_anchor else ""
    return (start+style+anchor+"Preserve the source hairstyle, costume, garment coverage, text and frame layout. "
            "Use a consistent base skin tone per person, preserving dimensional shadows. Treat skin, cloth, hair and metal as different materials. "
            "Keep cropped endpoints; add no limbs or objects. Output only image 1. "+
            ("Character color notes: "+palette[:400]+". " if palette else "")+notes[:500])


class Renderer:
    def __init__(self, models, notify=lambda *a, **k: None):
        self.models = Path(models)
        self.notify = notify
        self.pipe = None
        self.key = None
        self.embeds = {}
        self.protector = None
        self.locator = None
        torch.set_num_threads(8)
        torch.backends.cuda.matmul.allow_tf32 = True

    def release(self):
        self.pipe = None
        self.key = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def flux(self, prompt, precision):
        from diffusers import Flux2KleinPipeline, Flux2Transformer2DModel, BitsAndBytesConfig
        from transformers import Qwen3ForCausalLM, Qwen2TokenizerFast
        from transformers import BitsAndBytesConfig as TextQuant
        model = self.models / "flux2-klein-4b"
        cache_key = (prompt, precision)
        if cache_key not in self.embeds:
            self.release()
            self.notify("text")
            kwargs = {}
            if precision == "nf4":
                kwargs["quantization_config"] = TextQuant(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
            encoder = Qwen3ForCausalLM.from_pretrained(model / "text_encoder", local_files_only=True,
                torch_dtype=torch.bfloat16, device_map={"": "cuda:0"}, low_cpu_mem_usage=True, **kwargs)
            tokenizer = Qwen2TokenizerFast.from_pretrained(model / "tokenizer", local_files_only=True)
            with torch.inference_mode():
                value = Flux2KleinPipeline._get_qwen3_prompt_embeds(encoder, tokenizer, prompt,
                    dtype=torch.bfloat16, device=torch.device("cuda"), max_sequence_length=512)
            self.embeds[cache_key] = value.cpu()
            if len(self.embeds)>8:
                self.embeds.pop(next(iter(self.embeds)))
            del encoder, tokenizer, value
            gc.collect(); torch.cuda.empty_cache()
        if self.key != ("flux", precision):
            self.release()
            self.notify("model")
            kwargs = {}
            if precision == "nf4":
                kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
            transformer = Flux2Transformer2DModel.from_pretrained(model / "transformer", local_files_only=True,
                torch_dtype=torch.bfloat16, device_map={"": "cuda:0"}, low_cpu_mem_usage=True, **kwargs)
            self.pipe = Flux2KleinPipeline.from_pretrained(model, transformer=transformer, text_encoder=None,
                tokenizer=None, torch_dtype=torch.bfloat16, local_files_only=True)
            self.pipe.vae.to("cuda")
            self.pipe.vae.enable_tiling()
            self.pipe.set_progress_bar_config(disable=True)
            self.key = ("flux", precision)
        return self.pipe, self.embeds[cache_key].to("cuda")

    def render(self, source, options):
        if options.get("correction") in ("face", "hands"):
            return self.correct_regions(source, options)
        return self.render_image(source, options)

    def correct_regions(self, source, options):
        from .anatomy import RegionLocator, context_box, composite_context
        import tempfile
        began = time.perf_counter()
        base_path = options.get("base", "")
        if not base_path or not Path(base_path).is_file():
            raise FileNotFoundError("The image to correct is missing.")
        result = image(base_path)
        if result.size != source.size:
            raise ValueError("Correction image dimensions do not match the original")
        kind = options["correction"]
        self.notify("region_detection")
        if self.locator is None:
            self.locator = RegionLocator(self.models)
        boxes = self.locator.find(source, kind)
        if not boxes:
            raise ValueError("No suitable face or hand was located. No image was changed.")
        passes = []
        for box in boxes:
            context = context_box(box,source.size)
            crop = source.crop(context)
            scale = 784/max(crop.size)
            size = tuple(max(64,round(v*scale/16)*16) for v in crop.size)
            crop = crop.resize(size,Image.Resampling.LANCZOS)
            with tempfile.TemporaryDirectory(prefix="context-",dir=Path(base_path).parent) as folder:
                guide = Path(folder)/"guide.png"
                result.crop(context).resize(size,Image.Resampling.LANCZOS).save(guide)
                opts = {**options, "correction":"", "base":"", "generation":"color", "reference":"",
                        "anchor":str(guide), "fidelity":"strict", "protect_paper":False, "protect_text":False,
                        "notes":"The color guide is the colored version of this exact drawing. Colorize the ORIGINAL shapes and proportions of image 1. Do not enlarge eyes, irises, mouth or fingers. Keep the same colors as the guide.", "palette_notes":""}
                patch, report = self.render_image(crop,opts)
            result = composite_context(result,patch,source,box,context,kind)
            passes.append({"box":box,"context":context,"render":report})
        mask, text_boxes = None, []
        if options.get("protect_text", True):
            from .protection import TextProtector
            if self.protector is None:
                self.protector = TextProtector(self.models)
            mask,text_boxes = self.protector.regions(source)
        from .protection import finish
        result,audit = finish(source,result,mask,preserve_paper=options.get("protect_paper",True))
        metadata = {**passes[-1]["render"], **audit, "correction":kind, "base_sha256":sha(base_path),
                    "source_size":source.size, "context_passes":passes, "detector":"microsoft/Florence-2-base",
                    "detector_revision":"5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac",
                    "seconds_total":round(time.perf_counter()-began,3), "protected_text_regions":len(text_boxes),
                    "text_boxes":text_boxes, "reference_sha256":"", "anchor_sha256":""}
        metadata["warnings"] = list(dict.fromkeys(audit["warnings"]+["check_local_anatomy_edit"]))
        return result,metadata

    def render_image(self, source, options):
        if not torch.cuda.is_available():
            raise RuntimeError("FLUX rendering needs a CUDA GPU. Existing images can still be viewed and exported without it.")
        began = time.perf_counter()
        text_mask, text_boxes = None, []
        if options.get("protect_text", True):
            from .protection import TextProtector
            if self.protector is None:
                self.protector = TextProtector(self.models)
            self.notify("text_detection")
            text_mask, text_boxes = self.protector.regions(source)
        reference = options.get("reference", "") if options.get("generation") != "color" else ""
        correction = options.get("correction", "")
        base = options.get("base", "") if correction else ""
        role = options.get("reference_role", "style")
        if role not in ("style", "palette", "light", "all"):
            raise ValueError("Unknown reference role")
        if correction and (not base or not Path(base).is_file()):
            raise FileNotFoundError("The image to correct is missing.")
        anchor = options.get("anchor", "")
        if reference and not Path(reference).is_file():
            raise FileNotFoundError("Reference image is missing: " + reference)
        if anchor and not Path(anchor).is_file():
            raise FileNotFoundError("Chapter color reference is missing: " + anchor)
        mode = options.get("generation", "color")
        if mode not in ("color", "reference", "redraw"):
            raise ValueError("Unknown generation mode")
        if mode == "reference" and not reference:
            raise ValueError("Add a reference or choose automatic coloring.")
        backend = options.get("renderer", "flux")
        backend = "flux"
        precision = options.get("precision", "auto")
        if precision == "auto":
            precision = self.key[1] if self.key and self.key[0]=="flux" else (
                "bf16" if torch.cuda.mem_get_info()[0] > 12*2**30 else "nf4")
        source_input, content_box = fit(source, area=int(options.get("pixels", 1024*1024)))
        primary = fit(image(base), area=int(options.get("pixels", 1024*1024)))[0] if base else source_input
        if primary.size != source_input.size:
            raise ValueError("Correction source dimensions do not match the original")
        refs = [source_input] if correction else []
        if reference:
            refs.append(reference_image(reference, role))
        if anchor:
            refs.append(fit(image(anchor), area=640*640, max_side=896)[0])
        seed = int(options.get("seed", 20261105))
        generator = torch.Generator(device="cuda").manual_seed(seed)
        steps = 4
        def step(_pipe, i, _t, values):
            self.notify("step", step=i+1, total=steps)
            return values
        torch.cuda.reset_peak_memory_stats()
        prompt = instruction(mode, bool(reference), bool(anchor), options.get("notes", ""), role, correction, options.get("palette_notes", ""))
        with torch.inference_mode():
            if backend == "flux":
                pipe, embeds = self.flux(prompt, precision)
                args = {}
                freedom = max(.2,min(1.,float(options.get("freedom", 1.0)))) if mode == "redraw" else {"strict": .75, "balanced": .8, "creative": .95}.get(options.get("fidelity"), .8)
                if correction:
                    freedom = .65 if correction in ("face", "hands") else .55
                if freedom < .99:
                    # Flow-matching img2img initialization, not an output blend or prompt-only slider.
                    from diffusers.pipelines.flux2.pipeline_flux2_klein import compute_empirical_mu
                    processed = pipe.image_processor.preprocess(primary,
                        height=source_input.height, width=source_input.width).to("cuda", torch.bfloat16)
                    source_latents = pipe._encode_vae_image(processed, generator)
                    sigmas = np.linspace(max(.1, freedom), max(.1, freedom)/steps, steps)
                    mu = compute_empirical_mu(source_latents.shape[2]*source_latents.shape[3], steps)
                    pipe.scheduler.set_timesteps(sigmas=sigmas, device="cuda", mu=mu)
                    start_sigma = pipe.scheduler.sigmas[0]
                    noise = torch.randn(source_latents.shape, device="cuda", dtype=torch.bfloat16, generator=generator)
                    args = {"latents": (1-start_sigma)*source_latents + start_sigma*noise, "sigmas": sigmas}
                self.notify("render")
                generated = pipe(image=[primary]+refs, prompt_embeds=embeds, width=source_input.width,
                    height=source_input.height, num_inference_steps=steps, guidance_scale=1.,
                    generator=generator, callback_on_step_end=step, **args).images[0]
        generated = generated.crop(content_box).resize(source.size, Image.Resampling.LANCZOS)
        from .protection import finish
        generated, audit = finish(source,generated,text_mask,preserve_gutters=mode!="redraw", preserve_paper=options.get("protect_paper", True))
        metadata = {
            "contract": CONTRACT, "model": MODELS[backend][0], "revision": MODELS[backend][1],
            "backend": backend, "mode": mode, "correction": correction, "base_sha256": sha(base), "reference_role": role, "fidelity": options.get("fidelity", "balanced"), "precision": precision, "seed": seed,
            "reference_sha256": sha(reference), "anchor_sha256": sha(anchor), "prompt": prompt,
            "source_size": source.size, "working_size": source_input.size, "steps": steps,
            "freedom": freedom if backend=="flux" else None, "seconds_total": round(time.perf_counter()-began, 3),
            "peak_allocated_GiB": round(torch.cuda.max_memory_allocated()/2**30, 3),
            "peak_reserved_GiB": round(torch.cuda.max_memory_reserved()/2**30, 3),
            "gpu": torch.cuda.get_device_name(), "manual_masks": False,
            "protected_text_regions":len(text_boxes), "text_boxes":text_boxes, **audit,
        }
        from importlib.metadata import version
        metadata["runtime"] = {name:version(name) for name in ("torch","diffusers","transformers","bitsandbytes")}
        metadata["limits"] = ["fine_details_can_change", "palette_reference_is_guidance_not_identity_tracking"]
        return generated, metadata
