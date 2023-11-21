import json
from pathlib import Path
# from typing import Dict, List
from warnings import warn

from .exceptions import UnknownAttributeWarning, UnknownElementTypeWarning
from .parse import parse_elegant, parse_madx
from .utils import sort_lattices, seq2line, line2seq
# from .validate import schema_version

"""
Map between element/attribute names for LatticeJSON and different lattice formats.
x - contains the name for LatticeJSON
y - contains the name for the lattice format
"""
NAME_MAP = json.loads((Path(__file__).parent / "map.json").read_text())["map"]
TO_ELEGANT = {x: y[0][0] for x, *y in NAME_MAP}
FROM_ELEGANT = {y: x for x, *tup in NAME_MAP for y in tup[0]}
TO_MADX = {x: y[1][0] for x, *y in NAME_MAP}
FROM_MADX = {y: x for x, *tup in NAME_MAP for y in tup[1]}
TO_PYAT= {x: y[2][0] for x, *y in NAME_MAP}


def from_elegant(string: str) -> dict:
    """
    Convert a string in elegant format to a LatticeJSON dict.

    Parameters
    ----------
    string : str
        Content of the input lattice file in MADX format.

    Returns
    -------
    dict
        Dict in LatticeJSON format.

    """
    return _map_names(parse_elegant(string), FROM_ELEGANT)


def from_madx(string: str) -> dict:
    """
    Convert a string in MADX lattice format to a LatticeJSON dict.
    Is able to handle input in both line and sequence format. For a sequence drifts are generated.

    Parameters
    ----------
    string : str
        Content of the input lattice file in MADX format.

    Returns
    -------
    dict
        Dict in LatticeJSON format.

    """    
    
    latticejson = _map_names(parse_madx(string), FROM_MADX)
    
    # Handle if input is a sequence file
    commands = latticejson["commands"]
    if "sequence" in list(zip(*commands))[0]:
    
        lattices = latticejson["lattices"]
        elements = latticejson["elements"]
        sequence = lattices[list(zip(*commands))[1][0]]

        # Add drifts
        new_sequence = seq2line(sequence, elements)
        lattices[list(zip(*commands))[1][0]] = new_sequence
    
    return latticejson

def _map_names(lattice_data: dict, name_map: dict) -> dict: 
    """
    Map element/attribute names in input lattice format to element/attribute names in LatticeJSON format.

    Parameters
    ----------
    lattice_data : dict
        Dict in the input lattice format.
    name_map : dict
        Dict with the map of the element/attribute names.

    Returns
    -------
    dict
        Dict in LatticeJSON format.

    """

    # Map elements
    elements = {}
    for name, (other_type, other_attributes) in lattice_data["elements"].items():
        
        # Check if the element type refers to another element
        # If so change the type and add the attributes
        if other_type in lattice_data["elements"]: 
            (other_type, additional_attributes) = lattice_data["elements"].get(other_type)
            other_attributes.update(additional_attributes)
            
        latticejson_type = name_map.get(other_type)        
        if latticejson_type is None:
            elements[name] = ["Drift", {"length": other_attributes.get("L", 0)}]
            warn(UnknownElementTypeWarning(name, other_type))
            continue

        # Map attributes
        attributes = {}
        elements[name] = [latticejson_type, attributes]
        
        # Handle if no attributes exist
        if not other_attributes:
            attributes['length'] = 0
        else:
            for other_key, value in other_attributes.items():
                latticejson_key = name_map.get(other_key)
                if latticejson_key is not None:
                    attributes[latticejson_key] = value
                else:
                    warn(UnknownAttributeWarning(other_key, name))
                        
    lattices = lattice_data["lattices"]    
    root = lattice_data.get("root", tuple(lattices.keys())[-1])
    title = lattice_data.get("title", "")
    commands = lattice_data["commands"]
    return dict(
#        version=str(schema_version),
        title=title,
        root=root,
        elements=elements,
        lattices=lattices,
        commands=commands
    )

def to_elegant(latticejson: dict) -> str:
    """
    Convert a LatticeJSON dict to the elegant lattice file format.

    Parameters
    ----------
    latticejson : dict
        dict in LatticeJSON format.

    Returns
    -------
    str
        string with in elegant lattice file format.

    """

    elements = latticejson["elements"]
#    lattices = latticejson["lattices"]

    strings = [f"! TITLE: {latticejson['title']}"]
    element_template = "{}: {}, {}".format
    # TODO: check if equivalent type exists in elegant
    for name, (type_, attributes) in elements.items():
        attrs = ", ".join(f"{TO_ELEGANT[k]}={v}" for k, v in attributes.items())
        elegant_type = TO_ELEGANT[type_]
        strings.append(element_template(name, elegant_type, attrs))

    lattice_template = "{}: line=({})".format
    for name, children in sort_lattices(latticejson).items():
        strings.append(lattice_template(name, ", ".join(children)))

    strings.append(f"USE, {latticejson['root']}\n")
    return "\n".join(strings)


def to_madx(latticejson: dict) -> str:
    """
    Convert a LatticeJSON dict to the MADX lattice file format.

    Parameters
    ----------
    latticejson : dict
        dict in LatticeJSON format.

    Returns
    -------
    str
        string in madx lattice file format.

    """

    elements = latticejson["elements"]
    lattices = latticejson["lattices"]
    commands = latticejson["commands"]

    strings = []
    
    # TODO: check if equivalent type exists in madx
    for name, (type_, attributes) in elements.items():
        attrs = ", ".join(f"{TO_MADX[k]}={v}" for k, v in attributes.items())
        elegant_type = TO_MADX[type_]
        
        # Add attributes
        element_template = "{}: {}, {};".format
        strings.append(element_template(name, elegant_type, attrs))
        
        # # Handle if an element has no attributes (e.g. a marker)
        # if len(attrs) > 0:
        #     element_template = "{}: {}, {};".format
        #     strings.append(element_template(name, elegant_type, attrs))
        # else:
        #     element_template = "{}: {};".format
        #     strings.append(element_template(name, elegant_type)) 
               
    # Handle if input is a sequence file
    commands = latticejson["commands"]
    if "sequence" in list(zip(*commands))[0]:
            
        # Add the sequence name and attributes
        substr = []
        name = latticejson["commands"][0][1]
        substr.append(f"{name}: SEQUENCE,")
        for attr, value in latticejson["commands"][0][2]:
            substr.append(f"{attr} = {value}")
        substr.append(";\n")
        strings.append("".join(substr))
        
        # Add the at definitions
        root = latticejson["root"]
        new_sequence = line2seq(lattices[root],elements)
        at_template = "{}, at = {};".format
        for name, pos in new_sequence:
            strings.append(at_template(name, pos))
        strings.append("ENDSEQUENCE;\n")
        
    else:
        strings.append(f"TITLE, \"{latticejson['title']}\";")
        lattice_template = "{}: line=({});".format
        for name, children in sort_lattices(latticejson).items():
            strings.append(lattice_template(name, ", ".join(children)))
            strings.append(f"USE, SEQUENCE={latticejson['root']};\n")
            
    return "\n".join(strings)

def to_pyat(latticejson: dict) -> str:
    """
    Convert a LatticeJSON dict to the pyat lattice file format.

    Parameters
    ----------
    latticejson : dict
        dict in LatticeJSON format.

    Returns
    -------
    str
        string with in pyat lattice file format.

    """
    
    function_name = latticejson.get('title')
    if function_name == "":
        function_name = "lattice"
    strings = [f"def {function_name}():\n"]
    
    elements = latticejson["elements"]

    element_template = "    {} = {}('{}', {})".format
      # TODO: check if equivalent type exists in pyat
    for name, (type_, attributes) in elements.items():
        attrs = ", ".join(f"{TO_PYAT[k]}={v}" for k, v in attributes.items())
        pyat_type = TO_PYAT[type_]
        strings.append(element_template(name, pyat_type, name, attrs))
        
    lattices = latticejson["lattices"]

    # lattice_template = "{}: line=({})".format
    # for name, children in sort_lattices(latticejson).items():
    #     strings.append(lattice_template(name, ", ".join(children)))

    strings.append(f"USE, {latticejson['root']}\n")
    return "\n".join(strings)