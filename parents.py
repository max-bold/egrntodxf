import xml.etree.ElementTree as et

tree = et.parse(
    r"C:\Users\boldm\Downloads\report-b9ad575d-75e7-46f7-b44e-f5fbc03198da-EPGU-2026-04-17-1028980-50-01[0].xml"
)
root = tree.getroot()
for element in root.iter("contour"):
    print(element.text)