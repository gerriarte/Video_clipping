from modules import layout_detector as L


def test_visible_frac_9x16_from_16x9():
    assert abs(L._visible_frac(1080 / 1920, 16 / 9) - 81 / 256) < 1e-4


def test_visible_frac_wider_target_no_horizontal_crop():
    assert L._visible_frac(2.0, 16 / 9) == 1.0


def test_face_x_center_maps_to_center():
    r = L._visible_frac(1080 / 1920, 16 / 9)
    assert abs(L._face_x_to_object_position(0.5, r) - 0.5) < 1e-6


def test_face_x_extremes_clamped():
    r = L._visible_frac(1080 / 1920, 16 / 9)
    assert L._face_x_to_object_position(0.0, r) == 0.0
    assert L._face_x_to_object_position(1.0, r) == 1.0


def test_face_x_full_visible_returns_center():
    assert L._face_x_to_object_position(0.3, 1.0) == 0.5


def test_cluster_by_x_two_people():
    centers = L._cluster_by_x([0.1, 0.12, 0.70, 0.72, 0.71], 0.14)
    assert len(centers) == 2
    assert centers[0] < 0.3 and centers[1] > 0.6


def test_dedup_times_strictly_increasing():
    kf = [{"t": 0, "x": 0.1}, {"t": 0, "x": 0.2}, {"t": 1, "x": 0.3}]
    out = L._dedup_times(kf)
    assert [k["t"] for k in out] == [0, 1]


def test_simplify_keyframes_flat_line_keeps_endpoints():
    times = [0, 1, 2, 3, 4]
    vals = [0.5, 0.5, 0.5, 0.5, 0.5]
    kf = L._simplify_keyframes(times, vals, 0.012)
    assert len(kf) == 2


def test_simplify_keyframes_keeps_peak():
    times = [0, 1, 2, 3, 4]
    vals = [0.0, 0.0, 1.0, 0.0, 0.0]
    kf = L._simplify_keyframes(times, vals, 0.012)
    assert any(abs(k["x"] - 1.0) < 1e-6 for k in kf)
