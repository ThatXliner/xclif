from xclif import Cli

from . import routes

cli = Cli.from_routes(routes)
if __name__ == "__main__":
    cli()
