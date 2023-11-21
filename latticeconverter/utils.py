from itertools import chain
from warnings import warn
from .exceptions import ElementsOverlapError
import numpy as np

# def tree(latticejson, name=None):
#     lattices = latticejson["lattices"]

#     def _tree(name, prefix=""):
#         string = f"{name}\n"
#         if name in lattices:
#             *other, last = lattices[name]
#             for child in other:
#                 string += f"{prefix}├─── {_tree(child, prefix + '│   ')}"
#             string += f"{prefix}└─── {_tree(last, prefix + '    ')}"
#         return string

#     return _tree(latticejson["root"] if name is None else name)


def sort_lattices(latticejson, root=None, keep_unused=False):
    """Returns a sorted dict of lattice objects."""
    lattices = latticejson["lattices"]
    lattices_set = set(lattices)
    lattices_sorted = {}

    def _sort_lattices(name):
        lattices_set.remove(name)
        for child in lattices[name]:
            if child in lattices_set:
                _sort_lattices(child)
        lattices_sorted[name] = lattices[name]

    _sort_lattices(root if root is not None else latticejson["root"])
    if keep_unused:
        while len(lattices_set) > 0:
            _sort_lattices(lattices_set.pop())
    else:
        for lattice in lattices_set:
            warn(f"Discard unused lattice '{lattice}'.")
    return lattices_sorted


# def remove_unused(latticejson, root=None, warn_unused=False):
#     """Remove unused objects starting from the `root` lattice. Also sorts lattices."""
#     if root is None:
#         root = latticejson["root"]
#     elements = latticejson["elements"]
#     lattices = latticejson["lattices"]
#     elements_set = set(elements)
#     lattices_set = set(lattices)
#     elements_new = {}
#     lattices_new = {}

#     def _remove_unused(name):
#         try:
#             elements_set.remove(name)
#         except KeyError:
#             pass
#         else:
#             elements_new[name] = elements[name]
#             return

#         try:
#             lattices_set.remove(name)
#         except KeyError:
#             pass
#         else:
#             lattice = lattices[name]
#             for child in lattice:
#                 _remove_unused(child)
#             lattices_new[name] = lattices[name]

#     _remove_unused(root)
#     latticejson_new = latticejson.copy()
#     latticejson_new["root"] = root
#     latticejson_new["elements"] = elements_new
#     latticejson_new["lattices"] = lattices_new
#     if warn_unused:
#         for obj in chain(elements_set, lattices_set):
#             warn(f"Discard unused object '{obj}'.")
#     return latticejson_new


# def flattened_element_sequence(latticejson, start_lattice=None):
#     "Returns a flattened generator of the element names in the physical order."

#     def _helper(lattice_name, lattices=latticejson["lattices"]):
#         for child in lattices[lattice_name]:
#             if child in lattices:
#                 yield from _helper(child)
#             else:
#                 yield child

#     return _helper(start_lattice if start_lattice is not None else latticejson["root"])

def seq2line(sequence: list , elements: dict) -> list:
    """
    
    Add drifts to MADX sequence to translate from sequence format to lines format. So far only the default at reference point of centre can be handled.
    The drift spaces are generated according to the same principle as in madx.
    
    1. When the distance between the exit of previous element and the entrance of the next element is positive
       and greater than 1 μm a drift is generated.
       
    2. When the absolute value of the distance between the exit of the previous element the entrance
       of the next element is less than 1 μm no drift space is generated.
       
    3. When the distance between the exit of the previous element and the entrance of the next
       element is negative and less than -1 μm the elements are considered overlapping and an error is generated.
    
    Parameters
    ----------
    sequence : list
        Input sequence with element names and positions.
    elements : dict
        Dict of all elements.

    Returns
    -------
    list
        Output list with drifts added between the elements.

    """
   
    # Separate sequence of elements and position
    #elem_seq, position = list(zip(*sequence))
    
    # Define the threshold for generating drifts
    threshold = 1e-6
       
    # Add drifts to list
    drift_nbr = 0
    elem_seq = []
    elem_exit = 0.0 # s position of the exit of previous element
    for elem, pos in sequence:
        
        # Get length of element
        elem_length = elements[elem][1]['length']
        
        # Entrance position of element
        elem_entrance = pos-elem_length/2
        
        # Distance between entrance of the element and exit of previous element
        distance = elem_entrance-elem_exit
        
        # Generate drifts
        if np.absolute(distance) < threshold:
            # Elements are considered to sit next to each other and no drift is generated
            
            # Add element to list
            elem_seq.append(elem)
            
            # Update the exit position
            elem_exit += elem_length
            
        elif distance < -threshold:
            # Elements are considered to overlap
            raise ElementsOverlapError(elem,pos)
            
        elif distance > threshold:
            # A drift is generated and added to the lattice
            
            # Create drift element
            new_drift = "drift_" + str(drift_nbr)
            drift_nbr += 1
                       
            # Add drift to element dict         
            elements[new_drift] = ['Drift', {'length':  distance}]
            
            # Add drift and element to list
            elem_seq.append(new_drift)
            elem_seq.append(elem)
            
            # Update the exit position
            elem_exit += distance + elem_length
                                   
    return elem_seq

def line2seq(sequence: list , elements: dict) -> list:
    """
    
    Remove drifts from MADX lines to translate from lines to sequence format. So far only the default at reference point of centre can be handled.

    Parameters
    ----------
    sequence : list
        Input list with drifts added between the elements.
    elements : dict
        Dict of all elements.

    Returns
    -------
    list
        Output sequence with element names and positions.

    """
        
    seq_list = []
    pos = 0.0
    for elem in sequence:
               
        # Check if element is drift
        if elements[elem][0] == "Drift":
            # Add the length of the drift to the position
            pos += elements[elem][1]["length"]
        else:
            length = elements[elem][1]["length"]
            seq_list.append((elem,pos+length/2))
            
            # Add the length of the element to the position
            pos += length
        
    return seq_list
