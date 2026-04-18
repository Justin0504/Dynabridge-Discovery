"""Chart rendering module — generates matplotlib chart PNGs matching template style.

Renders horizontal bar charts, donut charts, vertical bar charts, stacked bars,
and dual-layout charts (donut + hbar side by side). All charts follow the CozyFit
reference deck's orange color scheme and clean visual style.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams['font.style'] = 'normal'
matplotlib.rcParams['axes.labelweight'] = 'normal'
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

# ── Color Palette (matching template) ─────────────────────────

PRIMARY = "#FB641F"
COLORS = [
    "#FB641F",  # orange
    "#F4A261",  # light orange
    "#E76F51",  # coral
    "#2A9D8F",  # teal
    "#264653",  # dark blue
    "#E9C46A",  # yellow
    "#606C38",  # olive
    "#BC6C25",  # brown
    "#6D6875",  # mauve
    "#B5838D",  # dusty rose
]
GRAY_TEXT = "#4A4A4A"
LIGHT_GRAY = "#E8E8E8"
DARK_TEXT = "#292524"
BG_COLOR = "#FFFFFF"

DPI = 200
FULL_WIDTH = (3200, 1400)
HALF_WIDTH = (1600, 1400)
DUAL_WIDTH = (3200, 1400)


def _get_font():
    """Try Montserrat, fall back to system sans-serif."""
    for name in ["Montserrat", "Helvetica Neue", "Helvetica", "Arial"]:
        try:
            fp = fm.findfont(fm.FontProperties(family=name, style="normal"), fallback_to_default=False)
            if fp:
                return name
        except Exception:
            continue
    return "sans-serif"


FONT_NAME = None


def _font():
    global FONT_NAME
    if FONT_NAME is None:
        FONT_NAME = _get_font()
    return FONT_NAME


LABEL_SIZE = 18
VALUE_SIZE = 18
LEGEND_SIZE = 16
TITLE_SIZE = 20


def _wrap_labels(labels, max_chars=14):
    """Wrap long labels by inserting newlines."""
    wrapped = []
    for label in labels:
        if len(label) <= max_chars:
            wrapped.append(label)
        else:
            words = label.split()
            lines, current = [], ""
            for word in words:
                if current and len(current) + 1 + len(word) > max_chars:
                    lines.append(current)
                    current = word
                else:
                    current = f"{current} {word}" if current else word
            if current:
                lines.append(current)
            wrapped.append("\n".join(lines))
    return wrapped


def _setup_axes(ax):
    """Apply clean styling to axes."""
    ax.set_facecolor(BG_COLOR)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(LIGHT_GRAY)
    ax.spines["bottom"].set_color(LIGHT_GRAY)
    ax.tick_params(colors=DARK_TEXT, labelsize=LABEL_SIZE)


# ── Chart Renderers ───────────────────────────────────────────

def render_hbar(categories: list[str], values: list[float],
                question: str = "", output_path: Path = None,
                size: tuple = None) -> Path:
    """Render a horizontal bar chart."""
    if size is None:
        size = FULL_WIDTH

    fig_w, fig_h = size[0] / DPI, size[1] / DPI
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=DPI)
    fig.patch.set_facecolor(BG_COLOR)
    _setup_axes(ax)

    y_pos = np.arange(len(categories))
    colors = [COLORS[i % len(COLORS)] for i in range(len(categories))]

    bars = ax.barh(y_pos, values, color=colors, height=0.6, edgecolor="none")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(categories, fontsize=LABEL_SIZE, fontfamily=_font(), fontstyle="normal", color=DARK_TEXT)
    ax.invert_yaxis()

    max_val = max(values) if values else 100
    ax.set_xlim(0, max_val * 1.2)
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)

    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + max_val * 0.02, bar.get_y() + bar.get_height() / 2,
                f"{val:.0f}%", va="center", ha="left",
                fontsize=VALUE_SIZE, fontfamily=_font(), color=DARK_TEXT, fontweight="bold")

    plt.tight_layout(pad=0.5)

    if output_path is None:
        output_path = Path("/tmp/chart_hbar.png")
    fig.savefig(str(output_path), dpi=DPI, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    plt.close(fig)
    return output_path


def render_donut(categories: list[str], values: list[float],
                 question: str = "", center_text: str = "",
                 output_path: Path = None, size: tuple = None) -> Path:
    """Render a donut (doughnut) chart filling the full slide width.

    Layout: large donut on the left (~40%), category breakdown bars on the right (~60%)
    to fill the page and avoid whitespace.
    """
    if size is None:
        size = DUAL_WIDTH  # full width to fill the slide

    fig_w, fig_h = size[0] / DPI, size[1] / DPI
    fig, (ax_donut, ax_bars) = plt.subplots(
        1, 2, figsize=(fig_w, fig_h), dpi=DPI,
        gridspec_kw={"width_ratios": [2, 3]}
    )
    fig.patch.set_facecolor(BG_COLOR)

    colors = [COLORS[i % len(COLORS)] for i in range(len(categories))]

    # Left: donut chart
    wedges, texts, autotexts = ax_donut.pie(
        values, labels=None, colors=colors, autopct="%1.0f%%",
        startangle=90, pctdistance=0.78,
        wedgeprops=dict(width=0.4, edgecolor=BG_COLOR, linewidth=3),
    )
    for t in autotexts:
        t.set_fontsize(VALUE_SIZE)
        t.set_fontfamily(_font())
        t.set_color("white")
        t.set_fontweight("bold")

    if center_text:
        ax_donut.text(0, 0, center_text, ha="center", va="center",
                      fontsize=TITLE_SIZE, fontfamily=_font(), color=DARK_TEXT, fontweight="bold")

    # Right: horizontal bars showing the same data as a breakdown
    _setup_axes(ax_bars)
    y_pos = np.arange(len(categories))
    bars = ax_bars.barh(y_pos, values, color=colors, height=0.6, edgecolor="none")
    ax_bars.set_yticks(y_pos)
    ax_bars.set_yticklabels(categories, fontsize=LABEL_SIZE, fontfamily=_font(), color=DARK_TEXT)
    ax_bars.invert_yaxis()

    for bar, val in zip(bars, values):
        ax_bars.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                     f"{val:.0f}%", va="center", fontsize=VALUE_SIZE,
                     fontfamily=_font(), color=DARK_TEXT, fontweight="bold")

    ax_bars.set_xlim(0, max(values) * 1.25)
    ax_bars.set_xlabel("")

    # Divider line between the two panels
    line_x = 0.42
    fig.add_artist(plt.Line2D([line_x, line_x], [0.05, 0.90],
                              transform=fig.transFigure, color=LIGHT_GRAY, linewidth=1.5))

    plt.tight_layout(pad=1.5, w_pad=5.0)

    if output_path is None:
        output_path = Path("/tmp/chart_donut.png")
    fig.savefig(str(output_path), dpi=DPI, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    plt.close(fig)
    return output_path


def render_vbar(categories: list[str], values: list[float],
                question: str = "", output_path: Path = None,
                size: tuple = None) -> Path:
    """Render a vertical (column) bar chart."""
    if size is None:
        size = FULL_WIDTH

    fig_w, fig_h = size[0] / DPI, size[1] / DPI
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=DPI)
    fig.patch.set_facecolor(BG_COLOR)
    _setup_axes(ax)

    x_pos = np.arange(len(categories))
    colors = [COLORS[i % len(COLORS)] for i in range(len(categories))]

    bars = ax.bar(x_pos, values, color=colors, width=0.6, edgecolor="none")

    ax.set_xticks(x_pos)
    wrapped = _wrap_labels(categories)
    ax.set_xticklabels(wrapped, fontsize=LABEL_SIZE, fontfamily=_font(), fontstyle="normal", color=DARK_TEXT,
                       rotation=0, ha="center")

    max_val = max(values) if values else 100
    ax.set_ylim(0, max_val * 1.25)
    ax.yaxis.set_visible(False)
    ax.spines["left"].set_visible(False)

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max_val * 0.02,
                f"{val:.0f}%", ha="center", va="bottom",
                fontsize=VALUE_SIZE, fontfamily=_font(), fontstyle="normal", color=DARK_TEXT, fontweight="bold")

    plt.tight_layout(pad=0.5)

    if output_path is None:
        output_path = Path("/tmp/chart_vbar.png")
    fig.savefig(str(output_path), dpi=DPI, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    plt.close(fig)
    return output_path


def render_stacked_bar(categories: list[str], series: list[dict],
                       question: str = "", output_path: Path = None,
                       size: tuple = None) -> Path:
    """Render a stacked horizontal bar chart."""
    if size is None:
        size = FULL_WIDTH

    fig_w, fig_h = size[0] / DPI, size[1] / DPI
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=DPI)
    fig.patch.set_facecolor(BG_COLOR)
    _setup_axes(ax)

    y_pos = np.arange(len(categories))
    left = np.zeros(len(categories))

    for i, s in enumerate(series):
        vals = np.array(s["values"][:len(categories)])
        color = COLORS[i % len(COLORS)]
        bars = ax.barh(y_pos, vals, left=left, color=color, height=0.6,
                       edgecolor="none", label=s["name"])
        for j, (bar, val) in enumerate(zip(bars, vals)):
            if val > 5:
                ax.text(left[j] + val / 2,
                        bar.get_y() + bar.get_height() / 2,
                        f"{val:.0f}%", ha="center", va="center",
                        fontsize=VALUE_SIZE - 2, fontfamily=_font(), color="white", fontweight="bold")
        left += vals

    ax.set_yticks(y_pos)
    ax.set_yticklabels(categories, fontsize=LABEL_SIZE, fontfamily=_font(), fontstyle="normal", color=DARK_TEXT)
    ax.invert_yaxis()
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)

    ax.legend(loc="lower right", fontsize=LEGEND_SIZE, frameon=False, prop={"family": _font(), "weight": "bold"})

    plt.tight_layout(pad=0.5)

    if output_path is None:
        output_path = Path("/tmp/chart_stacked.png")
    fig.savefig(str(output_path), dpi=DPI, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    plt.close(fig)
    return output_path


def render_dual(left_data: dict, right_data: dict,
                output_path: Path = None, size: tuple = None) -> Path:
    """Render a dual chart layout (left chart + right chart side by side)."""
    if size is None:
        size = DUAL_WIDTH

    fig_w, fig_h = size[0] / DPI, size[1] / DPI
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(fig_w, fig_h), dpi=DPI,
                                    gridspec_kw={"width_ratios": [2, 3]})
    fig.patch.set_facecolor(BG_COLOR)

    _render_subplot(ax1, left_data)
    _render_subplot(ax2, right_data)

    line_x = 0.42
    fig.add_artist(plt.Line2D([line_x, line_x], [0.05, 0.90],
                              transform=fig.transFigure, color=LIGHT_GRAY,
                              linewidth=1.5))

    plt.tight_layout(pad=1.5, w_pad=5.0)

    if output_path is None:
        output_path = Path("/tmp/chart_dual.png")
    fig.savefig(str(output_path), dpi=DPI, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    plt.close(fig)
    return output_path


def _render_subplot(ax, data: dict):
    """Render a single chart into a subplot axes."""
    chart_type = data.get("type", "hbar")
    categories = data.get("categories", [])
    values = data.get("values", [])

    if chart_type in ("donut", "pie"):
        is_donut = chart_type == "donut"
        colors = [COLORS[i % len(COLORS)] for i in range(len(categories))]
        wedges, texts, autotexts = ax.pie(
            values, labels=None, colors=colors, autopct="%1.0f%%",
            startangle=90, pctdistance=0.75 if not is_donut else 0.78,
            wedgeprops=dict(width=0.4 if is_donut else 1.0, edgecolor=BG_COLOR, linewidth=3),
        )
        for t in autotexts:
            t.set_fontsize(VALUE_SIZE - 2)
            t.set_fontfamily(_font())
            t.set_color("white")
            t.set_fontweight("bold")

        ax.legend(wedges, categories, loc="center left", bbox_to_anchor=(1.0, 0.5),
                  fontsize=LEGEND_SIZE, frameon=False, prop={"family": _font(), "weight": "bold"})

    elif chart_type == "hbar":
        _setup_axes(ax)
        y_pos = np.arange(len(categories))
        colors = [COLORS[i % len(COLORS)] for i in range(len(categories))]
        bars = ax.barh(y_pos, values, color=colors, height=0.6, edgecolor="none")
        ax.set_yticks(y_pos)
        ax.set_yticklabels(categories, fontsize=LABEL_SIZE, fontfamily=_font(), fontstyle="normal", color=DARK_TEXT)
        ax.invert_yaxis()
        max_val = max(values) if values else 100
        ax.set_xlim(0, max_val * 1.2)
        ax.xaxis.set_visible(False)
        ax.spines["bottom"].set_visible(False)
        for bar, val in zip(bars, values):
            ax.text(bar.get_width() + max_val * 0.02,
                    bar.get_y() + bar.get_height() / 2,
                    f"{val:.0f}%", va="center", ha="left",
                    fontsize=VALUE_SIZE, fontfamily=_font(), color=DARK_TEXT, fontweight="bold")

    elif chart_type == "vbar":
        _setup_axes(ax)
        x_pos = np.arange(len(categories))
        colors = [COLORS[i % len(COLORS)] for i in range(len(categories))]
        bars = ax.bar(x_pos, values, color=colors, width=0.6, edgecolor="none")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(categories, fontsize=LABEL_SIZE, fontfamily=_font(), color=DARK_TEXT,
                           rotation=0, ha="center")
        max_val = max(values) if values else 100
        ax.set_ylim(0, max_val * 1.2)
        ax.yaxis.set_visible(False)
        ax.spines["left"].set_visible(False)
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max_val * 0.02,
                    f"{val:.0f}%", ha="center", va="bottom",
                    fontsize=VALUE_SIZE, fontfamily=_font(), color=DARK_TEXT, fontweight="bold")


def render_pie(categories: list[str], values: list[float],
               question: str = "", output_path: Path = None,
               size: tuple = None) -> Path:
    """Render a simple pie chart (used for marital status in segment profiles)."""
    if size is None:
        size = HALF_WIDTH

    fig_w, fig_h = size[0] / DPI, size[1] / DPI
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=DPI)
    fig.patch.set_facecolor(BG_COLOR)

    colors = [COLORS[i % len(COLORS)] for i in range(len(categories))]

    wedges, texts, autotexts = ax.pie(
        values, labels=None, colors=colors, autopct="%1.0f%%",
        startangle=90, pctdistance=0.75,
        wedgeprops=dict(edgecolor=BG_COLOR, linewidth=2),
    )

    for t in autotexts:
        t.set_fontsize(VALUE_SIZE)
        t.set_fontfamily(_font())
        t.set_color("white")
        t.set_fontweight("bold")

    legend = ax.legend(wedges, categories, loc="center left", bbox_to_anchor=(1.0, 0.5),
                       fontsize=LEGEND_SIZE, frameon=False, prop={"family": _font(), "weight": "bold"})
    for text in legend.get_texts():
        text.set_color(DARK_TEXT)

    plt.tight_layout(pad=0.5)

    if output_path is None:
        output_path = Path("/tmp/chart_pie.png")
    fig.savefig(str(output_path), dpi=DPI, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    plt.close(fig)
    return output_path


def render_funnel(brands: list[str], metrics: list[dict],
                  output_path: Path = None, size: tuple = None) -> Path:
    """Render a brand metrics funnel (Awareness → Purchase → Satisfaction → Recommend).

    Args:
        brands: ["Brand A", "Brand B", ...]
        metrics: [{"name": "Awareness", "values": [75, 60, ...]},
                  {"name": "Purchase", "values": [40, 30, ...]}, ...]
    """
    if size is None:
        size = FULL_WIDTH

    fig_w, fig_h = size[0] / DPI, size[1] / DPI
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=DPI)
    fig.patch.set_facecolor(BG_COLOR)
    _setup_axes(ax)

    n_brands = len(brands)
    n_metrics = len(metrics)
    bar_height = 0.8 / n_metrics
    y_positions = np.arange(n_brands)

    for i, metric in enumerate(metrics):
        vals = metric["values"][:n_brands]
        offset = (i - n_metrics / 2 + 0.5) * bar_height
        color = COLORS[i % len(COLORS)]
        bars = ax.barh(y_positions + offset, vals, height=bar_height * 0.85,
                       color=color, edgecolor="none", label=metric["name"])
        for bar, val in zip(bars, vals):
            ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                    f"{val:.0f}%", va="center", ha="left",
                    fontsize=VALUE_SIZE - 4, fontfamily=_font(), color=DARK_TEXT, fontweight="bold")

    ax.set_yticks(y_positions)
    ax.set_yticklabels(brands, fontsize=LABEL_SIZE, fontfamily=_font(), fontstyle="normal", color=DARK_TEXT)
    ax.invert_yaxis()
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)

    ax.legend(loc="lower right", fontsize=LEGEND_SIZE, frameon=False,
              prop={"family": _font(), "weight": "bold"}, ncol=n_metrics)

    plt.tight_layout(pad=0.5)

    if output_path is None:
        output_path = Path("/tmp/chart_funnel.png")
    fig.savefig(str(output_path), dpi=DPI, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    plt.close(fig)
    return output_path


def render_matrix(row_labels: list[str], col_labels: list[str],
                  values: list[list], output_path: Path = None,
                  size: tuple = None) -> Path:
    """Render a brand association matrix (brands × attributes with % values).

    Args:
        row_labels: Attribute names (rows)
        col_labels: Brand names (columns)
        values: 2D array of percentage values [row][col]
    """
    if size is None:
        size = (3200, 1800)

    fig_w, fig_h = size[0] / DPI, size[1] / DPI
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=DPI)
    fig.patch.set_facecolor(BG_COLOR)
    ax.axis("off")

    cell_text = []
    for row_vals in values:
        cell_text.append([f"{v}%" if isinstance(v, (int, float)) else str(v) for v in row_vals])

    n_cols = len(col_labels)
    col_widths = [0.18] + [0.82 / n_cols] * n_cols

    row_labels_col = [[label] for label in row_labels]
    full_rows = []
    for i, row_vals in enumerate(cell_text):
        full_rows.append([row_labels[i]] + row_vals)

    table = ax.table(
        cellText=full_rows, colLabels=[""] + col_labels, loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(LABEL_SIZE - 4)
    table.scale(1, 2.5)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(LIGHT_GRAY)
        if row == 0:
            cell.set_facecolor(PRIMARY)
            cell.set_text_props(color="white", fontweight="bold",
                                fontfamily=_font(), fontsize=LABEL_SIZE - 4)
        elif col == 0:
            cell.set_facecolor("#F5F5F4")
            cell.set_text_props(color=DARK_TEXT, fontweight="bold",
                                fontfamily=_font(), fontsize=LABEL_SIZE - 4, ha="left")
        else:
            val = 0
            try:
                val = float(cell.get_text().get_text().replace("%", ""))
            except (ValueError, AttributeError):
                pass
            if val >= 50:
                cell.set_facecolor("#FEE2E2")
            elif val >= 30:
                cell.set_facecolor("#FFF5F0")
            else:
                cell.set_facecolor(BG_COLOR)
            cell.set_text_props(color=DARK_TEXT, fontfamily=_font(), fontsize=LABEL_SIZE - 4, fontweight="bold")

    plt.tight_layout(pad=0.3)

    if output_path is None:
        output_path = Path("/tmp/chart_matrix.png")
    fig.savefig(str(output_path), dpi=DPI, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    plt.close(fig)
    return output_path


def render_table(headers: list[str], rows: list[list[str]],
                 output_path: Path = None, size: tuple = None) -> Path:
    """Render a data table as a clean image."""
    if size is None:
        size = FULL_WIDTH

    fig_w, fig_h = size[0] / DPI, size[1] / DPI
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=DPI)
    fig.patch.set_facecolor(BG_COLOR)
    ax.axis("off")

    n_cols = len(headers)
    col_widths = [1.0 / n_cols] * n_cols

    table = ax.table(
        cellText=rows, colLabels=headers, loc="center",
        cellLoc="center", colWidths=col_widths,
    )
    table.auto_set_font_size(False)
    table.set_fontsize(LABEL_SIZE)
    table.scale(1, 2.2)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(LIGHT_GRAY)
        if row == 0:
            cell.set_facecolor(PRIMARY)
            cell.set_text_props(color="white", fontweight="bold",
                                fontfamily=_font(), fontsize=LABEL_SIZE)
        else:
            cell.set_facecolor(BG_COLOR if row % 2 == 1 else "#FFF5F0")
            cell.set_text_props(color=DARK_TEXT, fontfamily=_font(), fontsize=LABEL_SIZE)

    plt.tight_layout(pad=0.3)

    if output_path is None:
        output_path = Path("/tmp/chart_table.png")
    fig.savefig(str(output_path), dpi=DPI, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    plt.close(fig)
    return output_path


def render_wordcloud(words: dict, output_path: Path = None,
                     size: tuple = None) -> Path:
    """Render a dense, visually compact word cloud from word frequencies.

    Args:
        words: {"word": frequency, ...} — higher frequency = larger text
    """
    from wordcloud import WordCloud

    if size is None:
        size = (3200, 2000)

    wc_colors = [
        "#E8552D", "#F28C28", "#D4532B", "#2A9D8F", "#264653",
        "#E76F51", "#F4A261", "#C44536", "#1B7A6E", "#3D405B",
    ]

    if len(words) < 30:
        padded = dict(words)
        generic_fillers = [
            "great", "love", "amazing", "good", "best", "nice", "solid",
            "works", "happy", "useful", "handy", "smooth", "clean", "fresh",
            "sturdy", "sleek", "perfect", "excellent", "fantastic", "superb",
            "impressive", "brilliant", "wonderful", "outstanding", "remarkable",
        ]
        min_weight = max(min(words.values()) // 2, 3)
        for filler in generic_fillers:
            if filler.lower() not in {w.lower() for w in padded}:
                padded[filler] = min_weight
                if len(padded) >= 45:
                    break
        words = padded

    # Create a circular mask for a tighter, more aesthetic cloud shape
    import numpy as np
    radius = min(size[0], size[1]) // 2
    cx, cy = size[0] // 2, size[1] // 2
    y, x = np.ogrid[:size[1], :size[0]]
    mask = np.full((size[1], size[0]), 255, dtype=np.uint8)
    mask[((x - cx) ** 2 + (y - cy) ** 2) <= radius ** 2] = 0

    wc = WordCloud(
        width=size[0], height=size[1],
        background_color=BG_COLOR,
        color_func=lambda *a, **kw: wc_colors[hash(a[0]) % len(wc_colors)],
        font_path=None,
        mask=mask,
        max_words=120,
        prefer_horizontal=0.65,
        min_font_size=10,
        max_font_size=260,
        relative_scaling=0.4,
        margin=1,
        collocations=False,
    ).generate_from_frequencies(words)

    fig_w, fig_h = size[0] / DPI, size[1] / DPI
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=DPI)
    fig.patch.set_facecolor(BG_COLOR)
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")

    plt.tight_layout(pad=0.5)

    if output_path is None:
        output_path = Path("/tmp/chart_wordcloud.png")
    fig.savefig(str(output_path), dpi=DPI, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    plt.close(fig)
    return output_path


def render_grouped_bar(categories: list[str], groups: list[dict],
                       output_path: Path = None, size: tuple = None,
                       horizontal: bool = True) -> Path:
    """Render a grouped bar chart (multiple series side by side).

    Matches real case Brand Metrics layout: brands on Y-axis, metrics as grouped bars.

    Args:
        categories: Y-axis labels (e.g., brand names)
        groups: [{"name": "Awareness", "values": [85, 72, ...]}, ...]
        horizontal: True for horizontal bars (default), False for vertical
    """
    if size is None:
        size = FULL_WIDTH

    fig_w, fig_h = size[0] / DPI, size[1] / DPI
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=DPI)
    fig.patch.set_facecolor(BG_COLOR)
    _setup_axes(ax)

    n_cats = len(categories)
    n_groups = len(groups)
    bar_size = 0.75 / n_groups

    if horizontal:
        y_pos = np.arange(n_cats)
        for i, grp in enumerate(groups):
            vals = grp["values"][:n_cats]
            offset = (i - n_groups / 2 + 0.5) * bar_size
            color = COLORS[i % len(COLORS)]
            bars = ax.barh(y_pos + offset, vals, height=bar_size * 0.9,
                           color=color, edgecolor="none", label=grp["name"])
            for bar, val in zip(bars, vals):
                ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                        f"{val:.0f}%", va="center", ha="left",
                        fontsize=VALUE_SIZE - 4, fontfamily=_font(), color=DARK_TEXT, fontweight="bold")

        ax.set_yticks(y_pos)
        ax.set_yticklabels(categories, fontsize=LABEL_SIZE, fontfamily=_font(), fontstyle="normal", color=DARK_TEXT)
        ax.invert_yaxis()
        max_val = max(max(g["values"][:n_cats]) for g in groups) if groups else 100
        ax.set_xlim(0, max_val * 1.25)
        ax.xaxis.set_visible(False)
        ax.spines["bottom"].set_visible(False)
    else:
        x_pos = np.arange(n_cats)
        for i, grp in enumerate(groups):
            vals = grp["values"][:n_cats]
            offset = (i - n_groups / 2 + 0.5) * bar_size
            color = COLORS[i % len(COLORS)]
            bars = ax.bar(x_pos + offset, vals, width=bar_size * 0.9,
                          color=color, edgecolor="none", label=grp["name"])
            for bar, val in zip(bars, vals):
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 1,
                        f"{val:.0f}%", ha="center", va="bottom",
                        fontsize=VALUE_SIZE - 4, fontfamily=_font(), color=DARK_TEXT, fontweight="bold")

        ax.set_xticks(x_pos)
        ax.set_xticklabels(categories, fontsize=LABEL_SIZE, fontfamily=_font(), color=DARK_TEXT,
                           rotation=0, ha="center")
        max_val = max(max(g["values"][:n_cats]) for g in groups) if groups else 100
        ax.set_ylim(0, max_val * 1.25)
        ax.yaxis.set_visible(False)
        ax.spines["left"].set_visible(False)

    ax.legend(loc="lower right", fontsize=LEGEND_SIZE, frameon=False,
              prop={"family": _font(), "weight": "bold"}, ncol=n_groups)

    plt.tight_layout(pad=0.5)

    if output_path is None:
        output_path = Path("/tmp/chart_grouped.png")
    fig.savefig(str(output_path), dpi=DPI, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    plt.close(fig)
    return output_path


# ── Main Dispatcher ───────────────────────────────────────────

def _normalize_chart(raw: dict) -> dict:
    """Normalize Claude's varied chart output into the flat format render_chart expects."""
    chart = dict(raw)

    # Accept "type" as alias for "chart_type"
    if "chart_type" not in chart and "type" in chart:
        chart["chart_type"] = chart["type"]

    raw_data = chart.get("data", {})
    if not raw_data:
        return chart

    ct = chart.get("chart_type", "hbar")
    data = raw_data if isinstance(raw_data, dict) else {}

    # Flat charts: pull labels/values from data
    if ct in ("hbar", "vbar", "donut", "pie"):
        # Format A: data is list of {label, value} objects
        if isinstance(raw_data, list) and raw_data and isinstance(raw_data[0], dict) and ("label" in raw_data[0] or "name" in raw_data[0]):
            chart["categories"] = [d.get("label", d.get("name", "")) for d in raw_data]
            chart["values"] = [d.get("value", d.get("weight", 0)) for d in raw_data]
        # Format B: data dict with labels/values arrays
        elif "categories" not in chart and "labels" in data:
            chart["categories"] = data["labels"]
        if "values" not in chart and "values" in data:
            chart["values"] = data["values"]

    # Dual charts: data has two sub-dicts (e.g., gender/ethnicity, frequency/spend)
    if ct == "dual" and "left_categories" not in chart:
        sub_keys = [k for k in data if isinstance(data[k], dict) and "labels" in data[k]]
        if len(sub_keys) >= 2:
            left_key, right_key = sub_keys[0], sub_keys[1]
            left, right = data[left_key], data[right_key]
            chart["left_type"] = "donut"
            chart["left_title"] = left_key.replace("_", " ").title()
            chart["left_categories"] = left.get("labels", [])
            chart["left_values"] = left.get("values", [])
            chart["right_type"] = "hbar"
            chart["right_title"] = right_key.replace("_", " ").title()
            chart["right_categories"] = right.get("labels", [])
            chart["right_values"] = right.get("values", [])

    # Wordcloud: raw_data may be list of {text/word, weight} or dict with "words" key
    if ct == "wordcloud":
        if isinstance(raw_data, list):
            chart["words"] = {w.get("text", w.get("word", "")): w.get("weight", 10) for w in raw_data if isinstance(w, dict) and (w.get("text") or w.get("word"))}
        elif isinstance(raw_data, dict):
            words = raw_data.get("words", chart.get("words", {}))
            if isinstance(words, list):
                chart["words"] = {w.get("text", w.get("word", "")): w.get("weight", 10) for w in words if isinstance(w, dict) and (w.get("text") or w.get("word"))}
            elif isinstance(words, dict):
                chart["words"] = words
        if "words" not in chart:
            chart["words"] = chart.get("words", {})

    # Grouped bar: multiple input formats
    if ct == "grouped_bar":
        # Format A: "series" with brand objects + "groups" as metric name strings
        series = chart.get("series", data.get("series", []))
        group_names = chart.get("groups", data.get("groups", []))
        if series and isinstance(series, list) and isinstance(series[0], dict) and group_names and isinstance(group_names, list) and isinstance(group_names[0], str):
            chart["categories"] = [s.get("brand", s.get("name", "")) for s in series]
            chart["groups"] = [
                {"name": g, "values": [s.get("values", [])[i] if i < len(s.get("values", [])) else 0 for s in series]}
                for i, g in enumerate(group_names)
            ]
            chart["horizontal"] = True
        # Format B: data.brands + data.metrics + data.values dict
        elif "categories" not in chart and "brands" in data:
            chart["categories"] = data["brands"]
            metrics = data.get("metrics", [])
            vals = data.get("values", {})
            if metrics and isinstance(vals, dict):
                groups = []
                for metric in metrics:
                    metric_vals = [vals.get(brand, [0]*len(metrics))[metrics.index(metric)]
                                   for brand in data.get("brands", [])]
                    groups.append({"name": metric, "values": metric_vals})
                chart["groups"] = groups
                chart["horizontal"] = True

    # Matrix: data has brands/attributes/scores OR rows/columns/data
    if ct == "matrix":
        if "row_labels" not in chart:
            chart["row_labels"] = chart.get("rows") or data.get("attributes", data.get("rows", []))
        if "col_labels" not in chart:
            chart["col_labels"] = chart.get("columns") or data.get("brands", data.get("columns", []))
        if "values" not in chart:
            if isinstance(raw_data, list) and raw_data and isinstance(raw_data[0], list):
                chart["values"] = raw_data
            elif isinstance(raw_data, dict):
                scores = data.get("scores", {})
                if isinstance(scores, dict):
                    brands = data.get("brands", [])
                    attrs = data.get("attributes", [])
                    chart["values"] = [[scores.get(b, [0]*len(attrs))[i] for b in brands] for i in range(len(attrs))]
                elif isinstance(scores, list) and scores and isinstance(scores[0], list):
                    chart["values"] = scores

    return chart


def render_chart(chart_data: dict, output_dir: Path, chart_idx: int) -> Path | None:
    """Render a chart from analyzer output data. Returns None if data is empty."""
    output_dir.mkdir(parents=True, exist_ok=True)
    chart_data = _normalize_chart(chart_data)
    chart_type = chart_data.get("chart_type", "hbar")

    cats = chart_data.get("categories", [])
    vals = chart_data.get("values", [])
    has_data = bool(cats and vals)
    if chart_type == "dual":
        has_data = bool(chart_data.get("left_categories") or chart_data.get("right_categories"))
    elif chart_type == "wordcloud":
        has_data = bool(chart_data.get("words"))
    elif chart_type == "grouped_bar":
        has_data = bool(cats and chart_data.get("groups"))
    elif chart_type == "matrix":
        has_data = bool(chart_data.get("row_labels") and chart_data.get("col_labels"))
    elif chart_type == "table":
        has_data = bool(chart_data.get("headers") and chart_data.get("rows"))
    elif chart_type == "funnel":
        has_data = bool(chart_data.get("brands") and chart_data.get("metrics"))

    if not has_data:
        print(f"[chart_renderer] Skipping chart {chart_idx} ({chart_data.get('title', 'untitled')}): no data")
        return None

    if chart_type == "dual":
        left_data = {
            "type": chart_data.get("left_type", "donut"),
            "title": chart_data.get("left_title", ""),
            "categories": chart_data.get("left_categories", []),
            "values": chart_data.get("left_values", []),
        }
        right_data = {
            "type": chart_data.get("right_type", "hbar"),
            "title": chart_data.get("right_title", ""),
            "categories": chart_data.get("right_categories", []),
            "values": chart_data.get("right_values", []),
        }
        return render_dual(left_data, right_data,
                           output_path=output_dir / f"chart_{chart_idx:02d}_dual.png")

    elif chart_type == "donut":
        return render_donut(
            categories=chart_data.get("categories", []),
            values=chart_data.get("values", []),
            question=chart_data.get("question", ""),
            center_text=chart_data.get("center_text", ""),
            output_path=output_dir / f"chart_{chart_idx:02d}_donut.png",
        )

    elif chart_type == "vbar":
        return render_vbar(
            categories=chart_data.get("categories", []),
            values=chart_data.get("values", []),
            question=chart_data.get("question", ""),
            output_path=output_dir / f"chart_{chart_idx:02d}_vbar.png",
        )

    elif chart_type == "stacked":
        return render_stacked_bar(
            categories=chart_data.get("categories", []),
            series=chart_data.get("series", []),
            question=chart_data.get("question", ""),
            output_path=output_dir / f"chart_{chart_idx:02d}_stacked.png",
        )

    elif chart_type == "pie":
        return render_pie(
            categories=chart_data.get("categories", []),
            values=chart_data.get("values", []),
            question=chart_data.get("question", ""),
            output_path=output_dir / f"chart_{chart_idx:02d}_pie.png",
        )

    elif chart_type == "funnel":
        return render_funnel(
            brands=chart_data.get("brands", []),
            metrics=chart_data.get("metrics", []),
            output_path=output_dir / f"chart_{chart_idx:02d}_funnel.png",
        )

    elif chart_type == "matrix":
        return render_matrix(
            row_labels=chart_data.get("row_labels", []),
            col_labels=chart_data.get("col_labels", []),
            values=chart_data.get("values", []),
            output_path=output_dir / f"chart_{chart_idx:02d}_matrix.png",
        )

    elif chart_type == "table":
        return render_table(
            headers=chart_data.get("headers", []),
            rows=chart_data.get("rows", []),
            output_path=output_dir / f"chart_{chart_idx:02d}_table.png",
        )

    elif chart_type == "wordcloud":
        return render_wordcloud(
            words=chart_data.get("words", {}),
            output_path=output_dir / f"chart_{chart_idx:02d}_wordcloud.png",
        )

    elif chart_type == "grouped_bar":
        grps = chart_data.get("groups", [])
        if grps and isinstance(grps[0], str):
            series = chart_data.get("series", [])
            if series and isinstance(series[0], dict):
                chart_data["categories"] = [s.get("brand", s.get("name", "")) for s in series]
                chart_data["groups"] = [
                    {"name": g, "values": [s.get("values", [])[i] if i < len(s.get("values", [])) else 0 for s in series]}
                    for i, g in enumerate(grps)
                ]
        return render_grouped_bar(
            categories=chart_data.get("categories", []),
            groups=chart_data.get("groups", []),
            horizontal=chart_data.get("horizontal", True),
            output_path=output_dir / f"chart_{chart_idx:02d}_grouped.png",
        )

    else:
        return render_hbar(
            categories=chart_data.get("categories", []),
            values=chart_data.get("values", []),
            question=chart_data.get("question", ""),
            output_path=output_dir / f"chart_{chart_idx:02d}_hbar.png",
        )
