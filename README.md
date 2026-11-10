# AI World — live browser simulation

GitHub Pages serves the 3D viewer and Python engine. Pyodide 0.27.7 loads from cdn.jsdelivr.net and runs the original engine in a worker. Each tab has an independent ephemeral CPU/mock world with five humans and two animals per species. No model server, shared world or persistent storage is provided. Pause/resume and new-world controls are available. Sessions stop at 720 ticks to bound memory.

Build: `python scripts/build_pages.py`. Publish the contents of site/ to the gh-pages branch. Pages source must be gh-pages, / (root).

Paper-inspired memory comparison: learning.html. The measured report is separate from the live browser world.
