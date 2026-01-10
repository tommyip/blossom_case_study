import zipfile
from pathlib import Path

import aiohttp
import polars as pl

DATA_DIR = Path(__file__).parent.parent / "data"

COMPANIES_URL = "https://opendata.cro.ie/dataset/bf6f837d-0946-4c14-9a99-82cd6980c121/resource/3fef41bc-b8f4-4b10-8434-ce51c29b1bba/download/companies.csv.zip"


async def _download_file(url: str, dest: Path) -> Path:
    if dest.exists():
        return dest
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(await resp.read())
    return dest


async def download_companies() -> pl.DataFrame:
    zip_path = DATA_DIR / "companies.csv.zip"
    csv_path = DATA_DIR / "companies.csv"

    if not csv_path.exists():
        await _download_file(COMPANIES_URL, zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            csv_name = [n for n in zf.namelist() if n.endswith(".csv")][0]
            csv_path.write_bytes(zf.read(csv_name))

    return pl.read_csv(csv_path, infer_schema_length=10000)
