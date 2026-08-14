from loguru import logger
from rich.logging import RichHandler
from rich.console import Console
import sys

# 1. Setup a Rich console
console = Console()

# 2. Configure Loguru to use Rich
logger.remove()
logger.add(
    lambda msg: console.print(msg, end=""),
    colorize=True,
    format="{message}"
)

# 3. Use Rich link syntax in your logs
logger.info("Check out the [link=https://github.com/delgan/loguru]Loguru GitHub[/link]!")


def rich_link(dpath):
    return '[link={dpath}]{dpath}[/link]'

dpath = "https://github.com/delgan/loguru"
logger.info("Check out the {rich_link(dpath)}")
