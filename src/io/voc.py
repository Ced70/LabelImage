from __future__ import annotations

import os
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.dom import minidom

from src.models.annotation import Annotation, AnnotationType, BoundingBox, ImageAnnotations
from src.models.label import LabelManager


def save_voc(annotations: ImageAnnotations, label_manager: LabelManager) -> None:
    """Save annotations as PASCAL VOC XML next to the image."""
    if not annotations.image_path:
        return

    xml_path = str(Path(annotations.image_path).with_suffix(".xml"))

    if not annotations.annotations:
        if os.path.isfile(xml_path):
            os.remove(xml_path)
        return

    root = ET.Element("annotation")

    ET.SubElement(root, "folder").text = os.path.basename(os.path.dirname(annotations.image_path))
    ET.SubElement(root, "filename").text = os.path.basename(annotations.image_path)
    ET.SubElement(root, "path").text = annotations.image_path

    source = ET.SubElement(root, "source")
    ET.SubElement(source, "database").text = "Unknown"

    size = ET.SubElement(root, "size")
    ET.SubElement(size, "width").text = str(annotations.image_width)
    ET.SubElement(size, "height").text = str(annotations.image_height)
    ET.SubElement(size, "depth").text = "3"

    ET.SubElement(root, "segmented").text = "0"

    for ann in annotations.annotations:
        if ann.ann_type != AnnotationType.BBOX or not ann.bbox:
            continue

        label = label_manager.get(ann.label_id)
        name = label.name if label else f"class_{ann.label_id}"

        obj = ET.SubElement(root, "object")
        ET.SubElement(obj, "name").text = name
        ET.SubElement(obj, "pose").text = "Unspecified"
        ET.SubElement(obj, "truncated").text = "0"
        ET.SubElement(obj, "difficult").text = "0"

        bndbox = ET.SubElement(obj, "bndbox")
        ET.SubElement(bndbox, "xmin").text = str(int(round(ann.bbox.x)))
        ET.SubElement(bndbox, "ymin").text = str(int(round(ann.bbox.y)))
        ET.SubElement(bndbox, "xmax").text = str(int(round(ann.bbox.x + ann.bbox.width)))
        ET.SubElement(bndbox, "ymax").text = str(int(round(ann.bbox.y + ann.bbox.height)))

    xml_str = minidom.parseString(ET.tostring(root, encoding="unicode")).toprettyxml(indent="  ")
    # Remove extra XML declaration from toprettyxml
    lines = xml_str.split("\n")
    if lines[0].startswith("<?xml"):
        lines = lines[1:]
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + "\n".join(lines)

    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml_str)


def load_voc(xml_path: str, label_manager: LabelManager) -> list[Annotation]:
    """Load annotations from a PASCAL VOC XML file."""
    if not os.path.isfile(xml_path):
        return []

    tree = ET.parse(xml_path)
    root = tree.getroot()
    annotations = []

    # Build name -> class_id map
    name_to_id = {l.name: l.class_id for l in label_manager.labels}

    for obj in root.findall("object"):
        name_elem = obj.find("name")
        if name_elem is None:
            continue
        name = name_elem.text or ""

        bndbox = obj.find("bndbox")
        if bndbox is None:
            continue

        xmin = float(bndbox.findtext("xmin", "0"))
        ymin = float(bndbox.findtext("ymin", "0"))
        xmax = float(bndbox.findtext("xmax", "0"))
        ymax = float(bndbox.findtext("ymax", "0"))

        # Get or create class
        if name not in name_to_id:
            label = label_manager.add(name)
            name_to_id[name] = label.class_id

        annotations.append(Annotation(
            label_id=name_to_id[name],
            ann_type=AnnotationType.BBOX,
            bbox=BoundingBox(x=xmin, y=ymin, width=xmax - xmin, height=ymax - ymin),
        ))

    return annotations
