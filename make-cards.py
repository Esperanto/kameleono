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
import collections

POINTS_PER_MM = 2.8346457

PAGE_WIDTH = 297 * POINTS_PER_MM
PAGE_HEIGHT = 210 * POINTS_PER_MM

COLUMNS_PER_PAGE = 2
LINES_PER_PAGE = 2
CARDS_PER_PAGE = COLUMNS_PER_PAGE * LINES_PER_PAGE

MARGIN = 15 * POINTS_PER_MM
TITLE_SPACE = 20 * POINTS_PER_MM
COORDS_HEIGHT = 10 * POINTS_PER_MM
COORDS_WIDTH = 8 * POINTS_PER_MM
WORDS_X = COORDS_WIDTH
WORDS_Y = TITLE_SPACE + COORDS_HEIGHT
TEXT_GAP = 5 * POINTS_PER_MM

CARD_WIDTH = (PAGE_WIDTH - MARGIN * 2) / COLUMNS_PER_PAGE
CARD_HEIGHT = (PAGE_HEIGHT - MARGIN * 2) / LINES_PER_PAGE

WORD_COLUMNS_PER_CARD = 4
WORD_LINES_PER_CARD = 4
WORD_BOX_WIDTH = (CARD_WIDTH - WORDS_X) / WORD_COLUMNS_PER_CARD
WORD_BOX_HEIGHT = (CARD_HEIGHT - WORDS_Y) / WORD_LINES_PER_CARD
WORD_WIDTH = WORD_BOX_WIDTH - TEXT_GAP * 2

CROSSHAIR_SIZE = 5 * POINTS_PER_MM

Card = collections.namedtuple('Card', ['topic', 'words'])

class CardGenerator:
    def __init__(self, filename):
        self.surface = cairo.PDFSurface(filename, PAGE_HEIGHT, PAGE_WIDTH)

        self.cr = cairo.Context(self.surface)

        # Use ½mm line width
        self.cr.set_line_width(0.5 * POINTS_PER_MM)

        self.card_num = 0

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
        layout = self._get_paragraph_layout(text, "Noto Sans 7.5")
        layout.set_width(WORD_WIDTH * Pango.SCALE)
        layout.set_alignment(Pango.Alignment.CENTER)
        (ink_rect, logical_rect) = layout.get_pixel_extents()

        self.cr.move_to(TEXT_GAP,
                        WORD_BOX_HEIGHT / 2 -
                        logical_rect.height / 2)

        PangoCairo.show_layout(self.cr, layout)

    def _draw_crosshairs(self):
        self.cr.save()

        self.cr.set_source_rgb(0.5, 0.5, 0.5)

        for y in range(0, LINES_PER_PAGE + 1):
            for x in range(0, COLUMNS_PER_PAGE + 1):
                self.cr.move_to(CARD_WIDTH * x + MARGIN,
                                CARD_HEIGHT * y -
                                CROSSHAIR_SIZE / 2.0 +
                                MARGIN)
                self.cr.rel_line_to(0, CROSSHAIR_SIZE)
                self.cr.rel_move_to(CROSSHAIR_SIZE / 2.0,
                                    -CROSSHAIR_SIZE / 2.0)
                self.cr.rel_line_to(-CROSSHAIR_SIZE, 0.0)

        self.cr.stroke()

        self.cr.restore()

    def _draw_grid(self):
        self.cr.save()

        for y in range(WORD_LINES_PER_CARD):
            for x in range(WORD_COLUMNS_PER_CARD // 2):
                self.cr.rectangle((x * 2 + (y & 1)) * WORD_BOX_WIDTH + WORDS_X,
                                  y * WORD_BOX_HEIGHT + WORDS_Y,
                                  WORD_BOX_WIDTH,
                                  WORD_BOX_HEIGHT)

        self.cr.set_source_rgb(0.8, 0.8, 0.8)

        self.cr.fill()

        self.cr.restore()

    def _draw_coords(self):
        self.cr.save()
        self.cr.select_font_face("Noto Sans")
        self.cr.set_font_size(COORDS_HEIGHT * 0.6)

        for x in range(WORD_COLUMNS_PER_CARD):
            letter = chr(ord("A") + x)
            extents = self.cr.text_extents(letter)
            self.cr.move_to(WORDS_X +
                            x * WORD_BOX_WIDTH +
                            WORD_BOX_WIDTH / 2 -
                            extents.width / 2,
                            TITLE_SPACE + COORDS_HEIGHT * 0.8)
            self.cr.show_text(letter)

        for y in range(WORD_LINES_PER_CARD):
            digit = chr(ord("1") + y)
            extents = self.cr.text_extents(digit)
            self.cr.move_to(WORDS_X -
                            COORDS_WIDTH / 2 -
                            extents.width / 2,
                            WORDS_Y +
                            (y + 0.5) * WORD_BOX_HEIGHT +
                            COORDS_HEIGHT * 0.25)
            self.cr.show_text(digit)

        self.cr.restore()            

    def add_card(self, card):
        card_in_page = self.card_num % CARDS_PER_PAGE
        page_num = self.card_num // CARDS_PER_PAGE

        if card_in_page == 0:
            if self.card_num != 0:
                # Remove the page rotation
                self.cr.restore()
                self.cr.show_page()

            self.cr.save()

            # Rotate the page by 90°, either clockwise or
            # anti-clockwise depending on the page parity
            if page_num & 1 == 0:
                self.cr.translate(PAGE_HEIGHT, 0.0)
                self.cr.rotate(math.pi / 2.0)
            else:
                self.cr.translate(0, PAGE_WIDTH)
                self.cr.rotate(-math.pi / 2.0)

            self._draw_crosshairs()

        card_x = card_in_page % COLUMNS_PER_PAGE
        card_y = card_in_page // COLUMNS_PER_PAGE

        if page_num & 1 != 0:
            card_x = COLUMNS_PER_PAGE - 1 - card_x

        self.cr.save()
        self.cr.translate(card_x * CARD_WIDTH + MARGIN,
                          card_y * CARD_HEIGHT + MARGIN)

        self._draw_grid()
        self._draw_coords()

        self._render_title(card.topic)

        for i, word in enumerate(card.words):
            self.cr.save()
            self.cr.translate(WORDS_X +
                              i % WORD_COLUMNS_PER_CARD * WORD_BOX_WIDTH,
                              WORDS_Y +
                              i // WORD_COLUMNS_PER_CARD * WORD_BOX_HEIGHT)
            self._render_word(word)
            self.cr.restore()

        self.cr.restore()

        self.card_num += 1

    def flush_page(self):
        card_in_page = self.card_num % CARDS_PER_PAGE

        if card_in_page > 0:
            self.card_num += CARDS_PER_PAGE - card_in_page

def read_cards(file):
    topic = None
    words = []

    for line in file:
        line = line.strip()

        if line.startswith('#'):
            continue

        if len(line) == 0:
            if len(words) > 0:
                yield Card(topic, list(words))
                words.clear()
                topic = None
            continue

        if topic is None:
            topic = line
            continue

        words.append(line)

    if len(words) > 0:
        yield Card(topic, words)

cards = list(read_cards(sys.stdin))

generator = CardGenerator("kameleono.pdf")

# Split the last odd page into two so that when it is printed
# double-sided each card will have something on both sides
n_cards_in_pairs = (len(cards) //
                    (CARDS_PER_PAGE * 2) *
                    CARDS_PER_PAGE * 2)
split_point = (n_cards_in_pairs +
               (len(cards) - n_cards_in_pairs + 1) // 2)

for card_num, card in enumerate(cards):
    if card_num == split_point:
        generator.flush_page()
    generator.add_card(card)
