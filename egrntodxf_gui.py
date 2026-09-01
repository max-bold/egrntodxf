"""Dear PyGui front-end for exporting EGRN XML and GeoJSON to DXF."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
from typing import Any, Iterator
import xml.etree.ElementTree as ET

import dearpygui.dearpygui as dpg
from ezdxf.enums import InsertUnits
from ezdxf.filemanagement import new
from ezdxf.lldxf.const import DXFError


WINDOW_TITLE = "EGRN / GeoJSON to DXF"
CHECKBOX_GROUP = "parent_name_checkboxes"
SELECT_ALL_BUTTON = "select_all_button"
SAVE_BUTTON = "save_dxf_button"
STATUS_TEXT = "status_text"
OTHER_GROUP_NAME = "other"
GEOJSON_GROUP_NAME = "GeoJSON Features"
GEOJSON_LAYER_NAME = "geojson_features"
GEOJSON_GEOMETRY_TYPES = (
    "Point",
    "MultiPoint",
    "LineString",
    "MultiLineString",
    "Polygon",
    "MultiPolygon",
)

GeoJsonObject = dict[str, Any]


@dataclass
class AppState:
    source_path: Path | None = None
    tree: ET.ElementTree[ET.Element[str]] | None = None
    geojson: GeoJsonObject | None = None
    checkbox_tags: dict[str, int | str] = field(default_factory=dict)


state = AppState()


def local_name(tag: str) -> str:
    """Return an XML tag without its optional namespace."""
    return tag.rsplit("}", 1)[-1]


def discover_record_names(root: ET.Element[str]) -> list[str]:
    """Find all ``*_record`` element types containing a contour."""
    names = {
        local_name(record.tag)
        for record in root.iter()
        if local_name(record.tag).endswith("_record")
        and any(local_name(item.tag) == "contour" for item in record.iter())
    }
    return sorted(names)


def find_unassigned_contours(root: ET.Element[str]) -> list[ET.Element[str]]:
    """Find contours that have no enclosing ``*_record`` element."""
    parent_by_child = {
        child: parent for parent in root.iter() for child in parent
    }
    unassigned: list[ET.Element[str]] = []

    for contour in root.iter():
        if local_name(contour.tag) != "contour":
            continue

        ancestor = parent_by_child.get(contour)
        while ancestor is not None:
            if local_name(ancestor.tag).endswith("_record"):
                break
            ancestor = parent_by_child.get(ancestor)
        else:
            unassigned.append(contour)

    return unassigned


def child_text(element: ET.Element[str], name: str) -> str | None:
    for child in element:
        if local_name(child.tag) == name:
            return child.text
    return None


def contour_polylines(contour: ET.Element[str]):
    """Yield a point list for every spatial_element inside a contour."""
    for spatial_element in contour.iter():
        if local_name(spatial_element.tag) != "spatial_element":
            continue

        points: list[tuple[float, float]] = []
        for ordinate in spatial_element.iter():
            if local_name(ordinate.tag) != "ordinate":
                continue

            x_text = child_text(ordinate, "x")
            y_text = child_text(ordinate, "y")
            if x_text is None or y_text is None:
                continue

            # Coordinates in EGRN extracts are conventionally written as X=northing,
            # Y=easting. DXF expects easting first, hence the intentional Y/X order.
            points.append((float(y_text), float(x_text)))

        if len(points) >= 2:
            yield points


def layer_name(parent_name: str) -> str:
    if parent_name.endswith("_record"):
        parent_name = parent_name[: -len("_record")]
    return f"kad_{parent_name}"


def split_record_contours(
    record: ET.Element[str],
) -> tuple[list[ET.Element[str]], list[ET.Element[str]]]:
    """Split record contours into regular and object_part contours."""
    part_contour_set = {
        contour
        for part in record.iter()
        if local_name(part.tag) == "object_part"
        for contour in part.iter()
        if local_name(contour.tag) == "contour"
    }
    all_contours = [
        item for item in record.iter() if local_name(item.tag) == "contour"
    ]
    regular_contours = [
        contour for contour in all_contours if contour not in part_contour_set
    ]
    part_contours = [
        contour for contour in all_contours if contour in part_contour_set
    ]
    return regular_contours, part_contours


def export_to_dxf(
    tree: ET.ElementTree[ET.Element[str]],
    selected_record_names: list[str],
    output_path: Path,
) -> int:
    """Export contours below all selected record types; return polyline count."""
    document = new()
    modelspace = document.modelspace()
    root = tree.getroot()
    polyline_count = 0
    next_color = 1

    for record_name in selected_record_names:
        if record_name == OTHER_GROUP_NAME:
            regular_contours = find_unassigned_contours(root)
        else:
            regular_contours = []
        part_contours: list[ET.Element[str]] = []
        if record_name != OTHER_GROUP_NAME:
            for record in root.iter():
                if local_name(record.tag) == record_name:
                    regular, parts = split_record_contours(record)
                    regular_contours.extend(regular)
                    part_contours.extend(parts)

        regular_layer = layer_name(record_name)
        document.layers.add(name=regular_layer, color=next_color)
        next_color += 1

        part_layer = f"{regular_layer}_part"
        if part_contours:
            document.layers.add(name=part_layer, color=next_color)
            next_color += 1

        for contour in regular_contours:
            for points in contour_polylines(contour):
                modelspace.add_lwpolyline(
                    points, dxfattribs={"layer": regular_layer}
                )
                polyline_count += 1

        for contour in part_contours:
            for points in contour_polylines(contour):
                modelspace.add_lwpolyline(points, dxfattribs={"layer": part_layer})
                polyline_count += 1

    document.units = InsertUnits.Meters
    document.update_extents()
    document.saveas(output_path)
    return polyline_count


def iter_geojson_geometries(value: Any) -> Iterator[GeoJsonObject]:
    """Yield primitive geometries from a GeoJSON object."""
    if not isinstance(value, dict):
        return

    object_type = value.get("type")
    if object_type == "FeatureCollection":
        features = value.get("features")
        if isinstance(features, list):
            for feature in features:
                yield from iter_geojson_geometries(feature)
    elif object_type == "Feature":
        yield from iter_geojson_geometries(value.get("geometry"))
    elif object_type == "GeometryCollection":
        geometries = value.get("geometries")
        if isinstance(geometries, list):
            for geometry in geometries:
                yield from iter_geojson_geometries(geometry)
    elif object_type in GEOJSON_GEOMETRY_TYPES:
        yield value


def discover_geojson_geometry_types(data: GeoJsonObject) -> list[str]:
    present_types = {
        geometry["type"] for geometry in iter_geojson_geometries(data)
    }
    return [
        geometry_type
        for geometry_type in GEOJSON_GEOMETRY_TYPES
        if geometry_type in present_types
    ]


def geojson_point(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None


def add_geojson_line(
    modelspace: Any,
    coordinates: Any,
    layer: str,
    *,
    closed: bool,
) -> int:
    if not isinstance(coordinates, (list, tuple)):
        return 0

    points = [
        point
        for coordinate in coordinates
        if (point := geojson_point(coordinate)) is not None
    ]
    if closed and len(points) > 1 and points[0] == points[-1]:
        points.pop()
    if len(points) < 2:
        return 0

    polyline = modelspace.add_lwpolyline(points, dxfattribs={"layer": layer})
    polyline.closed = closed
    return 1


def add_geojson_geometry(
    modelspace: Any, geometry: GeoJsonObject, layer: str
) -> int:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")

    if geometry_type == "Point":
        point = geojson_point(coordinates)
        if point is None:
            return 0
        modelspace.add_point(point, dxfattribs={"layer": layer})
        return 1

    if geometry_type == "MultiPoint":
        if not isinstance(coordinates, (list, tuple)):
            return 0
        count = 0
        for coordinate in coordinates:
            point = geojson_point(coordinate)
            if point is not None:
                modelspace.add_point(point, dxfattribs={"layer": layer})
                count += 1
        return count

    if geometry_type == "LineString":
        return add_geojson_line(modelspace, coordinates, layer, closed=False)

    if geometry_type == "MultiLineString":
        if not isinstance(coordinates, (list, tuple)):
            return 0
        return sum(
            add_geojson_line(modelspace, line, layer, closed=False)
            for line in coordinates
        )

    if geometry_type == "Polygon":
        if not isinstance(coordinates, (list, tuple)):
            return 0
        return sum(
            add_geojson_line(modelspace, ring, layer, closed=True)
            for ring in coordinates
        )

    if geometry_type == "MultiPolygon":
        if not isinstance(coordinates, (list, tuple)):
            return 0
        return sum(
            add_geojson_line(modelspace, ring, layer, closed=True)
            for polygon in coordinates
            if isinstance(polygon, (list, tuple))
            for ring in polygon
        )

    return 0


def export_geojson_to_dxf(
    data: GeoJsonObject,
    output_path: Path,
) -> int:
    document = new()
    modelspace = document.modelspace()
    entity_count = 0

    document.layers.add(name=GEOJSON_LAYER_NAME, color=7)
    for geometry in iter_geojson_geometries(data):
        entity_count += add_geojson_geometry(
            modelspace, geometry, GEOJSON_LAYER_NAME
        )

    document.units = InsertUnits.Meters
    document.update_extents()
    document.saveas(output_path)
    return entity_count


def set_status(message: str, *, error: bool = False) -> None:
    dpg.set_value(STATUS_TEXT, message)
    dpg.configure_item(
        STATUS_TEXT,
        color=(220, 80, 80) if error else (180, 180, 180),
    )


def selected_groups() -> list[str]:
    return [
        name for name, tag in state.checkbox_tags.items() if dpg.get_value(tag)
    ]


def on_checkbox_changed() -> None:
    dpg.configure_item(SAVE_BUTTON, show=bool(selected_groups()))


def select_all() -> None:
    for checkbox_tag in state.checkbox_tags.values():
        dpg.set_value(checkbox_tag, True)
    on_checkbox_changed()


def show_groups(
    group_names: list[str], source_label: str, empty_message: str
) -> None:
    state.checkbox_tags.clear()
    dpg.delete_item(CHECKBOX_GROUP, children_only=True)

    for group_name in group_names:
        checkbox_tag = dpg.add_checkbox(
            label=group_name,
            parent=CHECKBOX_GROUP,
            callback=on_checkbox_changed,
        )
        state.checkbox_tags[group_name] = checkbox_tag

    dpg.configure_item(SELECT_ALL_BUTTON, show=bool(group_names))
    dpg.configure_item(SAVE_BUTTON, show=False)
    if group_names:
        set_status(f"{source_label}: {len(group_names)} group(s) found")
    else:
        set_status(empty_message, error=True)


def load_xml(path: Path) -> None:
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        record_names = discover_record_names(root)
        if find_unassigned_contours(root):
            record_names.append(OTHER_GROUP_NAME)
    except (OSError, ET.ParseError) as error:
        set_status(f"Could not open XML: {error}", error=True)
        return

    state.source_path = path
    state.tree = tree
    state.geojson = None
    show_groups(
        record_names,
        "XML",
        "No *_record elements containing contours found",
    )


def load_geojson(path: Path) -> None:
    try:
        with path.open(encoding="utf-8-sig") as source_file:
            data = json.load(source_file)
        if not isinstance(data, dict):
            raise ValueError("the root value must be a JSON object")
        geometry_types = discover_geojson_geometry_types(data)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        set_status(f"Could not open GeoJSON: {error}", error=True)
        return

    state.source_path = path
    state.tree = None
    state.geojson = data
    show_groups(
        [GEOJSON_GROUP_NAME] if geometry_types else [],
        "GeoJSON",
        "No supported geometries found in the GeoJSON",
    )


def load_source(path: Path) -> None:
    if path.suffix.lower() == ".xml":
        load_xml(path)
    elif path.suffix.lower() in {".geojson", ".json"}:
        load_geojson(path)
    else:
        set_status("Select an XML or GeoJSON file", error=True)


def show_open_dialog() -> None:
    dialog_parent = tk.Tk()
    dialog_parent.withdraw()
    dialog_parent.attributes("-topmost", True)
    dialog_parent.update()
    try:
        file_path = filedialog.askopenfilename(
            parent=dialog_parent,
            title="Open XML or GeoJSON",
            filetypes=(
                ("XML and GeoJSON", "*.xml *.geojson *.json"),
                ("XML files", "*.xml"),
                ("GeoJSON files", "*.geojson *.json"),
                ("All files", "*.*"),
            ),
        )
    finally:
        dialog_parent.destroy()

    if file_path:
        load_source(Path(file_path))


def show_save_dialog() -> None:
    dialog_parent = tk.Tk()
    dialog_parent.withdraw()
    dialog_parent.attributes("-topmost", True)
    dialog_parent.update()
    try:
        file_path = filedialog.asksaveasfilename(
            parent=dialog_parent,
            title="Save DXF",
            initialdir=(
                str(state.source_path.parent) if state.source_path else None
            ),
            initialfile=(
                f"{state.source_path.stem}.dxf" if state.source_path else None
            ),
            defaultextension=".dxf",
            filetypes=(("DXF files", "*.dxf"), ("All files", "*.*")),
        )
    finally:
        dialog_parent.destroy()

    selected = selected_groups()
    if not file_path or not selected:
        return

    output_path = Path(file_path)
    if output_path.suffix.lower() != ".dxf":
        output_path = output_path.with_suffix(".dxf")

    try:
        if state.tree is not None:
            count = export_to_dxf(state.tree, selected, output_path)
        elif state.geojson is not None:
            count = export_geojson_to_dxf(state.geojson, output_path)
        else:
            return
    except (OSError, ValueError, DXFError) as error:
        set_status(f"Could not save DXF: {error}", error=True)
        return

    set_status(f"Saved {count} entities to {output_path.name}")


def build_ui() -> None:
    dpg.create_context()

    with dpg.window(  # pyright: ignore[reportGeneralTypeIssues]
        tag="main_window", label=WINDOW_TITLE
    ):
        dpg.add_button(
            label="Open",
            width=110,
            callback=show_open_dialog,
        )
        dpg.add_group(tag=CHECKBOX_GROUP)
        dpg.add_button(
            tag=SELECT_ALL_BUTTON,
            label="Select all",
            width=110,
            show=False,
            callback=select_all,
        )
        dpg.add_button(
            tag=SAVE_BUTTON,
            label="Save",
            width=110,
            show=False,
            callback=show_save_dialog,
        )
        dpg.add_text(
            "Open an XML or GeoJSON file", tag=STATUS_TEXT, wrap=330
        )

    dpg.create_viewport(title=WINDOW_TITLE, width=380, height=420, min_width=260)
    dpg.setup_dearpygui()
    dpg.set_primary_window("main_window", True)
    dpg.show_viewport()


def main() -> None:
    build_ui()
    try:
        dpg.start_dearpygui()
    finally:
        dpg.destroy_context()


if __name__ == "__main__":
    main()
