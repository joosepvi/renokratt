import os
import json
import compute_rhino3d.Grasshopper as gh
import compute_rhino3d.Util
import rhino3dm

# Set the compute_rhino3d.Util.url, default URL is http://localhost:6500/
compute_rhino3d.Util.url = 'http://localhost:6500/'

# Define path to local working directory
workdir = os.getcwd() + '\\'

# Read input parameters from JSON file
with open(workdir + 'input.json') as f:
    input_params = json.load(f)


# Create the input DataTree
input_trees = []
for key, value in input_params.items():
    print(key)
    tree = gh.DataTree(key)
    tree.Append([{0}], [str(value)])
    input_trees.append(tree)


# Evaluate the Grasshopper definition
output = gh.EvaluateDefinition(
    workdir + 'konfiguraator.gh',
    input_trees
)

# Create a new rhino3dm file
file = rhino3dm.File3dm()

# Iterate over each output node's result stored in 'output['values']'
for output_value in output['values']:
    # Iterate over all items in the InnerTree of each output value
    for key, items in output_value['InnerTree'].items():
        for item in items:
            # Decode the mesh object from each item's data
            obj = rhino3dm.CommonObject.Decode(json.loads(item['data']))
            # Add the decoded object to the file if it's a Mesh
            if isinstance(obj, rhino3dm.Mesh):
                file.Objects.AddMesh(obj)

# Save the rhino3dm file to your working directory
file.Write(workdir + 'geometry.3dm', 7)



