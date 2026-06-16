import argparse
import gc
import functools
import os
import sys
import threading
import types


gpu_job_lock = threading.Lock()
DEFAULT_REMBG_MODEL = "ZhengPeng7/BiRefNet"
GATED_REMBG_MODEL = "briaai/RMBG-2.0"


def allow_local_gradio_file_urls(host: str):
    """Let Gradio re-fetch files from this local server during API preprocessing."""
    try:
        from gradio import processing_utils
    except Exception as exc:
        print(f"[Gradio] Could not patch local file URL whitelist: {exc}", flush=True)
        return

    whitelist = getattr(processing_utils, "PUBLIC_HOSTNAME_WHITELIST", None)
    if not isinstance(whitelist, list):
        return

    local_hosts = [host, "127.0.0.1", "localhost", "::1"]
    added = []
    for hostname in local_hosts:
        if hostname and hostname not in whitelist:
            whitelist.append(hostname)
            added.append(hostname)

    if added:
        print(f"[Gradio] Allowing local file URLs for: {', '.join(added)}", flush=True)


def prefer_public_rembg_model():
    """Use a public background-removal model unless the user explicitly opts in."""
    requested_model = os.environ.get("PIXAL3D_REMBG_MODEL")
    if not requested_model:
        os.environ["HF_TOKEN"] = ""
        os.environ["HUGGING_FACE_HUB_TOKEN"] = ""
        os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")

    try:
        import pixal3d.pipelines.rembg as rembg
    except Exception as exc:
        print(f"[RMBG] Could not patch background-removal model selection: {exc}", flush=True)
        return

    birefnet_cls = getattr(rembg, "BiRefNet", None)
    if birefnet_cls is None or getattr(birefnet_cls, "_pinokio_public_default", False):
        return

    original_init = birefnet_cls.__init__

    @functools.wraps(original_init)
    def init_with_public_default(self, model_name=DEFAULT_REMBG_MODEL, *args, **kwargs):
        if requested_model:
            model_name = requested_model
        elif model_name == GATED_REMBG_MODEL:
            model_name = DEFAULT_REMBG_MODEL
            print(
                f"[RMBG] Using public {DEFAULT_REMBG_MODEL} instead of gated {GATED_REMBG_MODEL}. "
                f"Set PIXAL3D_REMBG_MODEL={GATED_REMBG_MODEL} to opt in.",
                flush=True,
            )

        return original_init(self, model_name=model_name, *args, **kwargs)

    birefnet_cls.__init__ = init_with_public_default
    birefnet_cls._pinokio_public_default = True


def force_natten_flex_on_blackwell():
    """Avoid NATTEN CUTLASS kernels that are not usable on RTX 50/sm_120 yet."""
    try:
        import torch

        if not torch.cuda.is_available():
            return

        major, _ = torch.cuda.get_device_capability(0)
        if major < 12:
            return

        import natten.backends as natten_backends
        import natten.functional as natten_functional
        import natten as natten_module
    except Exception as exc:
        print(f"[NATTEN] Could not patch backend selection: {exc}", flush=True)
        return

    original_choose_backend = natten_backends.choose_backend
    original_choose_fmha_backend = natten_backends.choose_fmha_backend
    fna_backends_to_replace = {"cutlass-fna", "hopper-fna", "blackwell-fna"}
    fmha_backends_to_replace = {"cutlass-fmha", "hopper-fmha", "blackwell-fmha"}

    def is_blackwell_tensor(tensor):
        if not getattr(tensor, "is_cuda", False):
            return False
        device_index = tensor.device.index
        if device_index is None:
            device_index = torch.cuda.current_device()
        device_major, _ = torch.cuda.get_device_capability(device_index)
        return device_major >= 12

    def choose_backend(query, key, value, torch_compile=False):
        if is_blackwell_tensor(query):
            return "flex-fna"
        return original_choose_backend(query, key, value, torch_compile=torch_compile)

    def choose_fmha_backend(query, key, value, torch_compile=False):
        if is_blackwell_tensor(query):
            return "flex-fmha"
        return original_choose_fmha_backend(query, key, value, torch_compile=torch_compile)

    def pair(value):
        if isinstance(value, int):
            return (value, value)
        return tuple(value)

    def torch_na2d_mixed_head_dim(query, key, value, kernel_size, stride=1, dilation=1, is_causal=False, scale=None):
        if pair(stride) != (1, 1):
            raise ValueError("Blackwell mixed-head NAF fallback only supports stride=1.")
        if is_causal not in (False, None, (False, False)):
            raise ValueError("Blackwell mixed-head NAF fallback does not support causal attention.")

        import torch.nn.functional as F

        kernel_h, kernel_w = pair(kernel_size)
        dilation_h, dilation_w = pair(dilation)
        radius_h = kernel_h // 2
        radius_w = kernel_w // 2
        pad_h = radius_h * dilation_h
        pad_w = radius_w * dilation_w
        scale = scale if scale is not None else query.shape[-1] ** -0.5

        batch, height, width, heads, value_dim = value.shape
        tile_rows = max(1, int(os.environ.get("PIXAL3D_NATTEN_FALLBACK_TILE_ROWS", "64")))
        query_f = query.float()
        key_pad = F.pad(key.permute(0, 3, 4, 1, 2), (pad_w, pad_w, pad_h, pad_h))
        value_pad = F.pad(value.permute(0, 3, 4, 1, 2), (pad_w, pad_w, pad_h, pad_h))
        valid_pad = F.pad(
            torch.ones(1, 1, 1, height, width, device=query.device, dtype=torch.bool),
            (pad_w, pad_w, pad_h, pad_h),
        )

        output = torch.empty((batch, height, width, heads, value_dim), device=query.device, dtype=value.dtype)

        for row_start in range(0, height, tile_rows):
            row_end = min(row_start + tile_rows, height)
            tile_height = row_end - row_start
            query_tile = query_f[:, row_start:row_end]
            max_score = torch.full((batch, tile_height, width, heads), -torch.inf, device=query.device, dtype=torch.float32)
            normalizer = torch.zeros((batch, tile_height, width, heads), device=query.device, dtype=torch.float32)
            output_tile = torch.zeros((batch, tile_height, width, heads, value_dim), device=query.device, dtype=value.dtype)

            for offset_h in range(kernel_h):
                src_h = offset_h * dilation_h + row_start
                for offset_w in range(kernel_w):
                    src_w = offset_w * dilation_w
                    key_shift = key_pad[..., src_h:src_h + tile_height, src_w:src_w + width].permute(0, 3, 4, 1, 2)
                    value_shift = value_pad[..., src_h:src_h + tile_height, src_w:src_w + width].permute(0, 3, 4, 1, 2)
                    valid = valid_pad[..., src_h:src_h + tile_height, src_w:src_w + width].permute(0, 3, 4, 1, 2).squeeze(-1)
                    score = (query_tile * key_shift.float()).sum(dim=-1) * scale
                    score = score.masked_fill(~valid, -torch.inf)
                    next_max = torch.maximum(max_score, score)
                    old_weight = torch.exp(max_score - next_max).nan_to_num(0.0)
                    new_weight = torch.exp(score - next_max).nan_to_num(0.0)
                    output_tile = (
                        output_tile * old_weight.to(output_tile.dtype).unsqueeze(-1)
                        + value_shift * new_weight.to(output_tile.dtype).unsqueeze(-1)
                    )
                    normalizer = normalizer * old_weight + new_weight
                    max_score = next_max

            output[:, row_start:row_end] = output_tile / normalizer.clamp_min(1e-20).to(output_tile.dtype).unsqueeze(-1)
        return output

    def get_call_arg(args, kwargs, name, index, default=None):
        if len(args) > index:
            return args[index]
        return kwargs.get(name, default)

    def wrap_attention_function(name, fn, flex_backend, backends_to_replace):
        @functools.wraps(fn)
        def wrapped(query, *args, **kwargs):
            print(f"[NATTEN WRAPPER] {name} called. query shape: {query.shape}, backend: {kwargs.get('backend')}, Blackwell: {is_blackwell_tensor(query)}", flush=True)
            if (
                name == "na2d"
                and is_blackwell_tensor(query)
                and kwargs.get("backend") in backends_to_replace
            ):
                key = get_call_arg(args, kwargs, "key", 0)
                value = get_call_arg(args, kwargs, "value", 1)
                kernel_size = get_call_arg(args, kwargs, "kernel_size", 2)
                print(f"[NATTEN WRAPPER] key shape: {getattr(key, 'shape', None)}, value shape: {getattr(value, 'shape', None)}, kernel_size: {kernel_size}", flush=True)
                if (
                    key is not None
                    and value is not None
                    and kernel_size is not None
                    and getattr(value, "shape", [None])[-1] != query.shape[-1]
                ):
                    print(f"[NATTEN WRAPPER] Entering mixed head dim fallback!", flush=True)
                    try:
                        res = torch_na2d_mixed_head_dim(
                            query,
                            key,
                            value,
                            kernel_size,
                            stride=get_call_arg(args, kwargs, "stride", 3, 1),
                            dilation=get_call_arg(args, kwargs, "dilation", 4, 1),
                            is_causal=get_call_arg(args, kwargs, "is_causal", 5, False),
                            scale=get_call_arg(args, kwargs, "scale", 6, None),
                        )
                        print(f"[NATTEN WRAPPER] Fallback executed successfully, output shape: {res.shape}", flush=True)
                        return res
                    except Exception as e:
                        print(f"[NATTEN WRAPPER] Fallback failed: {e}", flush=True)
                        import traceback
                        traceback.print_exc()
                        raise e
            if is_blackwell_tensor(query) and kwargs.get("backend") in backends_to_replace:
                print(f"[NATTEN WRAPPER] Forcing flex_backend '{flex_backend}'", flush=True)
                kwargs["backend"] = flex_backend
            return fn(query, *args, **kwargs)

        return wrapped

    natten_backends.choose_backend = choose_backend
    natten_backends.choose_fmha_backend = choose_fmha_backend
    natten_functional.choose_backend = choose_backend
    natten_functional.choose_fmha_backend = choose_fmha_backend
    for name in ("na1d", "na2d", "na3d"):
        wrapped = wrap_attention_function(
            name,
            getattr(natten_functional, name),
            "flex-fna",
            fna_backends_to_replace,
        )
        setattr(natten_functional, name, wrapped)
        setattr(natten_module, name, wrapped)
    wrapped_attention = wrap_attention_function(
        "attention",
        natten_functional.attention,
        "flex-fmha",
        fmha_backends_to_replace,
    )
    natten_functional.attention = wrapped_attention
    natten_module.attention = wrapped_attention
    print("[NATTEN] Forcing Flex backend on Blackwell/sm_120 GPUs, including explicit CUTLASS calls.", flush=True)


def cleanup_cuda_state(app_module, endpoint_name: str):
    try:
        import torch

        pipeline = getattr(app_module, "pipeline", None)
        if getattr(app_module, "LOW_VRAM", False) and pipeline is not None:
            for attr in (
                "image_cond_model_ss",
                "image_cond_model_shape_512",
                "image_cond_model_shape_1024",
                "image_cond_model_tex_1024",
                "rembg_model",
            ):
                model = getattr(pipeline, attr, None)
                if model is not None and hasattr(model, "cpu"):
                    model.cpu()

            for model in getattr(pipeline, "models", {}).values():
                if hasattr(model, "cpu"):
                    model.cpu()
                if hasattr(model, "low_vram"):
                    model.low_vram = False

            moge_model = getattr(app_module, "moge_model", None)
            if moge_model is not None and hasattr(moge_model, "cpu"):
                moge_model.cpu()

            for env_light in getattr(app_module, "envmap", {}) or {}:
                value = app_module.envmap[env_light]
                if hasattr(value, "_nvdiffrec_envlight"):
                    del value._nvdiffrec_envlight
                image = getattr(value, "image", None)
                if image is not None and getattr(image, "is_cuda", False):
                    value.image = image.cpu()
        else:
            # Standard Mode: just clean up envmap structures
            for env_light in getattr(app_module, "envmap", {}) or {}:
                value = app_module.envmap[env_light]
                if hasattr(value, "_nvdiffrec_envlight"):
                    del value._nvdiffrec_envlight

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            if os.environ.get("PIXAL3D_CUDA_IPC_COLLECT", "0") == "1":
                torch.cuda.ipc_collect()
    except Exception as exc:
        print(f"[Cleanup] CUDA cleanup after {endpoint_name} skipped: {exc}", flush=True)


def stabilize_low_vram_image_conditioners(app_module):
    """Avoid repeated DINO/NAF CPU-GPU cycling that can destabilize Blackwell WSL runs."""
    try:
        import torch

        pipeline = getattr(app_module, "pipeline", None)
        if (
            not getattr(app_module, "LOW_VRAM", False)
            or pipeline is None
            or not torch.cuda.is_available()
            or torch.cuda.get_device_capability(0)[0] < 12
        ):
            return

        stabilized = []
        for attr in (
            "image_cond_model_ss",
            "image_cond_model_shape_512",
            "image_cond_model_shape_1024",
            "image_cond_model_tex_1024",
        ):
            model = getattr(pipeline, attr, None)
            if model is None or getattr(model, "_pinokio_cuda_persistent", False):
                continue

            if hasattr(model, "to"):
                model.to(torch.device("cuda"))

            original_cpu = getattr(model, "cpu", None)
            if callable(original_cpu):
                model._pinokio_original_cpu = original_cpu

                def stay_on_cuda(self):
                    return self

                model.cpu = types.MethodType(stay_on_cuda, model)

            model._pinokio_cuda_persistent = True
            stabilized.append(attr)

        if stabilized:
            print(
                "[Blackwell] Keeping low-VRAM image conditioners on GPU across runs: "
                + ", ".join(stabilized),
                flush=True,
            )
    except Exception as exc:
        print(f"[Blackwell] Image conditioner stabilization skipped: {exc}", flush=True)


def prepare_low_vram_endpoint(app_module):
    if not getattr(app_module, "LOW_VRAM", False):
        return
    init_models = getattr(app_module, "init_models", None)
    if callable(init_models):
        init_models()
    stabilize_low_vram_image_conditioners(app_module)


def is_fatal_cuda_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(
        pattern in message
        for pattern in (
            "device not ready",
            "cudacachingallocator.cpp",
            "internal assert failed",
            "illegal memory access",
            "unspecified launch failure",
            "device-side assert",
        )
    )


def serialize_gpu_apis(app_module):
    deferred_apis = getattr(app_module.app, "_deferred_apis", None)
    if not deferred_apis:
        return

    wrapped_apis = []
    endpoint_names = []
    for fn, api_kwargs in deferred_apis:
        endpoint_name = getattr(fn, "__name__", "api")
        endpoint_names.append(endpoint_name)
        api_kwargs = dict(api_kwargs)
        api_kwargs["concurrency_limit"] = 1
        api_kwargs["concurrency_id"] = "pixal3d-gpu"

        @functools.wraps(fn)
        def wrapped(*args, __fn=fn, __endpoint_name=endpoint_name, **kwargs):
            with gpu_job_lock:
                try:
                    prepare_low_vram_endpoint(app_module)
                    return __fn(*args, **kwargs)
                except Exception as exc:
                    import traceback
                    traceback.print_exc()
                    if isinstance(exc, RuntimeError) and is_fatal_cuda_error(exc):
                        print(
                            f"[CUDA] Fatal CUDA context error in {__endpoint_name}; exiting so Pinokio can restart cleanly: {exc}",
                            flush=True,
                        )
                        cleanup_cuda_state(app_module, __endpoint_name)
                        os._exit(0)

                    raise
                finally:
                    cleanup_cuda_state(app_module, __endpoint_name)

        wrapped_apis.append((wrapped, api_kwargs))

    app_module.app._deferred_apis = wrapped_apis
    print(f"[Gradio] Serialized GPU API queue: {', '.join(endpoint_names)}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Launch Pixal3D inside Pinokio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--low_vram", action="store_true")
    parser.add_argument("--preload", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("ATTN_BACKEND", "flash_attn_3")
    os.environ.setdefault("SPARSE_ATTN_BACKEND", os.environ["ATTN_BACKEND"])
    os.environ.setdefault("SPARSE_CONV_BACKEND", "flex_gemm")
    if args.low_vram:
        os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True,garbage_collection_threshold:0.8,max_split_size_mb:512"
    else:
        os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "garbage_collection_threshold:0.8"
    os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    os.environ["GRADIO_SERVER_NAME"] = args.host
    os.environ["GRADIO_SERVER_PORT"] = str(args.port)
    if args.low_vram:
        os.environ["LOW_VRAM"] = "1"

    sys.path.insert(0, os.getcwd())
    force_natten_flex_on_blackwell()
    allow_local_gradio_file_urls(args.host)
    import app as pixal3d_app

    prefer_public_rembg_model()
    pixal3d_app.LOW_VRAM = args.low_vram
    serialize_gpu_apis(pixal3d_app)
    if args.preload:
        pixal3d_app.init_models()

    print(f"Running on local URL: http://{args.host}:{args.port}", flush=True)
    pixal3d_app.app.launch(
        server_name=args.host,
        server_port=args.port,
        show_error=True,
        share=False,
        allowed_paths=[pixal3d_app.TMP_DIR],
    )
    threading.Event().wait()


if __name__ == "__main__":
    main()
