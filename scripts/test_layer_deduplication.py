import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import create_deduped_rgba_layers


def test_parent_child_pixels_are_removed_from_background_and_parent():
    image = np.full((120, 160, 3), 240, dtype=np.uint8)
    image[20:100, 30:130] = (40, 120, 210)
    image[70:88, 92:116] = (5, 5, 5)

    parent = np.zeros((120, 160), dtype=np.uint8)
    parent[20:100, 30:130] = 1
    child = np.zeros((120, 160), dtype=np.uint8)
    child[70:88, 92:116] = 1

    layers = create_deduped_rgba_layers(image, [parent, child], repair_radius_px=3)

    background = np.array(layers[0].convert("RGBA"))
    parent_layer = np.array(layers[1].convert("RGBA"))
    child_layer = np.array(layers[2].convert("RGBA"))

    # The movable child should remain intact as its own layer.
    assert child_layer[78, 102, 3] == 255
    assert tuple(child_layer[78, 102, :3]) == (5, 5, 5)

    # The background should no longer contain the black child pixels.
    assert background[78, 102, 3] == 255
    assert tuple(background[78, 102, :3]) != (5, 5, 5)

    # The parent card should also have its child pixels repaired away.
    assert parent_layer[78, 102, 3] == 255
    assert tuple(parent_layer[78, 102, :3]) != (5, 5, 5)


def test_layers_are_ordered_parent_before_child_even_when_input_is_reversed():
    image = np.full((120, 160, 3), 240, dtype=np.uint8)
    image[20:100, 30:130] = (40, 120, 210)
    image[70:88, 92:116] = (5, 5, 5)

    parent = np.zeros((120, 160), dtype=np.uint8)
    parent[20:100, 30:130] = 1
    child = np.zeros((120, 160), dtype=np.uint8)
    child[70:88, 92:116] = 1

    layers = create_deduped_rgba_layers(image, [child, parent], repair_radius_px=3)

    parent_alpha_area = int(np.count_nonzero(np.array(layers[1].split()[3])))
    child_alpha_area = int(np.count_nonzero(np.array(layers[2].split()[3])))

    assert parent_alpha_area > child_alpha_area
    assert np.array(layers[1].convert("RGBA"))[78, 102, 3] == 255
    assert tuple(np.array(layers[1].convert("RGBA"))[78, 102, :3]) != (5, 5, 5)
    assert tuple(np.array(layers[2].convert("RGBA"))[78, 102, :3]) == (5, 5, 5)


if __name__ == "__main__":
    test_parent_child_pixels_are_removed_from_background_and_parent()
    test_layers_are_ordered_parent_before_child_even_when_input_is_reversed()
