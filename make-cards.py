#!/usr/bin/python3

import gi
gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg
gi.require_version('Pango', '1.0')
from gi.repository import Pango
gi.require_version('PangoCairo', '1.0')
from gi.repository import PangoCairo
import cairo
import re
import sys
import math

POINTS_PER_MM = 2.8346457

PAGE_WIDTH = 297
PAGE_HEIGHT = 210

COLUMNS_PER_PAGE = 2
LINES_PER_PAGE = 2
CARDS_PER_PAGE = COLUMNS_PER_PAGE * LINES_PER_PAGE

MARGIN = 15
TITLE_SPACE = 20
TEXT_GAP = 5

CARD_WIDTH = (PAGE_WIDTH - MARGIN * 2) / COLUMNS_PER_PAGE
CARD_HEIGHT = (PAGE_HEIGHT - MARGIN * 2) / LINES_PER_PAGE

WORD_COLUMNS_PER_CARD = 4
WORD_LINES_PER_CARD = 4
WORD_BOX_WIDTH = CARD_WIDTH / WORD_COLUMNS_PER_CARD
WORD_BOX_HEIGHT = (CARD_HEIGHT - TITLE_SPACE) / WORD_LINES_PER_CARD
WORD_WIDTH = WORD_BOX_WIDTH - TEXT_GAP * 2

CROSSHAIR_SIZE = 5

class CardGenerator:
    def __init__(self, filename):
        self.surface = cairo.PDFSurface(filename,
                                        PAGE_WIDTH * POINTS_PER_MM,
                                        PAGE_HEIGHT * POINTS_PER_MM)

        self.cr = cairo.Context(self.surface)

        # Use mm for the units from now on
        self.cr.scale(POINTS_PER_MM, POINTS_PER_MM)

        # Use ½mm line width
        self.cr.set_line_width(0.5)

        self.card_num = 0
        self.topic = None
        self.words = []

    def _get_paragraph_layout(self, text, font):
        layout = PangoCairo.create_layout(self.cr)
        m = re.match(r'(.*?)([0-9]+(\.[0-9]*)?)$', font)
        font_size = float(m.group(2))
        font = m.group(1) + str(font_size)
        fd = Pango.FontDescription.from_string(font)
        layout.set_font_description(fd)
        layout.set_text(text, -1)

        return layout

    def _render_title(self, text):
        self.cr.save()

        self.cr.select_font_face("Noto Sans")
        self.cr.set_font_size(TITLE_SPACE * 0.6)
        extents = self.cr.text_extents(text)
        self.cr.move_to(CARD_WIDTH / 2 - extents.width / 2,
                        TITLE_SPACE * 0.8)
        self.cr.show_text(text)

        self.cr.restore()        

    def _render_word(self, text):
        layout = self._get_paragraph_layout(text, "Noto Sans 9")
        layout.set_width(WORD_WIDTH * POINTS_PER_MM * Pango.SCALE)
        layout.set_alignment(Pango.Alignment.CENTER)
        (ink_rect, logical_rect) = layout.get_pixel_extents()

        self.cr.save()

        # Remove the mm scale
        self.cr.scale(1.0 / POINTS_PER_MM, 1.0 / POINTS_PER_MM)

        self.cr.move_to(TEXT_GAP * POINTS_PER_MM,
                        WORD_BOX_HEIGHT / 2 * POINTS_PER_MM -
                        logical_rect.height / 2)

        PangoCairo.show_layout(self.cr, layout)

        self.cr.restore()

    def _draw_crosshairs(self):
        self.cr.save()

        self.cr.set_source_rgb(0.5, 0.5, 0.5)

        for y in range(0, LINES_PER_PAGE + 1):
            for x in range(0, COLUMNS_PER_PAGE + 1):
                self.cr.move_to(CARD_WIDTH * x,
                                CARD_HEIGHT * y - CROSSHAIR_SIZE / 2.0)
                self.cr.rel_line_to(0, CROSSHAIR_SIZE)
                self.cr.rel_move_to(CROSSHAIR_SIZE / 2.0,
                                    -CROSSHAIR_SIZE / 2.0)
                self.cr.rel_line_to(-CROSSHAIR_SIZE, 0.0)

        self.cr.stroke()

        self.cr.restore()

    def flush_card(self):
        if self.topic is None or len(self.words) == 0:
            return
        
        card_in_page = self.card_num % CARDS_PER_PAGE

        self.cr.save()
        self.cr.translate(MARGIN,
                          card_in_page //
                          COLUMNS_PER_PAGE *
                          CARD_HEIGHT +
                          MARGIN)

        if card_in_page == 0:
            if self.card_num != 0:
                self.cr.show_page()

            self._draw_crosshairs()

        page_num = self.card_num // CARDS_PER_PAGE
        column = self.card_num % COLUMNS_PER_PAGE

        self.cr.translate(column * CARD_WIDTH, 0.0)

        for x in range(WORD_COLUMNS_PER_CARD + 1):
            self.cr.move_to(x * WORD_BOX_WIDTH, TITLE_SPACE)
            self.cr.rel_line_to(0, WORD_BOX_HEIGHT * WORD_LINES_PER_CARD)
        for y in range(WORD_LINES_PER_CARD + 1):
            self.cr.move_to(0, TITLE_SPACE + y * WORD_BOX_HEIGHT)
            self.cr.rel_line_to(WORD_BOX_WIDTH * WORD_COLUMNS_PER_CARD, 0)

        self.cr.stroke()

        self._render_title(self.topic)

        for i, word in enumerate(self.words):
            self.cr.save()
            self.cr.translate(i % WORD_COLUMNS_PER_CARD * WORD_BOX_WIDTH,
                              TITLE_SPACE +
                              i // WORD_COLUMNS_PER_CARD * WORD_BOX_HEIGHT)
            self._render_word(word)
            self.cr.restore()

        self.cr.restore()

        self.topic = None
        self.words.clear()
        self.card_num += 1

    def add_line(self, line):
        if len(line) == 0:
            if len(self.words) > 0:
                self.flush_card()
            return

        if self.topic is None:
            self.topic = line
            return

        self.words.append(line)

generator = CardGenerator("kameleono.pdf")

for line in sys.stdin:
    if line.startswith('#'):
        continue
    generator.add_line(line.strip())

generator.flush_card()
