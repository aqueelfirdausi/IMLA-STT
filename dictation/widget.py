"""
dictation/widget.py -- Compact floating dictation HUD.

Layout (380 x 68 px pill)
  [  MIC BUTTON  |  WAVEFORM BARS  |  STATUS TEXT  ]

Visual states
  idle          withdrawn (completely off-screen, blocks nothing)
  listening     shown, full alpha, bars animate from live mic, red accent
  transcribing  shown, full alpha, sweeping sine-wave bars, orange accent

Visibility contract
  - show()      : deiconify + re-apply WS_EX_NOACTIVATE
  - set_state("idle") : withdraw (truly hidden, not just transparent)
  - All active states call show() implicitly

Non-focusable
  WS_EX_NOACTIVATE prevents Windows from activating this window when it is
  shown, clicked, or raised.  Focus always stays in the target text field.

Transparent corners
  wm_attributes('-transparentcolor', KEY_COLOR) makes every pixel of KEY_COLOR
  fully transparent.  The canvas background is set to KEY_COLOR so only the
  pill shape (drawn in BG_COLOR) and its contents are visible.
"""

import tkinter as tk
import ctypes
import math
import time
import collections

# ── Colours ───────────────────────────────────────────────────────────────────
KEY_COLOR    = "#010101"   # transparent key (must not appear inside the pill)
BG_COLOR     = "#1C1C1E"   # pill fill
CLR_IDLE     = "#48484A"   # bars / text when idle
CLR_LISTEN   = "#FF3B30"   # iOS-red  — listening
CLR_PROCESS  = "#FF9F0A"   # iOS-orange — transcribing
CLR_MIC_OFF  = "#636366"   # mic icon when inactive
CLR_MIC_ON   = "#FF3B30"   # mic icon when active
CLR_TEXT     = "#EBEBF5"   # status text

# ── Geometry ──────────────────────────────────────────────────────────────────
W, H         = 380, 68     # widget size
PAD          = 3           # gap between window edge and pill edge

# Mic button (left side)
MIC_CX, MIC_CY = 36, H // 2    # centre of mic button circle
MIC_R           = 22            # clickable radius

# Waveform (centre)
N_BARS       = 20
BAR_W        = 5
BAR_GAP      = 4
# Total bar area width = N_BARS*(BAR_W+BAR_GAP) - BAR_GAP = 20*9-4 = 176 px
# Centre it between x=72 and x=280 (208 px available).
_WAVE_AREA_W = N_BARS * (BAR_W + BAR_GAP) - BAR_GAP   # 176
WAVE_X0      = 72 + (208 - _WAVE_AREA_W) // 2          # = 72 + 16 = 88
BAR_CY       = H // 2                                   # vertical centre of bars
MAX_BAR_H    = 26          # tallest bar (px, half up + half down)
MIN_BAR_H    = 3           # flat-line bar height

# Status text (right side)
STATUS_X     = 284
STATUS_Y     = H // 2

# Opacity
ALPHA_IDLE   = 0.20        # widget barely visible at rest
ALPHA_ACTIVE = 0.94        # fully visible while dictating

# Windows extended-style constants
_GWL_EXSTYLE      = -20
_WS_EX_NOACTIVATE = 0x08000000
_WS_EX_TOOLWINDOW = 0x00000080


class DictateWidget:
    """
    Floating dictation HUD.  Must be created on the main (tkinter) thread.

    Parameters
    ----------
    root    : tk.Tk   hidden root that owns the event loop
    on_mic  : callable  invoked when the user clicks the mic button
    """

    def __init__(self, root: tk.Tk, on_mic):
        self._root   = root
        self._on_mic = on_mic
        self._state  = "idle"

        # Live amplitude: written from audio thread, read in animation loop.
        # deque.append is atomic under CPython's GIL -- no lock needed.
        self._amp          = 0.0
        self._amp_history  = collections.deque([0.0] * N_BARS, maxlen=N_BARS)
        self._amp_tick     = 0     # downsampling counter

        # Per-bar smoothed heights (animation state, main thread only)
        self._bar_h = [float(MIN_BAR_H)] * N_BARS

        self._build()
        self._apply_no_activate()
        self._win.withdraw()               # start fully hidden
        self._root.after(33, self._tick)   # start 30-fps animation loop

    # ── Construction ──────────────────────────────────────────────────────────

    def _build(self):
        self._win = tk.Toplevel(self._root)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.attributes("-transparentcolor", KEY_COLOR)
        self._win.configure(bg=KEY_COLOR)
        self._win.resizable(False, False)

        # Bottom-centre of primary screen, above the taskbar
        sw = self._win.winfo_screenwidth()
        sh = self._win.winfo_screenheight()
        x  = (sw - W) // 2
        y  = sh - H - 88
        self._win.geometry(f"{W}x{H}+{x}+{y}")

        # Canvas (covers whole window; KEY_COLOR areas become transparent)
        self._cv = tk.Canvas(
            self._win, width=W, height=H,
            bg=KEY_COLOR, highlightthickness=0, bd=0)
        self._cv.pack()

        # --- Pill background -------------------------------------------------
        self._draw_pill()

        # --- Waveform bars (drawn on top of pill) ----------------------------
        self._bars: list[int] = []
        for i in range(N_BARS):
            x = WAVE_X0 + i * (BAR_W + BAR_GAP)
            bid = self._cv.create_rectangle(
                x, BAR_CY - 1, x + BAR_W, BAR_CY + 1,
                fill=CLR_IDLE, outline="")
            self._bars.append(bid)

        # --- Mic button icon (drawn on top of pill) ---------------------------
        self._draw_mic(active=False)

        # --- Status text ------------------------------------------------------
        self._txt_id = self._cv.create_text(
            STATUS_X, STATUS_Y,
            text="Idle",
            fill=CLR_IDLE, anchor="w",
            font=("Segoe UI", 10, "bold"))

        # --- Click binding ---------------------------------------------------
        self._cv.bind("<Button-1>", self._on_click)

        # Start dim
        self._win.attributes("-alpha", ALPHA_IDLE)

    def _draw_pill(self):
        """
        Draw the rounded-rectangle (pill / stadium) background.

        Eight control points fed to create_polygon with smooth=True produce a
        Bézier-smoothed pill.  With r = H/2 the left and right ends become
        near-perfect semicircles.
        """
        x1, y1 = PAD, PAD
        x2, y2 = W - PAD, H - PAD
        r = (H - PAD * 2) // 2   # 31 px → half the pill height

        pts = [
            x1 + r, y1,
            x2 - r, y1,
            x2,     y1 + r,
            x2,     y2 - r,
            x2 - r, y2,
            x1 + r, y2,
            x1,     y2 - r,
            x1,     y1 + r,
        ]
        self._pill = self._cv.create_polygon(
            pts, smooth=True, fill=BG_COLOR, outline="")

    def _draw_mic(self, active: bool):
        """Draw (or redraw) the mic button icon; deletes previous 'mic' items."""
        self._cv.delete("mic")
        icon_col   = CLR_MIC_ON  if active else CLR_MIC_OFF
        circle_bg  = "#3A0F0F"   if active else "#2A2A2C"
        cx, cy = MIC_CX, MIC_CY

        # Outer circle (button background)
        self._cv.create_oval(
            cx - MIC_R, cy - MIC_R,
            cx + MIC_R, cy + MIC_R,
            fill=circle_bg, outline=icon_col, width=1.5,
            tags="mic")

        # --- Mic capsule body ------------------------------------------------
        # An oval centred at (cx, cy-8): 12 px wide, 22 px tall
        self._cv.create_oval(
            cx - 6, cy - 19,
            cx + 6, cy - 3,
            fill=icon_col, outline="",
            tags="mic")

        # --- Stand arc (U-shape below capsule) --------------------------------
        # Bounding box so the arc passes through roughly (cx, cy+10)
        self._cv.create_arc(
            cx - 13, cy - 7,
            cx + 13, cy + 13,
            start=0, extent=-180,
            style="arc", outline=icon_col, width=2,
            tags="mic")

        # --- Pole -------------------------------------------------------------
        self._cv.create_line(
            cx, cy + 13,
            cx, cy + 19,
            fill=icon_col, width=2,
            tags="mic")

        # --- Base -------------------------------------------------------------
        self._cv.create_line(
            cx - 8, cy + 19,
            cx + 8, cy + 19,
            fill=icon_col, width=2,
            tags="mic")

    # ── Public API (call from main thread only) ────────────────────────────────

    def show(self):
        """
        Make the widget visible without changing focus.
        Safe to call even if the widget is already visible.
        """
        self._win.deiconify()
        self._win.attributes("-alpha", ALPHA_ACTIVE)
        self._root.after(30, self._set_no_activate)   # re-apply after deiconify

    def set_state(self, state: str):
        """
        Transition between visual states.
        States: "idle", "listening", "transcribing"

        "idle" withdraws the window (truly hidden).
        Any other state shows the window first.
        """
        self._state = state
        self._draw_mic(active=(state == "listening"))

        label, color = {
            "idle":         ("Idle",          CLR_IDLE),
            "listening":    ("Listening",     CLR_LISTEN),
            "transcribing": ("Transcribing",  CLR_PROCESS),
        }.get(state, ("Idle", CLR_IDLE))

        self._cv.itemconfig(self._txt_id, text=label, fill=color)

        if state == "idle":
            self._win.withdraw()   # truly off-screen — blocks nothing
        else:
            self.show()

    def update_amplitude(self, amp: float):
        """
        Feed live microphone RMS amplitude.  Safe to call from any thread.
        `amp` is expected in 0.0–1.0; values are scaled for visual impact.
        """
        scaled = min(1.0, amp * 4.0)    # scale up so quiet speech still shows
        self._amp = scaled
        self._amp_tick += 1
        if self._amp_tick % 2 == 0:     # append ~15 Hz to keep the history scroll smooth
            self._amp_history.append(scaled)

    # ── Animation loop (main thread, ~30 fps) ─────────────────────────────────

    def _tick(self):
        state = self._state
        t     = time.monotonic()

        if state == "listening":
            # Each bar reflects a historical amplitude sample → scrolling waveform.
            targets = [
                MIN_BAR_H + v * (MAX_BAR_H - MIN_BAR_H)
                for v in self._amp_history
            ]
            bar_color = CLR_LISTEN

        elif state == "transcribing":
            # Sine-wave sweep across the bars.
            targets = [
                MIN_BAR_H + (MAX_BAR_H - MIN_BAR_H) * 0.45
                * (1.0 + math.sin(t * 4.5 + i * 0.50))
                for i in range(N_BARS)
            ]
            bar_color = CLR_PROCESS

        else:
            targets   = [float(MIN_BAR_H)] * N_BARS
            bar_color = CLR_IDLE

        # Smooth current heights toward targets (exponential moving average)
        alpha = 0.28
        for i in range(N_BARS):
            self._bar_h[i] = self._bar_h[i] * (1 - alpha) + targets[i] * alpha
            h  = max(2, int(self._bar_h[i]))
            x  = WAVE_X0 + i * (BAR_W + BAR_GAP)
            y1 = BAR_CY - h // 2
            y2 = y1 + max(2, h)
            self._cv.coords(self._bars[i], x, y1, x + BAR_W, y2)
            self._cv.itemconfig(self._bars[i], fill=bar_color)

        self._root.after(33, self._tick)

    # ── Interaction ───────────────────────────────────────────────────────────

    def _on_click(self, event):
        """Fire the mic callback only when the click lands inside the mic circle."""
        if math.hypot(event.x - MIC_CX, event.y - MIC_CY) <= MIC_R:
            self._on_mic()

    # ── Windows no-activate style ─────────────────────────────────────────────

    def _apply_no_activate(self):
        """Schedule WS_EX_NOACTIVATE to be applied after the HWND is ready."""
        self._win.after(80, self._set_no_activate)

    def _set_no_activate(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self._win.winfo_id())
            if hwnd == 0:
                hwnd = self._win.winfo_id()
            cur = ctypes.windll.user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, _GWL_EXSTYLE,
                cur | _WS_EX_NOACTIVATE | _WS_EX_TOOLWINDOW)
        except Exception:
            pass
