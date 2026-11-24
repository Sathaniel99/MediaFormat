"""Phase 1 command line interface.

The Qt UI arrives in Phase 2 and will call the same engine used here.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from app.config import Config
from app.converter import BatchConverter, available_formats, collect_sources
from app.logging_setup import setup_logging
from app.models import BatchProgress, ConflictPolicy, ConversionResult, JobStatus, OutputFormat
from app.paths import config_path, format_size, is_writable_dir
from app.version import __version__

_FORMAT_ALIASES = {"jpg": "JPEG", "jpeg": "JPEG", "tif": "TIFF", "tiff": "TIFF"}


def _parse_format(value: str) -> OutputFormat:
    normalized = value.strip().lower()
    return OutputFormat.from_value(_FORMAT_ALIASES.get(normalized, normalized))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mediaformat",
        description="Convierte imagenes entre formatos (motor de la Fase 1).",
    )
    parser.add_argument("--version", action="version", version=f"MediaFormat {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    formats = subparsers.add_parser("formats", help="lista los formatos disponibles")
    formats.set_defaults(handler=_handle_formats)

    config = subparsers.add_parser("config", help="muestra la configuracion efectiva")
    config.add_argument("--show", action="store_true", help="imprime todos los valores")
    config.set_defaults(handler=_handle_config)

    convert = subparsers.add_parser("convert", help="convierte archivos o carpetas")
    convert.add_argument("inputs", nargs="+", help="archivos o carpetas de entrada")
    convert.add_argument("-f", "--format", type=_parse_format, help="formato de salida")
    convert.add_argument("-o", "--out", type=Path, help="carpeta de salida")
    convert.add_argument("-q", "--quality", type=int, help="calidad 1-100 (JPG/WEBP/AVIF)")
    convert.add_argument("--lossless", action="store_true", help="WebP sin perdida")
    convert.add_argument("--animated", action="store_true", help="conservar animaciones")
    convert.add_argument(
        "--conflict",
        choices=[policy.value for policy in ConflictPolicy],
        help="que hacer si el archivo existe",
    )
    convert.add_argument("--no-metadata", action="store_true", help="no copiar EXIF/ICC")
    convert.add_argument(
        "--no-orientation", action="store_true", help="no aplicar la orientacion EXIF"
    )
    convert.add_argument("--workers", type=int, help="hilos de conversion (1-16)")
    convert.add_argument("--no-recursive", action="store_true", help="no entrar en subcarpetas")
    convert.set_defaults(handler=_handle_convert)
    return parser


def _handle_formats(_: argparse.Namespace) -> int:
    for fmt in available_formats():
        flags = []
        if fmt.supports_quality:
            flags.append("calidad")
        if fmt.supports_alpha:
            flags.append("alfa")
        if fmt.supports_animation:
            flags.append("animacion")
        suffix = f" ({', '.join(flags)})" if flags else ""
        print(f"{fmt.value:<5} {fmt.extension:<6}{suffix}")
    return 0


def _handle_config(args: argparse.Namespace) -> int:
    settings = Config()
    print(f"Archivo: {settings.path} ({'existe' if settings.path.exists() else 'no existe'})")
    if not args.show:
        print(f"Salida:  {settings.output_folder}")
        print(f"Formato: {settings.default_format.value}")
        print("Usa --show para ver todo.")
        return 0
    for section, values in settings._data.items():  # noqa: SLF001 - diagnostics command
        print(f"[{section}]")
        for key, value in values.items():
            print(f"  {key} = {value}")
    if settings.warnings:
        print("\nAvisos:")
        for warning in settings.warnings:
            print(f"  - {warning}")
    return 0


def _handle_convert(args: argparse.Namespace) -> int:
    settings = Config()
    options = settings.conversion_options(args.format, quality=args.quality)
    options.lossless = bool(args.lossless) or options.lossless
    options.animated = bool(args.animated) or options.animated
    options.keep_metadata = not args.no_metadata
    options.apply_exif_orientation = not args.no_orientation
    if args.conflict is not None:
        options.on_conflict = ConflictPolicy.from_value(args.conflict)
    options = options.normalized()

    output_dir = Path(args.out) if args.out else settings.output_folder
    if not is_writable_dir(output_dir, create=True):
        print(f"ERROR: la carpeta de salida no es escribible: {output_dir}", file=sys.stderr)
        return 2

    recursive = settings.recursive_folders if not args.no_recursive else False
    sources = collect_sources(args.inputs, recursive=recursive)
    if not sources:
        print("ERROR: no se encontraron imagenes en la entrada", file=sys.stderr)
        return 2

    workers = args.workers or settings.max_workers
    converter = BatchConverter(output_dir, options, max_workers=workers)

    def report(progress: BatchProgress) -> None:
        print(f"[{progress.done}/{progress.total}] {progress.result.summary()}")

    results = converter.run(sources, on_progress=report)
    return _print_summary(results, output_dir)


def _print_summary(results: list[ConversionResult], output_dir: Path) -> int:
    done = sum(1 for result in results if result.status is JobStatus.DONE)
    skipped = sum(1 for result in results if result.status is JobStatus.SKIPPED)
    errors = [result for result in results if result.status is JobStatus.ERROR]
    saved = sum(result.size_out for result in results if result.status is JobStatus.DONE)
    source_size = sum(result.size_in for result in results if result.status is JobStatus.DONE)

    print()
    print(f"Convertidas: {done} | Omitidas: {skipped} | Errores: {len(errors)}")
    if done:
        delta = source_size - saved
        sign = "+" if delta >= 0 else "-"
        print(f"Salida: {format_size(saved)} ({sign}{format_size(abs(delta))} vs original)")
    print(f"Carpeta: {output_dir}")

    if errors:
        print("\nErrores:")
        for result in errors:
            print(f"  - {result.source.name}: {result.error}")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(level=logging.WARNING)
    try:
        return int(args.handler(args))
    except KeyboardInterrupt:
        print("\nCancelado.", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 - last resort for a friendly CLI
        logging.getLogger("mediaformat.cli").exception("error no controlado")
        print(f"ERROR: {exc}", file=sys.stderr)
        print(f"Config: {config_path()}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
