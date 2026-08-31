import json
import ezdxf
import ezdxf.enums
import ezdxf.layouts
from pprint import pp


with open(
    r"C:\Users\boldm\Desktop\LOCAL\Склад Болтино\02 Стадия П\0020 Схема планировочной организации\intersections-info.geojson"
) as file:
    data = json.load(file)

doc = ezdxf.new()
msp = doc.modelspace()
for feature in data["features"]:
    for line in feature["geometry"]["coordinates"]:
        pl = msp.add_lwpolyline(line)
        pl.closed = True


doc.units = ezdxf.enums.InsertUnits.Meters
doc.update_extents()
doc.saveas(
    r"C:\Users\boldm\Desktop\LOCAL\Склад Болтино\02 Стадия П\0020 Схема планировочной организации\intersections-info.dxf"
)
