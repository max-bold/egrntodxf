import ezdxf

doc = ezdxf.new()
msp = doc.modelspace()
points = [(0, 0), (3, 0), (6, 3), (6, 6)]
msp.add_lwpolyline(points)

doc.saveas("tests/lwpolyline1.dxf")