from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("avero-devdeck")
except PackageNotFoundError:
    # Source checkouts without an installed distribution have no package metadata.
    __version__ = "0+unknown"
