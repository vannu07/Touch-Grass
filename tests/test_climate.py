from lastlight.climate import FEATURE_COLUMNS, generate_dataset, hidden_score, load_or_build


def test_dataset_has_the_columns_tabpfn_needs():
    df = generate_dataset(n=40, seed=1)
    for col in FEATURE_COLUMNS + ["walk_score"]:
        assert col in df.columns
    assert df["walk_score"].between(1, 99).all()


def test_rain_lowers_the_hidden_score():
    dry = {
        "temp_c": 16,
        "precip_mm": 0,
        "cloud": 0.1,
        "wind_ms": 2,
        "minutes_to_sunset": 22,
        "foliage": 0.4,
        "duration_min": 20,
        "urban": 0,
        "humidity": 0.5,
    }
    wet = dict(dry, precip_mm=8, cloud=0.95)
    assert hidden_score(wet) < hidden_score(dry)


def test_load_or_build_writes_once(tmp_path):
    path = tmp_path / "dusk.csv"
    a = load_or_build(path)
    b = load_or_build(path)
    assert len(a) == len(b)
    assert path.exists()
