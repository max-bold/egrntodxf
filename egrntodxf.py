import xml.etree.ElementTree as et
from altair import Element
import ezdxf
import ezdxf.layouts

# from sympy import false


def tofloat(ord: et.Element, key: str) -> float | None:
    a = ord.find(key)
    a = a.text if a else None
    a = float(a) if a else None
    return a


def getcontours(
    element: et.Element,
    modelspace: ezdxf.layouts.layout.Modelspace,
    layer: str,
    closed: bool = False,
):
    for contour in element.iter("contour"):
        for sp in contour.iter("spatial_element"):
            points = []
            for ord in sp.iter("ordinate"):
                x = tofloat(ord, "x")
                y = tofloat(ord, "y")
                if x and y:
                    points.append((y, x))
            pl = modelspace.add_lwpolyline(points)
            pl.dxf.layer = layer
            pl.closed = closed


doc = ezdxf.new()
msp = doc.modelspace()
tree = et.parse(
    r"\\192.168.1.74\объекты\Б. Черная\Входящие\20250227 ЕГРН\report-8caf8a38-118d-4ff0-9daf-0754e4603adf-EPGU-2025-02-26-922276-50-01[0].xml"
)
root = tree.getroot()
# for contour in root.iter("contour"):
#         for sp in contour.iter("spatial_element"):
#             points = []
#             for ord in sp.iter("ordinate"):
#                 points.append((float(ord.find("y").text), float(ord.find("x").text)))
#             pl = msp.add_lwpolyline(points)
# pl.close()
doc.layers.add(name="kad_buildings", color=1)
for bulding in root.iter("build_record"):
    getcontours(bulding, msp, "kad_buildings", closed=True)

doc.layers.add(name="kad_buildings_uc", color=2)
for bulding in root.iter("object_under_construction_record"):
    getcontours(bulding, msp, "kad_buildings_uc", closed=True)

doc.layers.add(name="kad_plots", color=5)
for plot in root.iter("land_record"):
    getcontours(plot, msp, "kad_plots", closed=True)

doc.layers.add(name="kad_nets", color=6)
for net in root.iter("construction_record"):
    getcontours(net, msp, "kad_nets")

doc.layers.add(name="kad_zones", color=3)
for zone in root.iter("zones_and_territories_record"):
    getcontours(zone, msp, "kad_zones", closed=True)
# doc.units = ezdxf.units.M
doc.update_extents()
doc.saveas(r"\\192.168.1.74\объекты\Б. Черная\Входящие\20250227 ЕГРН\contours.dxf")
# doc.close()
