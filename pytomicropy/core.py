from pathlib import Path
from types import SimpleNamespace
import autoflake
from strip_hints import strip_file_to_string
import python_minifier
import f2format
import click
import tempfile
import shutil

BUILD_DIR = Path(__file__).parent.parent / "build" / "lib" / "pyserialdrivers"
ARCHIVE_NAME = "dist/upyserialdrivers.zip"


def remove_unused(src: Path) -> None:
    """Removes unused imports and variables from file in place"""
    input_str = src.read_text(encoding="utf-8")
    output_str = autoflake.fix_code(input_str)
    src.write_text(output_str, encoding="utf-8")


def remove_typehints(src: Path) -> None:
    """Removes typehints from file in place"""
    result_str = strip_file_to_string(src, to_empty=True, strip_nl=True)
    src.write_text(result_str, encoding="utf-8")


def convert_fstrings(src: Path) -> None:
    """Converts fstring to str.format for Python < 3.6"""
    input_str = src.read_text(encoding="utf-8")
    output_str = f2format.convert(input_str)
    src.write_text(output_str, encoding="utf-8")


def minify(src: Path) -> None:
    """Minifies actual code without changing it functionally"""
    input_str = src.read_text(encoding="utf-8")
    output_str = python_minifier.minify(input_str, remove_literal_statements=True)
    src.write_text(output_str, encoding="utf-8")


@click.command()
@click.option(
    "--input", required=True, help="Package root directory to convert", type=Path
)
@click.option("--output", required=True, help="Package output directory", type=Path)
def main(input: Path, output: Path):
    input = input.resolve()
    if not input.exists():
        raise FileNotFoundError(f"{input} not found.")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir).resolve()
        shutil.copytree(
            input,
            tmp_path,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        for file in tmp_path.rglob("*.py"):
            file = file.resolve()
            try:
                convert_fstrings(file)
                remove_typehints(file)
                remove_unused(file)
                minify(file)
            except:
                print(f"Failed on: {file}")
                raise

        if not output.exists():
            output.mkdir()
        if output.is_dir():
            shutil.copytree(tmp_path, output, dirs_exist_ok=True)
        elif output.suffix == "zip":
            shutil.make_archive(
                str(output).rstrip(".zip"), root_dir=tmp_path, format="zip"
            )
        else:
            raise ValueError(
                "Unknown output, please select directory or file ending in *zip"
            )


if __name__ == "__main__":
    main()
