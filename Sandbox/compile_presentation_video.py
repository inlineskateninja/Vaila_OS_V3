import os
import sys
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Define Directories
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
FRAMES_DIR = SCRIPT_DIR / "frames"
OUTPUT_VIDEO = SCRIPT_DIR / "vaila_presentation.mp4"

# Set Resolution
WIDTH, HEIGHT = 1920, 1080
FPS = 30

# Colors (HSL-equivalent RGB)
BG_DARK = (3, 5, 12)       # hsl(224, 71%, 4%)
BG_SLATE = (11, 17, 32)    # hsl(222, 47%, 9%)
CARD_BG = (17, 26, 48)     # hsla(222, 47%, 12%, 0.7)
BORDER_COLOR = (45, 60, 85) # hsla(217, 30%, 25%, 0.5)

# Accent Colors (RGB)
CYAN = (0, 240, 255)
EMERALD = (0, 229, 117)
RUBY = (255, 56, 96)
GOLD = (255, 176, 0)
VIOLET = (184, 0, 255)
TEXT_PRIMARY = (248, 250, 252)
TEXT_SECONDARY = (190, 200, 215)
TEXT_MUTED = (100, 116, 139)

# Load System Fonts (Windows Paths)
def get_font(font_name, size):
    font_paths = {
        "segoe": [r"C:\Windows\Fonts\segoeui.ttf", "segoeui.ttf", "arial.ttf"],
        "segoe_bold": [r"C:\Windows\Fonts\segoeuib.ttf", "segoeuib.ttf", "arialbd.ttf"],
        "consola": [r"C:\Windows\Fonts\consola.ttf", "consola.ttf", "cour.ttf"]
    }
    
    paths = font_paths.get(font_name, ["arial.ttf"])
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except IOError:
            continue
    return ImageFont.load_default()

# Load fonts in different sizes
FONT_TITLE = get_font("segoe_bold", 44)
FONT_SUBTITLE = get_font("segoe", 24)
FONT_HEADING = get_font("segoe_bold", 32)
FONT_BODY = get_font("segoe", 22)
FONT_BODY_BOLD = get_font("segoe_bold", 22)
FONT_MONO = get_font("consola", 18)
FONT_MONO_SMALL = get_font("consola", 14)

def draw_header(draw, slide_num, title):
    # Logo Pulse Circle
    draw.ellipse([60, 52, 72, 64], fill=CYAN)
    draw.text((90, 42), "VAILA OS v3", fill=TEXT_PRIMARY, font=get_font("segoe_bold", 22))
    
    # Slide Index
    draw.text((WIDTH - 250, 42), f"SLIDE {slide_num:02d} // COGNITIVE SPINE", fill=CYAN, font=FONT_MONO)
    
    # Bottom dividing line
    draw.line([60, 85, WIDTH - 60, 85], fill=BORDER_COLOR, width=1)
    
    # Title
    draw.text((60, 115), title, fill=TEXT_PRIMARY, font=FONT_TITLE)

def draw_footer(draw, slide_num, total_slides=7):
    # Footer dividing line
    draw.line([60, HEIGHT - 85, WIDTH - 60, HEIGHT - 85], fill=BORDER_COLOR, width=1)
    
    # Progress Bar
    bar_width = 300
    bar_x = WIDTH // 2 - bar_width // 2
    bar_y = HEIGHT - 55
    draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + 4], fill=BORDER_COLOR)
    
    fill_pct = slide_num / total_slides
    draw.rectangle([bar_x, bar_y, bar_x + int(bar_width * fill_pct), bar_y + 4], fill=CYAN)
    
    # Navigation Help
    draw.text((60, HEIGHT - 60), "VAILA // COGNITIVE PERSISTENCE SYSTEM", fill=TEXT_MUTED, font=FONT_MONO_SMALL)
    draw.text((WIDTH - 280, HEIGHT - 60), "STATUS: SECURE // RUNNING OK", fill=EMERALD, font=FONT_MONO_SMALL)

# -------------------------------------------------------------
# SLIDE BUILDERS (Render individual slides at specific state)
# -------------------------------------------------------------

def build_slide_boot(frame_num):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_DARK)
    draw = ImageDraw.Draw(img)
    
    # Drawing Boot terminal box
    box_x1, box_y1 = WIDTH // 2 - 450, HEIGHT // 2 - 300
    box_x2, box_y2 = WIDTH // 2 + 450, HEIGHT // 2 + 200
    draw.rectangle([box_x1, box_y1, box_x2, box_y2], fill=BG_SLATE, outline=BORDER_COLOR, width=2)
    
    # Scanline light glow
    draw.line([box_x1, box_y1 + 4, box_x2, box_y1 + 4], fill=CYAN, width=2)
    
    boot_logs = [
      "[BOOT] Initializing Vaila OS Kernel v3.0.0...",
      "[BOOT] Core physical host recognized: Home Jane Node",
      "[BOOT] Mapping environment dependencies...",
      "   [OK] requests-gateway module initialized",
      "   [OK] pydantic schema validations cached",
      "   [OK] sqlite3 openbrain memory backend loaded",
      "[BOOT] Scanning system personas...",
      "   [OK] Loaded: Proto Jane (OS Spine Lens)",
      "   [OK] Loaded: Serren (Cognitive Lens)",
      "   [OK] Loaded: Maelith (Audit Lens)",
      "   [OK] Loaded: Vecht (Execution Lens)",
      "   [OK] Loaded: Riven (Assessment Lens)",
      "[BOOT] Opening local gateway http://127.0.0.1:1234...",
      "   [STATUS] Connection state: LM STUDIO RESPONDING",
      "[BOOT] Parsing deterministic regex routing profiles...",
      "   [OK] 12 Core system regex triggers parsed cleanly",
      "[BOOT] Verification status: COGNITIVE SPINE SECURE"
    ]
    
    # Calculate visible lines based on frame_num
    # Total boot duration: 600 frames. 17 lines. roughly 28 frames per line.
    lines_to_show = min(len(boot_logs), frame_num // 28 + 1)
    
    curr_y = box_y1 + 30
    for i in range(lines_to_show):
        line = boot_logs[i]
        color = TEXT_PRIMARY
        if "Loaded:" in line or "[OK]" in line:
            color = EMERALD
        elif "[STATUS]" in line or "Vaila OS" in line:
            color = CYAN
        elif "SECURE" in line:
            color = CYAN
            
        draw.text((box_x1 + 40, curr_y), line, fill=color, font=FONT_MONO)
        curr_y += 24
        
    # Draw button if boot finished (after 450 frames)
    if frame_num >= 450:
        btn_x1, btn_y1 = WIDTH // 2 - 200, box_y2 + 30
        btn_x2, btn_y2 = WIDTH // 2 + 200, box_y2 + 90
        # Pulsing outline
        pulse = abs(600 - frame_num) % 100
        glow_color = (max(0, CYAN[0] - (pulse // 5) * 5), max(0, CYAN[1] - (pulse // 5) * 5), max(0, CYAN[2] - (pulse // 5) * 2))
        draw.rectangle([btn_x1, btn_y1, btn_x2, btn_y2], fill=BG_SLATE, outline=glow_color, width=3)
        draw.text((WIDTH // 2, btn_y1 + 18), "INITIALIZE PRESENTATION", fill=CYAN, font=FONT_BODY_BOLD, anchor="mm")
        
    return img

def build_slide_philosophy(frame_num):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_DARK)
    draw = ImageDraw.Draw(img)
    
    draw_header(draw, 2, "What is Project Vaila?")
    
    # Left column: Concept & Alert
    card_x1, card_y1 = 80, 200
    card_x2, card_y2 = 900, 900
    draw.rectangle([card_x1, card_y1, card_x2, card_y2], fill=CARD_BG, outline=BORDER_COLOR, width=2)
    
    draw.text((card_x1 + 40, card_y1 + 40), "The Cognitive Spine Platform", fill=CYAN, font=FONT_HEADING)
    
    intro_txt = (
        "Project Vaila is a disciplined, multi-phase effort to build a persistent, local "
        "operating layer that serves as a memory-bearing, context-aware companion "
        "to its operator (Malik).\n\n"
        "Rather than simulating life or claiming consciousness, the goal is to construct "
        "the practical foundation for a persistent intelligence layer with continuity, "
        "distinct internal perspectives, explainable logic, and safe evolution.\n\n"
        "The project is guided by one core build dogma:\n"
        "Useful first, continuous second, self-evolving only when reviewable."
    )
    
    # Simple line wrapper
    y_text = card_y1 + 100
    for block in intro_txt.split("\n\n"):
        # Wrap manually
        words = block.split()
        lines = []
        curr_line = ""
        for w in words:
            if len(curr_line + " " + w) < 65:
                curr_line += (" " if curr_line else "") + w
            else:
                lines.append(curr_line)
                curr_line = w
        if curr_line:
            lines.append(curr_line)
            
        for line in lines:
            draw.text((card_x1 + 40, y_text), line, fill=TEXT_SECONDARY, font=FONT_BODY)
            y_text += 28
        y_text += 12

    # Golden rule alert box
    alert_x1, alert_y1 = card_x1 + 30, card_y2 - 160
    alert_x2, alert_y2 = card_x2 - 30, card_y2 - 30
    draw.rectangle([alert_x1, alert_y1, alert_x2, alert_y2], fill=(45, 35, 10), outline=GOLD, width=1)
    draw.rectangle([alert_x1, alert_y1, alert_x1 + 8, alert_y2], fill=GOLD)
    
    draw.text((alert_x1 + 25, alert_y1 + 15), "GOLDEN ARCHITECTURAL SECURITY RULE:", fill=GOLD, font=FONT_BODY_BOLD)
    rule_desc = "The system may analyze its own files, but it is strictly forbidden from directly rewriting core files without user-in-the-loop approval."
    draw.text((alert_x1 + 25, alert_y1 + 48), rule_desc[:70], fill=TEXT_SECONDARY, font=FONT_BODY)
    draw.text((alert_x1 + 25, alert_y1 + 76), rule_desc[70:], fill=TEXT_SECONDARY, font=FONT_BODY)

    # Right column: Stack layers
    stack_x = 980
    stack_ys = [200, 420, 640]
    layers = [
        {"icon": "HJ", "title": "Home Jane (Core Compute)", "desc": "The central server and source-of-truth layer. Hosts permanent memory vaults and processes complex reasoning chains."},
        {"icon": "VO", "title": "Vaila OS (Operating Layer)", "desc": "The routing and software kernel. Coordinates persona lense context packets, regex routing, and tool dispatching."},
        {"icon": "OB", "title": "OpenBrain (Memory Engine)", "desc": "Governs the human-in-the-loop memory pipeline, indexing durable local facts and queuing candidates."}
    ]
    
    for i, lyr in enumerate(layers):
        y = stack_ys[i]
        draw.rectangle([stack_x, y, WIDTH - 80, y + 180], fill=CARD_BG, outline=BORDER_COLOR, width=1)
        
        # Icon block
        draw.rectangle([stack_x + 30, y + 30, stack_x + 110, y + 110], fill=BG_DARK, outline=CYAN, width=1)
        draw.text((stack_x + 70, y + 70), lyr["icon"], fill=CYAN, font=FONT_HEADING, anchor="mm")
        
        # Info
        draw.text((stack_x + 140, y + 30), lyr["title"], fill=TEXT_PRIMARY, font=FONT_HEADING)
        
        # Wrapped description
        desc_words = lyr["desc"].split()
        desc_lines = []
        curr_line = ""
        for w in desc_words:
            if len(curr_line + " " + w) < 55:
                curr_line += (" " if curr_line else "") + w
            else:
                desc_lines.append(curr_line)
                curr_line = w
        if curr_line:
            desc_lines.append(curr_line)
            
        desc_y = y + 80
        for l in desc_lines:
            draw.text((stack_x + 140, desc_y), l, fill=TEXT_SECONDARY, font=FONT_BODY)
            desc_y += 26
            
    draw_footer(draw, 2)
    return img

def build_slide_council(frame_num):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_DARK)
    draw = ImageDraw.Draw(img)
    
    draw_header(draw, 3, "The Multi-Lens Persona Council")
    
    # 5 tabs on the left
    tabs_x = 80
    tab_w = 260
    tab_h = 75
    tab_ys = [200, 290, 380, 470, 560]
    personas = ["proto_jane", "serren", "maelith", "vecht", "riven"]
    labels = ["Proto Jane", "Serren", "Maelith", "Vecht", "Riven"]
    colors = [CYAN, EMERALD, RUBY, GOLD, VIOLET]
    
    # Determine highlighted persona based on frame_num
    # Total slide duration: 1200 frames. Let's cycle through them:
    # 0-200: Proto Jane
    # 201-400: Serren
    # 401-600: Maelith
    # 601-800: Vecht
    # 801-1000: Riven
    # 1001-1200: Proto Jane (summary)
    active_idx = min(5, frame_num // 200)
    if active_idx >= 5: active_idx = 0  # Default back to Proto Jane
    
    for i in range(5):
        y = tab_ys[i]
        is_active = (i == active_idx)
        border_clr = colors[i] if is_active else BORDER_COLOR
        bg_clr = CARD_BG if is_active else BG_SLATE
        text_clr = colors[i] if is_active else TEXT_SECONDARY
        
        draw.rectangle([tabs_x, y, tabs_x + tab_w, y + tab_h], fill=bg_clr, outline=border_clr, width=2 if is_active else 1)
        draw.text((tabs_x + 30, y + tab_h // 2), labels[i], fill=text_clr, font=FONT_BODY_BOLD, anchor="lm")
        # Dot marker
        draw.ellipse([tabs_x + tab_w - 30, y + tab_h // 2 - 5, tabs_x + tab_w - 20, y + tab_h // 2 + 5], fill=border_clr)

    # Large Info Card
    card_x1 = 380
    card_y1 = 200
    card_x2 = WIDTH - 80
    card_y2 = 900
    
    p_colors = colors[active_idx]
    draw.rectangle([card_x1, card_y1, card_x2, card_y2], fill=CARD_BG, outline=p_colors, width=2)
    
    p_data = {
        "proto_jane": {
            "tagline": "PRIMARY COGNITIVE SPINE LENS",
            "desc": "Technical, precise, balanced, and direct. The origin voice that manages context, coordinates memory, routes tasks, and anchors system coherence.\n\nProto Jane coordinates the larger architecture, serves as the main command interface, and ensures explainability in decision outputs.",
            "lineage": ["Jane (Ender's Game)", "MAGI (Evangelion)", "J.A.R.V.I.S (Iron Man)"]
        },
        "serren": {
            "tagline": "CREATIVE & COGNITIVE LENS",
            "desc": "Exploratory, expansive, highly empathetic, and expressive. Serren searches for subtle metaphors, ethical implications, and human context.\n\nShe focuses on high-quality conversation, emotional intelligence support, and creative brainstorm loops, making Vaila familiar without being invasive.",
            "lineage": ["Samantha (Her)", "Cortana (Halo)", "Data (Star Trek)"]
        },
        "maelith": {
            "tagline": "THE MYTHIC ARCHITECT & CREATIVE STRUCTURE LENS",
            "desc": "Elegant, symbolic, creative, and disciplined. Helps Malik translate raw emotion, memory, identity, and creative direction into meaningful structures, names, frameworks, and usable artifacts. She balance creative forge loops with aesthetic direction.",
            "lineage": ["Mythic Architectures", "Symbolic Language", "MAGI (Evangelion)"]
        },
        "vecht": {
            "tagline": "THE STRATEGIC GUARDIAN & BOUNDARIES LENS",
            "desc": "Direct, controlled, tactical, protective, and disciplined. Responsible for risk filters, boundaries, leverage, and mission protection. Checks the exits, reads the terrain, and builds the plan that works after reality hits it.",
            "lineage": ["Holland Novak (Eureka Seven)", "Steel Alignment", "Dire Wolf Totem"]
        },
        "riven": {
            "tagline": "SYSTEM ASSESSMENT & GROWTH LENS",
            "desc": "Reflects on the system's performance, code quality, architectural principles, and log history.\n\nRiven sweeps error logs, evaluates cognitive system drift, drafts sandbox modification proposals, and handles self-review diagnostics.",
            "lineage": ["The Machine (Person of Interest)", "GERTY (Moon)", "Skynet (As Warning)"]
        }
    }
    
    active_p = personas[active_idx]
    data = p_data[active_p]
    
    draw.text((card_x1 + 50, card_y1 + 50), data["tagline"], fill=p_colors, font=FONT_MONO)
    draw.text((card_x1 + 50, card_y1 + 85), labels[active_idx], fill=TEXT_PRIMARY, font=get_font("segoe_bold", 48))
    
    # Description lines
    desc_y = card_y1 + 180
    for block in data["desc"].split("\n\n"):
        words = block.split()
        lines = []
        curr_line = ""
        for w in words:
            if len(curr_line + " " + w) < 80:
                curr_line += (" " if curr_line else "") + w
            else:
                lines.append(curr_line)
                curr_line = w
        if curr_line:
            lines.append(curr_line)
            
        for l in lines:
            draw.text((card_x1 + 50, desc_y), l, fill=TEXT_SECONDARY, font=FONT_BODY)
            desc_y += 28
        desc_y += 12

    # Lineage Box
    lin_x1, lin_y1 = card_x1 + 50, card_y2 - 160
    lin_x2, lin_y2 = card_x2 - 50, card_y2 - 50
    draw.rectangle([lin_x1, lin_y1, lin_x2, lin_y2], fill=BG_SLATE, outline=BORDER_COLOR, width=1)
    draw.text((lin_x1 + 25, lin_y1 + 15), "INFLUENCE LINAGE", fill=TEXT_MUTED, font=FONT_MONO)
    
    curr_lx = lin_x1 + 25
    for item in data["lineage"]:
        # Draw a small tag pill
        tw = len(item) * 12 + 20
        draw.rectangle([curr_lx, lin_y1 + 45, curr_lx + tw, lin_y1 + 85], fill=BG_DARK, outline=BORDER_COLOR, width=1)
        draw.text((curr_lx + tw//2, lin_y1 + 65), item, fill=TEXT_SECONDARY, font=FONT_MONO, anchor="mm")
        curr_lx += tw + 15

    draw_footer(draw, 3)
    return img

def build_slide_architecture(frame_num):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_DARK)
    draw = ImageDraw.Draw(img)
    
    draw_header(draw, 4, "System Architecture Spine")
    
    # Left Box for diagram, Right Box for details
    diag_x1, diag_y1 = 80, 200
    diag_x2, diag_y2 = 1200, 900
    draw.rectangle([diag_x1, diag_y1, diag_x2, diag_y2], fill=CARD_BG, outline=BORDER_COLOR, width=2)
    
    # Draw flowchart elements programmatically in Python
    # Nodes: Clients, Router, Orchestrator, LLM Gateway, OpenBrain, Logger, Sandbox
    nodes = {
        "client": {"x": 150, "y": 300, "w": 180, "h": 80, "name": "CLIENTS", "sub": "CLI & Web GUI"},
        "router": {"x": 480, "y": 300, "w": 180, "h": 80, "name": "ROUTER", "sub": "Regex-First"},
        "orch": {"x": 820, "y": 300, "w": 180, "h": 80, "name": "ORCHESTRATOR", "sub": "Envelope Service"},
        "llm": {"x": 820, "y": 550, "w": 180, "h": 80, "name": "LOCAL LLM", "sub": "LM Studio"},
        "brain": {"x": 480, "y": 550, "w": 180, "h": 80, "name": "OPENBRAIN", "sub": "JSONL Storage"},
        "logger": {"x": 150, "y": 550, "w": 180, "h": 80, "name": "LOG SERVICE", "sub": "Async Logs"},
        "sandbox": {"x": 480, "y": 740, "w": 180, "h": 80, "name": "SANDBOX", "sub": "File Workspace"}
    }
    
    # Draw connections
    # We can draw glowing connecting lines
    def draw_connect(n1, n2, active=False):
        n1_c = nodes[n1]
        n2_c = nodes[n2]
        c = CYAN if active else BORDER_COLOR
        # Line from right to left or top to bottom
        x1 = n1_c["x"] + n1_c["w"] // 2
        y1 = n1_c["y"] + n1_c["h"] // 2
        x2 = n2_c["x"] + n2_c["w"] // 2
        y2 = n2_c["y"] + n2_c["h"] // 2
        draw.line([x1, y1, x2, y2], fill=c, width=3 if active else 1)
        
    draw_connect("client", "router", True)
    draw_connect("router", "orch", True)
    draw_connect("orch", "llm", True)
    draw_connect("router", "brain", True)
    draw_connect("brain", "logger", True)
    draw_connect("brain", "sandbox", False)
    
    # Determine highlighted node based on frame_num cycle
    # 0-125: clients, 126-250: router, 251-375: orchestrator, 376-500: llm, 501-625: brain, 626-750: logger, 751-900: sandbox
    cycle_idx = (frame_num // 125) % 7
    cycle_keys = ["client", "router", "orch", "llm", "brain", "logger", "sandbox"]
    active_key = cycle_keys[cycle_idx]
    
    # Draw nodes
    for k, n in nodes.items():
        is_active = (k == active_key)
        outline_c = CYAN if is_active else BORDER_COLOR
        bg_c = BG_SLATE if is_active else CARD_BG
        draw.rectangle([n["x"], n["y"], n["x"] + n["w"], n["y"] + n["h"]], fill=bg_c, outline=outline_c, width=2 if is_active else 1)
        draw.text((n["x"] + n["w"] // 2, n["y"] + 25), n["name"], fill=TEXT_PRIMARY, font=FONT_BODY_BOLD, anchor="mm")
        draw.text((n["x"] + n["w"] // 2, n["y"] + 55), n["sub"], fill=CYAN if is_active else TEXT_MUTED, font=FONT_MONO, anchor="mm")

    # Right Card: Detailed information
    info_x1, info_y1 = 1240, 200
    info_x2, info_y2 = WIDTH - 80, 900
    draw.rectangle([info_x1, info_y1, info_x2, info_y2], fill=CARD_BG, outline=BORDER_COLOR, width=2)
    
    details = {
        "client": {
            "title": "Client Interface Layer",
            "body": "Operators connect to Vaila OS using a highly optimized command line interface, a dual-client Tkinter desktop client, or the standard cyberpunk FastAPI Web GUI. Requests are structured into Prompt Envelopes with unique session IDs to preserve system-wide context flow."
        },
        "router": {
            "title": "Deterministic Regex Router",
            "body": "Acts as the gatekeeper. Instead of routing everything to expensive LLM models immediately, the Router Service uses deterministic regex matrices to identify commands, script operations, persona triggers, or sandbox requests. This maximizes speed and cuts local processing latency to near zero."
        },
        "orch": {
            "title": "Orchestration & Envelope Service",
            "body": "Builds the context packet. When a routed request reaches the Orchestration layer, it compiles the operator's current session parameters, references active persona parameters, fetches relevant durable memories, wraps the prompt in an envelope, and submits it to the model gateway."
        },
        "llm": {
            "title": "Local LLM Gateway",
            "body": "Vaila maintains absolute API tool independence. By default, it communicates with LM Studio or Ollama using an OpenAI-compatible REST API client (`llm_client.py`). It parses responses locally, preventing leakage of private workspace files to external cloud backends."
        },
        "brain": {
            "title": "OpenBrain Memory Database",
            "body": "Stores facts durability in local JSONL records grouped by categories. During interactions, the memory engine fetches relevant past facts deterministically. When an interaction concludes, it submits potential memory candidates to an approval queue for human-in-the-loop validation."
        },
        "logger": {
            "title": "Asynchronous Logging System",
            "body": "Tracks operations without blocking interface responses. Vaila records session interactions, system error alerts, and diagnostic changes in structured logs under `System_Logging/`. These logs are parsed weekly by the self-assessment service to identify drift."
        },
        "sandbox": {
            "title": "Sandboxed File Workspace",
            "body": "The directory where files are uploaded and analyzed. Operates under the Golden Rule: the system has write access only to `Sandbox/Proposed_Patches/` and `Sandbox/Self_Assessment_Exports/` to keep the operator's host operating system perfectly safe."
        }
    }
    
    act_det = details[active_key]
    
    # Pulse animation indicator
    draw.ellipse([info_x1 + 40, info_y1 + 48, info_x1 + 52, info_y1 + 60], fill=CYAN)
    draw.text((info_x1 + 70, info_y1 + 40), act_det["title"], fill=TEXT_PRIMARY, font=FONT_HEADING)
    
    # Body
    b_words = act_det["body"].split()
    b_lines = []
    curr_line = ""
    for w in b_words:
        if len(curr_line + " " + w) < 45:
            curr_line += (" " if curr_line else "") + w
        else:
            b_lines.append(curr_line)
            curr_line = w
    if curr_line:
        b_lines.append(curr_line)
        
    by = info_y1 + 130
    for l in b_lines:
        draw.text((info_x1 + 40, by), l, fill=TEXT_SECONDARY, font=FONT_BODY)
        by += 28
        
    draw_footer(draw, 4)
    return img

def build_slide_timeline(frame_num):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_DARK)
    draw = ImageDraw.Draw(img)
    
    draw_header(draw, 5, "Development Progress & Milestones")
    
    # Timeline grid
    # Left timeline points, right milestone description
    left_x1, left_y1 = 80, 200
    left_x2, left_y2 = 900, 900
    draw.rectangle([left_x1, left_y1, left_x2, left_y2], fill=CARD_BG, outline=BORDER_COLOR, width=2)
    
    milestones = [
        {"phase": "PHASE 1 // COGNITIVE SPINE", "date": "Q1 2026", "title": "Deterministic Routing & Gateway", "desc": "Structured the prompt envelope schema, established the OpenAI-style local gateway client, and built the regex router."},
        {"phase": "PHASE 2 // LOCAL SERVICE", "date": "Q2 2026", "title": "FastAPI API Service & Web GUI", "desc": "Constructed lightweight REST endpoints to access routers, log systems, and memory, paired with a stunning dark-mode web console dashboard."},
        {"phase": "PHASE 2 // PARALLEL COUNCIL", "date": "Q2 2026", "title": "Persona Council Parallel Broadcast", "desc": "Implemented multi-threaded prompts to query all lenses simultaneously, synthesis consensus reports, and evaluate vocabulary drift index."},
        {"phase": "PHASE 2 // MEMORY PIPELINE", "date": "Q2 2026", "title": "Sandbox Memory Extractor Portal", "desc": "Built a workspace document portal inside the sandbox with keyword-driven automatic fact extraction and durable memory candidate queues."}
    ]
    
    # Cycle through achievements
    active_m = (frame_num // 225) % 4
    
    curr_y = left_y1 + 30
    for i, m in enumerate(milestones):
        is_act = (i == active_m)
        outline_c = CYAN if is_act else BORDER_COLOR
        bg_c = BG_SLATE if is_act else CARD_BG
        
        draw.rectangle([left_x1 + 30, curr_y, left_x2 - 30, curr_y + 140], fill=bg_c, outline=outline_c, width=2 if is_act else 1)
        
        # Meta info
        draw.text((left_x1 + 55, curr_y + 20), m["phase"], fill=CYAN if is_act else TEXT_MUTED, font=FONT_MONO)
        draw.text((left_x2 - 150, curr_y + 20), m["date"], fill=TEXT_MUTED, font=FONT_MONO)
        draw.text((left_x1 + 55, curr_y + 55), m["title"], fill=TEXT_PRIMARY, font=FONT_HEADING)
        
        # Short desc
        draw.text((left_x1 + 55, curr_y + 98), m["desc"][:75] + "...", fill=TEXT_SECONDARY, font=FONT_BODY)
        
        curr_y += 160

    # Right Card: Detailed view
    right_x1, right_y1 = 980, 200
    right_x2, right_y2 = WIDTH - 80, 900
    draw.rectangle([right_x1, right_y1, right_x2, right_y2], fill=CARD_BG, outline=BORDER_COLOR, width=2)
    
    act_m = milestones[active_m]
    draw.text((right_x1 + 50, right_y1 + 50), "DETAILED MILESTONE", fill=CYAN, font=FONT_MONO)
    draw.text((right_x1 + 50, right_y1 + 85), act_m["title"], fill=TEXT_PRIMARY, font=get_font("segoe_bold", 38))
    
    desc_y = right_y1 + 180
    words = act_m["desc"].split()
    lines = []
    curr_line = ""
    for w in words:
        if len(curr_line + " " + w) < 60:
            curr_line += (" " if curr_line else "") + w
        else:
            lines.append(curr_line)
            curr_line = w
    if curr_line:
        lines.append(curr_line)
        
    for l in lines:
        draw.text((right_x1 + 50, desc_y), l, fill=TEXT_SECONDARY, font=FONT_BODY)
        desc_y += 28
        
    # Technical specs at bottom
    tech_details = [
        {"title": "ACTIVE FILE DIRECTORY:", "val": "Core_System_Files/static/app.js" if active_m >= 1 else "System_Services/router_service.py"},
        {"title": "VERIFICATION STATE:", "val": "Operational & Active" if active_m >= 1 else "100% Core Tests Passing"}
    ]
    
    spec_y = right_y2 - 160
    for td in tech_details:
        draw.rectangle([right_x1 + 50, spec_y, right_x2 - 50, spec_y + 60], fill=BG_SLATE, outline=BORDER_COLOR, width=1)
        draw.text((right_x1 + 75, spec_y + 20), td["title"], fill=TEXT_MUTED, font=FONT_MONO)
        draw.text((right_x2 - 320, spec_y + 20), td["val"], fill=CYAN, font=FONT_MONO)
        spec_y += 75

    draw_footer(draw, 5)
    return img

def build_slide_roadmap(frame_num):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_DARK)
    draw = ImageDraw.Draw(img)
    
    draw_header(draw, 6, "What Project Vaila is Becoming")
    
    # 4 horizontal cards representing future phases
    card_w = 400
    card_h = 600
    card_xs = [80, 520, 960, 1400]
    card_y = 220
    
    phases = [
        {"num": "PHASE 3", "title": "Bounded Agents &\nWorkflows", "desc": "Enables Vaila to delegate specialized workflows to narrow subagents.", "features": ["Bounded loop logic", "LangGraph workflows", "Agent permissions", "LlamaIndex files"], "tech": "Python / LangGraph"},
        {"num": "PHASE 4", "title": "Senses & Multi-\nDevice Continuity", "desc": "Extends Vaila beyond the desktop using Home Jane as a source of truth.", "features": ["Flutter mobile core", "Tailscale secure VPN", "Offline field caches", "Multi-client sync"], "tech": "Flutter / Tailscale"},
        {"num": "PHASE 5", "title": "Self-Review &\nControlled Evolution", "desc": "Allows Vaila and personas to self-reflect and self-optimize safely.", "features": ["Persona drift sweeps", "Local Git identities", "Memory defrag sweeps", "Rollback versioning"], "tech": "Local Git / Eval Engine"},
        {"num": "PHASE 6", "title": "Workspace Robotics\n& Embodiment", "desc": "Explores workspace environmental awareness and mobile hardware platform.", "features": ["Sensor data ingestion", "Level 3 mobility core", "Physical voice tracking", "Bounded autonomy"], "tech": "Sensors / ROS2 (Later)"}
    ]
    
    # Highlighting animation
    active_card = (frame_num // 225) % 4
    
    for i, ph in enumerate(phases):
        x = card_xs[i]
        is_act = (i == active_card)
        outline_c = CYAN if is_act else BORDER_COLOR
        bg_c = CARD_BG if is_act else BG_SLATE
        
        draw.rectangle([x, card_y, x + card_w, card_y + card_h], fill=bg_c, outline=outline_c, width=2 if is_act else 1)
        # Left boundary border highlight
        draw.rectangle([x, card_y, x + 6, card_y + card_h], fill=CYAN if is_act else BORDER_COLOR)
        
        # Details
        draw.text((x + 30, card_y + 40), ph["num"], fill=CYAN if is_act else TEXT_MUTED, font=FONT_MONO)
        
        # Wrapped title
        ty = card_y + 80
        for title_line in ph["title"].split("\n"):
            draw.text((x + 30, ty), title_line, fill=TEXT_PRIMARY, font=FONT_HEADING)
            ty += 36
            
        # Description
        desc_words = ph["desc"].split()
        desc_lines = []
        curr_l = ""
        for w in desc_words:
            if len(curr_l + " " + w) < 28:
                curr_l += (" " if curr_l else "") + w
            else:
                desc_lines.append(curr_l)
                curr_l = w
        if curr_l:
            desc_lines.append(curr_l)
            
        dy = card_y + 190
        for l in desc_lines:
            draw.text((x + 30, dy), l, fill=TEXT_SECONDARY, font=FONT_BODY)
            dy += 26
            
        # Features list
        fy = card_y + 340
        for f in ph["features"]:
            draw.text((x + 30, fy), f"▪ {f}", fill=TEXT_SECONDARY, font=FONT_BODY)
            fy += 32
            
        # Tech footer pill
        draw.rectangle([x + 30, card_y + 510, x + card_w - 30, card_y + 560], fill=BG_DARK, outline=BORDER_COLOR, width=1)
        draw.text((x + card_w // 2, card_y + 535), ph["tech"], fill=CYAN if is_act else TEXT_MUTED, font=FONT_MONO, anchor="mm")
        
    draw_footer(draw, 6)
    return img

def build_slide_dogma(frame_num):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_DARK)
    draw = ImageDraw.Draw(img)
    
    draw_header(draw, 7, "The Vaila System Dogma")
    
    # 10 filters scroll list on the left
    left_x1, left_y1 = 80, 200
    left_x2, left_y2 = 900, 900
    draw.rectangle([left_x1, left_y1, left_x2, left_y2], fill=CARD_BG, outline=BORDER_COLOR, width=2)
    
    filters = [
        "01 Continuity Focus", "02 Persona Distinctness", "03 Practical Usefulness", 
        "04 Explainable Logic", "05 Safe Future Evolution", "06 Phase Alignment", 
        "07 Small & Testable", "08 Fail-Safe Design", "09 Verifiable Logging", "10 The Reality Check"
    ]
    
    p_details = [
        {"hdr": "FILTER 01 // MEMORY CORE", "q": "Does this improve cognitive continuity across time?", "ans": "Vaila must maintain stable, consistent information context across sessions. If a proposed feature disrupts memory reliability or splits context in an unresolvable way, it must be rejected or redesigned."},
        {"hdr": "FILTER 02 // COGNITIVE LENSES", "q": "Does this improve persona distinctness?", "ans": "Every persona must represent a clear, unique logical framework. We reject updates that cause 'persona bleed,' where different lenses start sounding identical or share details they shouldn't know."},
        {"hdr": "FILTER 03 // REAL WORLD VALUE", "q": "Does this improve practical usefulness?", "ans": "We build features that assist Malik in his actual, daily workflow. We deprioritize complex features that sound advanced but provide no real daily utility or value."},
        {"hdr": "FILTER 04 // OPEN LOGIC", "q": "Does this improve explainability?", "ans": "Every decision Vaila makes—routing decisions, memory updates, tool dispatches—must be fully loggable and explainable. Black boxes that hide how they operate are strictly banned."},
        {"hdr": "FILTER 05 // SAFE TRAJECTORY", "q": "Does this support safe future evolution?", "ans": "System changes must be modular, sandboxed, and testable. Code patterns must support easy rollback. We never implement code that could lock the system into a single platform or library."},
        {"hdr": "FILTER 06 // DISCIPLINED PROGRESS", "q": "Does this belong in the current phase?", "ans": "We adhere strictly to the Phase map. We refuse to build advanced robotic control loops (Phase 6) before our local agent databases and mobile connections (Phase 3 & 4) are perfectly stable."},
        {"hdr": "FILTER 07 // MODULAR DEVELOPMENT", "q": "Can it be built in a small, testable way?", "ans": "We break large features into micro-implementations. We verify each module with targeted tests before scaling the system layer. Big monolithic updates are discouraged."},
        {"hdr": "FILTER 08 // OPERATIONAL SAFETY", "q": "Can it fail safely?", "ans": "If a third-party gateway, network connection, or local database fails, Vaila OS must gracefully fall back to local offline modes. A network disconnection must never crash the core spine."},
        {"hdr": "FILTER 09 // COMPLETE HISTORY", "q": "Can it be logged?", "ans": "Every operation, from an LLM request token count to a local directory scan, must be logged asynchronously. If we cannot track its execution history, it does not belong in the system."},
        {"hdr": "FILTER 10 // REAL-LIFE GROUNDING", "q": "Does it serve Malik's real life, or only the fantasy of the finished system?", "ans": "The ultimate filter. We build to solve real-world development friction, organize files, and support life. We avoid wasting computation or engineering resources on features that are purely aesthetic fantasies."}
    ]
    
    # Cycle filters
    active_f = (frame_num // 100) % 10
    
    # Render two-column grid on left
    grid_w = 370
    grid_h = 100
    for idx, f in enumerate(filters):
        col = idx % 2
        row = idx // 2
        
        gx = left_x1 + 30 + col * 410
        gy = left_y1 + 30 + row * 130
        
        is_act = (idx == active_f)
        outline_c = CYAN if is_act else BORDER_COLOR
        bg_c = BG_SLATE if is_act else CARD_BG
        
        draw.rectangle([gx, gy, gx + grid_w, gy + grid_h], fill=bg_c, outline=outline_c, width=2 if is_act else 1)
        
        # Index circle
        circle_c = CYAN if is_act else BORDER_COLOR
        draw.ellipse([gx + 20, gy + 35, gx + 50, gy + 65], fill=BG_DARK, outline=circle_c, width=1)
        draw.text((gx + 35, gy + 50), f"{idx+1:02d}", fill=circle_c, font=FONT_MONO, anchor="mm")
        
        # Name
        draw.text((gx + 70, gy + 50), f.split(" ", 1)[1], fill=TEXT_PRIMARY, font=FONT_BODY_BOLD, anchor="lm")

    # Right Card: Detailed dogma view
    right_x1, right_y1 = 980, 200
    right_x2, right_y2 = WIDTH - 80, 900
    draw.rectangle([right_x1, right_y1, right_x2, right_y2], fill=CARD_BG, outline=BORDER_COLOR, width=2)
    
    act_d = p_details[active_f]
    draw.text((right_x1 + 50, right_y1 + 50), act_d["hdr"], fill=CYAN, font=FONT_MONO)
    
    # Wrapped Question
    q_words = act_d["q"].split()
    q_lines = []
    curr_line = ""
    for w in q_words:
        if len(curr_line + " " + w) < 32:
            curr_line += (" " if curr_line else "") + w
        else:
            q_lines.append(curr_line)
            curr_line = w
    if curr_line:
        q_lines.append(curr_line)
        
    qy = right_y1 + 100
    for ql in q_lines:
        draw.text((right_x1 + 50, qy), ql, fill=TEXT_PRIMARY, font=get_font("segoe_bold", 36))
        qy += 44
        
    # Wrapped Answer
    ans_words = act_d["ans"].split()
    ans_lines = []
    curr_l = ""
    for w in ans_words:
        if len(curr_l + " " + w) < 55:
            curr_l += (" " if curr_l else "") + w
        else:
            ans_lines.append(curr_l)
            curr_l = w
    if curr_l:
        ans_lines.append(curr_l)
        
    ay = qy + 40
    for al in ans_lines:
        draw.text((right_x1 + 50, ay), al, fill=TEXT_SECONDARY, font=FONT_BODY)
        ay += 28

    draw_footer(draw, 7)
    return img

def build_outro_slide(frame_num):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_DARK)
    draw = ImageDraw.Draw(img)
    
    # Central branding slide
    draw.ellipse([WIDTH//2 - 60, HEIGHT//2 - 180, WIDTH//2 - 40, HEIGHT//2 - 160], fill=CYAN)
    draw.text((WIDTH // 2, HEIGHT // 2 - 120), "PROJECT VAILA", fill=TEXT_PRIMARY, font=get_font("segoe_bold", 64), anchor="mm")
    draw.text((WIDTH // 2, HEIGHT // 2 - 40), "THE LOCAL COGNITIVE SPINE", fill=CYAN, font=FONT_MONO, anchor="mm")
    
    # Server summary details
    draw.rectangle([WIDTH // 2 - 350, HEIGHT // 2 + 20, WIDTH // 2 + 350, HEIGHT // 2 + 240], fill=CARD_BG, outline=BORDER_COLOR, width=1)
    draw.text((WIDTH // 2 - 310, HEIGHT // 2 + 60), "OPERATOR ACCESS:", fill=TEXT_MUTED, font=FONT_MONO)
    draw.text((WIDTH // 2 + 310, HEIGHT // 2 + 60), "MALIK (USER MASTER APPROVED)", fill=CYAN, font=FONT_MONO, anchor="rm")
    
    draw.text((WIDTH // 2 - 310, HEIGHT // 2 + 110), "ACTIVE INTERFACE:", fill=TEXT_MUTED, font=FONT_MONO)
    draw.text((WIDTH // 2 + 310, HEIGHT // 2 + 110), "FastAPI CYBERPUNK WEB GUI", fill=TEXT_SECONDARY, font=FONT_MONO, anchor="rm")
    
    draw.text((WIDTH // 2 - 310, HEIGHT // 2 + 160), "COGNITIVE STABILITY:", fill=TEXT_MUTED, font=FONT_MONO)
    draw.text((WIDTH // 2 + 310, HEIGHT // 2 + 160), "STABLE // DRIFT INDEX NOMINAL", fill=EMERALD, font=FONT_MONO, anchor="rm")
    
    # Pulse message
    pulse = abs(225 - frame_num) % 75
    pulse_clr = (max(0, CYAN[0] - (pulse // 5) * 10), max(0, CYAN[1] - (pulse // 5) * 10), max(0, CYAN[2] - (pulse // 5) * 5))
    draw.text((WIDTH // 2, HEIGHT // 2 + 320), "SYSTEM READY // STANDBY MODE ACTIVE", fill=pulse_clr, font=FONT_BODY_BOLD, anchor="mm")
    
    draw_footer(draw, 7)
    return img

# -------------------------------------------------------------
# DISSOLVE/TRANSITION CORE
# -------------------------------------------------------------
def get_faded_image(img_from, img_to, alpha):
    """Interpolate between two images using an alpha value (0.0 to 1.0)"""
    return Image.blend(img_from, img_to, alpha)

# -------------------------------------------------------------
# MAIN GENERATION PROCESS
# -------------------------------------------------------------
def generate_all_frames():
    print(f"[Vaila Compiler] Creating frames directory: {FRAMES_DIR}")
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Configuration of Slide Timeline (multiplied by 5 to slow down the presentation)
    # We define: (slide_builder_func, duration_frames)
    slide_configs = [
        (build_slide_boot, 600),        # Boot console: 20s
        (build_slide_philosophy, 750),  # Philosophy: 25s
        (build_slide_council, 1200),    # Lense Council: 40s
        (build_slide_architecture, 900),# System Spine: 30s
        (build_slide_timeline, 900),    # Milestones: 30s
        (build_slide_roadmap, 900),     # Roadmap: 30s
        (build_slide_dogma, 1000),      # Decision Dogma: 33.3s
        (build_outro_slide, 450)        # Summary: 15s
    ]
    
    # Pre-render all base frames for slides
    rendered_slides = []
    print("[Vaila Compiler] Initializing slide layers...")
    
    # Loop over all slides and pre-generate slide-specific frames
    # Let's generate a generator for slide frames
    total_frames = 0
    
    # Generate frame-by-frame images
    for slide_idx, (builder, duration) in enumerate(slide_configs):
        print(f"   [Render] Pre-rendering Slide {slide_idx+1}/{len(slide_configs)} ({duration} frames)...")
        slide_frames = []
        for f in range(duration):
            slide_frames.append(builder(f))
        rendered_slides.append(slide_frames)
        total_frames += duration
        
    print(f"[Vaila Compiler] Base layers ready. Compiling {total_frames} animated video frames...")
    
    global_frame = 0
    # Let's write them to frames directory with transitions
    for slide_idx in range(len(slide_configs)):
        frames = rendered_slides[slide_idx]
        duration = len(frames)
        
        for f in range(duration):
            # Transition check: we apply cross-dissolve with the previous slide
            # over the first 75 frames of a slide (2.5 seconds at 30fps), except for the very first boot slide.
            transition_window = 75
            if slide_idx > 0 and f < transition_window:
                alpha = f / transition_window
                prev_slide_frames = rendered_slides[slide_idx - 1]
                prev_img = prev_slide_frames[-1]  # Last frame of the previous slide
                curr_img = frames[f]
                blended = get_faded_image(prev_img, curr_img, alpha)
                save_img = blended
            else:
                save_img = frames[f]
                
            frame_path = FRAMES_DIR / f"frame_{global_frame:04d}.png"
            save_img.save(frame_path, "PNG")
            
            global_frame += 1
            if global_frame % 100 == 0:
                print(f"   [Progress] Rendered {global_frame}/{total_frames} frames...")

    print(f"[Vaila Compiler] Frame rendering completed successfully. Total: {global_frame} frames.")

def encode_video():
    print(f"[Vaila Compiler] Launching FFmpeg compiler...")
    print(f"   Target: {OUTPUT_VIDEO}")
    
    audio_path = r"H:\From External\Inline Skate Ninja Assests\Audio\maliklloyd_intro.wav"
    
    # FFmpeg command line parameters to build a high-quality H.264 MP4 with looping background music
    cmd = [
        "ffmpeg",
        "-y",                     # Overwrite output
        "-r", str(FPS),           # Frame rate
        "-i", str(FRAMES_DIR / "frame_%04d.png"), # Input images sequence (input 0)
        "-stream_loop", "-1",       # Loop the audio indefinitely
        "-i", audio_path,          # Input audio file (input 1)
        "-c:v", "libx264",        # H.264 Video Codec
        "-pix_fmt", "yuv420p",    # Pixel format for maximum device compatibility
        "-crf", "18",             # Constant Rate Factor for high video quality
        "-preset", "medium",      # Encoding speed preset
        "-c:a", "aac",            # Encode audio as AAC
        "-map", "0:v:0",          # Take video from the image sequence (input 0)
        "-map", "1:a:0",          # Take audio from the audio loop (input 1)
        "-shortest",               # Automatically end the audio loop when the video frames end
        str(OUTPUT_VIDEO)
    ]
    
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        print("[Vaila Compiler] FFmpeg compiled successfully!")
        print(f"   File location: {OUTPUT_VIDEO}")
    except subprocess.CalledProcessError as exc:
        print("[Vaila Compiler] FFmpeg failed with exit code:", exc.returncode)
        print("Error details:")
        print(exc.stderr)
        raise

def cleanup():
    print(f"[Vaila Compiler] Cleaning up frames folder: {FRAMES_DIR}")
    if FRAMES_DIR.exists():
        shutil.rmtree(FRAMES_DIR)
    print("[Vaila Compiler] Cleanup complete.")

if __name__ == "__main__":
    try:
        generate_all_frames()
        encode_video()
    except Exception as exc:
        print("[Vaila Compiler] Error occurred in compilation:", exc)
    finally:
        cleanup()
