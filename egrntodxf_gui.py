"""Small Dear PyGui front-end for exporting EGRN contours to DXF."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import xml.etree.ElementTree as ET

import dearpygui.dearpygui as dpg
from ezdxf.enums import InsertUnits
from ezdxf.filemanagement import new
from ezdxf.lldxf.const import DXFError


WINDOW_TITLE = "EGRN to DXF"
CHECKBOX_GROUP = "parent_name_checkboxes"
SELECT_ALL_BUTTON = "select_all_button"
SAVE_BUTTON = "save_dxf_button"
STATUS_TEXT = "status_text"
OTHER_GROUP_NAME = "other"


@dataclass
class AppState:
    xml_path: Path | None = None
    tree: ET.ElementTree[ET.Element[str]] | None = None
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


def set_status(message: str, *, error: bool = False) -> None:
    dpg.set_value(STATUS_TEXT, message)
    dpg.configure_item(
        STATUS_TEXT,
        color=(220, 80, 80) if error else (180, 180, 180),
    )


def selected_record_names() -> list[str]:
    return [
        name for name, tag in state.checkbox_tags.items() if dpg.get_value(tag)
    ]


def on_checkbox_changed() -> None:
    dpg.configure_item(SAVE_BUTTON, show=bool(selected_record_names()))


def select_all() -> None:
    for checkbox_tag in state.checkbox_tags.values():
        dpg.set_value(checkbox_tag, True)
    on_checkbox_changed()


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

    state.xml_path = path
    state.tree = tree
    state.checkbox_tags.clear()
    dpg.delete_item(CHECKBOX_GROUP, children_only=True)

    for record_name in record_names:
        checkbox_tag = dpg.add_checkbox(
            label=record_name,
            parent=CHECKBOX_GROUP,
            callback=on_checkbox_changed,
        )
        state.checkbox_tags[record_name] = checkbox_tag

    dpg.configure_item(SELECT_ALL_BUTTON, show=bool(record_names))
    dpg.configure_item(SAVE_BUTTON, show=False)
    if record_names:
        set_status(f"{path.name}: {len(record_names)} group(s) found")
    else:
        set_status("No *_record elements containing contours found", error=True)


def show_open_dialog() -> None:
    dialog_parent = tk.Tk()
    dialog_parent.withdraw()
    dialog_parent.attributes("-topmost", True)
    dialog_parent.update()
    try:
        file_path = filedialog.askopenfilename(
            parent=dialog_parent,
            title="Open cadastral XML extract",
            filetypes=(("XML files", "*.xml"), ("All files", "*.*")),
        )
    finally:
        dialog_parent.destroy()

    if file_path:
        load_xml(Path(file_path))


def show_save_dialog() -> None:
    dialog_parent = tk.Tk()
    dialog_parent.withdraw()
    dialog_parent.attributes("-topmost", True)
    dialog_parent.update()
    try:
        file_path = filedialog.asksaveasfilename(
            parent=dialog_parent,
            title="Save DXF",
            initialdir=str(state.xml_path.parent) if state.xml_path else None,
            initialfile=f"{state.xml_path.stem}.dxf" if state.xml_path else None,
            defaultextension=".dxf",
            filetypes=(("DXF files", "*.dxf"), ("All files", "*.*")),
        )
    finally:
        dialog_parent.destroy()

    selected = selected_record_names()
    if not file_path or state.tree is None or not selected:
        return

    output_path = Path(file_path)
    if output_path.suffix.lower() != ".dxf":
        output_path = output_path.with_suffix(".dxf")

    try:
        count = export_to_dxf(state.tree, selected, output_path)
    except (OSError, ValueError, DXFError) as error:
        set_status(f"Could not save DXF: {error}", error=True)
        return

    set_status(f"Saved {count} polylines to {output_path.name}")


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
            "Open a cadastral XML extract", tag=STATUS_TEXT, wrap=330
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
