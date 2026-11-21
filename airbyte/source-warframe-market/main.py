from __future__ import annotations

import sys

from airbyte_cdk.entrypoint import launch

from source import SourceWarframeMarket


if __name__ == "__main__":
    launch(SourceWarframeMarket(), sys.argv[1:])
