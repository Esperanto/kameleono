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
import random

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

DECODER_COLUMNS = 6
DECODER_LINES = 8

CROSSHAIR_SIZE = 5 * POINTS_PER_MM

DICE_DOTS = [1 << 4,
             (1 << 2) | (1 << 6),
             (1 << 2) | (1 << 4) | (1 << 6),
             5 | (5 << 6),
             5 | (1 << 4) | (5 << 6),
             7 | (7 << 6)]

DECODER_GAP = 2 * POINTS_PER_MM
DECODER_LINE_SIZE = (CARD_HEIGHT - DECODER_GAP) / (DECODER_LINES + 1)
DICE_SIZE = DECODER_LINE_SIZE - DECODER_GAP

CROSSHATCH_GAP = CARD_HEIGHT / 25

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
        layout = self._get_paragraph_layout(text, "Noto Sans 8")
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

    def _start_card(self):
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

    def add_card(self, card):
        self._start_card()
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

    def _draw_die_outline(self, x, y):
        curve_size = DICE_SIZE / 10.0
        self.cr.move_to(x + curve_size, y)
        self.cr.rel_line_to(DICE_SIZE - curve_size * 2, 0)
        self.cr.arc(x + DICE_SIZE - curve_size,
                    y + curve_size,
                    curve_size,
                    math.pi * 1.5,
                    math.pi * 2.0)
        self.cr.rel_line_to(0, DICE_SIZE - curve_size * 2)
        self.cr.arc(x + DICE_SIZE - curve_size,
                    y + DICE_SIZE - curve_size,
                    curve_size,
                    0.0,
                    math.pi * 0.5)
        self.cr.rel_line_to(curve_size * 2 - DICE_SIZE, 0)
        self.cr.arc(x + curve_size,
                    y + DICE_SIZE - curve_size,
                    curve_size,
                    math.pi * 0.5,
                    math.pi)
        self.cr.rel_line_to(0, curve_size * 2 - DICE_SIZE)
        self.cr.arc(x + curve_size,
                    y + curve_size,
                    curve_size,
                    math.pi,
                    math.pi * 1.5)
        self.cr.stroke()

    def _draw_die_dots(self, x, y, value):
        dots = DICE_DOTS[value]

        for dx in range(3):
            for dy in range(3):
                bit = (dots & 1) != 0
                dots >>= 1

                if not bit:
                    continue

                self.cr.arc(x + (dx + 1) * (DICE_SIZE / 4),
                            y + (dy + 1) * (DICE_SIZE / 4),
                            DICE_SIZE / 11,
                            0.0,
                            math.pi * 2)
                self.cr.fill()

    def _draw_die(self, x, y, value):
        self._draw_die_outline(x, y)
        self._draw_die_dots(x, y, value)

    def _draw_d8(self, x, y, value):
        self.cr.move_to(x + DICE_SIZE / 2, y)
        self.cr.line_to(x + DICE_SIZE, y + DICE_SIZE * 3 / 4)
        self.cr.line_to(x + DICE_SIZE / 2, y + DICE_SIZE)
        self.cr.line_to(x, y + DICE_SIZE * 3 / 4)
        self.cr.close_path()
        self.cr.move_to(x, y + DICE_SIZE * 3 / 4)
        self.cr.rel_line_to(DICE_SIZE, 0)
        self.cr.stroke()

        self.cr.save()
        self.cr.set_font_size(DICE_SIZE / 1.8)
        self.cr.select_font_face("Noto Sans")

        digit = chr(ord("1") + value)
        extents = self.cr.text_extents(digit)
        self.cr.move_to(x + DICE_SIZE / 2 - extents.width / 2,
                        y + DICE_SIZE / 1.5)
        self.cr.show_text(digit)

        self.cr.restore()

    def add_decoder_card(self, decoder):
        self._start_card()

        for x in range(DECODER_COLUMNS):
            dice_left = x * (CARD_WIDTH / DECODER_COLUMNS) + DECODER_GAP
            self._draw_die(dice_left, DECODER_GAP, x)

            for y in range(DECODER_LINES):
                dice_top = DECODER_GAP + (y + 1) * DECODER_LINE_SIZE
                self._draw_d8(dice_left, dice_top, y)

                self.cr.save()
                self.cr.set_font_size(DICE_SIZE / 1.5)
                self.cr.select_font_face("Noto Sans")

                coords = decoder[x * DECODER_LINES + y]

                extents = self.cr.text_extents(coords)
                self.cr.move_to(dice_left + DECODER_GAP + DICE_SIZE,
                                dice_top + DICE_SIZE / 1.5)
                self.cr.show_text(coords)

                self.cr.restore()

        self.cr.restore()

        self.card_num += 1

    def add_chameleon_card(self):
        self._start_card()

        layout = self._get_paragraph_layout("Vi estas la\n"
                                            "kameleono",
                                            "Noto Sans " + str(CARD_HEIGHT / 5))
        layout.set_alignment(Pango.Alignment.CENTER)
        (ink_rect, logical_rect) = layout.get_pixel_extents()
        self.cr.move_to(CARD_WIDTH / 2 - logical_rect.width / 2,
                        CARD_HEIGHT / 2 - logical_rect.height / 2)
        PangoCairo.show_layout(self.cr, layout)

        self.cr.restore()

        self.card_num += 1

    def _draw_crosshatch(self):
        self.cr.save()
        self.cr.rectangle(0, 0, CARD_WIDTH, CARD_HEIGHT)
        self.cr.clip()

        max_axis = max(CARD_WIDTH, CARD_HEIGHT)

        for i in range(math.ceil(max_axis * 2 / CROSSHATCH_GAP)):
            self.cr.move_to(i * CROSSHATCH_GAP - CARD_WIDTH, 0)
            self.cr.rel_line_to(max_axis, max_axis)
            self.cr.move_to(i * CROSSHATCH_GAP, 0)
            self.cr.rel_line_to(-max_axis, max_axis)

        self.cr.stroke()

        self.cr.restore()

    def add_backing_card(self, text):
        self._start_card()

        self._draw_crosshatch()

        self.cr.select_font_face("Noto Sans")
        self.cr.set_font_size(CARD_HEIGHT / 3)
        extents = self.cr.text_extents(text)
        self.cr.move_to(CARD_WIDTH / 2 - extents.width / 2,
                        CARD_HEIGHT / 2 + CARD_HEIGHT / 6)
        self.cr.set_source_rgb(0.7, 0.7, 0.7)
        self.cr.show_text(text)

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

def generate_decoder_card():
    value_indices = list(range(DECODER_COLUMNS * DECODER_LINES))
    random.shuffle(value_indices)
    return list(chr(ord("A") + index % WORD_COLUMNS_PER_CARD) +
                chr(ord("1") +
                    index // WORD_COLUMNS_PER_CARD %
                    WORD_LINES_PER_CARD)
                for index in value_indices)

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

N_DECODER_CARDS = 7

generator.flush_page()
for backing in "VERDA", "BLUA":
    decoder = generate_decoder_card()
    for j in range(N_DECODER_CARDS):
        generator.add_decoder_card(decoder)

        if (j + 1) % CARDS_PER_PAGE == 0:
            for k in range(CARDS_PER_PAGE):
                generator.add_backing_card(backing)

    generator.add_chameleon_card()
    generator.flush_page()

    for k in range(N_DECODER_CARDS % CARDS_PER_PAGE + 1):
        generator.add_backing_card(backing)

    generator.flush_page()
