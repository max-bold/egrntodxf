from pyautocad import Autocad, APoint

acad = Autocad()
# acad.prompt("Hello, Autocad from Python\n")
print(acad.doc.Name)
for obj in acad.iter_objects():
    print(obj.ObjectName)