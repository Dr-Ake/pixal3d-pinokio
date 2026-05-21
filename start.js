module.exports = async (kernel) => {
  const port = await kernel.port()
  const lowVramEnabled = "{{args && (args.low_vram === true || args.low_vram === 'true' || args.low_vram === 1 || args.low_vram === '1') ? '1' : '0'}}"
  const lowVramArg = "{{args && (args.low_vram === true || args.low_vram === 'true' || args.low_vram === 1 || args.low_vram === '1') ? '--low_vram' : ''}}"
  const wslMode = "{{args && (args.low_vram === true || args.low_vram === 'true' || args.low_vram === 1 || args.low_vram === '1') ? 'low' : 'standard'}}"
  const requiredEnv = [{
    key: "HF_TOKEN",
    title: "Hugging Face token",
    description: "Pixal3D downloads briaai/RMBG-2.0, a gated model. Accept access at https://huggingface.co/briaai/RMBG-2.0, then enter a read token from https://huggingface.co/settings/tokens.",
    host: "huggingface.co"
  }]
  const hfEnv = {
    HF_TOKEN: "{{envs.HF_TOKEN}}",
    HUGGING_FACE_HUB_TOKEN: "{{envs.HF_TOKEN}}"
  }
  const wslEnv = {
    ...hfEnv,
    WSLENV: "{{envs.WSLENV ? envs.WSLENV + ':HF_TOKEN/u:HUGGING_FACE_HUB_TOKEN/u' : 'HF_TOKEN/u:HUGGING_FACE_HUB_TOKEN/u'}}"
  }

  if (kernel.platform === "win32") {
    return {
      env: requiredEnv,
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
          method: "local.set",
          params: {
            url: "{{input.event[1]}}"
          }
        }
      ]
    }
  }

  return {
    env: requiredEnv,
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
            GRADIO_SERVER_NAME: "127.0.0.1",
            GRADIO_SERVER_PORT: `${port}`,
            PYTORCH_CUDA_ALLOC_CONF: "expandable_segments:True",
            OPENCV_IO_ENABLE_OPENEXR: "1"
          },
          message: [
            `python ../launch.py --host 127.0.0.1 --port ${port} ${lowVramArg}`
          ],
          on: [{
            event: "/(http:\\/\\/[0-9.:]+)/",
            done: true
          }]
        }
      },
      {
        method: "local.set",
        params: {
          url: "{{input.event[1]}}"
        }
      }
    ]
  }
}
