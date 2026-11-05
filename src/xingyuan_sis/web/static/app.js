(() => {
  "use strict";

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  function openDialog(id) {
    const dialog = document.getElementById(id);
    if (!(dialog instanceof HTMLDialogElement) || dialog.open) return;
    dialog.showModal();
    document.body.dataset.dialogActive = "true";
  }

  function closeDialog(dialog) {
    if (!(dialog instanceof HTMLDialogElement)) return;
    dialog.close();
    if (!document.querySelector("dialog[open]")) delete document.body.dataset.dialogActive;
  }

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;

    const opener = target.closest("[data-dialog-open]");
    if (opener) {
      event.preventDefault();
      openDialog(opener.getAttribute("data-dialog-open"));
      return;
    }

    const closer = target.closest("[data-dialog-close]");
    if (closer) {
      event.preventDefault();
      closeDialog(closer.closest("dialog"));
      return;
    }

    const dismiss = target.closest("[data-dismiss]");
    if (dismiss) {
      dismiss.closest(".toast")?.remove();
    }
  });

  document.querySelectorAll("dialog").forEach((dialog) => {
    dialog.addEventListener("close", () => {
      if (!document.querySelector("dialog[open]")) delete document.body.dataset.dialogActive;
    });
    dialog.addEventListener("click", (event) => {
      if (event.target !== dialog) return;
      const rect = dialog.getBoundingClientRect();
      const outside = event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom;
      if (outside) closeDialog(dialog);
    });
  });
  document.querySelectorAll("[data-auto-open]").forEach((dialog) => openDialog(dialog.id));

  document.querySelectorAll("[data-password-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = document.getElementById(button.getAttribute("data-password-toggle"));
      if (!input) return;
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      button.textContent = show ? "HIDE" : "SHOW";
      button.setAttribute("aria-label", show ? "隐藏密码" : "显示密码");
    });
  });

  document.querySelectorAll("form").forEach((form) => {
    const family = form.querySelector("[data-family-select]");
    const branch = form.querySelector("[data-branch-select]");
    if (!family || !branch) return;
    const options = [...branch.querySelectorAll("option[data-family]")];
    const syncBranches = (reset) => {
      options.forEach((option) => {
        option.hidden = option.dataset.family !== family.value;
      });
      if (reset) branch.value = "";
      if (branch.selectedOption?.hidden) branch.value = "";
    };
    syncBranches(false);
    family.addEventListener("change", () => syncBranches(true));
  });

  document.addEventListener("keydown", (event) => {
    const active = document.activeElement;
    const isTyping = active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement || active instanceof HTMLSelectElement || active?.isContentEditable;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      const input = [...document.querySelectorAll(".global-search input, .filter-search input")].find((item) => item.getClientRects().length);
      input?.focus();
      return;
    }
    if (isTyping || document.querySelector("dialog[open]")) return;
    if (event.key === "/") {
      event.preventDefault();
      const filterInput = document.querySelector(".filter-search input");
      const globalInput = document.querySelector(".global-search input");
      const input = filterInput?.getClientRects().length ? filterInput : globalInput;
      input?.focus();
    }
    if (event.key.toLowerCase() === "n") {
      const button = document.querySelector("[data-new-student]");
      if (button) {
        event.preventDefault();
        button.click();
      }
    }
  });

  function initStarfield(canvas) {
    const fallback = () => {
      canvas.dataset.state = "fallback";
      canvas.style.display = "none";
    };
    const gl = canvas.getContext("webgl2", {
      alpha: true,
      antialias: false,
      depth: false,
      stencil: false,
      powerPreference: "low-power",
    });
    if (!gl) {
      fallback();
      return;
    }

    const vertexSource = `#version 300 es
      precision highp float;
      out vec2 v_uv;
      void main() {
        vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
        v_uv = p;
        gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
      }
    `;
    const fragmentSource = `#version 300 es
      precision highp float;
      in vec2 v_uv;
      out vec4 outColor;
      uniform vec2 u_resolution;
      uniform vec2 u_pointer;
      uniform float u_time;

      float hash21(vec2 p) {
        p = fract(p * vec2(123.34, 456.21));
        p += dot(p, p + 45.32);
        return fract(p.x * p.y);
      }
      float valueNoise(vec2 p) {
        vec2 i = floor(p);
        vec2 f = fract(p);
        f = f * f * (3.0 - 2.0 * f);
        return mix(mix(hash21(i), hash21(i + vec2(1., 0.)), f.x),
                   mix(hash21(i + vec2(0., 1.)), hash21(i + vec2(1.)), f.x), f.y);
      }
      mat2 rotate2d(float a) {
        float c = cos(a), s = sin(a);
        return mat2(c, -s, s, c);
      }
      float stars(vec2 uv, float scale, float threshold) {
        vec2 grid = uv * scale;
        vec2 id = floor(grid);
        vec2 cell = fract(grid) - .5;
        float seed = hash21(id);
        vec2 offset = vec2(hash21(id + 1.3), hash21(id + 7.1)) - .5;
        float d = length(cell - offset * .7);
        float core = smoothstep(.045, .002, d) * step(threshold, seed);
        return core * (.55 + .45 * sin(u_time * .8 + seed * 18.));
      }
      void main() {
        vec2 uv = gl_FragCoord.xy / u_resolution.xy;
        float aspect = u_resolution.x / max(u_resolution.y, 1.);
        vec2 p = uv - .5;
        p.x *= aspect;
        vec2 mouse = u_pointer - .5;
        mouse.x *= aspect;
        vec2 delta = p - mouse;
        float proximity = exp(-length(delta) * 4.5);
        p += vec2(-delta.y, delta.x) * proximity * .16;

        float t = u_time * .055;
        vec2 q = rotate2d(-.18 + sin(t) * .05) * p;
        float n = valueNoise(q * 2.6 + vec2(t, -t * .6));
        n += .5 * valueNoise(q * 5.2 - vec2(t * .7, t));
        float field = sin(q.x * 3.4 + t * 3.) + cos(q.y * 4.1 - t * 2.) + n;
        float contour = pow(1.0 - abs(sin(field * 4.2)), 22.0);
        float energy = exp(-abs(field - 1.1) * 2.4);

        vec3 color = vec3(.019, .031, .063);
        color += vec3(.015, .075, .10) * n * .8;
        color += vec3(.06, .36, .42) * contour * .34;
        color += vec3(.70, .83, .02) * proximity * contour * .34;
        color += vec3(.16, .025, .12) * energy * .18;

        float star = stars(uv + vec2(t * .008, 0.), 34., .82);
        star += stars(uv * rotate2d(.3) - vec2(0., t * .006), 57., .9) * .7;
        star += stars(uv + vec2(0., t * .004), 83., .95) * .5;
        color += vec3(.86, .94, .91) * star;

        float vignette = smoothstep(.95, .25, length((uv - .5) * vec2(.85, 1.)));
        color *= .62 + .38 * vignette;
        outColor = vec4(color, 1.0);
      }
    `;

    function compile(type, source) {
      const shader = gl.createShader(type);
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        gl.deleteShader(shader);
        throw new Error("shader unavailable");
      }
      return shader;
    }

    let program;
    try {
      const vertex = compile(gl.VERTEX_SHADER, vertexSource);
      const fragment = compile(gl.FRAGMENT_SHADER, fragmentSource);
      program = gl.createProgram();
      gl.attachShader(program, vertex);
      gl.attachShader(program, fragment);
      gl.linkProgram(program);
      gl.deleteShader(vertex);
      gl.deleteShader(fragment);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error("shader unavailable");
    } catch {
      fallback();
      return;
    }

    gl.useProgram(program);
    const resolutionUniform = gl.getUniformLocation(program, "u_resolution");
    const pointerUniform = gl.getUniformLocation(program, "u_pointer");
    const timeUniform = gl.getUniformLocation(program, "u_time");
    const pointer = { x: .5, y: .5, targetX: .5, targetY: .5 };
    let raf = 0;
    let lastFrame = 0;
    let start = performance.now();
    let disposed = false;

    function resize() {
      const rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      let dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      const pixels = rect.width * rect.height * dpr * dpr;
      if (pixels > 1500000) dpr *= Math.sqrt(1500000 / pixels);
      const width = Math.max(1, Math.round(rect.width * dpr));
      const height = Math.max(1, Math.round(rect.height * dpr));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
        gl.viewport(0, 0, width, height);
      }
    }

    function draw(now) {
      resize();
      pointer.x += (pointer.targetX - pointer.x) * .08;
      pointer.y += (pointer.targetY - pointer.y) * .08;
      gl.uniform2f(resolutionUniform, canvas.width, canvas.height);
      gl.uniform2f(pointerUniform, pointer.x, pointer.y);
      gl.uniform1f(timeUniform, reducedMotion.matches ? 0 : (now - start) / 1000);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      canvas.dataset.state = "ready";
      canvas.dataset.frameTime = String(Math.round(now - start));
    }

    function frame(now) {
      if (disposed) return;
      raf = requestAnimationFrame(frame);
      if (now - lastFrame < 1000 / 30) return;
      lastFrame = now;
      draw(now);
    }

    function syncPlayback() {
      cancelAnimationFrame(raf);
      if (document.hidden) return;
      if (reducedMotion.matches) {
        draw(performance.now());
      } else {
        start = performance.now() - Number(canvas.dataset.frameTime || 0);
        raf = requestAnimationFrame(frame);
      }
    }

    const parent = canvas.parentElement;
    parent?.addEventListener("pointermove", (event) => {
      const rect = canvas.getBoundingClientRect();
      pointer.targetX = (event.clientX - rect.left) / Math.max(rect.width, 1);
      pointer.targetY = 1 - (event.clientY - rect.top) / Math.max(rect.height, 1);
    }, { passive: true });
    parent?.addEventListener("pointerleave", () => {
      pointer.targetX = .5;
      pointer.targetY = .5;
    });
    document.addEventListener("visibilitychange", syncPlayback);
    reducedMotion.addEventListener("change", syncPlayback);
    new ResizeObserver(() => {
      resize();
      if (reducedMotion.matches) draw(performance.now());
    }).observe(canvas);
    canvas.addEventListener("webglcontextlost", (event) => {
      event.preventDefault();
      disposed = true;
      cancelAnimationFrame(raf);
      fallback();
    });
    syncPlayback();
  }

  document.querySelectorAll("#starfield").forEach(initStarfield);
})();
