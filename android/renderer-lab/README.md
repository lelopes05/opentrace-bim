# IngeTrazo Android — GPU compatibility lab

This independent **first-stage diagnostic APK** is not a port of IngeTrazo.
It is built on branch `android-ingetrazo-renderers` of the OpenTrace BIM repository; **main is not modified**.

- Three persistent backend choices: Qt QRhi + Vulkan, wgpu/Rust, Google Filament.
- Each correctly says **PENDENTE**: no false claim of implementing/rendering with it.
- Real OpenGL ES 3.0 rotating-triangle GPU test (a separate baseline, NOT one of the three options).
- Android version, ABIs, OpenGL ES driver support and advertised Vulkan capability.
- Does not package any IngeTrazo sources and does not alter the original upstream.

## Why this order?
Current IngeTrazo shaders use `#version 330 core` and request OpenGL 3.3 Core in `main.py`; Android's standard OpenGL API is ES. Qt's `QRhiWidget` supports Vulkan in C++, but rewriting the existing renderer, and integrating Rust wgpu or Filament within Qt Widgets, are distinct substantive projects. Selector UI alone cannot make these backends real.

## Build
Pushes to `android-ingetrazo-renderers` build via GitHub Actions and upload a **debug APK** as artifact `ingetrazo-gpu-lab-apk`. The APK is installable on Android 8+ (API 26+), and debug-signed by Gradle. The result is *not* the full modeling app.

## Next implementation gates
1. Verify Android compilation, install, pointer/keyboard input, EGL ES3 drawing on the target device.
2. Prepare a reproducible Qt/PySide6 arm64 Android build of unmodified IngeTrazo UI, isolating unsupported native Python libraries.
3. Implement geometry adapters and a **genuine** Qt QRhi Vulkan renderer.
4. Implement the Rust/wgpu and Filament renderer adapters with equivalent scene/camera/material semantics.
5. Swap renderers only before creating the main Qt window. Test same saved geometry and camera, compare crashes, FPS, and rendering correctness.

**PENDENTE:** APK build and device test until GitHub Actions and the device confirm them. Never interpret this diagnostic APK as proof that IngeTrazo runs on Android.
