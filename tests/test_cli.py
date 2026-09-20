from digital_fte.cli import build_parser

def test_cli_contract():
    a=build_parser().parse_args(["--vault","vault","run","task.md"])
    assert a.command=="run" and str(a.task)=="task.md"
