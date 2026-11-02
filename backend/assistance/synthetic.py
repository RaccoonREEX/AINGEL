"""Server-controlled synthetic material: the only content that may reach Meta without the person's authorization for
real data.

A client saying that something is synthetic proves nothing: a typed question, a photo, a clip or microphone audio
can hold anyone's private data. So a request without that authorization may only name a fixture defined here. The
server builds the content itself, with a fictitious profile, and never reads the person's profile (name,
preferences, support needs, allergies, notes, memories, history, locale). The old `synthetic` declaration is refused,
and so is free content sent next to a fixture, before any provider request is built.

Every function that calls Meta also receives the basis the view decided (FIXTURE or REAL) and refuses without one.
"""

import io
import os
import tempfile
from pathlib import Path

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .persona import profile_preferences

FIXTURE = "synthetic_fixture"
REAL = "authorized_real"
LOCALES = ("es-EC", "en-US")

# A fictitious adult with the default style: not anyone's profile.
FICTIONAL_PREFERENCES = profile_preferences({})

QUESTIONS = {
    "greeting": {"es-EC": "Hola, ¿cómo estás hoy?", "en-US": "Hello, how are you today?"},
    "capabilities": {"es-EC": "¿En qué me puedes ayudar en casa?", "en-US": "How can you help me at home?"},
    "hydration": {
        "es-EC": "¿Por qué es importante tomar agua durante el día?",
        "en-US": "Why is it important to drink water during the day?",
    },
    "morning": {
        "es-EC": "Dame una idea sencilla para organizar la mañana.",
        "en-US": "Give me one simple idea to organize the morning.",
    },
}
IMAGES = {
    "shapes": {"es-EC": "Figuras: cuadrado azul y círculo rojo", "en-US": "Shapes: blue square and red circle"},
    # Deep vision (AINGEL 3.0): drawn by the server, no real person, document or artwork.
    "drawing_dog": {"es-EC": "Dibujo a mano de un perro", "en-US": "Hand drawing of a dog"},
    "drawing_ambiguous": {"es-EC": "Dibujo de trazos ambiguos", "en-US": "Drawing of ambiguous strokes"},
    "face_drawn": {"es-EC": "Retrato ilustrado de una persona ficticia", "en-US": "Illustrated portrait of a fictitious person"},
    "document_page": {"es-EC": "Página de un libro ficticio", "en-US": "Page of a fictitious book"},
    "chart_bars": {"es-EC": "Gráfico de barras", "en-US": "Bar chart"},
    "screen_desktop": {"es-EC": "Pantalla de Windows ficticia", "en-US": "Fictitious Windows screen"},
}
# Find-object fixtures: the shapes image and an object name fixed here (the segmentation prompt is English).
OBJECTS = {
    "blue_square": {"es-EC": "Cuadrado azul", "en-US": "Blue square", "prompt": "blue square"},
    "red_circle": {"es-EC": "Círculo rojo", "en-US": "Red circle", "prompt": "red circle"},
}
# Documents (AINGEL 3.0, phase 3): a digital book with chapters and a figure, and a scanned PDF without text.
DOCUMENTS = {
    "book_pdf": {"es-EC": "Libro ficticio en PDF (4 páginas, 3 capítulos)", "en-US": "Fictitious PDF book (4 pages, 3 chapters)"},
    "scanned_pdf": {"es-EC": "PDF escaneado ficticio (2 páginas, sin texto)", "en-US": "Fictitious scanned PDF (2 pages, no text)"},
}
CLIPS = {"moving_square": {"es-EC": "Un cuadrado azul cruza la mesa", "en-US": "A blue square crosses the table"}}
CATALOG = {"question": QUESTIONS, "image": IMAGES, "object": OBJECTS, "clip": CLIPS, "document": DOCUMENTS}


def enabled():
    """Fixtures are the synthetic-test mode of the server (AINGEL_SYNTHETIC_TESTS_ONLY=1)."""
    return os.environ.get("AINGEL_SYNTHETIC_TESTS_ONLY", "1") == "1"


def require_basis(basis):
    """True only for a basis decided by a view; provider calls check it before building any payload."""
    return basis in (FIXTURE, REAL)


def route(data, kind, real, content):
    """How a request may proceed: ("fixture", id), ("real", None), ("mock", None) or (None, error code).

    [real]: the person's own authorization for this kind of data (care.consent), already checked by the caller.
    [content]: request fields that carry free content or personal context; none may accompany a fixture.
    Without a fixture or that authorization, free content only reaches the local test mode, never Meta.
    """
    if "synthetic" in data:
        return None, "synthetic_fixture_required"
    fixture = data.get("fixture")
    if fixture is not None:
        if not isinstance(fixture, str) or fixture not in CATALOG[kind]:
            return None, "synthetic_fixture_invalid"
        if not enabled():
            return None, "synthetic_tests_disabled"
        if any(field in data for field in content):
            return None, "synthetic_fixture_only"
        return "fixture", fixture
    if real:
        return "real", None
    if os.environ.get("AINGEL_AI_MODE", "mock") == "meta":
        return None, "privacy_review_required"
    return "mock", None


def locale(data):
    """The fixture's language, chosen in the request (never the profile's)."""
    value = data.get("locale", "es-EC")
    return value if value in LOCALES else None


def question(fixture, language):
    return QUESTIONS[fixture][language]


def shapes_image():
    """A blue square on the left and a red circle on the right, on a light background (JPEG)."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (640, 480), (236, 236, 232))
    draw = ImageDraw.Draw(image)
    draw.rectangle((90, 170, 230, 310), fill=(30, 80, 200))
    draw.ellipse((410, 170, 550, 310), fill=(210, 40, 40))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=90)
    return output.getvalue()


def moving_square_clip(seconds=6, fps=10):
    """An MP4: a still table for one second, then a blue square enters from the left and crosses it."""
    import cv2
    import numpy as np

    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "fixture.mp4")
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (480, 320))
        for i in range(seconds * fps):
            frame = np.full((320, 480, 3), 230, np.uint8)
            cv2.rectangle(frame, (0, 220), (480, 235), (120, 120, 120), -1)
            if i >= fps:
                x = -60 + (i - fps) * 9
                cv2.rectangle(frame, (x, 150), (x + 60, 210), (200, 80, 20), -1)
            writer.write(frame)
        writer.release()
        return Path(path).read_bytes()


def _jpeg(image):
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=90)
    return output.getvalue()


def dog_drawing():
    """A simple ink drawing of a dog on paper (the recognizable-drawing test): body, head with floppy ears, legs,
    tail, collar and a ground line."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (800, 600), (250, 248, 240))
    draw = ImageDraw.Draw(image)
    ink, brown = (35, 35, 35), (150, 95, 50)
    draw.line((60, 520, 740, 520), fill=(120, 160, 80), width=4)
    draw.ellipse((230, 280, 560, 430), fill=(205, 160, 105), outline=ink, width=6)
    for x in (280, 340, 450, 510):
        draw.rectangle((x, 400, x + 34, 515), fill=(205, 160, 105), outline=ink, width=5)
        draw.ellipse((x - 8, 500, x + 44, 525), fill=(205, 160, 105), outline=ink, width=5)
    draw.line((235, 330, 190, 280, 170, 220), fill=ink, width=8, joint="curve")
    draw.ellipse((470, 130, 650, 300), fill=(205, 160, 105), outline=ink, width=6)
    draw.ellipse((440, 140, 500, 290), fill=brown, outline=ink, width=5)
    draw.ellipse((620, 140, 680, 290), fill=brown, outline=ink, width=5)
    draw.ellipse((515, 185, 535, 205), fill=ink)
    draw.ellipse((585, 185, 605, 205), fill=ink)
    draw.ellipse((535, 225, 585, 255), fill=(240, 220, 190), outline=ink, width=4)
    draw.ellipse((548, 222, 572, 240), fill=ink)
    draw.arc((530, 240, 590, 280), 20, 160, fill=ink, width=4)
    draw.ellipse((552, 266, 570, 290), fill=(230, 110, 120), outline=ink, width=3)
    draw.arc((480, 255, 640, 330), 30, 150, fill=(200, 40, 40), width=10)
    return _jpeg(image)


def ambiguous_drawing():
    """Overlapping loops and scribbles that do not clearly represent anything (the ambiguous-drawing test)."""
    import math
    import random

    from PIL import Image, ImageDraw

    generator = random.Random(20261031)
    image = Image.new("RGB", (800, 600), (250, 248, 240))
    draw = ImageDraw.Draw(image)
    for stroke in range(7):
        cx, cy = generator.randint(200, 600), generator.randint(160, 440)
        radius, turns = generator.randint(40, 140), generator.uniform(1.2, 2.6)
        points = [
            (cx + radius * math.cos(t / 20) * (1 + 0.3 * math.sin(t / 7)), cy + radius * 0.7 * math.sin(t / 20 * 1.3))
            for t in range(int(turns * 126))
        ]
        color = ((40, 40, 40), (60, 90, 170), (170, 70, 50))[stroke % 3]
        draw.line(points, fill=color, width=generator.randint(2, 7), joint="curve")
    return _jpeg(image)


def drawn_face():
    """A flat illustration of a fictitious adult's face (the face-description test without a real person)."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (600, 700), (225, 232, 240))
    draw = ImageDraw.Draw(image)
    skin, ink, hair = (214, 168, 130), (45, 35, 30), (70, 50, 40)
    draw.rectangle((200, 560, 400, 700), fill=skin)
    draw.rounded_rectangle((90, 600, 510, 760), radius=80, fill=(40, 90, 140))
    draw.ellipse((150, 120, 450, 540), fill=skin, outline=ink, width=3)
    draw.chord((140, 70, 460, 330), 180, 360, fill=hair)
    draw.ellipse((130, 280, 170, 360), fill=skin, outline=ink, width=3)
    draw.ellipse((430, 280, 470, 360), fill=skin, outline=ink, width=3)
    for x in (215, 335):
        draw.arc((x, 255, x + 60, 285), 200, 340, fill=hair, width=9)
        draw.ellipse((x + 8, 290, x + 52, 320), fill=(255, 255, 255), outline=ink, width=2)
        draw.ellipse((x + 20, 293, x + 42, 317), fill=(110, 70, 40))
        draw.ellipse((x + 27, 300, x + 35, 310), fill=ink)
        draw.rounded_rectangle((x - 5, 280, x + 65, 330), radius=12, outline=(30, 30, 30), width=4)
    draw.line((285, 305, 315, 305), fill=(30, 30, 30), width=4)
    draw.line((300, 320, 290, 390, 312, 395), fill=ink, width=3)
    draw.arc((240, 400, 360, 470), 15, 165, fill=(150, 60, 60), width=7)
    draw.arc((175, 330, 425, 560), 30, 150, fill=(95, 75, 65), width=2)
    return _jpeg(image)


def document_page():
    """A page of a fictitious book: chapter title, two paragraphs and a page number."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (900, 1200), (252, 251, 246))
    draw = ImageDraw.Draw(image)
    title, body = ImageFont.load_default(size=44), ImageFont.load_default(size=30)
    # Only unaccented words: Pillow's built-in font has no accented glyphs, and a missing glyph would read as noise.
    draw.text((90, 90), "Parte 3. La casa de Rosa", font=title, fill=(20, 20, 20))
    lines = [
        "La casa de Rosa estaba al final de la calle,",
        "junto a un parque con dos limoneros grandes.",
        "Antes de ir al mercado, Rosa regaba las plantas",
        "y saludaba a los vecinos de la esquina.",
        "",
        "En el centro del patio estaba una fuente redonda.",
        "Los vecinos contaban que el agua sonaba como",
        "lluvia y que por eso los gorriones llegaban temprano.",
    ]
    for row, line in enumerate(lines):
        draw.text((90, 200 + row * 52), line, font=body, fill=(30, 30, 30))
    draw.text((430, 1110), "42", font=body, fill=(60, 60, 60))
    return _jpeg(image)


def bar_chart():
    """A bar chart with a title, labelled axes and five values (S1 4, S2 6, S3 5, S4 8, S5 7), unaccented text."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (900, 650), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    font, small = ImageFont.load_default(size=32), ImageFont.load_default(size=24)
    draw.text((180, 30), "Vasos de agua en cinco semanas", font=font, fill=(20, 20, 20))
    draw.line((120, 560, 840, 560), fill=(30, 30, 30), width=3)
    draw.line((120, 100, 120, 560), fill=(30, 30, 30), width=3)
    for value in range(0, 11, 2):
        y = 560 - value * 42
        draw.text((80, y - 12), str(value), font=small, fill=(30, 30, 30))
        draw.line((115, y, 840, y), fill=(225, 225, 225), width=1)
    for index, (day, value) in enumerate((("S1", 4), ("S2", 6), ("S3", 5), ("S4", 8), ("S5", 7))):
        x = 160 + index * 135
        draw.rectangle((x, 560 - value * 42, x + 80, 559), fill=(40, 110, 190))
        draw.text((x + 22, 575), day, font=small, fill=(30, 30, 30))
    return _jpeg(image)


def desktop_screen():
    """A fictitious Windows screen (the desktop test): taskbar, a notes window with a title bar, a menu, a text area,
    a «Guardar» dialog with two buttons and a checkbox. Unaccented text (see document_page)."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1600, 900), (40, 90, 140))
    draw = ImageDraw.Draw(image)
    font, small, big = ImageFont.load_default(size=22), ImageFont.load_default(size=18), ImageFont.load_default(size=26)
    draw.rectangle((0, 852, 1600, 900), fill=(32, 32, 36))
    draw.rounded_rectangle((12, 860, 120, 892), radius=6, fill=(60, 60, 66))
    draw.text((30, 864), "Inicio", font=small, fill=(240, 240, 240))
    draw.text((1460, 864), "10:42", font=small, fill=(240, 240, 240))
    draw.rectangle((160, 80, 1240, 780), fill=(255, 255, 255), outline=(120, 120, 120), width=2)
    draw.rectangle((160, 80, 1240, 124), fill=(230, 230, 235))
    draw.text((180, 90), "Notas de la reunion - Bloc de notas", font=font, fill=(20, 20, 20))
    for index, label in enumerate(("_", "[]", "X")):
        draw.text((1130 + index * 40, 88), label, font=font, fill=(20, 20, 20))
    for index, label in enumerate(("Archivo", "Editar", "Ver", "Ayuda")):
        draw.text((180 + index * 110, 134), label, font=small, fill=(30, 30, 30))
    draw.line((160, 164, 1240, 164), fill=(210, 210, 210), width=1)
    for row, line in enumerate(("Reunion del lunes", "- Revisar el presupuesto del proyecto", "- Enviar el informe a Carla",
                                "- Proxima reunion: jueves a las 15:00")):
        draw.text((190, 190 + row * 40), line, font=font, fill=(25, 25, 25))
    draw.rectangle((520, 380, 1100, 640), fill=(248, 248, 250), outline=(90, 90, 90), width=2)
    draw.text((545, 400), "Guardar cambios", font=big, fill=(20, 20, 20))
    draw.text((545, 450), "Quieres guardar los cambios en Notas de la reunion?", font=small, fill=(30, 30, 30))
    draw.rectangle((545, 500, 569, 524), outline=(60, 60, 60), width=2)
    draw.text((582, 500), "No volver a preguntar", font=small, fill=(30, 30, 30))
    draw.rounded_rectangle((760, 570, 900, 616), radius=6, fill=(0, 95, 184))
    draw.text((792, 580), "Guardar", font=font, fill=(255, 255, 255))
    draw.rounded_rectangle((920, 570, 1070, 616), radius=6, fill=(255, 255, 255), outline=(90, 90, 90), width=2)
    draw.text((945, 580), "No guardar", font=font, fill=(20, 20, 20))
    return _jpeg(image)


def image(fixture):
    return {
        "shapes": shapes_image, "drawing_dog": dog_drawing, "drawing_ambiguous": ambiguous_drawing,
        "face_drawn": drawn_face, "document_page": document_page, "chart_bars": bar_chart,
        "screen_desktop": desktop_screen,
    }[fixture]()


def _pdf_text(value):
    """A PDF literal string in WinAnsi (Helvetica's encoding), which covers Spanish accents."""
    escaped = value.encode("cp1252").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    return b"(" + escaped + b")"


def _pdf_title(value):
    """A PDF text string in UTF-16 with its byte-order mark (outline titles and metadata)."""
    return b"<FEFF" + value.encode("utf-16-be").hex().upper().encode() + b">"


def _pdf(pages, outline, title):
    """A small PDF written by hand: [pages] are content streams, [outline] (title, page index) the bookmarks."""
    count = len(pages)
    page_ids = [5 + 2 * i for i in range(count)]
    outline_root = 5 + 2 * count
    items = list(range(outline_root + 1, outline_root + 1 + len(outline)))
    info = outline_root + len(outline) + 1
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R /Outlines %d 0 R /PageMode /UseOutlines >>" % outline_root,
        2: b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % i for i in page_ids) + b"] /Count %d >>" % count,
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        outline_root: b"<< /Type /Outlines /First %d 0 R /Last %d 0 R /Count %d >>" % (items[0], items[-1], len(items)),
        info: b"<< /Title " + _pdf_title(title) + b" /Producer (AINGEL synthetic fixture) >>",
    }
    for index, stream in enumerate(pages):
        page, content = page_ids[index], page_ids[index] + 1
        objects[page] = (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents %d 0 R "
                         b"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> >>" % content)
        objects[content] = b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"
    for position, (label, page_index) in enumerate(outline):
        links = b""
        if position > 0:
            links += b" /Prev %d 0 R" % items[position - 1]
        if position < len(items) - 1:
            links += b" /Next %d 0 R" % items[position + 1]
        objects[items[position]] = (b"<< /Title " + _pdf_title(label) + b" /Parent %d 0 R" % outline_root + links
                                    + b" /Dest [%d 0 R /Fit] >>" % page_ids[page_index])
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for number in sorted(objects):
        offsets[number] = len(output)
        output += b"%d 0 obj\n" % number + objects[number] + b"\nendobj\n"
    xref = len(output)
    output += b"xref\n0 %d\n0000000000 65535 f \n" % (info + 1)
    for number in range(1, info + 1):
        output += b"%010d 00000 n \n" % offsets[number]
    output += b"trailer\n<< /Size %d /Root 1 0 R /Info %d 0 R >>\nstartxref\n%d\n" % (info + 1, info, xref) + b"%%EOF\n"
    return bytes(output)


def _lines(font, size, x, y, lines):
    """Text lines from (x, y) downwards, in points."""
    body = b"0 g BT /%s %d Tf %d TL %d %d Td " % (font.encode(), size, round(size * 1.45), x, y)
    return body + b" T* ".join(_pdf_text(line) + b" Tj" for line in lines) + b" ET\n"


def book_pdf():
    """A fictitious book: a title page with a contents list and three chapters, the second with a bar chart. The
    first chapter splits «jardín» across two lines with a hyphen (the reader must join it)."""
    def footer(number):
        return _lines("F1", 10, 290, 40, [str(number)])

    cover = (_lines("F2", 28, 72, 720, ["El jardín de Rosa"])
             + _lines("F1", 14, 72, 685, ["Un libro ficticio para las pruebas de AINGEL"])
             + _lines("F2", 16, 72, 600, ["Índice"])
             + _lines("F1", 13, 72, 570, ["Capítulo 1. La casa ........ 2", "Capítulo 2. El patio ........ 3",
                                          "Capítulo 3. La fuente ........ 4"])
             + footer(1))
    first = (_lines("F2", 20, 72, 760, ["Capítulo 1. La casa"])
             + _lines("F1", 13, 72, 720, [
                 "La casa de Rosa estaba al final de la calle, junto a un parque con dos",
                 "limoneros grandes. Antes de ir al mercado, Rosa regaba las plantas del jar-",
                 "dín y saludaba a los vecinos de la esquina.",
                 "",
                 "Las ventanas eran azules y la puerta, de madera clara, crujía un poco al abrirse.",
             ])
             + footer(2))
    axes = b"0 0 0 RG 1 w 100 470 m 520 470 l S 100 470 m 100 650 l S\n"
    bars = b"0.16 0.43 0.75 rg " + b" ".join(
        b"%d 470 50 %d re f" % (110 + i * 80, height) for i, height in enumerate((80, 120, 100, 160, 140))) + b"\n"
    second = (_lines("F2", 20, 72, 760, ["Capítulo 2. El patio"])
              + _lines("F1", 13, 72, 720, [
                  "En el patio había macetas con geranios rojos y una mesa pequeña.",
                  "Rosa anotaba cuántos vasos de agua tomaba cada semana.",
              ])
              + axes + bars
              + b"".join(_lines("F1", 11, 127 + i * 80, 452, [f"S{i + 1}"]) for i in range(5))
              + _lines("F1", 12, 100, 420, ["Figura 1. Vasos de agua por semana (4, 6, 5, 8 y 7)."])
              + footer(3))
    third = (_lines("F2", 20, 72, 760, ["Capítulo 3. La fuente"])
             + _lines("F1", 13, 72, 720, [
                 "En el centro del patio estaba una fuente redonda.",
                 "Los vecinos contaban que el agua sonaba como lluvia y que por eso",
                 "los gorriones llegaban temprano.",
             ])
             + footer(4))
    return _pdf([cover, first, second, third],
                [("Capítulo 1. La casa", 1), ("Capítulo 2. El patio", 2), ("Capítulo 3. La fuente", 3)],
                "El jardín de Rosa")


def scanned_pdf():
    """Two pages that are only pictures, as a scanner makes them: the book page and the bar chart, no text layer."""
    from PIL import Image

    pages = [Image.open(io.BytesIO(maker())).convert("RGB") for maker in (document_page, bar_chart)]
    output = io.BytesIO()
    pages[0].save(output, format="PDF", save_all=True, append_images=pages[1:], resolution=150)
    return output.getvalue()


def document(fixture):
    return {"book_pdf": book_pdf, "scanned_pdf": scanned_pdf}[fixture]()


def clip(fixture):
    return {"moving_square": moving_square_clip}[fixture]()


@api_view(["GET"])
def catalog(request):
    """What a client may offer in synthetic-test mode; the server keeps the content."""
    def items(entries):
        return [{"id": key, **{loc: value[loc] for loc in LOCALES}} for key, value in entries.items()]

    return Response({
        "enabled": enabled(),
        "questions": items(QUESTIONS),
        "images": items(IMAGES),
        "objects": items(OBJECTS),
        "clips": items(CLIPS),
        "documents": items(DOCUMENTS),
        "captions": False,  # no server-held synthetic speech: live captions need the person's authorization
    })
