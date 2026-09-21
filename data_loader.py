from pathlib import Path
import pandas as pd

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
CACHE = DATA_DIR / "energydata_complete.csv"
REQUIRED_COLUMNS = {"date", "Appliances", "lights"}
MIN_ROWS = 1000  # the real dataset has ~19,735 rows; far fewer means a bad/partial file


def _normalize_date_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    ucimlrepo serves this dataset's 'date' column as strings like
    "2016-01-11 17:00:00", but the character between the date part and the
    time part is not always a plain ASCII space (it can be a stray/odd
    whitespace-like character depending on how the source data was
    encoded). pandas' to_datetime then silently fails to parse EVERY row,
    turning the whole column to NaT with errors="coerce" and leaving 0
    usable rows -- even though the data itself is perfectly fine. Forcing
    a plain space at that position fixes it for every row, every time.
    """
    if "date" not in df.columns:
        return df
    df = df.copy()
    s = df["date"].astype(str)
    df["date"] = s.str.slice(0, 10) + " " + s.str.slice(11)
    return df


def _is_valid(df: pd.DataFrame) -> bool:
    if df is None or len(df) < MIN_ROWS or not REQUIRED_COLUMNS.issubset(df.columns):
        return False
    parsed = pd.to_datetime(df["date"], errors="coerce")
    return parsed.notna().sum() >= MIN_ROWS


def load_real_dataset():
    """
    Downloads the UCI Appliances Energy Prediction dataset once through
    ucimlrepo, then caches it locally as CSV. Validates both the cache and
    any fresh download so a partial/corrupted file can never silently
    train the model on zero rows.
    """
    if CACHE.exists():
        try:
            cached = pd.read_csv(CACHE)
            cached = _normalize_date_column(cached)
        except Exception:
            cached = None
        if _is_valid(cached):
            return cached
        # Cache exists but is empty/corrupt/incomplete (e.g. an interrupted
        # first download) — remove it and fetch fresh instead of failing
        # deep inside model training with a confusing sklearn error.
        CACHE.unlink(missing_ok=True)

    try:
        from ucimlrepo import fetch_ucirepo
    except ImportError as exc:
        raise RuntimeError(
            "ucimlrepo is missing. Run: pip install -r requirements.txt"
        ) from exc

    try:
        dataset = fetch_ucirepo(id=374)
        df = dataset.data.features.copy()

        # The target is returned separately by ucimlrepo.
        target = dataset.data.targets.copy()
        if "Appliances" not in target.columns:
            target.columns = ["Appliances"]

        df["Appliances"] = target["Appliances"].values
        df = _normalize_date_column(df)
    except Exception as exc:
        raise RuntimeError(
            "Could not download the UCI dataset. Check your internet "
            "connection and try again. If a partial 'data' folder was "
            "left behind, delete it first."
        ) from exc

    if not _is_valid(df):
        raise RuntimeError(
            f"Downloaded dataset looks incomplete (got {0 if df is None else len(df)} "
            f"rows). Delete the 'data' folder and rerun 'python app.py' on a "
            f"stable connection."
        )

    # Write atomically (temp file + rename) so a crash mid-write can never
    # leave behind a corrupt CSV that a later run would trust blindly.
    tmp = CACHE.with_suffix(".csv.tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(CACHE)
    return df
