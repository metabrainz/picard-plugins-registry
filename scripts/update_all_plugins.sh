#! /usr/bin/bash

# Utility to update registry entries for all registered plugins.

# Copyright (C) 2026 Bob Swift (rdswift)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.

if [[ `pwd` =~ /scripts$ ]]; then
  cd ..
fi

echo "Updating registy entries for registered plugins."
echo ""

for plugin in `sed -n 's/^id = "\([^\"]*\)\"$/\1/p' plugins.toml`; do
  registry plugin update "$plugin"
done

echo ""
registry validate

echo ""
echo "Update complete. Review changes with: git diff plugins.toml"
