# [Quixel Megascans Livelink for Octane Blender Edition]
#
# ##### QUIXEL AB - MEGASCANS LIVELINK FOR BLENDER #####
#
# The Megascans LiveLink plugin for Blender is an add-on that lets
# you instantly import assets with their shader setup with one click only.
#
# Because it relies on some of the latest 2.80 features, this plugin is currently
# only available for Blender 2.80 and forward.
#
# You are free to modify, add features or tweak this add-on as you see fit, and
# don't hesitate to send us some feedback if you've done something cool with it.
#
# ##### QUIXEL AB - MEGASCANS LIVELINK FOR BLENDER #####

import bpy
import threading
import os
import time
import json
import socket
from bpy.types import Operator, AddonPreferences
from bpy.props import IntProperty, EnumProperty, BoolProperty

globals()['Megascans_DataSet'] = None
globals()['MG_Material'] = []
globals()['MG_AlembicPath'] = []
globals()['MG_ImportComplete'] = False

bl_info = {
    "name": "Megascans LiveLink Octane",
    "description": "Connects Octane Blender to Quixel Bridge for one-click imports with shader setup and geometry",
    "author": "Yichen Dou",
    "version": (1, 3),
    "blender": (2, 81, 0),
    "location": "File > Import",
    "warning": "",  # used for warning icon and text in addons panel
    "wiki_url": "https://docs.quixel.org/bridge/livelinks/blender/info_quickstart.html",
    "tracker_url": "https://docs.quixel.org/bridge/livelinks/blender/info_quickstart#release_notes",
    "support": "COMMUNITY",
    "category": "Import-Export"
}


# MS_Init_ImportProcess is the main asset import class.
# This class is invoked whenever a new asset is set from Bridge.

# Addon preferences
disp_types = [
    ('TEXTURE', 'Texture', 'Octane Texture Displacement'),
    ('VERTEX', 'Vertex', 'Octane Vertex Displacement')
]

disp_levels_texture = [
    ('OCTANE_DISPLACEMENT_LEVEL_256', '256', '256x256'),
    ('OCTANE_DISPLACEMENT_LEVEL_512', '512', '512x512'),
    ('OCTANE_DISPLACEMENT_LEVEL_1024', '1024', '1024x1024'),
    ('OCTANE_DISPLACEMENT_LEVEL_2048', '2048', '2048x2048'),
    ('OCTANE_DISPLACEMENT_LEVEL_4096', '4096', '4096x4096'),
    ('OCTANE_DISPLACEMENT_LEVEL_8192', '8192', '8192x8192')
]


class MSLiveLinkPrefs(AddonPreferences):
    bl_idname = __name__

    disp_type: EnumProperty(
        items=disp_types,
        name="Displacement Mode",
        description="Set default Octane displacement mode",
        default="TEXTURE"
    )

    disp_level_texture: EnumProperty(
        items=disp_levels_texture,
        name="Subdivision",
        default="OCTANE_DISPLACEMENT_LEVEL_4096"
    )

    disp_level_vertex: IntProperty(
        name="Subdivision",
        min=0,
        max=6,
        default=6
    )

    is_cavity_enabled: BoolProperty(
        name="Enable Cavity map",
        default=False
    )

    is_curvature_enabled: BoolProperty(
        name="Enable Curvature map",
        default=False
    )

    is_bump_enabled: BoolProperty(
        name="Enable Bump map",
        default=False
    )

    is_fuze_enabled: BoolProperty(
        name="Enable Fuze map",
        default=False
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        row = col.row()
        row.prop(self, "disp_type")
        if(self.disp_type == "TEXTURE"):
            row.prop(self, "disp_level_texture")
        else:
            row.prop(self, "disp_level_vertex")
        col.prop(self, "is_cavity_enabled")
        col.prop(self, "is_curvature_enabled")
        col.prop(self, "is_bump_enabled")
        col.prop(self, "is_fuze_enabled")


class MS_Init_ImportProcess():

    def __init__(self):
        # This initialization method create the data structure to process our assets
        # later on in the initImportProcess method. The method loops on all assets
        # that have been sent by Bridge.

        print("Initialized import class...")
        try:
            # Check if there's any incoming data
            if globals()['Megascans_DataSet'] != None:
                self.json_Array = json.loads(globals()['Megascans_DataSet'])

                # Start looping over each asset in the self.json_Array list
                for js in self.json_Array:
                    self.json_data = js
                    self.selectedObjects = []
                    self.assetType = self.json_data["type"]
                    self.assetPath = self.json_data["path"]
                    self.assetID = self.json_data["id"]
                    # Workflow setup
                    self.isMetal = bool(self.json_data["category"] == "Metal")
                    self.isHighPoly = bool(
                        self.json_data["activeLOD"] == "high")
                    self.activeLOD = self.json_data["activeLOD"]
                    self.minLOD = self.json_data["minLOD"]
                    self.isScatterAsset = self.CheckScatterAsset()
                    self.textureList = []
                    self.isBillboard = self.CheckIsBillboard()
                    self.ApplyToSelection = False
                    self.isAlembic = False

                    if "applyToSelection" in self.json_data.keys():
                        self.ApplyToSelection = bool(
                            self.json_data["applyToSelection"])

                    texturesListName = "components"
                    if(self.isBillboard):
                        texturesListName = "components"

                    self.textureTypes = [obj["type"]
                                         for obj in self.json_data[texturesListName]]
                    self.textureList = []

                    for obj in self.json_data[texturesListName]:
                        texFormat = obj["format"]
                        texType = obj["type"]
                        texPath = obj["path"]

                        if texType == "displacement" and texFormat != "exr":
                            texDir = os.path.dirname(texPath)
                            texName = os.path.splitext(
                                os.path.basename(texPath))[0]

                            if os.path.exists(os.path.join(texDir, texName + ".exr")):
                                texPath = os.path.join(
                                    texDir, texName + ".exr")
                                texFormat = "exr"
                        # Replace diffuse texture type with albedo so we don't have to add more conditions to handle diffuse map.
                        if texType == "diffuse" and "albedo" not in self.textureTypes:
                            texType = "albedo"
                            self.textureTypes.append("albedo")
                            self.textureTypes.remove("diffuse")

                        self.textureList.append((texFormat, texType, texPath))

                    # Create a tuple list of all the 3d meshes  available.
                    # This tuple is composed of (meshFormat, meshPath)
                    self.geometryList = [(obj["format"], obj["path"])
                                         for obj in self.json_data["meshList"]]

                    # Create name of our asset. Multiple conditions are set here
                    # in order to make sure the asset actually has a name and that the name
                    # is short enough for us to use it. We compose a name with the ID otherwise.
                    if "name" in self.json_data.keys():
                        self.assetName = self.json_data["name"].replace(
                            " ", "_")
                    else:
                        self.assetName = os.path.basename(
                            self.json_data["path"]).replace(" ", "_")
                    if len(self.assetName.split("_")) > 2:
                        self.assetName = "_".join(
                            self.assetName.split("_")[:-1])

                    self.materialName = self.assetName + '_' + self.assetID
                    self.colorSpaces = ["sRGB", "Non-Color"]

                    # Initialize the import method to start building our shader and import our geometry
                    self.initImportProcess()
                    print("Imported asset from " +
                          self.assetName + " Quixel Bridge")

            if len(globals()['MG_AlembicPath']) > 0:
                globals()['MG_ImportComplete'] = True
        except Exception as e:
            print(
                "Megascans LiveLink Error initializing the import process. Error: ", str(e))

        globals()['Megascans_DataSet'] = None
    # this method is used to import the geometry and create the material setup.

    def initImportProcess(self):
        try:
            if len(self.textureList) >= 1 and bpy.context.scene.render.engine == 'octane':

                if(self.ApplyToSelection and self.assetType not in ["3dplant", "3d"]):
                    self.CollectSelectedObjects()

                self.ImportGeometry()
                self.CreateMaterial()
                self.ApplyMaterialToGeometry()
                if(self.isScatterAsset and len(self.selectedObjects) > 1):
                    self.ScatterAssetSetup()

                self.SetupMaterial()

                if self.isAlembic:
                    globals()['MG_Material'].append(self.mat)

        except Exception as e:
            print("Megascans LiveLink Error while importing textures/geometry or setting up material. Error: ", str(e))

    # Geometry setup

    def ImportGeometry(self):
        try:
            # Import geometry
            abcPaths = []
            if len(self.geometryList) >= 1:
                for obj in self.geometryList:
                    meshPath = obj[1]
                    meshFormat = obj[0]

                    if meshFormat.lower() == "fbx":
                        bpy.ops.import_scene.fbx(filepath=meshPath)
                        # get selected objects
                        obj_objects = [
                            o for o in bpy.context.scene.objects if o.select_get()]
                        self.selectedObjects += obj_objects

                    elif meshFormat.lower() == "obj":
                        bpy.ops.import_scene.obj(
                            filepath=meshPath, use_split_objects=True, use_split_groups=True)
                        # get selected objects
                        obj_objects = [
                            o for o in bpy.context.scene.objects if o.select_get()]
                        self.selectedObjects += obj_objects

                    elif meshFormat.lower() == "abc":
                        self.isAlembic = True
                        abcPaths.append(meshPath)

            if self.isAlembic:
                globals()['MG_AlembicPath'].append(abcPaths)
        except Exception as e:
            print("Megascans Plugin Error while importing textures/geometry or setting up material. Error: ", str(e))

    def dump(self, obj):
        for attr in dir(obj):
            print("obj.%s = %r" % (attr, getattr(obj, attr)))

    def CollectSelectedObjects(self):
        try:
            sceneSelectedObjects = [
                o for o in bpy.context.scene.objects if o.select_get()]
            for obj in sceneSelectedObjects:
                if obj.type == "MESH":
                    self.selectedObjects.append(obj)
        except Exception as e:
            print("Megascans Plugin Error::CollectSelectedObjects::", str(e))

    def ApplyMaterialToGeometry(self):
        for obj in self.selectedObjects:
            # assign material to obj
            obj.active_material = self.mat

    def CheckScatterAsset(self):
        if('scatter' in self.json_data['categories'] or 'scatter' in self.json_data['tags']):
            return True
        return False

    def CheckIsBillboard(self):
        # Use billboard textures if importing the Billboard LOD.
        if(self.assetType == "3dplant"):
            if (self.activeLOD == self.minLOD):
                return True
        return False

    def ScatterAssetSetup(self):
        # Create an empty object
        bpy.ops.object.empty_add(type='SPHERE', radius=0.2)
        emptyRefList = [o for o in bpy.context.scene.objects if o.select_get(
        ) and o not in self.selectedObjects]
        for scatterParentObject in emptyRefList:
            scatterParentObject.name = self.assetID + "_" + self.assetName
            for obj in self.selectedObjects:
                obj.parent = scatterParentObject
            break

    # Material setup
    # Shader setups for all asset types. Some type specific functionality is also handled here.
    def CreateMaterial(self):
        self.mat = bpy.data.materials.new(self.materialName)
        self.mat.use_nodes = True
        self.nodes = self.mat.node_tree.nodes

        # Replace default octane shader with a universal shader
        self.outNode = self.nodes[0]
        oldMainMat = self.nodes[1]
        self.mainMat = self.nodes.new('ShaderNodeOctUniversalMat')
        self.mainMat.location = oldMainMat.location
        self.nodes.remove(oldMainMat)
        self.mat.node_tree.links.new(
            self.outNode.inputs['Surface'], self.mainMat.outputs[0])
        # Metallic value
        self.mainMat.inputs['Metallic'].default_value = 1 if self.isMetal else 0
        # IOR Value
        self.mainMat.inputs['Dielectric IOR'].default_value = 1.5
        self.mainMat.inputs['Specular'].default_value = 0.5

    def SetupMaterial(self):
        prefs = bpy.context.preferences.addons[__name__].preferences
        y_exp = 310

        # Create the albedo setup.
        if "albedo" in self.textureTypes:
            imgPath = self.GetTexturePath("albedo")
            if len(imgPath) >= 1:
                texNode = self.nodes.new('ShaderNodeOctImageTex')
                y_exp += -320
                texNode.location = (-720, y_exp)
                texNode.image = bpy.data.images.load(imgPath)
                texNode.show_texture = True
                texNode.image.colorspace_settings.name = self.colorSpaces[0]

                if "ao" in self.textureTypes:
                    aoPath = self.GetTexturePath("ao")
                    if len(aoPath) >= 1:
                        aoNode = self.nodes.new('ShaderNodeOctImageTex')
                        aoNode.image = bpy.data.images.load(aoPath)
                        aoNode.image.colorspace_settings.name = self.colorSpaces[1]
                        aoNode.location = (-720, y_exp + 320)
                        multiplyNode = self.nodes.new(
                            'ShaderNodeOctMultiplyTex')
                        multiplyNode.location = (-320, 180)
                        self.mat.node_tree.links.new(
                            multiplyNode.inputs[1], texNode.outputs[0])
                        self.mat.node_tree.links.new(
                            multiplyNode.inputs[0], aoNode.outputs[0])
                        self.mat.node_tree.links.new(
                            self.mainMat.inputs['Albedo color'], multiplyNode.outputs[0])
                else:
                    self.mat.node_tree.links.new(
                        self.mainMat.inputs['Albedo color'], texNode.outputs[0])

        # Create the specular map setup
        if "specular" in self.textureTypes:
            imgPath = self.GetTexturePath('specular')
            if len(imgPath) >= 1:
                texNode = self.nodes.new('ShaderNodeOctImageTex')

                y_exp += -320
                texNode.location = (-720, y_exp)

                texNode.image = bpy.data.images.load(imgPath)
                texNode.show_texture = True
                texNode.image.colorspace_settings.name = self.colorSpaces[0]

                self.mat.node_tree.links.new(
                    self.mainMat.inputs['Specular'], texNode.outputs[0])

        # Create the roughness setup.
        if "roughness" in self.textureTypes:
            imgPath = self.GetTexturePath("roughness")
            if len(imgPath) >= 1:
                texNode = self.nodes.new('ShaderNodeOctImageTex')
                y_exp += -320
                texNode.location = (-720, y_exp)
                texNode.image = bpy.data.images.load(imgPath)
                texNode.show_texture = True
                texNode.image.colorspace_settings.name = self.colorSpaces[1]

                self.mat.node_tree.links.new(
                    self.mainMat.inputs['Roughness'], texNode.outputs[0])

        # Create the metalness setup
        if "metalness" in self.textureTypes:
            imgPath = self.GetTexturePath("metalness")
            if len(imgPath) >= 1:
                texNode = self.nodes.new('ShaderNodeOctImageTex')
                y_exp += -320
                texNode.location = (-720, y_exp)
                texNode.image = bpy.data.images.load(imgPath)
                texNode.show_texture = True
                texNode.image.colorspace_settings.name = self.colorSpaces[1]

                self.mat.node_tree.links.new(
                    self.mainMat.inputs['Metallic'], texNode.outputs[0])

        # Create the displacement setup.
        if "displacement" in self.textureTypes:
            imgPath = self.GetTexturePath("displacement")
            if len(imgPath) >= 1:
                texNode = self.nodes.new('ShaderNodeOctImageTex')
                y_exp += -320
                texNode.location = (-720, y_exp)
                texNode.image = bpy.data.images.load(imgPath)
                texNode.show_texture = True
                texNode.image.colorspace_settings.name = self.colorSpaces[1]
                if prefs.disp_type == "VERTEX":
                    texNode.border_mode = 'OCT_BORDER_MODE_CLAMP'

                if prefs.disp_type == "TEXTURE":
                    dispNode = self.nodes.new(
                        'ShaderNodeOctDisplacementTex')
                    dispNode.displacement_level = prefs.disp_level_texture
                    #dispNode.displacement_filter = 'OCTANE_FILTER_TYPE_BOX'
                    dispNode.inputs['Mid level'].default_value = 0.5
                    dispNode.inputs['Height'].default_value = 0.1
                else:
                    dispNode = self.nodes.new(
                        'ShaderNodeOctVertexDisplacementTex')
                    dispNode.inputs['Auto bump map'].default_value = True
                    dispNode.inputs['Mid level'].default_value = 0.1
                    dispNode.inputs['Height'].default_value = 0.1
                    dispNode.inputs['Subdivision level'].default_value = prefs.disp_level_vertex

                dispNode.location = (-360, -680)

                self.mat.node_tree.links.new(
                    dispNode.inputs['Texture'], texNode.outputs[0])
                self.mat.node_tree.links.new(
                    self.mainMat.inputs['Displacement'], dispNode.outputs[0])

        # Create the translucency setup.
        if "translucency" in self.textureTypes:
            imgPath = self.GetTexturePath('translucency')
            if len(imgPath) >= 1:
                texNode = self.nodes.new('ShaderNodeOctImageTex')
                y_exp += -320
                texNode.location = (-720, y_exp)
                texNode.image = bpy.data.images.load(imgPath)
                texNode.show_texture = True
                texNode.image.colorspace_settings.name = self.colorSpaces[1]

                scatterNode = self.nodes.new(
                    'ShaderNodeOctScatteringMedium')
                scatterNode.inputs['Absorption Tex'].default_value = (
                    1, 1, 1, 1)
                scatterNode.inputs['Invert abs.'].default_value = False
                scatterNode.location = (-360, -1000)

                self.mat.node_tree.links.new(
                    self.mainMat.inputs['Transmission'], texNode.outputs[0])
                self.mat.node_tree.links.new(
                    self.mainMat.inputs['Medium'], scatterNode.outputs[0])

        # Create the opacity setup
        if "opacity" in self.textureTypes:
            imgPath = self.GetTexturePath('opacity')
            if len(imgPath) >= 1:
                texNode = self.nodes.new('ShaderNodeOctImageTex')
                # y_exp += -320
                texNode.location = (256, 0)
                texNode.image = bpy.data.images.load(imgPath)
                texNode.show_texture = True
                texNode.image.colorspace_settings.name = self.colorSpaces[1]

                mixNode = self.nodes.new('ShaderNodeOctMixMat')
                mixNode.location = (630, 0)
                mixNode.inputs['Amount'].default_value = 1
                self.mat.node_tree.links.new(
                    mixNode.inputs['Amount'], texNode.outputs[0])

                transpNode = self.nodes.new('ShaderNodeOctDiffuseMat')
                transpNode.location = (256, -320)
                transpNode.inputs['Opacity'].default_value = 0

                self.mat.node_tree.links.new(
                    mixNode.inputs['Material1'], self.mainMat.outputs[0])
                self.mat.node_tree.links.new(
                    mixNode.inputs['Material2'], transpNode.outputs[0])

                self.mat.node_tree.links.new(
                    self.outNode.inputs['Surface'], mixNode.outputs[0])

                self.mat.blend_method = 'CLIP'
                self.mat.shadow_method = 'CLIP'

        # Create the normal map setup for Redshift.
        if "normal" in self.textureTypes:
            imgPath = self.GetTexturePath('normal')
            if len(imgPath) >= 1:
                texNode = self.nodes.new('ShaderNodeOctImageTex')
                y_exp += -320
                texNode.location = (-720, y_exp)

                texNode.image = bpy.data.images.load(imgPath)
                texNode.show_texture = True
                texNode.image.colorspace_settings.name = self.colorSpaces[0]
                self.mat.node_tree.links.new(
                    self.mainMat.inputs['Normal'], texNode.outputs[0])

        # Create the bump map setup
        if ("bump" in self.textureTypes) and (prefs.is_bump_enabled):
            imgPath = self.GetTexturePath("bump")
            if len(imgPath) >= 1:
                texNode = self.nodes.new('ShaderNodeOctImageTex')

                y_exp += -320
                texNode.location = (-720, y_exp)

                texNode.image = bpy.data.images.load(imgPath)
                texNode.show_texture = True
                texNode.image.colorspace_settings.name = self.colorSpaces[1]

                #self.mat.node_tree.links.new(self.mainMat.inputs['Bump'], texNode.outputs[0])

        # Create the cavity map setup
        if ("cavity" in self.textureTypes) and (prefs.is_cavity_enabled):
            imgPath = self.GetTexturePath("cavity")
            if len(imgPath) >= 1:
                texNode = self.nodes.new('ShaderNodeOctImageTex')

                y_exp += -320
                texNode.location = (-720, y_exp)

                texNode.image = bpy.data.images.load(imgPath)
                texNode.show_texture = True
                texNode.image.colorspace_settings.name = self.colorSpaces[1]

        # Create the cavity map setup
        if ("curvature" in self.textureTypes) and (prefs.is_curvature_enabled):
            imgPath = self.GetTexturePath("curvature")
            if len(imgPath) >= 1:
                texNode = self.nodes.new('ShaderNodeOctImageTex')

                y_exp += -320
                texNode.location = (-720, y_exp)

                texNode.image = bpy.data.images.load(imgPath)
                texNode.show_texture = True
                texNode.image.colorspace_settings.name = self.colorSpaces[1]

        # Create the fuzziness setup.
        if ("fuzz" in self.textureTypes) and (prefs.is_fuze_enabled):
            imgPath = self.GetTexturePath('fuze')
            if len(imgPath) >= 1:
                texNode = nodes.new('ShaderNodeOctImageTex')

                y_exp += -320
                texNode.location = (-720, y_exp)

                texNode.image = bpy.data.images.load(imgPath)
                texNode.show_texture = True
                texNode.image.colorspace_settings.name = self.colorSpaces[1]

        # Deselect all nodes
        for node in self.nodes:
            node.select = False

        # End of material setup

    def GetTexturePath(self, textureType):
        for item in self.textureList:
            if item[1] == textureType:
                return item[2].replace("\\", "/")


class ms_Init(threading.Thread):

        # Initialize the thread and assign the method (i.e. importer) to be called when it receives JSON data.
    def __init__(self, importer):
        threading.Thread.__init__(self)
        self.importer = importer

        # Start the thread to start listing to the port.
    def run(self):
        try:
            run_livelink = True
            host, port = 'localhost', 28888
            # Making a socket object.
            socket_ = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Binding the socket to host and port number mentioned at the start.
            socket_.bind((host, port))

            # Run until the thread starts receiving data.
            while run_livelink:
                socket_.listen(5)
                # Accept connection request.
                client, addr = socket_.accept()
                data = ""
                buffer_size = 4096*2
                # Receive data from the client.
                data = client.recv(buffer_size)
                if data == b'Bye Megascans':
                    run_livelink = False
                    break

                # If any data is received over the port.
                if data != "":
                    self.TotalData = b""
                    # Append the previously received data to the Total Data.
                    self.TotalData += data
                    # Keep running until the connection is open and we are receiving data.
                    while run_livelink:
                        # Keep receiving data from client.
                        data = client.recv(4096*2)
                        if data == b'Bye Megascans':
                            run_livelink = False
                            break
                        # if we are getting data keep appending it to the Total data.
                        if data:
                            self.TotalData += data
                        else:
                            # Once the data transmission is over call the importer method and send the collected TotalData.
                            self.importer(self.TotalData)
                            break
        except Exception as e:
            print("Megascans LiveLink Error initializing the thread. Error: ", str(e))


class thread_checker(threading.Thread):

        # Initialize the thread and assign the method (i.e. importer) to be called when it receives JSON data.
    def __init__(self):
        threading.Thread.__init__(self)

        # Start the thread to start listing to the port.
    def run(self):
        try:
            run_checker = True
            while run_checker:
                time.sleep(3)
                for i in threading.enumerate():
                    if(i.getName() == "MainThread" and i.is_alive() == False):
                        host, port = 'localhost', 28888
                        s = socket.socket()
                        s.connect((host, port))
                        data = "Bye Megascans"
                        s.send(data.encode())
                        s.close()
                        run_checker = False
                        break
        except Exception as e:
            print("Megascans LiveLink Error initializing thread checker. Error: ", str(e))
            pass


class MS_Init_LiveLink(bpy.types.Operator):

    bl_idname = "ms_livelink.py"
    bl_label = "Megascans LiveLink Octane"
    socketCount = 0

    def execute(self, context):

        try:
            globals()['Megascans_DataSet'] = None
            self.thread_ = threading.Thread(target=self.socketMonitor)
            self.thread_.start()
            bpy.app.timers.register(self.newDataMonitor)
            print("Megascans LiveLink Octane Started")
            return {'FINISHED'}
        except Exception as e:
            print("Megascans LiveLink error starting blender plugin. Error: ", str(e))
            return {"FAILED"}

    def newDataMonitor(self):
        try:
            if globals()['Megascans_DataSet'] != None:
                MS_Init_ImportProcess()
                globals()['Megascans_DataSet'] = None
        except Exception as e:
            print(
                "Megascans LiveLink error starting blender plugin (newDataMonitor). Error: ", str(e))
            return {"FAILED"}
        return 1.0

    def socketMonitor(self):
        try:
            # Making a thread object
            threadedServer = ms_Init(self.importer)
            # Start the newly created thread.
            threadedServer.start()
            # Making a thread object
            thread_checker_ = thread_checker()
            # Start the newly created thread.
            thread_checker_.start()
        except Exception as e:
            print(
                "Megascans LiveLink error starting blender plugin (socketMonitor). Error: ", str(e))
            return {"FAILED"}

    def importer(self, recv_data):
        try:
            globals()['Megascans_DataSet'] = recv_data
        except Exception as e:
            print(
                "Megascans LiveLink error starting blender plugin (importer). Error: ", str(e))
            return {"FAILED"}


class MS_Init_Abc(bpy.types.Operator):

    bl_idname = "ms_livelink_abc.py"
    bl_label = "Import ABC"

    def execute(self, context):

        try:
            if globals()['MG_ImportComplete']:

                assetMeshPaths = globals()['MG_AlembicPath']
                assetMaterials = globals()['MG_Material']

                if len(assetMeshPaths) > 0 and len(assetMaterials) > 0:

                    materialIndex = 0
                    old_materials = []
                    for meshPaths in assetMeshPaths:
                        for meshPath in meshPaths:
                            bpy.ops.wm.alembic_import(
                                filepath=meshPath, as_background_job=False)
                            for o in bpy.context.scene.objects:
                                if o.select_get():
                                    old_materials.append(o.active_material)
                                    o.active_material = assetMaterials[materialIndex]

                        materialIndex += 1

                    for mat in old_materials:
                        try:
                            if mat is not None:
                                bpy.data.materials.remove(mat)
                        except:
                            pass

                    globals()['MG_AlembicPath'] = []
                    globals()['MG_Material'] = []
                    globals()['MG_ImportComplete'] = False

            return {'FINISHED'}
        except Exception as e:
            print("Megascans Plugin Error starting MS_Init_Abc. Error: ", str(e))
            return {"CANCELLED"}


def menu_func_import(self, context):
    self.layout.operator(MS_Init_LiveLink.bl_idname,
                         text="Start Megascans LiveLink Octane")
    #self.layout.operator(MS_Init_Abc.bl_idname, text="Import Megascans Alembic for Octane)")


def register():
    bpy.utils.register_class(MS_Init_LiveLink)
    #bpy.utils.register_class(MS_Init_Abc)
    bpy.utils.register_class(MSLiveLinkPrefs)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(MSLiveLinkPrefs)
    #bpy.utils.register_class(MS_Init_Abc)
    bpy.utils.unregister_class(MS_Init_LiveLink)


if __name__ == "__main__":
    register()
