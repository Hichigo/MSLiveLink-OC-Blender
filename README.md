# MSLiveLink-OC-Blender
Quixel Megascans Plugin for Octane Blender Edition

## Versions

> Windows

[Quixel Official Documentation](https://help.quixel.com/hc/en-us/articles/360002425298-Installing-the-Megascans-Plugin-for-Blender-2-8)

MSLiveLink Octane version 1.5.1

Official base addon version 2.7

OctaneRender™ for Blender 2019 and later

## Questions
- "Start Megascans Livelink Octane" is greyed out
  - The active render engine is not octane
- "Megascans LiveLink Octane is started already"
  - You already started the addon. The socket client will last in background until you quit the Blender
- I cannot see imported surface materials
  - Surface material will not be assigned to selected objects automatically. Instead, you can find it in the Material Slots from Nodes editor
- Mesh is imported without a correct material and the console prints "key 'Principled BSDF' not found"
  - There is a confict when both official addon and my addon are installed on a same machine
  - Remove the official addon
    - If you found a folder called "MSPlugin" in C:\Users\[Your username]\AppData\Roaming\Blender Foundation\Blender\2.8X\scripts\startup, kill it and repeat steps to install the addon and restart the Blender
- Other issues
  - Please check the log from Blender > Topbar > Window > Toggle System Console and let me know what's happening


## Installation

1. Go to [Releases](https://github.com/Yichen-Dou/MSLiveLink-OC-Blender/releases) and download the newest **MSLiveLink_Octane.zip**
4. In Octane Blender, install the addon from the zip file
4. Activate it
5. **File > Import > Start Megascans LiveLink Octane** will activate a socket client listening to the Megascans Bridge
6. Open the Megascans Bridge and change the export method to Blender
7. Click export. Feel fun

![image-20200308172530172](assets/image-20200308172530172.png)

![image-20200308172634672](assets/image-20200308172634672.png)

## Upgrading

1. Remove the addon in the settings and relaunch the OC Blender 
3. Follow instructions to install the addon

Otherwise, socket running in the thread will cause a problem

## Features
> Please turn on the **Specular map** option when you download the assets and export them from the Bridge, otherwise, the specular value will be set to 0.5 by default

> Surface materials will **not** be assigned to selected objects, instead, you can find it in the material slots in Node editor

Minimum textures to get a correct response

![image-20200308173100845](assets/image-20200308173100845.png)

Complete nodes setup

![image-20200308174856061](assets/image-20200308174856061.png)

![image-20200308175602574](assets/image-20200308175602574.png)

Textures info


| Textures         | Info                             |
| ---------------- | -------------------------------- |
| **Albedo**       | Added by default (If exists)     |
| **Displacement** | Added by default (If exists)     |
| **Normal**       | Added by default (If exists)     |
| **Roughness**    | Added by default (If exists)     |
| **Specular**     | Added by default (If exists)     |
| Opacity          | Added by default (If exists)     |
| Translucency     | Added by default (If exists)     |
| Metalness        | Added by default (If exists)     |
| AO               | Added by default (If exists)     |
| Bump             | Optional (Toggle in preferences) |
| Fuzz             | Optional (Toggle in preferences) |
| Cavity           | Optional (Toggle in preferences) |
| Curvature        | Optional (Toggle in preferences) |

