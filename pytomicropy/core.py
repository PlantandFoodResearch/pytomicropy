from pathlib import Path
import autoflake
from strip_hints import strip_string_to_string
import python_minifier
import f2format
import click
import tempfile
import shutil
import os
import parso
from parso.python.tree import KeywordStatement, Name, Operator
import logging

logging.basicConfig(level=logging.DEBUG)

BUILD_DIR = Path(__file__).parent.parent / "build" / "lib" / "pyserialdrivers"
ARCHIVE_NAME = "dist/upyserialdrivers.zip"


def remove_unused(src: Path) -> None:
    """Removes unused imports and variables from file in place"""
    input_str = src.read_text(encoding="utf-8")
    output_str = autoflake.fix_code(input_str)
    src.write_text(output_str, encoding="utf-8")


def remove_typehints(src: Path) -> None:
    """Removes typehints from file in place"""
    input_str = src.read_text(encoding="utf-8")
    result_str = strip_string_to_string(input_str, to_empty=True, strip_nl=True)
    src.write_text(result_str, encoding="utf-8")


def _patch_fstrings_starred_exp(src: Path) -> str:
    """Use AST to attempt to resolve some common errors. Return patched code string

    Technically it is correct and they are non-cmopliant. E.g. "del x, y, z"
    This is a hacky patch to attempt to fix it.
    """
    grammar = parso.load_grammar()
    input = src.read_text(encoding="utf-8")
    output_lines = input.splitlines(keepends=False)
    module = grammar.parse(src.read_text(encoding="utf-8"), error_recovery=True)
    errors = grammar.iter_errors(module)
    if len(errors) > 1:
        logging.warning(f"Patching multiple errors is not tested.")
    for issue in errors:
        # We can recover some...
        if "can't use starred expression here" in issue.message:
            node: KeywordStatement = issue._node
            children = node.children[1]
            if children.type == "exprlist":
                # we can unpack this!
                line = node.start_pos[0] - 1  # 0 indexing
                patch = ""
                for chld in children.children:
                    if isinstance(chld, Name):
                        patch += f"{node.keyword} {chld.value}{os.linesep}"
                logging.debug(
                    f"Fixing illegal starred expression in {src}. Patch changes:{os.linesep + output_lines[line] + os.linesep} TO:\
                {os.linesep + patch + os.linesep}"
                )
                output_lines.pop(line)
                output_lines.insert(line, patch)
        else:
            raise NotImplementedError(f'Don\'t know how to fix "issue.message"')
    output = os.linesep.join(output_lines)
    # Check for errors
    remaining_errors = grammar.iter_errors(grammar.parse(output, error_recovery=True))
    if remaining_errors:
        logging.error(
            "Failed to fix errors in file {src}, remaining: {remaining_errors}"
        )
        return None
    return output


def convert_fstrings(src: Path) -> None:
    """Converts fstring to str.format for Python < 3.6"""
    input_str = src.read_text(encoding="utf-8")
    try:
        output_str = f2format.convert(input_str)
    except f2format.ConvertError as exc:
        logging.warning(f"f2format failed with {src}, attempting to recover...")
        try:
            patched_str = _patch_fstrings_starred_exp(src)
            output_str = f2format.convert(patched_str)
        except Exception as e:
            logging.exception("Failed to recover", e)
            raise e
    src.write_text(output_str, encoding="utf-8")


def minify(src: Path) -> None:
    """Minifies actual code without changing it functionally"""
    input_str = src.read_text(encoding="utf-8")
    output_str = python_minifier.minify(
        input_str, remove_literal_statements=True, hoist_literals=False
    )
    src.write_text(output_str, encoding="utf-8")


@click.command()
@click.option(
    "--input",
    "-i",
    required=True,
    help="Package root directory or file to convert",
    type=Path,
)
@click.option(
    "--output", "-o", required=True, help="Package output directory", type=Path
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Overwrite output if it exists",
)
@click.option(
    "--skip-minifier",
    "-SM",
    is_flag=True,
    help="Don't minify output code. This can be useful to keep debug line numbers identical",
)
def main(input: Path, output: Path, force: bool, skip_minifier: bool):
    input = input.resolve()
    output = output.resolve()
    if not input.exists():
        raise FileNotFoundError(f"{input} not found.")
    if output.exists():
        if force:
            shutil.rmtree(output)
        else:
            raise FileExistsError(
                "Output directory already exists and --force not specified"
            )
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir).resolve()
        # Avoid shutil dir exists error
        tmp_path = tmp_path / "working"
        if input.is_dir():
            shutil.copytree(
                input,
                tmp_path,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        else:
            tmp_path.mkdir(exist_ok=True)
            shutil.copyfile(input, tmp_path / input.name)
        for file in tmp_path.rglob("*.py"):
            file = file.resolve()
            try:
                convert_fstrings(file)
                remove_typehints(file)
                remove_unused(file)
                if not skip_minifier:
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
