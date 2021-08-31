import pytest
from click.testing import CliRunner
from pytomicropy.core import main

runner = CliRunner()


def test_cli(tmp_path):
    indir = tmp_path / "in"
    outdir = tmp_path / "out"
    indir.mkdir()
    (indir / "main.py").write_text(
        """
print(f"Hello from{__file__}")
"""
    )
    response = runner.invoke(main, ["--input", indir, "--output", outdir])
    assert not response.exception
    assert outdir.exists and outdir.is_dir()
    # Ensure f-strings are replaced
    assert (outdir / "main.py").read_text() == "print('Hello from{}'.format(__file__))"
