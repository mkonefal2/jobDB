"""Debug script to inspect praca.pl HTML structure."""

import re
import sys

sys.path.insert(0, ".")

from selectolax.parser import HTMLParser

with open("data/debug_praca.html", "r", encoding="utf-8") as f:
    html = f.read()

tree = HTMLParser(html)

# Find all unique class names containing 'listing' or 'offer'
class_pattern = re.compile(r'class="([^"]*)"')
all_classes = set()
for m in class_pattern.finditer(html):
    for cls in m.group(1).split():
        if "listing" in cls or "offer" in cls:
            all_classes.add(cls)

print("=== Classes with 'listing' or 'offer' ===")
for c in sorted(all_classes):
    print(f"  {c}")

# Try to find offer link pattern
print("\n=== Links matching offer URL pattern ===")
links = tree.css("a[href]")
offer_links = []
for link in links:
    href = link.attributes.get("href", "")
    if re.search(r"_\d{7,10}\.html", href):
        parent = link.parent
        parent_cls = parent.attributes.get("class", "") if parent else "none"
        grandparent = parent.parent if parent else None
        gp_cls = grandparent.attributes.get("class", "") if grandparent else "none"
        gp_tag = grandparent.tag if grandparent else "none"
        offer_links.append((href[:60], parent.tag, parent_cls[:40], gp_tag, gp_cls[:40]))
        if len(offer_links) >= 5:
            break

for href, ptag, pcls, gptag, gpcls in offer_links:
    print(f"  link: {href}")
    print(f"    parent: <{ptag} class='{pcls}'>")
    print(f"    grandparent: <{gptag} class='{gpcls}'>")
    print()

# Find the first offer block and print its full HTML
print("=== First offer container HTML (truncated) ===")
for link in links:
    href = link.attributes.get("href", "")
    if re.search(r"_\d{7,10}\.html", href):
        # Walk up to find a container
        node = link
        for _ in range(5):
            if node.parent:
                node = node.parent
        print(node.html[:2000])
        break
