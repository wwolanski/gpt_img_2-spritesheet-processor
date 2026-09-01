from __future__ import annotations


import cv2
import numpy as np

from asset_pipeline.services.image_ops import connected_to_border, morph, rgb_hsv_fields, dilate


def hue_distance(hue: np.ndarray, center: float) -> np.ndarray:
    forward = np.abs(hue - center)
    return np.minimum(forward, 180 - forward)


def base_masks(
    fields: dict[str, np.ndarray], key: tuple[int, int, int], options: dict[str, object]
) -> dict[str, np.ndarray]:
    key_array = np.array(key, dtype=np.float32).reshape(1, 1, 3)
    delta = fields["rgb"] - key_array
    distance_sq = np.einsum("ijk,ijk->ij", delta, delta)
    transparent_threshold_sq = float(options["transparentThreshold"]) ** 2
    opaque_threshold_sq = float(options["opaqueThreshold"]) ** 2
    hue_delta = hue_distance(fields["hue"], float(options["greenHueCenter"]))
    green_dominance = fields["green"] - fields["max_rb"]
    hue_match = hue_delta <= float(options["greenHueRange"])
    chroma_base = (
        hue_match
        & (fields["sat"] >= float(options["greenSaturationMin"]))
        & (fields["val"] >= float(options["greenValueMin"]))
    )
    strict_green = (
        chroma_base
        & (green_dominance >= float(options["greenDominanceHard"]))
        & (fields["green"] > fields["red"] * 1.15)
        & (fields["green"] > fields["blue"] * 1.15)
    )
    soft_green = (
        chroma_base
        & (green_dominance >= float(options["greenDominanceSoft"]))
        & (fields["green"] > fields["red"] * 1.04)
        & (fields["green"] > fields["blue"] * 1.04)
    )
    return {
        "distance_sq": distance_sq,
        "green_dominance": green_dominance,
        "strict_green": strict_green,
        "soft_green": soft_green,
        "close_to_key": distance_sq <= opaque_threshold_sq,
        "very_close_to_key": distance_sq <= transparent_threshold_sq,
    }


def alpha_from_distance(distance_inside_foreground: np.ndarray, softness: float) -> np.ndarray:
    alpha = np.clip(distance_inside_foreground / max(softness, 0.01), 0.0, 1.0) * 255.0
    return alpha.astype(np.float32)


def distance_alpha(
    rgb: np.ndarray, key: tuple[int, int, int], options: dict[str, object]
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    fields = rgb_hsv_fields(rgb)
    masks = base_masks(fields, key, options)
    transparent_threshold = float(options["transparentThreshold"])
    opaque_threshold = float(options["opaqueThreshold"])
    span = max(1.0, opaque_threshold - transparent_threshold)
    distance = np.sqrt(masks["distance_sq"])
    alpha = np.where(
        distance <= transparent_threshold,
        0.0,
        np.where(distance >= opaque_threshold, 255.0, ((distance - transparent_threshold) / span) * 255.0),
    ).astype(np.float32)
    background = connected_to_border(masks["close_to_key"] & masks["soft_green"])
    alpha[background] = 0.0
    return np.clip(alpha, 0, 255).astype(np.uint8), fields


def pixel_alpha(
    rgb: np.ndarray, key: tuple[int, int, int], options: dict[str, object]
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    fields = rgb_hsv_fields(rgb)
    masks = base_masks(fields, key, options)
    background = connected_to_border(masks["soft_green"] | masks["close_to_key"])
    background = morph(background, cv2.MORPH_CLOSE, 3, iterations=1)
    visible = morph(~background, cv2.MORPH_OPEN, 3, iterations=1)
    return np.where(visible, 255, 0).astype(np.uint8), fields


def greenscreen_alpha(
    rgb: np.ndarray, key: tuple[int, int, int], options: dict[str, object]
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    fields = rgb_hsv_fields(rgb)
    masks = base_masks(fields, key, options)
    hard_background = connected_to_border(masks["strict_green"] | masks["very_close_to_key"])
    soft_background = connected_to_border(masks["soft_green"] | masks["close_to_key"])
    hard_background = morph(hard_background, cv2.MORPH_CLOSE, 3, iterations=1)
    soft_background = dilate(soft_background, 3, iterations=1) & (
        masks["soft_green"] | masks["close_to_key"] | hard_background
    )
    foreground_core = ~(soft_background | hard_background)
    distance_inside = cv2.distanceTransform(foreground_core.astype(np.uint8), cv2.DIST_L2, 3)
    alpha = alpha_from_distance(distance_inside, float(options["edgeSoftness"]))
    alpha[soft_background | hard_background] = 0.0
    blur_sigma = float(options["edgeBlurSigma"])
    if blur_sigma > 0:
        alpha = cv2.GaussianBlur(alpha, (0, 0), blur_sigma)
    return np.clip(alpha, 0, 255).astype(np.uint8), fields
