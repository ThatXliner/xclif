"""Greeter CLI implemented with Xclif using a pre-compiled manifest."""
from xclif import Cli
from xclif_greeter import _xclif_manifest

cli = Cli.from_manifest(_xclif_manifest)

if __name__ == "__main__":
    cli()
