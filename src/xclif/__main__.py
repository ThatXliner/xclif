from xclif import Cli
from xclif import _cli

cli = Cli.from_routes(_cli)

if __name__ == "__main__":
    cli()
