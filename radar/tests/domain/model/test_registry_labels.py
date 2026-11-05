from __future__ import annotations

from radar.adapters.files.model_json import load_registry

REGISTRY = load_registry()
IDENTICAL_ALLOWLIST = frozenset({
    "Cloud", "Autofocus", "Multispectral", "Interface", "Article", "LiDAR", "Ultraviolet (UV)", "Services", "Transport",
    "Code", "Brochure", "Image", "Monochrome", "Radar", "Classification", "Segmentation", "Applications", "Interfaces",
    "IP20", "IP30", "IP40", "IP50", "IP54", "IP64", "IP65", "IP66", "IP67", "IP68", "IP69K",
    "PROFINET", "EtherNet/IP", "EtherCAT", "IO-Link", "Modbus/TCP", "CANopen", "CC-Link", "OPC UA",
    "GigE", "10GigE", "100GigE", "5GigE", "2.5GigE", "25GigE", "USB", "USB 2.0", "USB 3.0", "USB 3.2", "Camera Link",
    "Camera Link HS", "CoaXPress", "CoaXPress CXP-6", "CoaXPress CXP-12", "MIPI CSI-2", "GMSL2", "PCIe", "Bluetooth",
    "RS-232", "RS-485", "RS-422", "UART", "I2C", "FireWire", "LVDS", "Sub-LVDS", "SLVS-EC", "HDMI", "SDI", "SPI",
    "PCIe Gen 2", "PCIe Gen 3", "PCIe Gen 4",
    "Windows", "Linux", "macOS", "Android", "C", "C++", "C#", ".NET", "Python", "Delphi", "LabVIEW", "Visual Basic",
    "CMOS", "sCMOS", "CCD", "EMCCD", "InGaAs", "InSb", "MCT (HgCdTe)", '1/4"', '1/3"', '1/2"', '2/3"', '1"', '4/3"',
    '1.1"', '1.2"', '1.3"', '1.4"', '1.8"', '2"', '2.3"', '2.5"', '2.7"', '3.4"', '3.6"', '4.1"', '4.2"', "APS-H",
    "FPD-Link III", "Micro Four Thirds",
    "APS-C", "Super 35", "OCR", "PDF417",
    "GigE Vision", "USB3 Vision", "GenICam", "GigE Vision 2.2", "USB3 Vision 1.2", "CoaXPress 2.1",
    "Camera Link HS 1.2", "EMVA 1288 4.0", "OPC UA Machine Vision 1.0", "FCC Part 15", "REACH", "RoHS",
    "FPGA", "Hailo", "MQTT", "Model Context Protocol (MCP)", "NVIDIA Jetson", "ONNX", "OpenVINO IR", "PyTorch", "ROS 2",
    "TensorFlow", "TensorFlow Lite", "TensorRT", "gRPC",
})

def test_registry_labels_fr_not_identical_to_en_without_allowlist() -> None:
    labels = [(f"vocab/{name}", i, t.label) for name, terms in REGISTRY.vocabularies.items() for i, t in terms.items()]
    labels += [("spec_definitions", i, s.label) for i, s in REGISTRY.spec_definitions.items()]
    same = [f"{src}:{i} -> {label.get('en')!r}" for src, i, label in labels if label.get("en") == label.get("fr")
            and label.get("en") not in IDENTICAL_ALLOWLIST]
    assert not same, "registry labels with fr == en not in the allowlist:\n" + "\n".join(same)

def test_category_descriptions_and_domain_labels_are_translated() -> None:
    untranslated = [c for c, cat in REGISTRY.categories.items() if cat.description is not None
                    and cat.description.get("fr") in (None, "", cat.description.get("en"))]
    assert not untranslated, f"categories without a French description: {untranslated}"
    domains = REGISTRY.vocabularies["domains"]
    assert [c for c, cat in REGISTRY.categories.items()
            if not (domains[cat.domain].label.get("fr") and domains[cat.domain].label.get("en"))] == []

def test_every_source_type_has_a_preference() -> None:
    assert [i for i, t in REGISTRY.vocabularies["source_types"].items() if t.preference is None] == []
