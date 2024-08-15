#!/bin/bash

# Ensure the script exits on the first failure
set -e

# Bump the version and create a tag (patch, minor, major)
# Adjust 'patch' to 'minor' or 'major' as needed
bump2version patch

# Push changes to Git
git push

# Push tags to Git
git push --tags

# Build the package
python3 -m build

# Upload to PyPI (ensure you have twine installed)
twine upload dist/*