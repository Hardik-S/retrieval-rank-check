# Launch checklist

The initial package version is `0.1.0`; release tooling must use the same version for the package and tag. This validator is offline, has no runtime dependencies, and uses synthetic example fixtures only.

Before distribution, install the built source archive into a fresh environment, run the full test suite with zero skips, and exercise the installed console script for valid data (exit 0), rank issues (exit 1), invalid input and invalid argument lists (exit 2), and help (exit 0). Confirm invalid responses contain no private argument, path, source text, or exception details.

CI should cover Ubuntu and Windows with Python 3.10 and 3.13. Build from a clean checkout and ensure every tracked source file is included in the published archive.
