import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import TextBlock, normalize_page_fonts, normalize_text_styles, prevent_small_text_overlaps, text_font_category


def block(
    text,
    font,
    x=0,
    y=0,
    w=100,
    h=20,
    size=12,
    color=(0, 0, 0),
    bold=False,
    original=None,
):
    original = original or (None, None, None, None)
    return TextBlock(
        text=text,
        x=x,
        y=y,
        w=w,
        h=h,
        font_name=font,
        font_size_pt=size,
        color=color,
        bold=bold,
        original_x=original[0],
        original_y=original[1],
        original_w=original[2],
        original_h=original[3],
    )


def test_categories():
    assert text_font_category("中文") == "zh"
    assert text_font_category("DeckLens") == "en"
    assert text_font_category("2026") == "num"
    assert text_font_category("版本 DeckLens 2026") == "zh"
    assert text_font_category("Q2 2026") == "en"


def test_page_fonts_are_unified_by_category():
    blocks = [
        block("标题", "Source Han Sans"),
        block("说明", "Source Han Sans"),
        block("DeckLens", "Helvetica"),
        block("Upload", "Arial"),
        block("2026", "DIN"),
        block("42", "DIN"),
        block("中文 Mixed 2026", "PingFang SC"),
    ]

    normalize_page_fonts(blocks)

    zh_fonts = {b.font_name for b in blocks if text_font_category(b.text) == "zh"}
    en_fonts = {b.font_name for b in blocks if text_font_category(b.text) == "en"}
    num_fonts = {b.font_name for b in blocks if text_font_category(b.text) == "num"}

    assert zh_fonts == {"Source Han Sans"}
    assert en_fonts == {"Helvetica"}
    assert num_fonts == {"DIN"}


def test_repeated_nearby_text_styles_are_unified():
    blocks = [
        block("第一项", "MiSans", x=80, y=120, h=24, size=15.6, color=(36, 39, 45)),
        block("第二项", "Arial", x=80, y=158, h=25, size=16.3, color=(38, 40, 46)),
        block("第三项", "MiSans", x=80, y=196, h=24, size=15.9, color=(35, 39, 44)),
    ]

    normalize_text_styles(blocks, image_size=(1200, 800))

    assert {b.font_size_pt for b in blocks} == {16.0}
    assert {b.font_name for b in blocks} == {"MiSans"}
    assert {b.bold for b in blocks} == {False}
    assert len({b.color for b in blocks}) == 1


def test_text_styles_keep_color_and_size_boundaries():
    blocks = [
        block("正文一", "MiSans", x=80, y=120, h=24, size=16, color=(35, 35, 35)),
        block("正文二", "Arial", x=80, y=158, h=24, size=16.4, color=(36, 36, 36)),
        block("标题", "MiSans", x=80, y=60, h=46, size=34, color=(35, 35, 35), bold=True),
        block("蓝色标签", "MiSans", x=80, y=230, h=24, size=16, color=(30, 105, 220)),
    ]

    normalize_text_styles(blocks, image_size=(1200, 800))

    assert blocks[0].font_size_pt == blocks[1].font_size_pt == 16.0
    assert blocks[2].font_size_pt == 34
    assert blocks[2].bold is True
    assert blocks[3].color == (30, 105, 220)
    assert blocks[3].font_name == "MiSans"


def test_aligned_menu_items_unify_despite_noisy_width_based_sizes():
    blocks = [
        block("Blog", "MiSans", x=1468, y=742, w=94, h=66, size=34, color=(5, 5, 5)),
        block("About", "Arial", x=1472, y=813, w=113, h=54, size=29, color=(6, 6, 6)),
        block("Terms and Condition", "MiSans", x=1475, y=885, w=338, h=44, size=26, color=(7, 7, 7)),
        block("Privacy Policy", "Arial", x=1473, y=949, w=233, h=58, size=27, color=(8, 8, 8)),
    ]

    normalize_text_styles(blocks, image_size=(2880, 2120))

    assert {b.font_size_pt for b in blocks} == {28.0}
    assert len({b.color for b in blocks}) == 1
    assert {b.bold for b in blocks} == {False}
    assert len({b.x for b in blocks}) == 1
    assert len({b.h for b in blocks}) == 1


def test_same_row_text_boxes_snap_to_shared_centerline():
    blocks = [
        block("Basic", "MiSans", x=80, y=120, w=96, h=28, size=16, color=(20, 20, 20)),
        block("Pro", "Arial", x=220, y=123, w=72, h=22, size=16.5, color=(21, 20, 20)),
        block("Team", "MiSans", x=340, y=118, w=90, h=30, size=15.8, color=(20, 21, 20)),
    ]

    normalize_text_styles(blocks, image_size=(1200, 800))

    centers = {round(b.y + b.h / 2) for b in blocks}
    assert len(centers) == 1
    assert len({b.h for b in blocks}) == 1


def test_vertical_menu_text_boxes_keep_shared_left_edge_and_height():
    blocks = [
        block("Blog", "MiSans", x=1468, y=742, w=94, h=66, size=34, color=(5, 5, 5)),
        block("About", "Arial", x=1472, y=813, w=113, h=54, size=29, color=(6, 6, 6)),
        block("Terms and Condition", "MiSans", x=1475, y=885, w=338, h=44, size=26, color=(7, 7, 7)),
        block("Privacy Policy", "Arial", x=1473, y=949, w=233, h=58, size=27, color=(8, 8, 8)),
    ]

    normalize_text_styles(blocks, image_size=(2880, 2120))

    assert len({b.x for b in blocks}) == 1
    assert len({b.h for b in blocks}) == 1


def test_small_vertical_text_overlaps_are_pushed_apart():
    blocks = [
        block("第一行", "MiSans", x=80, y=100, w=140, h=34, size=18, color=(20, 20, 20), original=(80, 100, 140, 34)),
        block("第二行", "MiSans", x=82, y=128, w=140, h=34, size=18, color=(20, 20, 20), original=(82, 138, 140, 34)),
    ]

    prevent_small_text_overlaps(blocks, image_size=(800, 600))

    assert blocks[1].y >= blocks[0].y + blocks[0].h


def test_large_text_overlaps_are_preserved_as_possible_design():
    blocks = [
        block("SALE", "MiSans", x=100, y=100, w=220, h=90, size=54, color=(20, 20, 20), original=(100, 100, 220, 90)),
        block("2026", "MiSans", x=120, y=118, w=180, h=70, size=50, color=(20, 20, 20), original=(120, 118, 180, 70)),
    ]

    original = [(b.x, b.y) for b in blocks]
    prevent_small_text_overlaps(blocks, image_size=(800, 600))

    assert [(b.x, b.y) for b in blocks] == original


def test_small_same_row_text_overlaps_are_pushed_apart():
    blocks = [
        block("Basic", "MiSans", x=80, y=100, w=96, h=28, size=16, color=(20, 20, 20), original=(80, 100, 96, 28)),
        block("Pro", "MiSans", x=170, y=101, w=72, h=28, size=16, color=(20, 20, 20), original=(180, 101, 72, 28)),
    ]

    prevent_small_text_overlaps(blocks, image_size=(800, 600))

    assert blocks[1].x >= blocks[0].x + blocks[0].w


def test_rendered_text_overlap_is_detected_even_when_boxes_do_not_overlap():
    blocks = [
        block("Long Label", "MiSans", x=80, y=100, w=54, h=28, size=24, color=(20, 20, 20), original=(80, 100, 54, 28)),
        block("Next", "MiSans", x=150, y=101, w=64, h=28, size=24, color=(20, 20, 20), original=(150, 101, 64, 28)),
    ]

    prevent_small_text_overlaps(blocks, image_size=(800, 600))

    assert blocks[1].x > 150


def test_existing_ocr_overlap_without_growth_is_preserved():
    blocks = [
        block("A", "MiSans", x=80, y=100, w=80, h=30, size=18, color=(20, 20, 20), original=(80, 100, 80, 30)),
        block("B", "MiSans", x=150, y=101, w=80, h=30, size=18, color=(20, 20, 20), original=(150, 101, 80, 30)),
    ]

    original_positions = [(b.x, b.y) for b in blocks]
    prevent_small_text_overlaps(blocks, image_size=(800, 600))

    assert [(b.x, b.y) for b in blocks] == original_positions


if __name__ == "__main__":
    test_categories()
    test_page_fonts_are_unified_by_category()
    test_repeated_nearby_text_styles_are_unified()
    test_text_styles_keep_color_and_size_boundaries()
    test_aligned_menu_items_unify_despite_noisy_width_based_sizes()
    test_same_row_text_boxes_snap_to_shared_centerline()
    test_vertical_menu_text_boxes_keep_shared_left_edge_and_height()
    test_small_vertical_text_overlaps_are_pushed_apart()
    test_large_text_overlaps_are_preserved_as_possible_design()
    test_small_same_row_text_overlaps_are_pushed_apart()
    test_rendered_text_overlap_is_detected_even_when_boxes_do_not_overlap()
    test_existing_ocr_overlap_without_growth_is_preserved()
