"""Tailwind classes picked in Python. Tailwind scans this file, so write every class out in full."""

HEADING = (
    "mt-6 mb-2.5 border-t border-line pt-3.5 first:mt-0 first:border-0 first:pt-0"
    " font-display text-2xl leading-none font-bold tracking-[.06em] uppercase"
)
HEADING_COLOURS = {"heading": "text-gold", "heading night": "text-moon"}

LINE = "mb-2 max-w-[65ch] border-l-3 py-0.5 pl-3"
# The left stripe says what kind of moment it is.
LINE_STYLES = {
    "": f"{LINE} border-line",
    "death": f"{LINE} border-blood [&_b:last-of-type]:text-blood",
    "hurt": f"{LINE} border-ember",
    "bad": f"{LINE} border-ember",
    "item": f"{LINE} border-gold",
    "team": f"{LINE} border-moon",
    "arena": f"{LINE} border-ember font-semibold text-ember",
    "cannon": "mb-2 max-w-[65ch] py-0.5 text-moss italic",
    "win": (
        "mb-2 max-w-[65ch] rounded-md border-2 border-gold p-4 text-gold"
        " font-display text-[clamp(1.6rem,5vw,2.4rem)] leading-tight font-black uppercase"
    ),
}
NEW_LINE = "motion-safe:animate-appear"

STATUS_PILLS = {
    "": "border-moss text-moss",
    "wounded": "border-ember text-ember",
    "dead": "border-blood text-blood",
}


def story_classes(style, is_new):
    """The classes of one story entry."""
    if style.startswith("heading"):
        return f"{HEADING} {HEADING_COLOURS.get(style, 'text-gold')}"
    classes = LINE_STYLES.get(style, LINE_STYLES[""])
    return f"{classes} {NEW_LINE}" if is_new else classes
