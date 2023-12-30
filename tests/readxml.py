import xml.etree.ElementTree as et
tree = et.parse('tests\\report2.xml')
root = tree.getroot()
for contour in root.iter('contour'):
        for ord in contour.iter('ordinate'):
            print(ord.find('x').text, ord.find('y').text)
        print('-----------')
