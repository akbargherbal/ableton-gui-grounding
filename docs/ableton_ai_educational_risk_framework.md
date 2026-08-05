# Comprehensive Risk Management & Failure Mitigation Framework for AI-Agent-Driven Ableton Live Automation

---

## 1. Core Educational Philosophy & The Non-Halt Imperative

- **Continuity Over Failure:** In an interactive AI learning environment, a technical automation failure must **never halt the student's lesson** or stall the agent.
- **Seamless Fallback:** If an automated method fails or cannot be verified, the agent must seamlessly fall through a predefined escalation ladder until execution or verification is achieved.
- **No "Scavenger Hunts":** The agent must never subject novice students to visual scavenger hunts ("_look somewhere on the top right for an orange icon_"). All fallbacks must maintain absolute clarity.

---

## 2. Multi-Tier Escalation Ladder & Reference Layer Protocol

### A. The Scoped Escalation Ladder

The execution model employs a strict multi-level ladder tailored explicitly to the capabilities of the specific codebase (excluding non-existent tiers to prevent dead code):

$$\text{Level 1: Mouse UI Click} \longrightarrow \text{Level 2: Keyboard Shortcut} \longrightarrow \text{Level 3: Direct MCP/LOM Call} \longrightarrow \text{Level 4: Human Instructions}$$

- **Investigation Logging Rule:** Every escalation past Level 1 must be logged as an investigation note detailing _why_ the preferred method failed (e.g., missing `automation_id`, disabled control, UI virtualization, or focus loss). This serves as a system improvement lead.

### B. The Reference Layer Protocol (`ableton-live-12-manual-en.pdf`)

- **Consultation Checkpoint:** The Reference Layer (the official Ableton manual `ableton-live-12-manual-en.pdf` and verified shortcut indices) is **not a 5th tier**, but a mandatory checkpoint **consulted _before_ escalating** past Level 1 or Level 2.
- **Anti-Hallucination Guardrail:** The AI agent is strictly forbidden from guessing plausible shortcuts or menu paths.
- **Evidence-Based Fallback Rule:** An escalation is only valid if backed by explicit verification against official documentation (e.g., _"Checked `ableton-live-12-manual-en.pdf`, no direct keyboard shortcut exists for Monitoring RadioButtons; escalating to Level 4"_).

---

## 3. UI Virtualization & Window Focus Management

- **UI Virtualization Risk:** Ableton’s Session View relies on aggressive UI virtualization. If the window is minimized, backgrounded, or non-maximized, controls are removed from the accessibility API tree (~60 `automation_id`s exposed vs. ~201 when fully rendered).
- **`ensure_window_ready()` Protocol:**
  - Prior to taking any action or tree walk, the agent must actively restore (`SW_RESTORE`), bring to front (`SetForegroundWindow`), and maximize (`SW_MAXIMIZE`) the Ableton Live window.
  - **Non-Blocking Recovery:** Window maximize operations are treated as non-blocking/best-effort, reporting status via informational logging (`NOTE:MAXIMIZED`), whereas focus and restore failures emit explicit blocking errors (`ERROR:FOCUS_FAILED`).

---

## 4. Control Resolution & Memory Stale-Handle Prevention

- **Stale Reference Risk:** Caching UIA Wrapper handles across state-changing actions causes silent automation failures (e.g., a handle captured before playback silently reports wrong toggle states after playback stops, leading to un-restored solo tracks).
- **Fresh Tree Resolution Rule:** Controls must **never be cached** across action gaps or time delays. Every click, read, or check must execute a fresh, targeted tree walk (`resolve()`) immediately prior to interaction.
- **Refocus Retry Fallback:** If a fresh tree walk fails to find an `automation_id`, the system performs `ensure_window_ready()` once and retries the walk before raising a `LookupError`.

---

## 5. Context Blindness Guardrails: The "Selected Track" Blind Spot

- **Identified System Blind Spot:** The accessibility/UIA tree in Ableton Live does **not** expose which track is currently focused/selected on screen.
- **Keyboard Shortcut Risk:** Most Ableton track-scoped commands (Arm, Solo, Mute) rely on shortcuts that act strictly on the _currently selected track_. Invoking a track shortcut without knowing track focus risks modifying the wrong track.
- **Safety Guardrail (`blocked=True`):** All track-scoped shortcuts dependent on track selection are flagged `blocked=True` in the shortcut registry. They remain disabled for Level 2 escalation until a structural read for track selection is established. Positional shortcuts independent of selection (e.g., `F1`–`F8` for Track 1–8 Mute/Activator) are unblocked and validated.

---

## 6. Spatial Risk, Target Geometry, & Tool Selection Matrix

Tool selection (Mouse vs. Keyboard vs. Direct API) is governed by physical geometry and consequence analysis pulled from live `bounding_rect` data:

1. **Directional Target Density:** Distance between controls is asymmetrical. Intra-track density (e.g., Activator, Solo, and Arm stacked vertically with 2–3px gaps) poses a high risk of mis-clicking neighbor controls compared to inter-track density (~82px horizontal gap).
2. **Density vs. Consequence Disconnect:** High density on Radio Buttons (Monitor In/Auto/Off) keeps a mis-click within the same functional family. High density on Checkboxes (Activator vs. Solo vs. Arm) flips fundamentally destructive operational states.
3. **Absolute Target Size Risk:** Small control dimensions (e.g., Clip Stop button at 15×16px) introduce target acquisition risks independent of neighbor density.
4. **Element-Type Failure Modes:**
   - **Buttons/Checkboxes:** Fail by hitting the _wrong element_.
   - **Sliders/Continuous Controls (Tempo):** Fail by setting the _wrong value on the correct element_. RangeValue Pattern is attempted first; fallback to numeric double-click typing is used if unexposed.

---

## 7. Human Instruction Protocol for Novice Learners (Level 4 Safety)

When automated levels (Mouse/Keyboard/API) are exhausted, the agent issues manual human instructions under strict pedagogical safety constraints:

- **Zero Prior Familiarity:** Instructions must assume the student has never seen Ableton Live before.
- **Strict Named Paths:** Use **only explicit, named menu paths and exact control names** (e.g., _"Go to Options menu $\rightarrow$ Preferences $\rightarrow$ Audio, uncheck Checkbox X if present"_).
- **Prohibition of Visual/Relative Descriptions:** Never use relative spatial cues (e.g., _"click the orange box near the top right"_).
- **Explicit Feedback Loop:** Every human instruction step must end with a mandatory request for student confirmation (_"Confirm once done, or let me know if you hit an issue"_) before proceeding.

---

## 8. State Preservation, Baselines, and Restoration Safety Nets

- **Baseline Capture:** Prior to multi-step tasks (e.g., `solo_tour`), the script must record the baseline state of all affected controls.
- **Mandatory Restoration (`finally` Blocks):** All multi-step automation tasks must encapsulate execution in `try...finally` structures to guarantee that track states (Solo, Arm, Mute, Transport) are restored to baseline even if an exception or abort occurs.
- **Conservative Orchestration Failure Policy:** If a screenshot or sub-task fails during orchestrator execution, the orchestrator must **log and continue**, explicitly avoiding retry loops against a live Ableton session to prevent compounding state corruption.

---

## 9. Inter-Process Synchronization, Timing, and Drift Prevention

- **WSL/Windows Interop Execution:** Native WSL Bash scripts (`take_shot.sh`, `orchestrate.sh`) drive Windows Python (`python.exe automate_ableton_task.py`) directly via interop, eliminating cross-OS branching risks.
- **DrvFs Directory Caching Lag:** WSL’s `/mnt/c` file system can lag behind Windows disk writes. Capture verification must poll for file existence up to 3 seconds rather than performing an immediate single check.
- **Structured Output Events (`EVENT:` Protocol):**
  - Replaces fragile stdout text parsing with versioned JSON events (`EVENT: {"v":1, "type":"...", ...}`).
  - Both execution paths (`click_by_id()` escalation ladder and `set_checkbox_by_id()` state toggles) must emit identical event schemas.
- **CLI Drift Introspection (`--list-tasks`):** To prevent decoupled orchestrators from failing mid-run due to renamed flags/tasks, the orchestrator executes `--list-tasks` at launch to validate schema versioning and argument compliance before touching Live.

---

## 10. The Two-Consumer Architecture Split

The trigger policy for capturing state visuals is strictly divided by the consumer's identity:

| Consumer                                  | Verification Axis      | Trigger Policy                                                                                                                                                       |
| :---------------------------------------- | :--------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **AI Agent (Self-Verification)**          | Cost-Driven Efficiency | Text/UIA read-back first (Buckets 1 & 2). Screenshots are triggered **only** for Bucket 3 visual blind spots (e.g., custom piano roll MIDI notes).                   |
| **Student (Documentation / Walkthrough)** | Pedagogical Clarity    | A screenshot is taken after **every single action unconditionally**, regardless of UI control readability, ensuring full pixel-level visual context in walkthroughs. |
