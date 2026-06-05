"""
imla_ui/colors.py
─────────────────
Single source of truth for every colour used in the IMLA UI.
All values are derived from mockup analysis.  Values marked # TUNE
are my best-guess picks where the mockup is ambiguous.

Import pattern:
    from imla_ui.colors import C
    pen = QPen(C.BLUE)
"""
from PySide6.QtGui import QColor


class C:  # namespace – never instantiated
    # ── Window / panel background ─────────────────────────────────────────
    BG_WINDOW   = QColor(10,  13,  25, 242)   # dark navy, slight transparency  # TUNE alpha
    BG_CARD     = QColor(16,  21,  38)         # transcript card fill           # TUNE
    BG_BTN      = QColor(21,  28,  48)         # action button resting          # TUNE
    BG_BTN_HOV  = QColor(32,  43,  68)         # action button hover            # TUNE
    BG_PILL_L   = QColor(14,  19,  34)         # left status pill bg            # TUNE
    BG_PILL_C   = QColor( 8,  28,  18)         # "Connected" pill (green tint)  # TUNE
    BG_PILL_T   = QColor(14,  19,  34)         # timer pill bg                  # TUNE

    # ── Accent colours ────────────────────────────────────────────────────
    BLUE        = QColor( 27, 155, 255)        # #1B9BFF  orb ring / primary     # TUNE
    CYAN        = QColor(  0, 218, 200)        # #00DAC8  waveform lead edge      # TUNE
    GREEN       = QColor(  0, 200, 110)        # #00C86E  connected / listening   # TUNE
    RED         = QColor(255,  72,  72)        # #FF4848  error state             # TUNE
    BLUE_GLOW   = QColor( 27, 155, 255,  55)   # orb outer glow (translucent)    # TUNE

    # ── Text ──────────────────────────────────────────────────────────────
    TEXT_PRI    = QColor(220, 235, 255)        # #DCEAFF  primary white           # TUNE
    TEXT_DIM    = QColor( 85, 112, 165)        # #5570A5  shortcuts / interim     # TUNE
    TEXT_LABEL  = QColor(152, 178, 220)        # #98B2DC  status / label text     # TUNE

    # ── Orb ───────────────────────────────────────────────────────────────
    ORB_CORE    = QColor(  7,  10,  22)        # #070A16  dark interior           # TUNE
    ORB_EDGE    = QColor( 12,  16,  36)        # #0C1024  gradient edge           # TUNE
    ORB_RING    = QColor( 27, 155, 255)        # same as BLUE
    ORB_GLOW    = QColor( 27, 155, 255,  50)   # ring soft glow                  # TUNE

    # ── Card border / subtle lines ────────────────────────────────────────
    CARD_BORDER = QColor( 30,  42,  70)        # #1E2A46  card outline            # TUNE

    # ── Waveform layers ───────────────────────────────────────────────────
    WAVE_CYAN   = QColor(  0, 218, 200, 190)   # leading wave                    # TUNE
    WAVE_BLUE   = QColor( 40, 130, 255, 150)   # mid wave                        # TUNE
    WAVE_DARK   = QColor( 20,  80, 200, 100)   # background wave                 # TUNE
    WAVE_FILL_C = QColor(  0, 200, 200,  40)   # wave filled area (centre)       # TUNE
    WAVE_FILL_E = QColor(  0, 100, 200,  10)   # wave filled area (edge)         # TUNE
