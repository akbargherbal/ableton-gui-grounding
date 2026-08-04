### Key Principles of Risk Management for AI Educational Agents in Ableton Live

#### 1. Graceful Escalation Ladder (Preventing Learning Stalls)

- **Core Philosophy:** A failure in automation must never halt the educational flow or frustrate the student. The system operates on a multi-tier fallback ladder:
  $$\text{Mouse UI Click} \longrightarrow \text{Keyboard Shortcut} \longrightarrow \text{MCP / LOM Direct Call} \longrightarrow \text{Explicit Human Instructions}$$
- **Principle:** Failure at any automated level triggers escalation to the next level rather than throwing an unhandled exception or stopping the lesson.

#### 2. Human Fallback Safety Protocol (Eliminating "Visual Scavenger Hunts")

- **Identified Risk:** AI agents frequently degrade student experience by giving vague, relative visual instructions (e.g., _"look at the top-right orange icon"_), leading to confusion for beginners.
- **Mitigation Strategy:**
  - Human instructions must be executable with **zero prior UI familiarity**.
  - Use **strict, named menu paths and exact control names/states** only (e.g., _"Go to Options menu, select Preferences, ensure Checkbox X is checked"_).
  - Every manual instruction must end with an explicit confirmation request before proceeding.

#### 3. State Preservation & Recovery Nets

- **Identified Risk:** Automated actions leaving Ableton in an unwanted live state (e.g., tracks left soloed/armed, transport running) if an error occurs mid-lesson.
- **Mitigation Strategy:**
  - **Always-Restore Policy:** Capture original state before any action, execute, and guarantee state restoration using `finally` cleanup blocks regardless of errors.
  - **Conservative Failure Handling:** On screenshot or orchestrator errors, the system must **log and continue**, explicitly avoiding retry loops against a live session that could compound state corruption.

#### 4. Verification Over Blind Assumption ("Verify, Don't Guess")

- **Identified Risk:** Assuming a sent input/click succeeded. Ableton’s custom UI can register inputs without applying state changes, or stale element handles can manipulate the wrong control.
- **Mitigation Strategy:**
  - **Re-resolution Rule:** Never hold UI control references across state-changing gaps or sleep delays; always re-resolve elements freshly from the UI tree.
  - **Structural Read-After-Write:** Verify actions structurally (reading toggle states via UIA) after execution rather than trusting the input event itself.
  - **Risk-Based Verification:** Target strict post-verification toward high-risk, index-sensitive operations (Arm, Solo, Mute) to balance efficiency and reliability.

#### 5. Tool Selection Based on Spatial Risk & Consequence

- **Identified Risk:** Target UI density causes accidental mis-clicks (e.g., Activator, Solo, and Arm buttons sharing tight vertical spacing of 2–3 pixels).
- **Mitigation Strategy:**
  - Evaluate actions by **density vs. consequence**: High-density/high-impact controls warrant escalation to direct keypresses or structural calls rather than raw mouse clicks.
  - Differentiate failure modes: Continuous controls (sliders like Tempo) fail by _wrong value_, whereas buttons fail by _wrong element_.

#### 6. Decoupling Agent Verification from Student Documentation

- **Dual-Consumer Strategy:**
  - **For the AI Agent (Self-Verification):** Uses a cost-driven 3-bucket taxonomy (structural text reads first; vision/screenshots used only as a last resort for UI blind spots).
  - **For the Student (Tutorial Generation):** Generates deterministic step-by-step screenshots unconditionally after every action, ensuring the novice learner always has visual context regardless of how the agent verified the state internally.
