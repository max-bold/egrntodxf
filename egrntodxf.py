import xml.etree.ElementTree as et
import ezdxf


doc = ezdxf.new()
msp = doc.modelspace()
tree = et.parse(r"\\192.168.1.74\текущие\Склад Шолохово\00 Входящие\20220205 ЕГРН2\report-51cf901a-1be7-4ddf-becd-2dae3dd8e333-OfSite-2022-02-03-336092-50-010.xml")
root = tree.getroot()
for contour in root.iter("contour"):
        for sp in contour.iter("spatial_element"):
            points = []
            for ord in sp.iter("ordinate"):
                points.append((float(ord.find("y").text), float(ord.find("x").text)))
            pl = msp.add_lwpolyline(points)
            # pl.close()
# doc.units = ezdxf.units.M
doc.update_extents()
doc.saveas(r"\\192.168.1.74\текущие\Склад Шолохово\00 Входящие\20220205 ЕГРН2\contours4.dxf")