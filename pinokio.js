module.exports = {
  version: "7.0",
  title: "Pixal3D",
  description: "Pixel-aligned image-to-3D generation from Tencent ARC. On Windows this launcher runs the Linux CUDA stack through WSL Ubuntu.",
  menu: async (kernel, info) => {
    const installed = info.exists("app/env") || info.exists(".wsl_installed")
    const wslBlackwell = kernel.platform === "win32" && info.exists(".wsl_blackwell")
    const running = {
      install: info.running("install.js"),
      start: info.running("start.js"),
      update: info.running("update.js"),
      reset: info.running("reset.js")
    }

    if (running.install) {
      return [{
        default: true,
        icon: "fa-solid fa-plug",
        text: "Installing",
        href: "install.js"
      }]
    }

    if (installed) {
      if (running.start) {
        const local = info.local("start.js")
        if (local && local.url) {
          return [{
            default: true,
            icon: "fa-solid fa-rocket",
            text: "Open Web UI",
            href: local.url
          }, {
            icon: "fa-solid fa-terminal",
            text: "Terminal",
            href: "start.js"
          }]
        }

        return [{
          default: true,
          icon: "fa-solid fa-terminal",
          text: "Terminal",
          href: "start.js"
        }]
      }

      if (running.update) {
        return [{
          default: true,
          icon: "fa-solid fa-terminal",
          text: "Updating",
          href: "update.js"
        }]
      }

      if (running.reset) {
        return [{
          default: true,
          icon: "fa-solid fa-terminal",
          text: "Resetting",
          href: "reset.js"
        }]
      }

      const items = [{
        default: true,
        icon: "fa-solid fa-gauge-high",
        text: kernel.platform === "win32" ? "Start WSL Low VRAM" : "Start Low VRAM",
        href: "start.js",
        params: {
          low_vram: true
        }
      }]

      items.push({
        icon: "fa-solid fa-bolt",
        text: kernel.platform === "win32" ? "Start WSL Standard" : "Start Standard",
        href: "start.js",
        params: {
          low_vram: false
        }
      })

      if (kernel.platform === "win32") {
        items.push({
          icon: "fa-solid fa-wrench",
          text: "Fix GPU Timeout (TDR)",
          href: "fix_tdr.js"
        })
      }

      return items.concat([{
        icon: "fa-solid fa-globe",
        text: "Hosted Demo",
        href: "https://huggingface.co/spaces/TencentARC/Pixal3D"
      }, {
        icon: "fa-solid fa-plug",
        text: "Update",
        href: "update.js"
      }, {
        icon: "fa-solid fa-plug",
        text: "Install",
        href: "install.js"
      }, {
        icon: "fa-regular fa-circle-xmark",
        text: "Reset",
        href: "reset.js"
      }])
    }

    return [{
      default: true,
      icon: "fa-solid fa-plug",
      text: kernel.platform === "win32" ? "Install in WSL" : "Install",
      href: "install.js"
    }, {
      icon: "fa-solid fa-globe",
      text: "Hosted Demo",
      href: "https://huggingface.co/spaces/TencentARC/Pixal3D"
    }].concat(kernel.platform === "win32" ? [{
      icon: "fa-solid fa-wrench",
      text: "Fix GPU Timeout (TDR)",
      href: "fix_tdr.js"
    }] : [])
  }
}
