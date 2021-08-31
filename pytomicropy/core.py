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
@click.option("--force", required=False, default=False, help="Overwrite output if it exists", type=bool)
def main(input: Path, output: Path, force: bool):
    input = input.resolve()
    output = output.resolve()
    if not input.exists():
        raise FileNotFoundError(f"{input} not found.")
    if output.exists():
        if force:
            shutil.rmtree(output)
        else:
            raise FileExistsError("Output directory already exists and --force not specified")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir).resolve()
        # Avoid shutil dir exists error
        tmp_path = tmp_path / "working"
        shutil.copytree(
            input,
            tmp_path,
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

        if not output.parent.exists():
            output.parent.mkdir()
        if output.suffix == "zip":
            shutil.make_archive(
                str(output).rstrip(".zip"), root_dir=tmp_path, format="zip"
            )
        else:
            shutil.copytree(tmp_path, output)


if __name__ == "__main__":
    main()
