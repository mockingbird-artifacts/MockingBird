import xml.etree.ElementTree as ET

tree = ET.parse('target/site/jacoco/jacoco.xml')
root = tree.getroot()

total_covered = 0
total_missed = 0

for method in root.findall('.//method'):
    name = method.get('name')

    if name == '<clinit>':
        continue

    if ('$' in name and 'lambda$' in name) or 'access$' in name or name.startswith('$'):
        continue

    for counter in method.findall('./counter'):
        if counter.get('type') == 'METHOD':
            total_covered += int(counter.get('covered'))
            total_missed += int(counter.get('missed'))

if total_covered + total_missed == 0:
    print("No method coverage data found.")
else:
    percentage = 100 * total_covered / (total_covered + total_missed)
    print(f"Total non-interface methods missed: {total_missed}")
    print(f"Filtered method coverage: {percentage:.2f}%")
