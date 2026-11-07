# The Godot witness on an Android phone (read-only)

The Godot viewer can run as an Android app. It is the same read-only witness: it only sends HTTP GET requests to a simulation server and
cannot command, feed or influence anyone. A phone has no command line, so the app asks for the server's address when it starts (and remembers it;
the small "server" button, top right, changes it).

## Using the test APK
1. Install `caitanya-witness.apk` (a **debug** build for arm64 phones; allow "install unknown apps" for your file manager or browser).
2. On the computer that runs the world start the server so the phone can reach it. The default only listens on that computer, so choose an address
   on a **private network you trust** (the viewer API has no login; anyone who can reach the address can WATCH the world, read-only):
   `python -m caitanya.server --families 6 --terrain geography-v2 --host <the computer's Tailscale address> --port 8000`
   (for a finished run: `python -m caitanya.server --playback <run folder> --host <address> --port 8000`). The server prints a warning when
   `--host` is not local.
3. Put the phone on the same private network (for example Tailscale on both), open the app, type `<address>:8000`, press Connect.
4. Controls: one finger drags to orbit, two fingers pinch to zoom and drag to pan, tap a person to inspect. In playback, drag the bar to any tick.

## What is and is not verified
* Built headlessly in a cloud container with Godot 4.4.1's prebuilt Android export template (arm64-v8a only, package `org.caitanya.witness`,
  INTERNET permission, debug-signed with a throwaway key, v1 and v2 signatures verified, entries aligned). The Android SDK could not be installed
  there, so the signer is a small stand-in built on Google's `apksig` library and `zipalign` is a Python stand-in. A normal build with the real
  SDK is the same export preset.
* **Not run on a phone or emulator**, so the install, the touch controls and the connection from a phone are untested on a device. The address
  panel, the gesture arithmetic and the touch handling are covered by headless tests (`godot/tests/mobile_test.gd`).
* A debug build is for testing, not for the Play Store (`android:debuggable` is true).

## Rebuilding
Open `godot/` in Godot 4.4.1 with the Android export template and Android SDK installed, or: `godot --headless --path godot --export-debug Android ../build/caitanya-witness.apk`
(the preset is `godot/export_presets.cfg`; the Android SDK, JDK and a debug keystore are set in the editor settings). The project sets
`rendering/textures/vram_compression/import_etc2_astc=true`, which Android export requires.
