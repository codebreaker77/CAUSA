# Causa — CORTEX Flight Recorder Dashboard

A high-density dark-mode workstation UI for a distributed agent flight recorder/debugger.

## Stack
- React + Vite
- Tailwind CSS
- `@xyflow/react` for the causal DAG canvas
- Lucide React icons

## Run

```bash
npm install
npm run dev
```

Then open the Vite URL (normally `http://localhost:5173`).

## Included interactions
- Pause/resume swarm state
- DAG pan/zoom/minimap
- Draggable typed causal nodes
- Right-click node context menu
- Step playback slider + VCR controls
- Breakpoint toggles
- Context drawer tabs
- Counterfactual fork action + toast feedback
