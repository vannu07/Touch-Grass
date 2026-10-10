"""TabPFN predicts dusk-walk quality. A linear model sits beside it as a check."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from lastlight.climate import FEATURE_COLUMNS, load_or_build

_lock = threading.Lock()
_engine: "GoEngine | None" = None


@dataclass
class Backtest:
    n_test: int
    tabpfn_mae: float | None
    ridge_mae: float
    mean_mae: float
    tabpfn_wins: bool
    fit_seconds: float
    backend: str


@dataclass
class GoEngine:
    backend: str
    tabpfn: object | None
    ridge: Pipeline
    backtest: Backtest
    train_mean: float

    def predict_one(self, features: dict) -> tuple[float, str]:
        x = np.array([[features[c] for c in FEATURE_COLUMNS]], dtype=float)
        if self.tabpfn is not None:
            score = float(np.clip(self.tabpfn.predict(x)[0], 1, 99))
            return score, "tabpfn"
        score = float(np.clip(self.ridge.predict(x)[0], 1, 99))
        return score, "ridge"


def _fit_tabpfn(x_train: np.ndarray, y_train: np.ndarray):
    from tabpfn import TabPFNRegressor

    model = TabPFNRegressor(device="cpu", n_estimators=8, random_state=26)
    model.fit(x_train, y_train)
    return model


def load_engine() -> GoEngine:
    global _engine
    if _engine is not None:
        return _engine
    with _lock:
        if _engine is not None:
            return _engine
        df = load_or_build()
        x = df[FEATURE_COLUMNS].to_numpy(dtype=float)
        y = df["walk_score"].to_numpy(dtype=float)
        x_tr, x_te, y_tr, y_te = train_test_split(x, y, test_size=0.22, random_state=26)
        ridge = Pipeline(
            [
                ("scale", StandardScaler()),
                ("ridge", Ridge(alpha=1.2)),
            ]
        )
        ridge.fit(x_tr, y_tr)
        ridge_mae = float(mean_absolute_error(y_te, ridge.predict(x_te)))
        mean_mae = float(mean_absolute_error(y_te, np.full_like(y_te, y_tr.mean())))

        tabpfn = None
        tabpfn_mae = None
        backend = "ridge"
        t0 = time.perf_counter()
        try:
            tabpfn = _fit_tabpfn(x_tr, y_tr)
            tabpfn_mae = float(mean_absolute_error(y_te, tabpfn.predict(x_te)))
            backend = "tabpfn"
        except Exception as exc:  # noqa: BLE001 — first-run download / torch can fail
            print(f"[lastlight] TabPFN unavailable, using ridge: {exc}")
        fit_seconds = time.perf_counter() - t0
        wins = tabpfn_mae is not None and tabpfn_mae < ridge_mae
        _engine = GoEngine(
            backend=backend,
            tabpfn=tabpfn,
            ridge=ridge,
            train_mean=float(y_tr.mean()),
            backtest=Backtest(
                n_test=len(y_te),
                tabpfn_mae=tabpfn_mae,
                ridge_mae=ridge_mae,
                mean_mae=mean_mae,
                tabpfn_wins=wins,
                fit_seconds=fit_seconds,
                backend=backend,
            ),
        )
        bt = _engine.backtest
        print(
            f"[lastlight] go-engine {bt.backend}  "
            f"tabpfn_mae={bt.tabpfn_mae} ridge_mae={bt.ridge_mae:.2f} "
            f"mean_mae={bt.mean_mae:.2f} n_test={bt.n_test} "
            f"fit={bt.fit_seconds:.1f}s"
        )
        return _engine


def verdict(score: float, minutes_to_sunset: float, sky: str) -> str:
    if minutes_to_sunset < -8:
        return "you missed it — go at dawn, or try tomorrow"
    if sky == "rain" and score < 42:
        return "stay in unless you like wet socks"
    if score >= 72:
        return "go. tonight is the night."
    if score >= 55:
        return "go anyway. it will not photograph well. that is the point."
    if score >= 40:
        return "a short loop. coat on. twenty minutes still counts."
    return "the light is poor. a doorway and a sky still count."
