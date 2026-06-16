module.exports = async (kernel) => {
  const port = await kernel.port()
  const lowVramEnabled = "{{args && (args.low_vram === true || args.low_vram === 'true' || args.low_vram === 1 || args.low_vram === '1') ? '1' : '0'}}"
  const lowVramArg = "{{args && (args.low_vram === true || args.low_vram === 'true' || args.low_vram === 1 || args.low_vram === '1') ? '--low_vram' : ''}}"
  const wslMode = "{{args && (args.low_vram === true || args.low_vram === 'true' || args.low_vram === 1 || args.low_vram === '1') ? 'low' : 'standard'}}"
  const rembgModel = "{{envs.PIXAL3D_REMBG_MODEL ? envs.PIXAL3D_REMBG_MODEL : ''}}"
  const hfToken = rembgModel ? "{{envs.HF_TOKEN ? envs.HF_TOKEN : ''}}" : ""
  const hubToken = rembgModel ? "{{envs.HUGGING_FACE_HUB_TOKEN ? envs.HUGGING_FACE_HUB_TOKEN : (envs.HF_TOKEN ? envs.HF_TOKEN : '')}}" : ""
  const hfEnv = rembgModel ? {
    PIXAL3D_REMBG_MODEL: rembgModel,
    HF_TOKEN: hfToken,
    HUGGING_FACE_HUB_TOKEN: hubToken
  } : {
    HF_TOKEN: "",
    HUGGING_FACE_HUB_TOKEN: ""
  }
  const wslPassThrough = rembgModel ? ":PIXAL3D_REMBG_MODEL/u:HF_TOKEN/u:HUGGING_FACE_HUB_TOKEN/u" : ":HF_TOKEN/u:HUGGING_FACE_HUB_TOKEN/u"
  const existingWslEnv = "{{envs.WSLENV ? envs.WSLENV : ''}}"
  const wslEnv = {
    ...hfEnv,
    WSLENV: existingWslEnv ? `${existingWslEnv}${wslPassThrough}` : wslPassThrough.slice(1)
  }

  if (kernel.platform === "win32") {
    return {
      daemon: true,
      run: [
        {
          method: "shell.run",
          params: {
            env: wslEnv,
            message: `wsl.exe -d Ubuntu --cd "{{cwd}}" -- bash scripts/start_wsl.sh ${port} ${wslMode}`,
            on: [{
              event: "/(http:\\/\\/[0-9.:]+)/",
              done: true
            }]
          }
        },
        {
          when: "{{input.event && input.event[1]}}",
          method: "local.set",
          params: {
            url: "{{input.event[1]}}"
          }
        }
      ]
    }
  }

  return {
    daemon: true,
    run: [
      {
        method: "shell.run",
        params: {
          venv: "env",
          path: "app",
          env: {
            ...hfEnv,
            ATTN_BACKEND: "flash_attn_3",
            SPARSE_ATTN_BACKEND: "flash_attn_3",
            SPARSE_CONV_BACKEND: "flex_gemm",
            LOW_VRAM: lowVramEnabled,
            GRADIO_ANALYTICS_ENABLED: "False",
            HF_HUB_DISABLE_IMPLICIT_TOKEN: rembgModel ? "" : "1",
            GRADIO_SERVER_NAME: "127.0.0.1",
            GRADIO_SERVER_PORT: `${port}`,
            PYTORCH_CUDA_ALLOC_CONF: lowVramEnabled === "1" ? "expandable_segments:True,garbage_collection_threshold:0.8,max_split_size_mb:512" : "garbage_collection_threshold:0.8",
            OPENCV_IO_ENABLE_OPENEXR: "1"
          },
          message: [
            "python ../scripts/check_hf_access.py",
            `python ../launch.py --host 127.0.0.1 --port ${port} ${lowVramArg}`
          ],
          on: [{
            event: "/(http:\\/\\/[0-9.:]+)/",
            done: true
          }]
        }
      },
      {
        when: "{{input.event && input.event[1]}}",
        method: "local.set",
        params: {
          url: "{{input.event[1]}}"
        }
      }
    ]
  }
}
