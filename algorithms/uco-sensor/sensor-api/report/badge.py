"""
UCO-Sensor — SVG Badge Generator
===================================
Gera badges SVG compatíveis com shields.io para embedar em READMEs.

Uso:
  from report.badge import generate_badge_svg
  svg = generate_badge_svg(score=87, status="STABLE", label="UCO Score")
  Path("uco-badge.svg").write_text(svg)

  # No README.md:
  # ![UCO Score](./uco-badge.svg)
"""
from __future__ import annotations


# ─── Paleta de cores por score ────────────────────────────────────────────────

def badge_color(score: float) -> tuple[str, str]:
    """Retorna (fill_hex, text_hex) para o score dado."""
    if score >= 80:
        return "#4c1",    "#fff"   # verde
    if score >= 65:
        return "#97ca00", "#fff"   # verde-amarelo
    if score >= 50:
        return "#dfb317", "#fff"   # amarelo
    if score >= 35:
        return "#fe7d37", "#fff"   # laranja
    return "#e05d44", "#fff"       # vermelho


def _shield_path(width: int) -> str:
    """Caminho SVG do contorno arredondado (estilo shields.io)."""
    h, r = 20, 3
    return (
        f"M{r},0 h{width - 2*r} a{r},{r} 0 0 1 {r},{r} "
        f"v{h - 2*r} a{r},{r} 0 0 1 -{r},{r} "
        f"H{r} a{r},{r} 0 0 1 -{r},-{r} "
        f"V{r} a{r},{r} 0 0 1 {r},-{r} z"
    )


def generate_badge_svg(
    score:   float,
    status:  str   = "STABLE",
    label:   str   = "UCO Score",
    repo:    str   = "",
) -> str:
    """
    Gera um badge SVG estilo shields.io.

    Args:
        score:  UCO Score [0–100]
        status: STABLE | WARNING | CRITICAL
        label:  Texto do lado esquerdo
        repo:   Nome do repositório (opcional, para alt text)

    Returns:
        String SVG completo (self-contained).
    """
    score_int              = max(0, min(100, int(round(score))))
    value_text             = f"{score_int}/100"
    fill_color, text_color = badge_color(score)

    # Larguras aproximadas (7px por char + padding)
    label_w = len(label) * 7 + 10
    value_w = len(value_text) * 7 + 10
    total_w = label_w + value_w

    # Tooltip
    title = f"UCO Score: {score_int}/100 — {status}"
    if repo:
        title = f"{repo} | {title}"

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" \
xmlns:xlink="http://www.w3.org/1999/xlink" \
width="{total_w}" height="20" role="img" aria-label="{title}">
  <title>{title}</title>
  <defs>
    <linearGradient id="uco_s" x2="0" y2="100%">
      <stop offset="0"   stop-color="#bbb" stop-opacity=".1"/>
      <stop offset="1"   stop-opacity=".1"/>
    </linearGradient>
    <clipPath id="uco_r">
      <rect width="{total_w}" height="20" rx="3" fill="#fff"/>
    </clipPath>
  </defs>
  <g clip-path="url(#uco_r)">
    <rect width="{label_w}" height="20" fill="#555"/>
    <rect x="{label_w}" width="{value_w}" height="20" fill="{fill_color}"/>
    <rect width="{total_w}" height="20" fill="url(#uco_s)"/>
  </g>
  <g fill="{text_color}" text-anchor="middle" \
font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="110">
    <text x="{label_w // 2 * 10}" y="150" \
fill="#010101" fill-opacity=".3" \
transform="scale(.1)" textLength="{(label_w - 10) * 10}">{label}</text>
    <text x="{label_w // 2 * 10}" y="140" \
transform="scale(.1)" textLength="{(label_w - 10) * 10}">{label}</text>
    <text x="{(label_w + value_w // 2) * 10}" y="150" \
fill="#010101" fill-opacity=".3" \
transform="scale(.1)" textLength="{(value_w - 10) * 10}">{value_text}</text>
    <text x="{(label_w + value_w // 2) * 10}" y="140" \
transform="scale(.1)" textLength="{(value_w - 10) * 10}">{value_text}</text>
  </g>
</svg>"""
    return svg


def generate_status_badge_svg(status: str) -> str:
    """Badge compacto só com o status (STABLE/WARNING/CRITICAL)."""
    colors = {
        "STABLE":   ("#4c1",    "STABLE"),
        "WARNING":  ("#dfb317", "WARNING"),
        "CRITICAL": ("#e05d44", "CRITICAL"),
    }
    fill, label = colors.get(status, ("#9f9f9f", status))
    w = len(label) * 7 + 20

    return f"""<svg xmlns="http://www.w3.org/2000/svg" \
width="{w}" height="20" role="img" aria-label="UCO: {label}">
  <title>UCO-Sensor: {label}</title>
  <g>
    <rect width="{w}" height="20" rx="3" fill="#555"/>
    <rect x="32" width="{w - 32}" height="20" rx="3" fill="{fill}"/>
    <rect x="29" width="4" height="20" fill="{fill}"/>
  </g>
  <g fill="#fff" text-anchor="middle" \
font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="16" y="14">UCO</text>
    <text x="{32 + (w - 32) // 2}" y="14">{label}</text>
  </g>
</svg>"""
