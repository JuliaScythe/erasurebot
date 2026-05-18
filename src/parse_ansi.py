

COLOR_GRAY = "\u001b[0;30m"
COLOR_RED = "\u001b[0;31m"
COLOR_GREEN = "\u001b[0;32m"
COLOR_YELLOW = "\u001b[0;33m"
COLOR_BLUE = "\u001b[0;34m"
COLOR_PINK = "\u001b[0;35m"
COLOR_CYAN = "\u001b[0;36m"
COLOR_WHITE = "\u001b[0;37m"
COLOR_BG_0 = "\u001b[0;40m"
COLOR_BG_1 = "\u001b[0;41m"
COLOR_BG_2 = "\u001b[0;42m"
COLOR_BG_3 = "\u001b[0;43m"
COLOR_BG_4 = "\u001b[0;44m"
COLOR_BG_5 = "\u001b[0;45m"
COLOR_BG_6 = "\u001b[0;46m"
COLOR_BG_7 = "\u001b[0;47m"

COLOR_RESET = "\u001b[0;0m"

COLOR_FGS = [COLOR_GRAY, COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_BLUE, COLOR_PINK, COLOR_CYAN, COLOR_WHITE]
COLOR_BGS = [COLOR_BG_0, COLOR_BG_1, COLOR_BG_2, COLOR_BG_3, COLOR_BG_4, COLOR_BG_5, COLOR_BG_6, COLOR_BG_7]

# example of sample message: normal text|[f1]i'm red now|[] 

def parse_ansi(input: str) -> str:
    return "".join(map(parse_segment, input.split("|[")))

def parse_segment(segment: str) -> str:
    parts = segment.split("]", maxsplit=1)
    if len(parts) != 2:
        return segment
    initial = parts[0]
    initial_parts = initial.split(",")

    fg = -1
    bg = -1

    for part in initial_parts:
        if len(part) != 2:
            continue 
        if part[0] == 'f':
            try:
                fg = int(part[1])
            except ValueError:
                continue
        if part[0] == 'b':
            try:
                bg = int(part[1])
            except ValueError:
                continue
    
    real_segment = parts[1]
    return color_segment(real_segment, fg, bg)

def color_segment(segment: str, id_fg: int, id_bg: int) -> str:
    if id_fg not in range(-1, 8) or id_bg not in range(-1, 8):
        return segment
    if id_fg == -1:
        if id_bg == -1:
            return segment
        else:
            return COLOR_BGS[id_bg] + segment + COLOR_RESET
    else:
        if id_bg == -1:
            return COLOR_FGS[id_fg] + segment + COLOR_RESET
        else:
            return COLOR_FGS[id_fg] + COLOR_BGS[id_bg] + segment + COLOR_RESET